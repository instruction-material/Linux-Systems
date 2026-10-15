"""Exercise real Bash lookup, executable selection and interpreter launches."""
import argparse
import hashlib
import json
import os
import platform
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKS = ['LS-01-ls0-setup-and-tooling-supplemental-2',
         'LS-02-ls0-setup-and-tooling-supplemental-3']
parser = argparse.ArgumentParser()
parser.add_argument('--proof', type=Path, required=True)
args = parser.parse_args()
assert platform.system() == 'Linux' and os.geteuid() > 0
assert Path('/bin/bash').is_file() and Path('/bin/sh').is_file()
bash = shutil.which('bash')
assert bash
environment = dict(os.environ, LC_ALL='C', BASH_ENV='/dev/null', ENV='/dev/null')
args.proof = args.proof.resolve()
args.proof.parent.mkdir(parents=True, exist_ok=True)
observations, events, profiles = [], [], []


def sha(content):
    return hashlib.sha256(content).hexdigest()


def hashes():
    return {str(f.relative_to(ROOT)): sha(f.read_bytes()) for p in PACKS
            for f in sorted((ROOT / p).rglob('*')) if f.is_file()}


def run(case, command, cwd, status=None):
    child = subprocess.Popen([str(x) for x in command], cwd=cwd, env=environment,
                             stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, start_new_session=True)
    entry = {'parentTaskId': os.environ.get('CLASSES_FAMILY_TASK_ID', 'linux-setup-source'),
             'parentPid': os.getpid(), 'pid': child.pid, 'cwd': str(cwd),
             'command': [str(x) for x in command], 'startTime': time.time(), 'timeoutSeconds': 15}
    events.append(dict(entry, event='start'))
    cleanup = 'owned process exited and reaped'
    try:
        out, err = child.communicate(timeout=15)
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
        events.append(dict(entry, event='end', endTime=time.time(), exitCode=child.returncode,
                           childProcessGroupCleanup=cleanup))
    try:
        os.killpg(child.pid, 0)
    except ProcessLookupError:
        pass
    else:
        os.killpg(child.pid, signal.SIGKILL)
        raise AssertionError('An owned child process remained after the command exited')
    row = {'case': case, 'command': [str(x) for x in command], 'cwd': str(cwd),
           'status': child.returncode, 'stdout': out.decode(), 'stderr': err.decode()}
    observations.append(row)
    if status is not None:
        assert row['status'] == status, row
    return row


def fields(row):
    return dict(line.split('=', 1) for line in row['stdout'].splitlines() if '=' in line)


def demo_output(values):
    return f'argument_count={len(values)}\n' + ''.join(
        f'argument[{i}]=<{value}>\n' for i, value in enumerate(values))


