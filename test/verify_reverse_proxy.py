"""Black-box app/proxy contract checks in an owned temporary workspace."""
import argparse
import hashlib
import http.client
import json
import os
import platform
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--proof', type=Path, required=True)
parser.add_argument('--app-only', action='store_true')
args = parser.parse_args()
SOURCE = Path(__file__).resolve().parents[1] / 'LS3-Nginx-Reverse-Proxy-App'
assert args.app_only or (platform.system() == 'Linux' and os.geteuid() != 0)
args.proof = args.proof.resolve()
args.proof.parent.mkdir(parents=True, exist_ok=True)
records, processes, profiles = [], [], []


def source_hashes():
    return {str(p.relative_to(SOURCE)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in SOURCE.rglob('*') if p.is_file()}


before = source_hashes()
assert len(before) == 7


def record(row):
    processes.append(row)
    with args.proof.with_suffix('.processes.jsonl').open('a') as out:
        out.write(json.dumps(row) + '\n')


def spawn(command, cwd, name, env=None):
    out = (args.proof.parent / (name + '.stdout')).open('wb')
    err = (args.proof.parent / (name + '.stderr')).open('wb')
    child = subprocess.Popen(command, cwd=cwd, env=env, stdout=out,
                             stderr=err, start_new_session=True)
    row = {'parentTaskId': os.environ.get('CLASSES_FAMILY_TASK_ID', 'linux-proxy-source'),
           'parentPid': os.getpid(), 'pid': child.pid, 'command': command,
           'cwd': str(cwd), 'startTime': time.time(), 'timeoutSeconds': 15,
           'name': name}
    record(dict(row, event='start'))
    return child, out, err, row


def finish(handle, interrupt=False, expected=None):
    child, out, err, row = handle
    cleanup = 'process exited'
    if interrupt and child.poll() is None:
        os.killpg(child.pid, signal.SIGINT)
        cleanup = 'owned process group interrupted'
    try:
        status = child.wait(timeout=8)
    except BaseException:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGKILL)
        child.wait()
        cleanup = 'owned process group killed after timeout or cancellation'
        raise
    finally:
        out.close()
        err.close()
        record(dict(row, event='end', endTime=time.time(), exitCode=child.returncode,
                    childProcessGroupCleanup=cleanup))
    if expected is not None:
        assert status == expected, row
    return status


def command(argv, cwd, name, expected=0, env=None):
    handle = spawn(argv, cwd, name, env)
    finish(handle, expected=expected)
    stdout = (args.proof.parent / (name + '.stdout')).read_text()
    stderr = (args.proof.parent / (name + '.stderr')).read_text()
    records.append({'case': name, 'status': expected, 'stdout': stdout, 'stderr': stderr})
    return stdout


def port():
    with socket.socket() as holder:
        holder.bind(('127.0.0.1', 0))
        return holder.getsockname()[1]


def request(server_port, target, status, method='GET', headers=None):
    connection = http.client.HTTPConnection('127.0.0.1', server_port, timeout=3)
    try:
        connection.request(method, target, headers=headers or {})
        response = connection.getresponse()
        body = response.read()
        assert response.status == status, (target, status, response.status, body)
        if status not in (502,):
            assert response.getheader('Content-Type').startswith('application/json')
            if method == 'HEAD':
                assert not body
            else:
                assert int(response.getheader('Content-Length')) == len(body)
        row = {'port': server_port, 'target': target, 'method': method,
               'status': response.status, 'headers': dict(response.getheaders()),
               'body': body.decode()}
        records.append(row)
        return row
    finally:
        connection.close()


def ready(handle, server_port):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        assert handle[0].poll() is None, handle[3]
        try:
            request(server_port, '/health', 200)
            return
        except (OSError, http.client.HTTPException):
            time.sleep(0.05)
    raise AssertionError('Owned listener did not become healthy')


def no_listener(server_port):
    with socket.socket() as probe:
        probe.settimeout(1)
        assert probe.connect_ex(('127.0.0.1', server_port)) != 0


