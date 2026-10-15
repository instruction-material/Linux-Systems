"""A small actual user-service worker for the owned observability studio."""
import json
import os
import re
import sys
import time
from pathlib import Path


def main():
    config, output, events = map(Path, sys.argv[1:4])
    job = json.loads(config.read_text())
    invocation = os.environ.get('INVOCATION_ID', '')
    if not re.fullmatch(r'[0-9a-f]{32}', invocation):
        raise ValueError('the real user manager must supply INVOCATION_ID')

    def emit(event, status):
        row = {'event': event, 'status': status, 'run': job['run'],
               'invocation': invocation, 'pid': os.getpid(), 'uid': os.geteuid(),
               'monotonicNs': time.monotonic_ns(), 'timeNs': time.time_ns()}
        with events.open('a') as stream:
            stream.write(json.dumps(row, sort_keys=True)+'\n')
            stream.flush()
            os.fsync(stream.fileno())
        print(json.dumps(row, sort_keys=True), flush=True)

    emit('start', 'started')
    # A real file gate keeps even a very short failed invocation inspectable.
    gate = Path(job['gate'])
    if gate.parent != config.parent or gate.is_symlink():
        raise ValueError('the observation gate must belong to this private job')
    until = time.monotonic()+12
    while not gate.is_file():
        if time.monotonic() >= until:
            raise TimeoutError('the observer did not acknowledge the live invocation')
        time.sleep(0.01)
    if gate.read_text().strip() != job['run']:
        raise ValueError('the observation gate belongs to a different run')
    if job['mode'] == 'hang':
        while True:
            time.sleep(0.2)
    if job['mode'] == 'good':
        data = (json.dumps({'run': job['run'], 'value': job['value']}, sort_keys=True)+'\n').encode()
        temporary = output.with_suffix('.partial')
        with temporary.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(0o600)
        os.replace(temporary, output)
    status = 'error' if job['mode'] in ['old-error', 'fail'] else 'finished'
    emit('end', status)
    return 7 if job['mode'] == 'fail' else 0


if __name__ == '__main__':
    raise SystemExit(main())
