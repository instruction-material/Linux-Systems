"""Owned foreground Nginx equipment for one supplied observation exercise."""
import argparse
import base64
import hashlib
import http.client
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import socket
import subprocess
import tempfile
import time


def quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$') + '"'


class OwnedNginx:
    def __init__(self, workspace, source, fixtures, hold, broken, reverse):
        self.workspace = workspace
        self.source = source
        self.fixtures = fixtures
        self.hold = hold
        self.broken = broken
        self.reverse = reverse
        self.root = None
        self.child = None
        self.output = None
        self.ready = False
        self.interrupted = False
        self.old_handlers = {}
        self.data = dict(parentTask='Linux web observation', uid=os.getuid(), workspace=str(workspace), commands=[], requests=[],
                         observationsCompleted=False, learnerWorksheetCompletionInferred=False,
                         interrupted=False, failure=None, serverStarted=False)

    def checkpoint(self):
        if self.interrupted:
            raise InterruptedError('Observation interrupted by the caller')

    def command(self, command):
        self.checkpoint()
        started = time.time()
        child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        cleanup = 'owned process exited and reaped'
        try:
            out, err = child.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            out, err = child.communicate()
            cleanup = 'owned process group killed after deadline'
        row = dict(parentTask='Linux web observation', cwd=str(Path.cwd()), command=command, pid=child.pid, parentPid=os.getpid(), startTime=started,
                   endTime=time.time(), timeoutSeconds=5, returnCode=child.returncode,
                   stdout=out.decode(errors='replace'), stderr=err.decode(errors='replace'),
                   childProcessGroupCleanup=cleanup)
        self.data['commands'].append(row)
        if child.returncode or cleanup != 'owned process exited and reaped':
            raise RuntimeError('Native command failed: ' + row['stderr'])
        return row

    def start(self, make_servers):
        self.root = Path(tempfile.mkdtemp(prefix='classes-web-', dir=self.workspace))
        for name in self.fixtures:
            source = self.source / name
            if source.is_symlink() or not source.is_file():
                raise ValueError('Each supplied fixture must be an ordinary file')
            shutil.copyfile(source, self.root / name)
        with socket.socket() as reserve:
            reserve.bind(('127.0.0.1', 0))
            self.port = reserve.getsockname()[1]
        assert self.port > 1023
        self.data['port'] = self.port
        nginx = shutil.which('nginx')
        if not nginx:
            raise RuntimeError('Install Nginx in the owned Linux lab first')
        self.command([nginx, '-v'])
        config = '\n'.join([
            'daemon off;', 'master_process off;', 'worker_processes 1;',
            'pid ' + quote(self.root / 'nginx.pid') + ';',
            'error_log ' + quote(self.root / 'error.log') + ' notice;',
            'events { worker_connections 64; }', 'http {',
            'types { }', 'default_type text/plain;', 'sendfile off;',
            "log_format lab '$request_method $host $request_uri $status';",
            'access_log ' + quote(self.root / 'access.log') + ' lab;',
            'client_body_temp_path ' + quote(self.root / 'client-temp') + ';',
            'proxy_temp_path ' + quote(self.root / 'proxy-temp') + ';',
            'fastcgi_temp_path ' + quote(self.root / 'fastcgi-temp') + ';',
            'uwsgi_temp_path ' + quote(self.root / 'uwsgi-temp') + ';',
            'scgi_temp_path ' + quote(self.root / 'scgi-temp') + ';',
            make_servers(self), '}'])
        if self.broken:
            config += '\nInvalidCourseDirective on;\n'
        self.data['configuration'] = config
        path = self.root / 'nginx.conf'
        path.write_text(config)
        self.command([nginx, '-p', str(self.root) + '/', '-c', str(path), '-t'])
        self.output = (self.root / 'foreground.log').open('w+b')
        args = [nginx, '-p', str(self.root) + '/', '-c', str(path)]
        self.child = subprocess.Popen(args, stdout=self.output, stderr=self.output, start_new_session=True)
        self.data.update(serverStarted=True, serverPid=self.child.pid, serverParentPid=os.getpid(), serverCwd=str(Path.cwd()), serverCommand=args, serverTimeoutSeconds=60, serverStartTime=time.time())
        deadline = time.monotonic() + 5
        while True:
            self.checkpoint()
            if self.child.poll() is not None:
                raise RuntimeError('The owned Nginx process exited before readiness')
            try:
                with socket.create_connection(('127.0.0.1', self.port), timeout=0.2):
                    break
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError('The owned Nginx listener did not become ready')
                time.sleep(0.02)
        pid_path = self.root / 'nginx.pid'
        while not pid_path.exists() or pid_path.read_text().strip() != str(self.child.pid):
            self.checkpoint()
            if self.child.poll() is not None or time.monotonic() >= deadline:
                raise RuntimeError('The owned Nginx PID file did not identify the process')
            time.sleep(0.01)
        pid = int(pid_path.read_text())
        assert pid == self.child.pid
        proc = Path('/proc') / str(pid)
        status = (proc / 'status').read_text()
        uid = int(next(line for line in status.splitlines() if line.startswith('Uid:')).split()[1])
        assert uid == os.getuid()
        self.data['serverUid'] = uid
        self.data['serverProcCommand'] = (proc / 'cmdline').read_bytes().decode(errors='replace').replace('\0', ' ')
        ready_path = self.workspace / 'ready.json'
        ready_source = self.root / 'ready-record.json'
        ready_source.write_text(json.dumps(dict(pid=pid, port=self.port, prefix=str(self.root))))
        os.link(ready_source, ready_path)
        self.ready = True
        deadline = time.monotonic() + self.hold
        while time.monotonic() < deadline:
            self.checkpoint()
            time.sleep(0.02)

    def request(self, label, target, host='lab.test', method='GET', headers=None, version='HTTP/1.1'):
        self.checkpoint()
        assert method in ('GET', 'HEAD') and version in ('HTTP/1.0', 'HTTP/1.1')
        fields = [('Connection', 'close')] + ([] if host is None else [('Host', host)]) + list((headers or {}).items())
        assert not any('\n' in x or '\r' in x for pair in fields for x in pair)
        raw = (method + ' ' + target + ' ' + version + '\r\n' + ''.join(k + ': ' + v + '\r\n' for k, v in fields) + '\r\n').encode('ascii')
        started = time.time()
        with socket.create_connection(('127.0.0.1', self.port), timeout=3) as wire:
            peer = wire.getpeername()
            wire.sendall(raw)
            response = http.client.HTTPResponse(wire, method=method)
            response.begin()
            body = response.read(65537)
            assert len(body) <= 65536
            row = dict(label=label, requestBase64=base64.b64encode(raw).decode(), peer=list(peer),
                       status=response.status, headers=response.getheaders(), bodyBase64=base64.b64encode(body).decode(),
                       bodySha256=hashlib.sha256(body).hexdigest(), startTime=started, endTime=time.time())
        self.data['requests'].append(row)
        self.checkpoint()
        return row

    def close(self):
        if self.child:
            cleanup = 'owned process exited and reaped'
            if self.child.poll() is None:
                self.child.send_signal(signal.SIGQUIT)
            try:
                self.child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(self.child.pid, signal.SIGKILL)
                self.child.wait()
                cleanup = 'owned process group killed after deadline'
            self.data.update(serverEndTime=time.time(), serverReturnCode=self.child.returncode,
                             serverCleanup=cleanup, serverPidGone=not (Path('/proc') / str(self.child.pid)).exists())
            try:
                with socket.create_connection(('127.0.0.1', self.port), timeout=0.2):
                    closed = False
            except OSError:
                closed = True
            self.data['listenerClosed'] = closed
        if self.output:
            self.output.close()
        if self.root:
            for filename, field in [('access.log', 'accessLog'), ('error.log', 'errorLog'), ('foreground.log', 'foregroundLog')]:
                path = self.root / filename
                self.data[field] = path.read_text(errors='replace') if path.exists() else ''
            shutil.rmtree(self.root)
        if self.ready:
            (self.workspace / 'ready.json').unlink()
        self.data['workspaceEmpty'] = not list(self.workspace.iterdir())
        self.data['ownedCaseRemoved'] = self.root is None or not self.root.exists()