accepted = False
try:
    with tempfile.TemporaryDirectory(prefix='linux-proxy-owned-') as directory:
        work = Path(directory)
        for role in ('starter', 'solution', 'completed'):
            folder = work / role
            shutil.copytree(SOURCE / ('starter' if role == 'completed' else role), folder)
            if role == 'completed':
                path = folder / 'app.py'
                code = path.read_text()
                marker = 'return None  # TODO: construct the inspection payload from the actual arguments.'
                assert code.count(marker) == 1
                path.write_text(code.replace(marker, 'return dict(service=SERVICE, path=path, query=query, peer=peer, headers=headers)'))
            app_port = port()
            env = dict(os.environ, APP_PORT=str(app_port))
            app = proxy = None
            proxy_port = None
            try:
                app = spawn([sys.executable, str(folder / 'app.py')], work, role + '-app', env)
                ready(app, app_port)
                assert (args.proof.parent / (role + '-app.stdout')).read_text().startswith('Listening on http://127.0.0.1:')
                health = request(app_port, '/health', 200)
                assert json.loads(health['body']) == {'service': 'linux-toy-app', 'status': 'ok'}
                inspection_status = 501 if role == 'starter' else 200
                target = '/inspect?mode=read&mode=write&blank=&message=%CE%BB'
                direct = request(app_port, target, inspection_status)
                if role != 'starter':
                    parsed = json.loads(direct['body'])
                    assert parsed['path'] == '/inspect' and parsed['peer'] == '127.0.0.1'
                    assert parsed['query'] == {'mode': ['read', 'write'], 'blank': [''], 'message': ['λ']}
                    assert parsed['headers']['X-Forwarded-For'] == ''
                assert json.loads(request(app_port, '/missing', 404)['body']) == {'error': 'not_found'}
                head = request(app_port, '/health', 200, 'HEAD')
                assert head['headers']['Content-Length'] == health['headers']['Content-Length']
                posted = request(app_port, '/health', 405, 'POST')
                assert posted['headers']['Allow'] == 'GET, HEAD'
                request(app_port, '/inspect?' + '&'.join('x=1' for _ in range(17)), 400)
                request(app_port, '/' + 'x' * 4096, 414)
                command([sys.executable, str(folder / 'app.py')], work, role + '-occupied-port', 1, env)
                for index, invalid in enumerate(('0', '1023', '65536', '08081', '8081x', ' 8081', '١٢٣٤')):
                    command([sys.executable, str(folder / 'app.py')], work, role + '-invalid-port-' + str(index), 2, dict(os.environ, APP_PORT=invalid))
                if not args.app_only:
                    sockets = command(['ss', '-ltnp', f'sport = :{app_port}'], work, role + '-app-socket')
                    assert f'127.0.0.1:{app_port}' in sockets and f'pid={app[0].pid}' in sockets
                    proxy_port = port()
                    assert proxy_port != app_port
                    prefix = folder / 'nginx'
                    (prefix / 'logs').mkdir(parents=True)
                    original = (folder / 'linux-toy-app.conf').read_text()
                    assert original.count('127.0.0.1:8080') == 1 and original.count('127.0.0.1:8081') == 1
                    config = original.replace('127.0.0.1:8080', f'127.0.0.1:{proxy_port}').replace('127.0.0.1:8081', f'127.0.0.1:{app_port}')
                    proxy_path = prefix / 'proxy.conf'
                    proxy_path.write_text(config)
                    main = prefix / 'nginx.conf'
                    main.write_text(f'pid logs/nginx.pid;\nerror_log logs/main-error.log info;\nevents {{}}\nhttp {{ access_log logs/main-access.log; include "{proxy_path}"; }}\n')
                    argv = ['nginx', '-p', str(prefix) + '/', '-c', str(main)]
                    command([*argv, '-t'], work, role + '-nginx-syntax')
                    proxy = spawn([*argv, '-g', 'daemon off;'], work, role + '-nginx')
                    ready(proxy, proxy_port)
                    request(proxy_port, '/missing', 404)
                    proxied = request(proxy_port, target, inspection_status, headers={'Host': 'lab.invalid', 'X-Forwarded-For': '203.0.113.9', 'X-Forwarded-Proto': 'https'})
                    if role != 'starter':
                        payload = json.loads(proxied['body'])
                        assert payload['query'] == json.loads(direct['body'])['query']
                        assert payload['headers'] == {'Host': 'lab.invalid', 'X-Real-IP': '127.0.0.1', 'X-Forwarded-For': '127.0.0.1', 'X-Forwarded-Proto': 'http'}
                    proxy_sockets = command(['ss', '-ltnp', f'sport = :{proxy_port}'], work, role + '-proxy-socket')
                    assert f'127.0.0.1:{proxy_port}' in proxy_sockets
                    finish(app, interrupt=True, expected=0)
                    app = None
                    no_listener(app_port)
                    request(proxy_port, '/health', 502)
                    assert 'connect() failed' in (prefix / 'logs/proxy-error.log').read_text()
                    app = spawn([sys.executable, str(folder / 'app.py')], work, role + '-app-restored', env)
                    ready(app, app_port)
                    request(proxy_port, '/health', 200)
                    for name in ('proxy-access.log', 'proxy-error.log'):
                        shutil.copyfile(prefix / 'logs' / name, args.proof.parent / (role + '-' + name))
                    profiles.append({'role': role, 'appPort': app_port, 'proxyPort': proxy_port, 'actualLinuxSockets': True, 'upstreamDown502': True, 'restored200': True})
                else:
                    profiles.append({'role': role, 'appPort': app_port, 'appOnly': True})
            finally:
                if app is not None:
                    finish(app, interrupt=True, expected=0)
                if proxy is not None:
                    finish(proxy, interrupt=True)
                no_listener(app_port)
                if proxy_port is not None:
                    no_listener(proxy_port)
    assert source_hashes() == before
    accepted = True
finally:
    args.proof.write_text(json.dumps({'accepted': accepted, 'platform': platform.platform(), 'uid': os.geteuid(), 'appOnly': args.app_only, 'sourceHashes': before, 'profiles': profiles, 'observations': records, 'processCount': len(processes) // 2, 'independentLearnerCompletions': 1, 'worksheetCompletionNotInferred': True, 'serviceManagerOperationNotInferred': True, 'sourceUnchanged': source_hashes() == before}, indent=2) + '\n')
print(json.dumps({'accepted': accepted, 'profiles': len(profiles), 'observations': len(records), 'appOnly': args.app_only}))
