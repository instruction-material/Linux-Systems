"""Black-box native acceptance of literal filename streams and pipeline failures."""
import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKS = ['LS-03-unit-1-shell-foundations-supplemental-2',
         'LS-04-unit-1-shell-foundations-supplemental-3']
parser = argparse.ArgumentParser()
parser.add_argument('--proof', required=True, type=Path)
args = parser.parse_args()
assert platform.system() == 'Linux' and os.geteuid() > 0
assert all(shutil.which(name) for name in ('bash', 'grep', 'sort', 'cat', 'awk'))
args.proof = args.proof.resolve()
args.proof.parent.mkdir(parents=True, exist_ok=True)
records, observations, profiles = [], [], []
environment = dict(os.environ, LC_ALL='C', PYTHONDONTWRITEBYTECODE='1')
task = environment.get('CLASSES_FAMILY_TASK_ID', 'linux-shell-optional-source')


def hashes():
    return {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest()
            for pack in PACKS for f in sorted((ROOT / pack).rglob('*')) if f.is_file()}


def run(argv, cwd, expected, label, env=None):
    child = subprocess.Popen(argv, cwd=cwd, env=environment if env is None else env,
                             stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, start_new_session=True)
    entry = {'parentTaskId': task, 'parentPid': os.getpid(), 'command': argv,
             'cwd': str(cwd), 'pid': child.pid, 'startTime': time.time(), 'timeoutSeconds': 15}
    records.append(dict(entry, event='start'))
    cleanup = 'owned process exited and reaped'
    try:
        out, err = child.communicate(timeout=15)
    except BaseException:
        cleanup = 'owned process group terminated after failure or timeout'
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
    result = {'case': label, 'command': argv, 'cwd': str(cwd), 'status': child.returncode,
              'stdout': out.decode(), 'stderr': err.decode()}
    observations.append(result)
    assert child.returncode == expected, result
    return result


def statuses(result, kind):
    pattern = r'grep=(\d+) sort=(\d+)' if kind == 0 else r'producer=(\d+) consumer=(\d+)'
    match = re.search(pattern, result['stderr'])
    assert match, result
    return tuple(map(int, match.groups()))


def names(result, expected):
    actual = result['stdout'].encode()
    wanted = b''.join(value.encode() + b'\0' for value in sorted(set(expected), key=lambda x: x.encode()))
    assert actual == wanted, result


