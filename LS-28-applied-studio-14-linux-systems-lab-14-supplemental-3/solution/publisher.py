"""One owned publisher process used by the concurrent activation exercise."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import platform
import signal
import time


def acquire_lock(stream):
    try:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return False
    return True


def publish():
    parser = argparse.ArgumentParser()
    parser.add_argument('workspace', type=Path)
    parser.add_argument('actor', choices=['alpha', 'beta', 'retry', 'interrupt', 'recovery'])
    args = parser.parse_args()
    root = args.workspace
    if platform.system() != 'Linux' or os.geteuid() == 0 or root.is_symlink() or not root.is_dir() or root.stat().st_uid != os.getuid():
        parser.error('Use the owned ordinary-account Linux case directory')
    root = root.resolve()
    stop = []
    for number in (signal.SIGINT, signal.SIGTERM):
        signal.signal(number, lambda signum, frame: stop.append(signum))
    data = dict(pid=os.getpid(), parentPid=os.getppid(), uid=os.getuid(), actor=args.actor,
                started=time.time(), published=False, interrupted=False)
    status = 2
    with (root / 'activation.lock').open('a+') as lock:
        data['lockInode'] = os.fstat(lock.fileno()).st_ino
        data['lockDevice'] = os.fstat(lock.fileno()).st_dev
        acquired = acquire_lock(lock)
        data['lockAcquired'] = acquired
        if not acquired:
            status = 75
        else:
            before = json.loads((root / 'current.json').read_text())
            data['observedGeneration'] = before['generation']
            ready = root / ('ready-' + args.actor + '.json')
            stage = root / ('ready-source-' + args.actor + '.json')
            stage.write_text(json.dumps(data))
            os.link(stage, ready)
            deadline = time.monotonic() + 12
            go = root / ('go-' + args.actor)
            while not go.exists() and not stop and time.monotonic() < deadline:
                time.sleep(0.01)
            if stop:
                data['interrupted'] = True
                data['signal'] = stop[0]
                status = 128 + stop[0]
            elif not go.exists():
                data['failure'] = 'The owned publication barrier deadline elapsed'
            else:
                after = dict(generation=before['generation'] + 1, release=args.actor, publisherPid=os.getpid())
                temporary = root / ('current-' + str(os.getpid()) + '.json')
                temporary.write_text(json.dumps(after))
                os.replace(temporary, root / 'current.json')
                data.update(published=True, publishedState=after)
                status = 0
    data.update(ended=time.time(), descriptorClosed=True)
    print(json.dumps(data))
    return status


if __name__ == '__main__':
    raise SystemExit(publish())