before = hashes()
assert len(before) == 18
with tempfile.TemporaryDirectory(prefix='linux-setup-') as temporary:
    work = Path(temporary)
    outside = work / 'outside-sentinel'
    outside.write_bytes(b'outside remains unchanged\n')
    outside_hash = sha(outside.read_bytes())
    caller = work / 'another caller'
    caller.mkdir()
    parent_path = os.environ.get('PATH')
    # The supported native profile uses Dash; record this premise explicitly.
    shell = run('actual sh implementation', ['/bin/sh', '-c', 'printf "%s\\n" "${BASH_VERSION-unset}"'], work, 0)
    assert shell['stdout'] == 'unset\n', 'This source acceptance profile requires a non-Bash /bin/sh'
    for index, pack in enumerate(PACKS):
        for role in ['starter', 'solution', 'completed']:
            initial = len(observations)
            target = work / (str(index) + '-' + role + ' quoted workspace')
            shutil.copytree(ROOT / pack / ('starter' if role == 'completed' else role), target)
            task = target / 'task.sh'
            if role == 'completed':
                text = task.read_text()
                old, new = (('if (( lookup_status == 0 ));', 'if (( lookup_status == 0 && run_status == 0 ));')
                            if index == 0 else ('exec /bin/sh', 'exec "$BASH" --noprofile --norc'))
                assert text.count(old) == 1
                task.write_text(text.replace(old, new))
            original_task = task.read_bytes()
            if index == 0:
                tools = {name: target / 'tools' / name for name in ['first', 'second', 'failing']}
                for directory in tools.values():
                    (directory / 'lab-tool.sh').chmod(0o700)
                tool_hashes = {name: sha((directory/'lab-tool.sh').read_bytes()) for name, directory in tools.items()}
                first_second = str(tools['first']) + ':' + str(tools['second'])
                for case, path, version in [('first available version', first_second, 'first 1.0'),
                                            ('reordered available version', str(tools['second'])+':'+str(tools['first']), 'second 2.0')]:
                    row = run(case, [bash, task, path], target, 0)
                    data = fields(row)
                    assert data['lookup_status'] == data['run_status'] == '0' and data['usable'] == 'yes'
                    chosen = version.split()[0]
                    assert data['resolved'] == str(tools[chosen] / 'lab-tool.sh')
                    assert 'lab-tool '+version+'\n' in row['stdout'] and not row['stderr']
                row = run('located tool actually fails', [bash, task, str(tools['failing'])+':'+str(tools['first'])], target, 0 if role == 'starter' else 1)
                data = fields(row)
                assert data['lookup_status'] == '0' and data['run_status'] == '23'
                assert data['usable'] == ('yes' if role == 'starter' else 'no')
                assert data['resolved'] == str(tools['failing']/'lab-tool.sh') and row['stderr'] == 'controlled version failure\n'
                empty = target / 'empty search'
                empty.mkdir()
                row = run('actual missing executable', [bash, task, empty], target, 1)
                data = fields(row)
                assert data['lookup_status'] == '1' and data['resolved'] == '' and data['run_status'] == '127' and data['usable'] == 'no'
                assert 'command not found' in row['stderr']
                first_file = tools['first'] / 'lab-tool.sh'
                first_file.chmod(0o600)
                try:
                    row = run('nonexecutable entry falls through to next directory', [bash, task, first_second], target, 0)
                    assert fields(row)['resolved'] == str(tools['second']/'lab-tool.sh')
                    assert 'lab-tool second 2.0\n' in row['stdout'] and not row['stderr']
                finally:
                    first_file.chmod(0o700)
                row = run('recovered first entry from another caller', [bash, task, first_second], caller, 0)
                assert fields(row)['resolved'] == str(first_file) and not row['stderr']
                linked = target / 'linked directory'
                linked.symlink_to(tools['first'], target_is_directory=True)
                for path in ['', ':pat', first_second+':', str(empty)+'::'+str(empty), 'relative', str(target/'absent'), str(first_file), str(linked), str(empty)+'\n']:
                    row = run('invalid search directory list', [bash, task, path], target, 2)
                    assert not row['stdout'] and row['stderr']
                for values in [[], [first_second, 'extra']]:
                    row = run('invalid search argument count', [bash, task, *values], target, 2)
                    assert not row['stdout'] and row['stderr']
                assert tool_hashes == {name: sha((directory/'lab-tool.sh').read_bytes()) for name, directory in tools.items()}
                assert first_file.stat().st_mode & 0o777 == 0o700
                actual_cases = len(observations)-initial
                assert actual_cases == 17
            else:
                demo = target / 'args-demo.sh'
                demo_hash = sha(demo.read_bytes())
                demo.chmod(0o600)
                for values in [[], ['two words', ''], ['*.txt', '-n', '', 'two\nlines']]:
                    row = run('preserve original argument boundaries', [bash, task, demo, *values], target, 2 if role == 'starter' else 0)
                    if role == 'starter':
                        assert not row['stdout'] and row['stderr']
                    else:
                        assert row['stdout'] == demo_output(values) and not row['stderr']
                row = run('relative source path', [bash, task, './args-demo.sh', 'two words', ''], target, 2 if role == 'starter' else 0)
                if role != 'starter':
                    assert row['stdout'] == demo_output(['two words', '']) and not row['stderr']
                row = run('absolute source from another caller', [bash, task, demo, 'other'], caller, 2 if role == 'starter' else 0)
                if role != 'starter':
                    assert row['stdout'] == demo_output(['other']) and not row['stderr']
                row = run('actual direct execution denied', [bash, '--noprofile', '--norc', '-c', '"$1" "$2"', 'direct-probe', demo, 'two words'], target, 126)
                assert not row['stdout'] and 'Permission denied' in row['stderr']
                demo.chmod(0o700)
                try:
                    row = run('actual shebang direct execution', [bash, '--noprofile', '--norc', '-c', '"$1" "$2"', 'direct-probe', demo, 'two words'], target, 0)
                    assert row['stdout'] == demo_output(['two words']) and not row['stderr']
                finally:
                    demo.chmod(0o600)
                row = run('explicit sh bypasses Bash shebang', ['/bin/sh', demo], target, 2)
                assert not row['stdout'] and row['stderr']
                demo.chmod(0)
                try:
                    row = run('actual source read denied', [bash, task, demo], target)
                    assert row['status'] != 0 and not row['stdout'] and 'Permission denied' in row['stderr']
                finally:
                    demo.chmod(0o600)
                row = run('read permission restored', [bash, task, demo, 'recovered'], target, 2 if role == 'starter' else 0)
                if role != 'starter':
                    assert row['stdout'] == demo_output(['recovered']) and not row['stderr']
                linked = target / 'linked.sh'
                linked.symlink_to(demo)
                for value in [target/'absent.sh', target, linked]:
                    row = run('invalid source target', [bash, task, value], target, 2)
                    assert not row['stdout'] and 'ordinary nonsymlink script' in row['stderr']
                row = run('missing source argument', [bash, task], target, 2)
                assert not row['stdout'] and 'usage:' in row['stderr']
                assert sha(demo.read_bytes()) == demo_hash and demo.stat().st_mode & 0o777 == 0o600
                actual_cases = len(observations)-initial
                assert actual_cases == 14
            assert task.read_bytes() == original_task and sha(outside.read_bytes()) == outside_hash
            assert os.environ.get('PATH') == parent_path
            profiles.append({'pack': pack, 'profile': role, 'actualCases': actual_cases,
                             'inputsUnchanged': True, 'outsideSentinelPreserved': True,
                             'temporaryModesRestored': True, 'callerPathUnchanged': True,
                             'starterIntentionallyIncomplete': role == 'starter', 'passed': True})
    assert len(profiles) == 6 and hashes() == before
assert not work.exists()
proof = {'nativePassed': True, 'unprivilegedUid': os.geteuid(), 'sourceHashes': before,
         'sourceUnchanged': True, 'profiles': profiles, 'actualCases': len(observations),
         'processLifecycles': len(events)//2, 'shProfile': 'non-Bash /bin/sh',
         'callerPathUnchanged': True, 'temporaryCasesRemoved': True}
assert proof['actualCases'] == proof['processLifecycles'] == 94
args.proof.write_text(json.dumps(proof, indent=2)+'\n')
args.proof.with_suffix('.observations.json').write_text(json.dumps(observations, indent=2)+'\n')
args.proof.with_suffix('.processes.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in events))
print(json.dumps({k:v for k,v in proof.items() if k != 'sourceHashes'}))