before = hashes()
try:
    with tempfile.TemporaryDirectory(prefix='linux-shell-optional-') as temporary:
        work = Path(temporary)
        bad_bin = work / 'failing-sort'
        bad_bin.mkdir()
        # Execute the actual GNU sort with an invalid option, not a fabricated status.
        real_sort = shutil.which('sort')
        shim = bad_bin / 'sort'
        shim.write_text('#!/bin/sh\nexec ' + real_sort + ' --invalid-course-option "$@"\n')
        shim.chmod(0o700)
        for kind, pack in enumerate(PACKS):
            for profile in ('starter', 'solution', 'completed'):
                cwd = work / (str(kind) + '-' + profile)
                source_role = 'starter' if profile == 'completed' else profile
                shutil.copytree(ROOT / pack / source_role, cwd)
                if profile == 'completed':
                    target = cwd / 'task.sh'
                    original = target.read_text()
                    if kind == 0:
                        old = '# TODO: distinguish a matching search, no matches and either tool failing.\nprintf \'TODO: interpret both saved pipeline statuses.\\n\' >&2\nexit 2\n'
                        new = 'if (( statuses[1] != 0 || statuses[0] > 1 )); then\n    printf \'Search or sorting failed; discard any partial filename list.\\n\' >&2\n    exit 2\nfi\nexit "${statuses[0]}"\n'
                    else:
                        old = 'if (( statuses[1] != 0 )); then # TODO: include the producer status.'
                        new = 'if (( statuses[0] != 0 || statuses[1] != 0 )); then'
                    assert original.count(old) == 1
                    target.write_text(original.replace(old, new))
                inputs = ['records/alpha.txt', 'records/with space.txt', 'records/-dash.txt']
                initial_hashes = {str(f.relative_to(cwd)): hashlib.sha256(f.read_bytes()).hexdigest()
                                  for f in sorted(cwd.rglob('*')) if f.is_file()}
                count_before = len(observations)
                if kind == 0:
                    result = run(['bash', 'task.sh', 'ERROR[42]', *inputs], cwd,
                                 2 if profile == 'starter' else 0, 'literal matching names')
                    names(result, [inputs[0], inputs[2]])
                    assert statuses(result, kind) == (0, 0)
                    result = run(['bash', 'task.sh', 'ABSENT', *inputs], cwd,
                                 2 if profile == 'starter' else 1, 'valid no matches')
                    names(result, [])
                    assert statuses(result, kind) == (1, 0)
                    result = run(['bash', 'task.sh', 'ERROR4', *inputs], cwd,
                                 2 if profile == 'starter' else 0, 'changed literal pattern')
                    names(result, inputs[1:])
                    odd = cwd / 'records/two\nlines.txt'
                    odd.write_text('00:09 INFO ERROR[42]\n')
                    result = run(['bash', 'task.sh', 'ERROR[42]', 'records/two\nlines.txt', inputs[0], inputs[0]], cwd,
                                 2 if profile == 'starter' else 0, 'newline and duplicate operand')
                    names(result, ['records/two\nlines.txt', inputs[0]])
                    odd.unlink()
                    result = run(['bash', 'task.sh', 'ERROR[42]', inputs[0], 'records/missing.txt'], cwd, 2,
                                 'match does not conceal a missing operand')
                    assert statuses(result, kind)[0] > 1
                    assert inputs[0] in result['stdout']
                    unreadable = cwd / 'records/private.txt'
                    unreadable.write_text('ERROR[42]\n')
                    unreadable.chmod(0)
                    try:
                        result = run(['bash', 'task.sh', 'ERROR[42]', str(unreadable)], cwd, 2,
                                     'actual permission denial differs from no matches')
                        assert statuses(result, kind)[0] > 1
                    finally:
                        unreadable.chmod(0o600)
                        unreadable.unlink()
                    result = run(['bash', 'task.sh', 'ERROR[42]', *inputs], cwd, 2,
                                 'actual consumer sort failure', env=dict(environment, PATH=str(bad_bin) + ':' + environment['PATH']))
                    assert statuses(result, kind)[1] > 0
                    assert 'invalid-course-option' in result['stderr']
                    escaped = cwd / 'records/-needle.txt'
                    escaped.write_text('-x[y]\n')
                    result = run(['bash', 'task.sh', '-x[y]', str(escaped)], cwd,
                                 2 if profile == 'starter' else 0, 'literal dash-leading pattern')
                    names(result, [str(escaped)])
                    escaped.unlink()
                    for argv in ([], [''], ['ERROR', '-'], ['ERROR', 'records']):
                        run(['bash', 'task.sh', *argv], cwd, 2, 'invalid operands')
                    result = run(['bash', str(cwd / 'task.sh'), 'ERROR[42]', str(cwd / inputs[0])], work,
                                 2 if profile == 'starter' else 0, 'caller directory and explicit path')
                    names(result, [str(cwd / inputs[0])])
                else:
                    result = run(['bash', 'task.sh', *inputs], cwd, 0, 'complete structured input')
                    assert result['stdout'] == 'errors=2 warnings=2\n'
                    assert statuses(result, kind) == (0, 0)
                    for operands in ([inputs[0], 'records/missing.txt'], ['records/missing.txt', inputs[0]]):
                        result = run(['bash', 'task.sh', *operands], cwd,
                                     0 if profile == 'starter' else 2, 'partial producer failure in both orders')
                        assert result['stdout'] == 'errors=1 warnings=1\n'
                        assert statuses(result, kind)[0] > 0 and statuses(result, kind)[1] == 0
                    empty = cwd / 'records/empty.txt'
                    empty.touch()
                    result = run(['bash', 'task.sh', str(empty)], cwd, 0, 'empty successful input')
                    assert result['stdout'] == 'errors=0 warnings=0\n'
                    empty.unlink()
                    copied = cwd / 'records/copied input.txt'
                    copied.write_bytes((cwd / inputs[0]).read_bytes())
                    result = run(['bash', 'task.sh', str(copied)], cwd, 0, 'quoted input path')
                    assert result['stdout'] == 'errors=1 warnings=1\n'
                    copied.unlink()
                    target = cwd / 'count.awk'
                    saved = target.read_bytes()
                    target.write_bytes(saved + b'\nBEGIN {\n')
                    try:
                        result = run(['bash', 'task.sh', *inputs], cwd, 2, 'actual awk syntax error')
                        assert statuses(result, kind)[1] > 0
                    finally:
                        target.write_bytes(saved)
                    result = run(['bash', str(cwd / 'task.sh'), str(cwd / inputs[0])], work, 0,
                                 'restoration and caller directory')
                    assert result['stdout'] == 'errors=1 warnings=1\n'
                    assert statuses(result, kind) == (0, 0)
                    for argv in ([], ['-'], ['records']):
                        run(['bash', 'task.sh', *argv], cwd, 2, 'invalid operands')
                symbolic = cwd / 'records/symbolic.txt'
                symbolic.symlink_to(cwd / inputs[0])
                fifo = cwd / 'records/pipe.txt'
                os.mkfifo(fifo)
                try:
                    for path in (symbolic, fifo):
                        operands = ['ERROR[42]', str(path)] if kind == 0 else [str(path)]
                        run(['bash', 'task.sh', *operands], cwd, 2, 'reject a symlink or FIFO without following or blocking')
                finally:
                    symbolic.unlink()
                    fifo.unlink()
                after_hashes = {str(f.relative_to(cwd)): hashlib.sha256(f.read_bytes()).hexdigest()
                                for f in sorted(cwd.rglob('*')) if f.is_file()}
                assert after_hashes == initial_hashes
                profiles.append({'pack': pack, 'profile': profile, 'actualCases': len(observations) - count_before,
                                 'inputAndHelperRestored': True, 'passed': True,
                                 'starterIntentionallyIncomplete': profile == 'starter'})
    assert hashes() == before
    result = {'nativePassed': True, 'sourceHashes': before, 'profiles': profiles,
              'actualCases': len(observations), 'unprivilegedUid': os.geteuid(),
              'sourceUnchanged': True, 'ownedTemporaryCasesRemoved': True}
    args.proof.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'nativePassed': True, 'profiles': len(profiles), 'actualCases': len(observations)}))
finally:
    args.proof.with_suffix('.observations.json').write_text(json.dumps(observations, indent=2) + '\n')
    args.proof.with_suffix('.processes.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in records))
