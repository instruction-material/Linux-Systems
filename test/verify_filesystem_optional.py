"""Accept actual logical/physical traversal and bounded Linux kernel-file reads."""
import argparse
import base64
import hashlib
import json
import os
import platform
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKS = ['LS-05-unit-2-filesystem-hierarchy-and-directory-purpose-supplemental-2',
         'LS-06-unit-2-filesystem-hierarchy-and-directory-purpose-supplemental-3']
parser = argparse.ArgumentParser()
parser.add_argument('--proof', type=Path, required=True)
args = parser.parse_args()
assert platform.system() == 'Linux' and os.geteuid() > 0
assert all(shutil.which(name) for name in ('bash', 'python3', 'stat', 'findmnt', 'head'))
args.proof = args.proof.resolve()
args.proof.parent.mkdir(parents=True, exist_ok=True)
environment = dict(os.environ, LC_ALL='C', PYTHONDONTWRITEBYTECODE='1')
task = environment.get('CLASSES_FAMILY_TASK_ID', 'linux-filesystem-source')
records, observations, profiles, inner = [], [], [], []


def hashes():
    return {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest()
            for pack in PACKS for f in sorted((ROOT / pack).rglob('*')) if f.is_file()}


def group_gone(pid):
    try:
        os.killpg(pid, 0)
    except ProcessLookupError:
        return True
    return False


def run(argv, cwd, expected, label, env=None, ready=None, interrupt=False):
    if ready:
        ready.unlink(missing_ok=True)
    child = subprocess.Popen(argv, cwd=cwd, env=environment if env is None else env,
                             stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, start_new_session=True)
    entry = {'parentTaskId': task, 'parentPid': os.getpid(), 'pid': child.pid,
             'cwd': str(cwd), 'command': argv, 'startTime': time.time(), 'timeoutSeconds': 35}
    records.append(dict(entry, event='start'))
    out, err = b'', b''
    cleanup = 'owned process exited and reaped'
    try:
        if interrupt:
            deadline = time.monotonic() + 5
            while not ready.exists():
                assert child.poll() is None and time.monotonic() < deadline
                time.sleep(0.025)
            os.kill(child.pid, signal.SIGINT)
        out, err = child.communicate(timeout=35)
    except BaseException:
        cleanup = 'owned process group terminated after failure or timeout'
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
        try:
            child.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.communicate()
        raise
    finally:
        records.append(dict(entry, event='end', endTime=time.time(), exitCode=child.returncode,
                            childProcessGroupCleanup=cleanup))
        # Recover only this verifier's controlled sleeper if the implementation failed.
        if ready and ready.exists():
            sleeper = json.loads(ready.read_text())['pid']
            if not group_gone(sleeper):
                os.killpg(sleeper, signal.SIGKILL)
                raise AssertionError('The observer left its owned tool process running')
    value = {'case': label, 'command': argv, 'cwd': str(cwd), 'status': child.returncode,
             'stdout': out.decode(), 'stderr': err.decode()}
    observations.append(value)
    assert child.returncode == expected, value
    return value


def paths(value):
    parts = value['stdout'].split('\0')
    assert parts[-1] == '' and len(parts) == 9, value
    assert parts[::2][:-1] == ['logical', 'physical', 'logical_parent', 'physical_parent']
    return dict(zip(parts[::2], parts[1::2]))


def report(value):
    data = json.loads(value['stdout'])
    assert data['observationsCompleted'] and not data['learnerWorksheetCompletionInferred']
    for entry in data['commands']:
        assert entry['endTime'] >= entry['startTime'] and entry['exitCode'] == 0
        assert not entry['timedOut'] and entry['childProcessGroupCleanup'] == 'owned process exited and reaped'
    assert len(data['commands']) == len(data['observations']) * 3
    inner.extend(data['commands'])
    for index, observed in enumerate(data['observations']):
        commands = data['commands'][index * 3:index * 3 + 3]
        assert [row['command'][0] for row in commands] == ['stat', 'findmnt', 'head']
        actual = base64.b64decode(commands[2]['stdoutBase64'])
        saved = base64.b64decode(observed['capturedBase64'])
        assert len(actual) == observed['bytesRead'] <= 4097
        assert saved == actual[:4096] and len(saved) <= 4096
        assert observed['truncated'] == (len(actual) > 4096)
        assert hashlib.sha256(saved).hexdigest() == observed['capturedSha256']
        size, device, inode = map(int, base64.b64decode(commands[0]['stdoutBase64']).decode().split(':'))
        assert (size, device, inode) == (observed['reportedSize'], observed['device'], observed['inode'])
        assert json.loads(base64.b64decode(commands[1]['stdoutBase64']))['filesystems'] == [observed['filesystem']]
    return data