def run_lab(make_servers, observe, fixture_names):
    parser = argparse.ArgumentParser()
    parser.add_argument('workspace')
    parser.add_argument('--reverse', action='store_true')
    parser.add_argument('--broken-config', action='store_true')
    parser.add_argument('--hold-seconds', default='0')
    args = parser.parse_args()
    if platform.system() != 'Linux' or os.geteuid() == 0:
        parser.error('Use an ordinary account in the owned Linux lab')
    if not re.fullmatch(r'(?:[0-7](?:\.[0-9]{1,2})?|8(?:\.0{1,2})?)', args.hold_seconds):
        parser.error('hold-seconds must be a decimal from 0 through 8')
    path = Path(args.workspace)
    if any(c in str(path) for c in ['\n', '\r', '\0']) or path.is_symlink() or not path.is_dir():
        parser.error('workspace must be an existing owned nonsymlink empty directory')
    workspace = path.resolve()
    if workspace.stat().st_uid != os.getuid() or list(workspace.iterdir()):
        parser.error('workspace must be an existing owned nonsymlink empty directory')
    lab = OwnedNginx(workspace, Path(__file__).resolve().parent, fixture_names,
                     float(args.hold_seconds), args.broken_config, args.reverse)
    for signum in (signal.SIGINT, signal.SIGTERM):
        lab.old_handlers[signum] = signal.signal(signum, lambda number, frame: setattr(lab, 'interrupted', True))
    status = 2
    try:
        lab.start(make_servers)
        target_observed = observe(lab)
        lab.data['targetBehaviorObserved'] = bool(target_observed)
        lab.data['observationsCompleted'] = True
        status = 0 if target_observed else 1
    except InterruptedError:
        lab.data['interrupted'] = True
        status = 130
    except (OSError, ValueError, RuntimeError, AssertionError, http.client.HTTPException) as error:
        lab.data['failure'] = type(error).__name__ + ': ' + str(error)
    finally:
        try:
            lab.close()
        finally:
            for signum, handler in lab.old_handlers.items():
                signal.signal(signum, handler)
    print(json.dumps(lab.data, indent=2))
    return status
