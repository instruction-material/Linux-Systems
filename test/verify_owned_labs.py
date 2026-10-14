"""Black-box Linux acceptance of the five corrected course source packs."""
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
import tarfile
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--proof', type=Path, required=True)
args = parser.parse_args()
assert platform.system() == 'Linux', 'Acceptance needs real Linux, not simulated host identity'
assert os.geteuid() != 0, 'Permission acceptance needs an ordinary Linux account'
args.proof = args.proof.resolve()
args.proof.parent.mkdir(parents=True, exist_ok=True)
log = args.proof.with_suffix('.processes.jsonl')
observations = []
processes = []
PACKS = {
    'shell': 'LS-05-unit-1-shell-foundations',
    'permissions': 'LS-06-unit-3-users-groups-and-permissions',
    'bootstrap': 'LS1-Personal-Lab-VM',
    'static': 'LS2-Static-Site-from-srv',
    'backup': 'LS6-Backup-Cron-and-Timer',
}


def hashes():
    return {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest()
            for pack in PACKS.values() for f in (ROOT / pack).rglob('*') if f.is_file()}


def run(command, cwd, expected=0, env=None, label=''):
    started = time.time()
    child = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, start_new_session=True)
    cleanup = 'process exited'
    try:
        out, err = child.communicate(timeout=45)
    except BaseException:
        os.killpg(child.pid, signal.SIGTERM)
        try:
            child.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.communicate()
        cleanup = 'process group terminated'
        raise
    finally:
        row = {'parentTaskId': os.environ.get('CLASSES_FAMILY_TASK_ID', 'linux-owned-labs-source-ci'), 'parentPid': os.getpid(), 'pid': child.pid, 'command': command, 'cwd': str(cwd), 'startTime': started, 'endTime': time.time(), 'exitCode': child.returncode, 'timeoutSeconds': 45, 'childProcessGroupCleanup': cleanup}
        processes.append(row)
        with log.open('a') as stream:
            stream.write(json.dumps(row) + '\n')
    observation = {'case': label, 'command': command, 'status': child.returncode, 'stdout': out.decode(), 'stderr': err.decode()}
    observations.append(observation)
    assert child.returncode == expected, observation
    print(json.dumps({'case': label, 'status': child.returncode}), flush=True)
    return observation


def copy_role(work, project, role):
    source_role = 'starter' if role == 'completed' else role
    target = work / (project + '-' + role)
    shutil.copytree(ROOT / PACKS[project] / source_role, target)
    if role == 'completed':
        name = 'backup_home.sh' if project == 'backup' else 'deploy_static_site.sh' if project == 'static' else 'task.sh'
        replacements = {
            'shell': ('warning_count=0 # TODO: retain the warning count returned by awk.', ': # Both parsed level counts are retained.'),
            'permissions': ('return 1 # TODO: restore only owner traversal on the private directory.', 'chmod u+x -- "$lab_root/site/private"'),
            'static': ('return 1 # TODO: install source argument 1 into staged argument 2 with mode 0644.', 'install -m 0644 -- "$1" "$2"'),
            'backup': (': "$old_name" # TODO: remove older managed archives once kept reaches retention_count - 1.', 'if (( kept >= retention_count - 1 )); then rm -f -- "$dest_dir/$old_name"; fi'),
        }
        original = (target / name).read_text()
        old, new = replacements[project]
        assert original.count(old) == 1
        (target / name).write_text(original.replace(old, new))
    return target


def archive_contents(path):
    with tarfile.open(path) as archive:
        members = archive.getmembers()
        assert all(not m.name.startswith('/') and '..' not in Path(m.name).parts for m in members)
        return {m.name.removeprefix('./'): archive.extractfile(m).read()
                for m in members if m.isfile()}


