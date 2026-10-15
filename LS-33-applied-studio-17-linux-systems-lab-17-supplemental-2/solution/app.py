"""A loopback-only application whose health record identifies the real process."""
import argparse
import errno
import hashlib
import json
import os
import re
import signal
import stat
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def ordinary_bytes(path):
    details = path.lstat()
    if not stat.S_ISREG(details.st_mode) or details.st_size > 1048576:
        raise ValueError('expected a small ordinary file: ' + str(path))
    return path.read_bytes()


def configuration(path):
    config = json.loads(ordinary_bytes(path))
    if set(config) != {'listen_host', 'release_id', 'data_file'}:
        raise ValueError('config must declare listen_host, release_id and data_file')
    if config['listen_host'] != '127.0.0.1':
        raise ValueError('the owned lab binds only to 127.0.0.1')
    release = config['release_id']
    if not isinstance(release, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', release) or release == 'TODO':
        raise ValueError('supply a specific release identity instead of TODO')
    if config['data_file'] != 'data.json':
        raise ValueError('this project reads only its adjacent data.json')
    data = json.loads(ordinary_bytes(path.parent / 'data.json'))
    if set(data) != {'message'} or not isinstance(data['message'], str) or len(data['message']) > 1024:
        raise ValueError('data.json must contain one short fictional message')
    return config, data


def write_probe():
    """Attempt an actual open for writing, without writing any source bytes."""
    try:
        descriptor = os.open(__file__, os.O_WRONLY | os.O_APPEND)
    except OSError as error:
        if error.errno not in (errno.EACCES, errno.EROFS, errno.EPERM):
            raise
        return {'denied': True, 'errno': error.errno}
    else:
        os.close(descriptor)
        return {'denied': False, 'errno': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path(__file__).with_name('config.json'))
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if os.geteuid() == 0 or not 1024 <= args.port <= 65535:
        raise ValueError('use an ordinary account and an unprivileged port')
    config, data = configuration(args.config.absolute())
    identity = {'release': config['release_id'], 'message': data['message'],
                'pid': os.getpid(), 'uid': os.geteuid(), 'gid': os.getegid(),
                'cwd': os.getcwd(), 'host': config['listen_host'], 'port': args.port,
                'invocationId': os.environ.get('INVOCATION_ID', ''),
                'codeSha256': hashlib.sha256(ordinary_bytes(Path(__file__))).hexdigest()}
    if args.check:
        print(json.dumps(dict(identity, configurationValid=True)))
        return 0

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            status = 200 if self.path == '/health' else 404
            result = dict(identity, codeWriteProbe=write_probe()) if status == 200 else {'error': 'not found'}
            body = (json.dumps(result, sort_keys=True) + '\n').encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def stop(_number, _frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    with ThreadingHTTPServer((config['listen_host'], args.port), Handler) as server:
        print(json.dumps(dict(identity, event='started')), flush=True)
        server.serve_forever(poll_interval=0.1)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