before = hashes()
try:
    with tempfile.TemporaryDirectory(prefix='linux-filesystem-optional-') as directory:
        work = Path(directory).resolve()
        outside = work / 'outside'
        outside.mkdir()
        sentinel = outside / 'untouched.txt'
        sentinel.write_bytes(b'unchanged outside the selected example\n')
        sentinel_hash = hashlib.sha256(sentinel.read_bytes()).hexdigest()
        bad_bin = work / 'controlled-tools'
        bad_bin.mkdir()
        ready = work / 'controlled-tool-ready.json'
        sleeper = 'import os,json,time;from pathlib import Path;Path(os.environ["FS_READY_FILE"]).write_text(json.dumps({"pid":os.getpid()}));time.sleep(60)'
        shim = bad_bin / 'head'
        shim.write_text('#!/bin/sh\nexec ' + shlex.quote(sys.executable) + ' -c ' + shlex.quote(sleeper) + '\n')
        shim.chmod(0o700)
        for kind, pack in enumerate(PACKS):
            for profile in ('starter', 'solution', 'completed'):
                cwd = work / (str(kind) + '-' + profile)
                shutil.copytree(ROOT / pack / ('starter' if profile == 'completed' else profile), cwd)
                if profile == 'completed':
                    name = 'task.sh' if kind == 0 else 'filesystem_observer.py'
                    target = cwd / name
                    text = target.read_text()
                    old = 'builtin cd -L -- .. # TODO: follow the physical parent, not the logical spelling.' if kind == 0 else 'return reported_size == 0 # TODO: use the count from the actual successful read.'
                    new = 'builtin cd -P -- ..' if kind == 0 else 'return observed_bytes == 0'
                    assert text.count(old) == 1
                    target.write_text(text.replace(old, new))
                count_before = len(observations)
                lab = work / ('example ' + str(kind) + '-' + profile)
                lab.mkdir()
                if kind == 0:
                    physical = lab / 'physical/site'
                    physical.mkdir(parents=True)
                    payload = physical / 'index.html'
                    payload.write_bytes(b'<h1>Owned example</h1>\n')
                    payload_hash = hashlib.sha256(payload.read_bytes()).hexdigest()
                    link = lab / 'served'
                    link.symlink_to('physical/site')
                    value = run(['bash', 'task.sh', str(link)], cwd, 0, 'logical link and different physical parent')
                    actual = paths(value)
                    assert actual == {'logical': str(link), 'physical': str(physical), 'logical_parent': str(lab),
                                      'physical_parent': str(lab if profile == 'starter' else physical.parent)}
                    direct = paths(run(['bash', 'task.sh', str(physical)], cwd, 0, 'direct physical path'))
                    assert direct['logical'] == direct['physical'] == str(physical)
                    assert direct['logical_parent'] == direct['physical_parent'] == str(physical.parent)
                    alternate = lab / 'another view'
                    alternate.symlink_to('physical/site')
                    alternate_result = paths(run(['bash', str(cwd / 'task.sh'), str(alternate)], work, 0, 'different link spelling and caller directory'))
                    assert alternate_result['logical'] == str(alternate) and alternate_result['physical'] == str(physical)
                    unusual = lab / 'trailing newline\n'
                    unusual.mkdir()
                    unusual_result = paths(run(['bash', 'task.sh', str(unusual)], cwd, 0, 'newline survives binary path record'))
                    assert unusual_result['logical'] == unusual_result['physical'] == str(unusual)
                    external = lab / 'outside view'
                    external.symlink_to(outside)
                    external_result = paths(run(['bash', 'task.sh', str(external)], cwd, 0, 'link name does not establish containment'))
                    assert external_result['physical'] == str(outside)
                    assert external_result['physical_parent'] == str(lab if profile == 'starter' else work)
                    broken = lab / 'broken'
                    broken.symlink_to('absent')
                    failed = run(['bash', 'task.sh', str(broken)], cwd, 2, 'broken target')
                    assert not failed['stdout']
                    broken.unlink()
                    broken.symlink_to('physical/site')
                    fixed = paths(run(['bash', 'task.sh', str(broken)], cwd, 0, 'corrected target recovery'))
                    assert fixed['physical'] == str(physical)
                    denied = lab / 'denied'
                    denied.mkdir()
                    denied.chmod(0)
                    try:
                        value = run(['bash', 'task.sh', str(denied)], cwd, 1, 'actual directory traversal denial')
                        assert not value['stdout'] and 'Permission denied' in value['stderr']
                    finally:
                        denied.chmod(0o700)
                    for argv in ([], [str(payload)], [str(physical), str(physical)]):
                        value = run(['bash', 'task.sh', *argv], cwd, 2, 'invalid path arguments')
                        assert not value['stdout']
                    assert hashlib.sha256(payload.read_bytes()).hexdigest() == payload_hash
                else:
                    ordinary, empty, long_file = lab / 'ordinary.txt', lab / 'empty.txt', lab / 'long.txt'
                    ordinary.write_bytes(b'alpha\n')
                    empty.touch()
                    long_file.write_bytes(b'x' * 5000)
                    value = run(['bash', 'task.sh', str(ordinary), str(empty), '/proc/uptime'], cwd, 0, 'ordinary empty and actual proc file')
                    data = report(value)
                    first, second, kernel = data['observations']
                    assert first['reportedSize'] == first['bytesRead'] == 6 and not first['contentEmpty']
                    assert second['reportedSize'] == second['bytesRead'] == 0 and second['contentEmpty']
                    assert kernel['reportedSize'] == 0 and kernel['bytesRead'] > 0 and kernel['filesystem']['fstype'] == 'proc'
                    assert kernel['contentEmpty'] == (profile == 'starter')
                    uptime = base64.b64decode(kernel['capturedBase64']).decode().split()
                    assert len(uptime) == 2 and all(float(value) >= 0 for value in uptime)
                    data = report(run(['bash', 'task.sh', str(long_file)], cwd, 0, 'bounded large ordinary read'))
                    entry = data['observations'][0]
                    assert entry['reportedSize'] == 5000 and entry['bytesRead'] == 4097 and entry['truncated'] and not entry['contentEmpty']
                    quoted = lab / 'with space.txt'
                    quoted.write_bytes(b'alpha\n')
                    data = report(run(['bash', str(cwd / 'task.sh'), str(quoted)], work, 0, 'quoted path and caller directory'))
                    assert data['observations'][0]['inputPath'] == str(quoted)
                    symbolic = lab / 'linked.txt'
                    symbolic.symlink_to(ordinary)
                    data = report(run(['bash', 'task.sh', str(symbolic)], cwd, 0, 'explicit resolved file link'))
                    assert data['observations'][0]['resolvedPath'] == str(ordinary)
                    missing = lab / 'absent.txt'
                    value = run(['bash', 'task.sh', str(ordinary), str(missing)], cwd, 2, 'incomplete multi-path observation')
                    assert not value['stdout']
                    error = json.loads(value['stderr'])
                    assert len(error['completed']) == 1 and len(error['commands']) == 3
                    inner.extend(error['commands'])
                    missing.write_bytes(b'alpha\n')
                    data = report(run(['bash', 'task.sh', str(ordinary), str(missing)], cwd, 0, 'corrected path recovery'))
                    assert len(data['observations']) == 2
                    private = lab / 'private.txt'
                    private.write_bytes(b'alpha\n')
                    private.chmod(0)
                    try:
                        value = run(['bash', 'task.sh', str(private)], cwd, 1, 'actual native read denial')
                        assert not value['stdout']
                        error = json.loads(value['stderr'])
                        assert error['commands'][-1]['exitCode'] == 1 and 'Permission denied' in error['commands'][-1]['stderr']
                        inner.extend(error['commands'])
                    finally:
                        private.chmod(0o600)
                    fifo = lab / 'unread-pipe'
                    os.mkfifo(fifo)
                    for argv in ([], ['-'], [str(lab)], [str(fifo)]):
                        value = run(['bash', 'task.sh', *argv], cwd, 2, 'invalid or nonregular input')
                        assert not value['stdout']
                    if profile == 'solution':
                        controlled_env = dict(environment, PATH=str(bad_bin) + ':' + environment['PATH'], FS_READY_FILE=str(ready))
                        for label, expected, interrupt in [('controlled native-tool deadline', 1, False), ('controlled observer interruption', 130, True)]:
                            value = run(['bash', 'task.sh', str(ordinary)], cwd, expected, label,
                                        env=controlled_env, ready=ready, interrupt=interrupt)
                            assert not value['stdout']
                            error = json.loads(value['stderr'])
                            final = error['commands'][-1]
                            assert final['exitCode'] == -signal.SIGTERM and final['timedOut'] == (not interrupt)
                            assert final['childProcessGroupCleanup'] == 'owned process group terminated after timeout or interruption'
                            assert group_gone(final['pid'])
                            inner.extend(error['commands'])
                    assert ordinary.read_bytes() == b'alpha\n' and empty.read_bytes() == b'' and long_file.read_bytes() == b'x' * 5000
                assert hashlib.sha256(sentinel.read_bytes()).hexdigest() == sentinel_hash
                profiles.append({'pack': pack, 'profile': profile, 'actualCases': len(observations) - count_before,
                                 'readOnlyInputsPreserved': True, 'outsideSentinelPreserved': True,
                                 'starterIntentionallyIncomplete': profile == 'starter', 'passed': True})
    assert hashes() == before
    assert len(profiles) == 6 and len(observations) == 68 and len(inner) == 96
    result = {'nativePassed': True, 'sourceHashes': before, 'profiles': profiles,
              'actualCases': len(observations), 'innerNativeCommands': len(inner),
              'unprivilegedUid': os.geteuid(), 'sourceUnchanged': True,
              'temporaryCasesRemoved': True, 'controlledDeadlineAndInterruptionPassed': True}
    args.proof.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key not in ('sourceHashes', 'profiles')}))
finally:
    args.proof.with_suffix('.observations.json').write_text(json.dumps(observations, indent=2) + '\n')
    args.proof.with_suffix('.processes.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in records))
    args.proof.with_suffix('.native-commands.json').write_text(json.dumps(inner, indent=2) + '\n')