before = hashes()
profiles = []
with tempfile.TemporaryDirectory(prefix='linux-owned-labs-') as temporary:
    work = Path(temporary)
    for role in ('starter', 'solution', 'completed'):
        # Independent fixtures exercise filenames, level vs message and failure status.
        source = copy_role(work, 'shell', role)
        warning = 0 if role == 'starter' else 2
        default = run(['bash', str(source / 'task.sh')], work, label='shell-' + role + '-default')
        assert default['stdout'] == f'files=3 errors=3 warnings={warning}\n'
        cases = [({}, (0, 0, 0)),
                 ({'one.log': 't ERROR first\n'}, (1, 1, 0)),
                 ({'a ; quoted.log': 't WARNING retry\nt ERROR second\nt INFO ERROR in message\n',
                   'second\nname.log': 't WARNING later\n', 'notes.txt': 't ERROR ignore\n'}, (2, 1, 2))]
        for i, (files, totals) in enumerate(cases):
            case = work / f'shell-case-{role}-{i}'
            case.mkdir()
            for name, value in files.items():
                (case / name).write_text(value)
            found = run(['bash', str(source / 'task.sh'), str(case)], work, label=f'shell-{role}-{i}')
            expected = (totals[0], totals[1], 0 if role == 'starter' else totals[2])
            assert found['stdout'] == 'files={} errors={} warnings={}\n'.format(*expected)
        missing = run(['bash', str(source / 'task.sh'), str(work / 'missing')], work, 1, label='shell-' + role + '-missing')
        assert not missing['stdout'] and missing['stderr']
        run(['bash', str(source / 'task.sh'), str(work), 'extra'], work, 2, label='shell-' + role + '-arguments')
        unreadable = work / ('unreadable-' + role)
        unreadable.mkdir()
        (unreadable / 'private.log').write_text('t ERROR one\n')
        (unreadable / 'private.log').chmod(0)
        try:
            failed = run(['bash', str(source / 'task.sh'), str(unreadable)], work, 2, label='shell-' + role + '-unreadable')
            assert not failed['stdout']
        finally:
            (unreadable / 'private.log').chmod(0o600)
        profiles.append({'project': 'shell', 'role': role, 'cases': 7, 'namedTodoCompleted': role == 'completed'})

        source = copy_role(work, 'permissions', role)
        lab = work / ('permission tree ' + role)
        lab.mkdir()
        try:
            state = run(['bash', str(source / 'task.sh'), 'setup', str(lab)], work, label='permissions-' + role + '-setup')
            assert 'can_read=no' in state['stdout']
            index = lab / 'site/private/index.html'
            assert not os.access(index, os.R_OK)
            run(['bash', str(source / 'task.sh'), 'verify', str(lab)], work, 1, label='permissions-' + role + '-blocked')
            state = run(['bash', str(source / 'task.sh'), 'fix', str(lab)], work, 1 if role == 'starter' else 0, label='permissions-' + role + '-fix')
            if role == 'starter':
                assert not os.access(index, os.R_OK)
                run(['bash', str(source / 'task.sh'), 'verify', str(lab)], work, 1, label='permissions-starter-remains-unfinished')
            else:
                assert os.access(index, os.R_OK) and index.read_bytes() == b'owned lab page\n'
                assert index.stat().st_mode & 0o777 == 0o640
                assert (lab / 'site/private').stat().st_mode & 0o777 == 0o700
                run(['bash', str(source / 'task.sh'), 'verify', str(lab)], work, label='permissions-' + role + '-verified')
                (lab / 'site/private').chmod(0o600)
                state = run(['bash', str(source / 'task.sh'), 'inspect', str(lab)], work, label='permissions-' + role + '-undo')
                assert 'can_read=no' in state['stdout']
            run(['bash', str(source / 'task.sh'), 'setup', str(lab)], work, 2, label='permissions-' + role + '-nonempty')
            link = work / ('permission-link-' + role)
            link.symlink_to(lab, target_is_directory=True)
            run(['bash', str(source / 'task.sh'), 'inspect', str(link)], work, 2, label='permissions-' + role + '-symlink')
        finally:
            (lab / 'site/private').chmod(0o700)
        profiles.append({'project': 'permissions', 'role': role, 'actualAncestorFailure': True, 'namedTodoCompleted': role == 'completed', 'fictionalOtherUsersNotInferred': True})

        source = copy_role(work, 'backup', role)
        input_dir = work / ('source notes ' + role)
        destination = work / ('backup copies ' + role)
        input_dir.mkdir()
        destination.mkdir()
        unrelated = destination / 'unrelated archive.tar.gz'
        unrelated.write_bytes(b'not managed')
        backup_env = dict(os.environ, RETENTION_COUNT='2')
        created = []
        for i in range(7):
            (input_dir / 'session.txt').write_text(f'observation {i}\n')
            state = run(['bash', str(source / 'backup_home.sh'), str(input_dir), str(destination)], work, env=backup_env, label=f'backup-{role}-{i}')
            archive = Path(state['stdout'].strip().removeprefix('Created '))
            assert archive.exists() and archive not in created
            created.append(archive)
            assert archive_contents(archive) == {'session.txt': f'observation {i}\n'.encode()}
            assert len(list(destination.glob('linux-systems-backup-*.tar.gz'))) == (i + 1 if role == 'starter' else min(i + 1, 2))
        assert unrelated.read_bytes() == b'not managed'
        prior = {f.name: f.read_bytes() for f in destination.glob('linux-systems-backup-*.tar.gz')}
        for value in ('0', '-1', 'abc', '01', '1001'):
            env = dict(os.environ, RETENTION_COUNT=value)
            state = run(['bash', str(source / 'backup_home.sh'), str(input_dir), str(destination)], work, 2, env=env, label='backup-' + role + '-invalid-' + value)
            assert not state['stdout']
            assert {f.name: f.read_bytes() for f in destination.glob('linux-systems-backup-*.tar.gz')} == prior
        run(['bash', str(source / 'backup_home.sh'), str(work / 'missing'), str(destination)], work, 2, label='backup-' + role + '-missing')
        assert {f.name: f.read_bytes() for f in destination.glob('linux-systems-backup-*.tar.gz')} == prior
        nested = input_dir / 'nested backup'
        run(['bash', str(source / 'backup_home.sh'), str(input_dir), str(nested)], work, 2, label='backup-' + role + '-recursive')
        assert not nested.exists()
        one_env = dict(os.environ, RETENTION_COUNT='1')
        state = run(['bash', str(source / 'backup_home.sh'), str(input_dir), str(destination)], work, env=one_env, label='backup-' + role + '-retention-one')
        latest = Path(state['stdout'].strip().removeprefix('Created '))
        assert latest.exists()
        assert len(list(destination.glob('linux-systems-backup-*.tar.gz'))) == (8 if role == 'starter' else 1)
        restore = work / ('restore ' + role)
        restore.mkdir()
        run(['tar', '-xzf', str(latest), '-C', str(restore)], work, label='backup-' + role + '-restore')
        assert (restore / 'session.txt').read_bytes() == (input_dir / 'session.txt').read_bytes()
        unit = (source / 'linux-backup.service').read_text()
        assert 'ExecStart="%h/.local/bin/backup_home.sh" "%h/linux-systems-lab" "%h/backups"' in unit
        assert '$HOME' not in unit and 'User=' not in unit
        assert '"$HOME/linux-systems-lab" "$HOME/backups"' in (source / 'crontab.example').read_text()
        profiles.append({'project': 'backup', 'role': role, 'archivesCreated': 8, 'uniqueArchives': True, 'actualRestoration': True, 'invalidRetentionPreservesPrior': True, 'namedTodoCompleted': role == 'completed', 'userSchedulerPathsExplicit': True})

        source = copy_role(work, 'static', role)
        destination = work / ('static root ' + role)
        expected = 1 if role == 'starter' else 0
        run(['bash', str(source / 'deploy_static_site.sh'), str(destination)], work, expected, label='static-' + role + '-publish')
        if role != 'starter':
            assert (destination / 'index.html').read_bytes() == (source / 'index.html').read_bytes()
            assert (destination / 'index.html').stat().st_mode & 0o777 == 0o644
        (destination / 'index.html').write_bytes(b'earlier owned page')
        failed = run(['bash', str(source / 'deploy_static_site.sh'), str(destination), 'no_such_course_owner_93258:no_such_course_group_93258'], work, 1, label='static-' + role + '-ownership-failure')
        assert 'Published' not in failed['stdout']
        assert (destination / 'index.html').read_bytes() == b'earlier owned page'
        run(['bash', str(source / 'deploy_static_site.sh')], work, 2, label='static-' + role + '-arguments')
        config = (source / 'linux-systems.conf').read_text()
        assert 'listen 127.0.0.1:8080;' in config and 'default_server' not in config
        if role != 'starter':
            run(['bash', str(source / 'deploy_static_site.sh'), str(destination)], work, label='static-' + role + '-republish')
            server_root = work / ('nginx-' + role)
            server_root.mkdir()
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                port = listener.getsockname()[1]
            block = config.replace('127.0.0.1:8080', '127.0.0.1:' + str(port))
            block = block.replace('/srv/linux-systems-site', '"' + str(destination) + '"')
            block = block.replace('/var/log/nginx/linux-systems.access.log', str(server_root / 'access.log'))
            block = block.replace('/var/log/nginx/linux-systems.error.log', str(server_root / 'error.log'))
            configuration = server_root / 'nginx.conf'
            configuration.write_text('daemon off;\nmaster_process off;\npid ' + str(server_root / 'nginx.pid') + ';\nerror_log ' + str(server_root / 'error.log') + ';\nevents { worker_connections 32; }\nhttp { default_type text/plain; access_log ' + str(server_root / 'http-access.log') + ';\n' + block + '\n}\n')
            nginx = shutil.which('nginx') or '/usr/sbin/nginx'
            run([nginx, '-t', '-p', str(server_root) + '/', '-c', str(configuration)], work, label='static-' + role + '-nginx-syntax')
            command = [nginx, '-p', str(server_root) + '/', '-c', str(configuration)]
            started = time.time()
            server = subprocess.Popen(command, cwd=work, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
            try:
                deadline = time.monotonic() + 10
                while True:
                    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=1)
                    try:
                        connection.request('GET', '/')
                        response = connection.getresponse()
                        body = response.read()
                        assert response.status == 200 and body == (source / 'index.html').read_bytes()
                        break
                    except OSError:
                        assert time.monotonic() < deadline and server.poll() is None
                        time.sleep(0.05)
                    finally:
                        connection.close()
                connection = http.client.HTTPConnection('127.0.0.1', port, timeout=2)
                try:
                    connection.request('GET', '/no-such-course-page')
                    response = connection.getresponse()
                    response.read()
                    assert response.status == 404
                finally:
                    connection.close()
                observations.append({'case': 'static-' + role + '-served-pages', 'rootStatus': 200, 'unknownStatus': 404, 'exactPageBytes': True})
            finally:
                if server.poll() is None:
                    os.killpg(server.pid, signal.SIGTERM)
                try:
                    server.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(server.pid, signal.SIGKILL)
                    server.communicate()
                with log.open('a') as stream:
                    stream.write(json.dumps({'parentTaskId': os.environ.get('CLASSES_FAMILY_TASK_ID', 'linux-owned-labs-source-ci'), 'parentPid': os.getpid(), 'pid': server.pid, 'command': command, 'cwd': str(work), 'startTime': started, 'endTime': time.time(), 'exitCode': server.returncode, 'timeoutSeconds': 10, 'childProcessGroupCleanup': 'owned server process group terminated'}) + '\n')
        profiles.append({'project': 'static', 'role': role, 'failedPublishPreservesEarlierPage': True, 'ownershipFailureObserved': role != 'starter', 'sourceAnchoredToScript': True, 'namedTodoCompleted': role == 'completed'})

    for role in ('starter', 'solution'):
        source = copy_role(work, 'bootstrap', role)
        state = run(['bash', str(source / 'lab_bootstrap_report.sh')], work, label='bootstrap-' + role + '-actual')
        assert 'Active identity: ' + subprocess.check_output(['id', '-un']).decode().strip() in state['stdout']
        assert 'Script interpreter: Bash ' in state['stdout']
        stub = work / ('host-stub-' + role)
        stub.mkdir()
        (stub / 'uname').write_text('#!/bin/sh\nprintf "Darwin\\n"\n')
        (stub / 'uname').chmod(0o755)
        env = dict(os.environ, PATH=str(stub) + os.pathsep + os.environ['PATH'])
        failed = run(['bash', str(source / 'lab_bootstrap_report.sh')], work, 2, env=env, label='bootstrap-' + role + '-host-rejected')
        assert not failed['stdout']
        profiles.append({'project': 'bootstrap', 'role': role, 'actualLinuxObserved': True, 'controlledHostBoundaryRejected': True, 'vmProvisioningNotInferred': True})

assert hashes() == before, 'Source files changed during acceptance'
record = {'platform': platform.platform(), 'uid': os.geteuid(), 'sourceHashes': before, 'profiles': profiles, 'observations': observations, 'commandCount': len(observations), 'independentLearnerCompletions': 4, 'sourceUnchanged': True, 'temporaryFilesCleaned': True, 'realLinuxAccessObserved': True, 'isolatedNginxServedExactPages': True, 'worksheetCompletionNotInferred': True, 'scheduledExecutionNotInferred': True, 'remainingGenericReferenceScripts': 44, 'fullLinuxAuditComplete': False, 'accepted': True}
args.proof.write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({'event': 'verified-linux-owned-labs', 'profiles': len(profiles), 'commands': len(observations), 'independentLearnerCompletions': 4, 'accepted': True}), flush=True)
