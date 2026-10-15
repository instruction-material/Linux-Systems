"""Exercise real recovery histories and privately repaired policy functions on Linux."""
import argparse
import ast
import hashlib
import json
import logging
import os
import platform
import shutil
import signal
import subprocess
import tempfile
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKS = ['LS-33-applied-studio-17-linux-systems-lab-17-supplemental-2', 'LS-34-applied-studio-17-linux-systems-lab-17-supplemental-3']
REPAIRS = {'LS-33-applied-studio-17-linux-systems-lab-17-supplemental-2': "def choose_backup(candidates, cutoff_ns):\n    import backup\n    import tarfile\n    eligible = []\n    for path in candidates:\n        if not path.name.endswith('.tar.gz'):\n            continue\n        try:\n            _, manifest = backup.validate(path)\n        except (OSError, ValueError, KeyError, TypeError, tarfile.TarError):\n            continue\n        if manifest['createdNs'] <= cutoff_ns:\n            eligible.append((manifest['createdNs'], path.name, path))\n    return max(eligible, key=lambda item: item[:2])[2] if eligible else None\n", 'LS-34-applied-studio-17-linux-systems-lab-17-supplemental-3': 'def recovered_matches(restored, expected):\n    import backup\n    import hashlib\n    if set(expected) != set(backup.REQUIRED):\n        return False\n    try:\n        if {path.name for path in restored.iterdir()} != set(expected):\n            return False\n        return all(not (restored/name).is_symlink() and (restored/name).is_file()\n                   and hashlib.sha256((restored/name).read_bytes()).hexdigest() == digest\n                   for name, digest in expected.items())\n    except OSError:\n        return False\n'}
ROWS = []
EVENTS = []
PROFILES = []
LOGGER = logging.getLogger(__name__)


def source_hashes():
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for pack in PACKS for p in (ROOT/pack).rglob('*') if p.is_file()}


def invoke(case, command, cwd, expected, interrupt_parent=None):
    started = time.time()
    child = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, start_new_session=True)
    start = {'parentTaskId': os.environ.get('CLASSES_FAMILY_TASK_ID', 'linux-capstone-recovery-source-ci'),
                 'parentPid': os.getpid(), 'case': case, 'command': command, 'cwd': str(cwd),
                 'pid': child.pid, 'startTime': started, 'timeoutSeconds': 45}
    EVENTS.append(dict(start, event='start'))
    cleanup = 'owned process exited and reaped'
    try:
        if interrupt_parent is not None:
            ready = interrupt_parent/'ready.json'
            deadline = time.monotonic()+25
            while not ready.exists():
                assert child.poll() is None and time.monotonic()<deadline, 'held equipment did not become ready'
                time.sleep(0.03)
            details = json.loads(ready.read_text())
            assert details['pid'] == child.pid and details['uid'] == os.geteuid()
            os.killpg(child.pid, signal.SIGINT)
        out, err = child.communicate(timeout=45)
    except BaseException:
        cleanup = 'owned process group terminated and reaped'
        os.killpg(child.pid, signal.SIGTERM)
        try:
            out, err = child.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            out, err = child.communicate()
        raise
    finally:
        EVENTS.append(dict(start, event='end', endTime=time.time(), exitCode=child.returncode,
                           childProcessGroupCleanup=cleanup))
    row={'case': case, 'command': command, 'cwd': str(cwd), 'pid': child.pid,
             'status': child.returncode, 'stdout': out.decode(), 'stderr': err.decode()}
    ROWS.append(row)
    assert child.returncode == expected, row
    assert not err if out else err
    return json.loads(out) if out else None


def completed(role, repair):
    path = role/'task.py'
    text = path.read_text()
    function = next(node for node in ast.parse(text).body if isinstance(node, ast.FunctionDef))
    lines=text.splitlines(keepends=True)
    path.write_text(''.join(lines[:function.lineno-1])+repair+'\n'+''.join(lines[function.end_lineno:]))


def check_report(data, complete, interrupted=False):
    assert data['sourceUnchanged'] and data['ownedCaseRemoved'] and data['workspaceEmpty']
    assert data['failure'] is None and data['uid'] == os.geteuid()
    assert data['interrupted'] == interrupted and not data['learnerWorksheetCompletionInferred']
    assert len(data['archives']) == 3
    assert all(row['status'] in [0,2] and row['cleanup']=='owned process exited and reaped'
               and row['uid']==os.geteuid() and row['endTime']>=row['startTime']
               for row in data['commands'])
    cases={row['case']:row for row in data['commands']}
    assert all(cases['build generation '+str(i)]['status']==cases['verify generation '+str(i)]['status']==0 for i in range(3))
    assert cases['reject changed payload']['status']==cases['reject candidate after write']['status']==2
    if interrupted:
        assert not data['decisions'] and not data['restores']
        return
    assert data['archiveHashesBeforeDecisions'] == data['archiveHashesAfterDecisions']
    assert data['targetBehaviorObserved'] == complete
    assert len(data['decisions']) == (4 if data['kind']=='selection' else 7)
    assert all(row['matchedTarget'] for row in data['decisions']) == complete
    if data['kind']=='selection':
        if complete:
            assert len(data['restores'])==3
            assert data['decisions'][-1]['selected'] is None
        else:
            assert all(row['selected'].endswith('/changed-payload.tar.gz') for row in data['decisions'])
            assert not data['restores']
    else:
        assert len(data['restores'])==3 and data['existingDestinationUnchanged']
        assert cases['reject existing restore destination']['status']==2
    assert len({row['pid'] for row in data['commands']})==len(data['commands'])
    for row in data['commands']:
        try:
            os.kill(row['pid'],0)
        except ProcessLookupError:
            continue
        raise AssertionError(('owned child survived',row['pid']))


def exercise(pack, profile, work):
    role=work/(str(PACKS.index(pack))+'-'+profile+' quoted role')
    shutil.copytree(ROOT/pack/('starter' if profile=='completed' else profile),role)
    if profile=='completed':
        completed(role, REPAIRS[pack])
    parent=work/(str(PACKS.index(pack))+'-'+profile+' quoted parent')
    parent.mkdir(mode=0o700)
    outside=work/'outside-sentinel'
    before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in role.iterdir() if p.is_file()}
    first=len(ROWS)
    complete=profile!='starter'
    for reverse in [False,True]:
        command=['bash',str(role/'task.sh'),str(parent)]+(['--reverse'] if reverse else [])
        data=invoke('actual reversed history' if reverse else 'actual ordinary history',command,work,0 if complete else 1)
        check_report(data,complete)
        assert data['reverse']==reverse and not any(parent.iterdir())
    data=invoke('actual recovery history interruption',
                ['bash',str(role/'task.sh'),str(parent),'--hold-seconds','8'],work,130,interrupt_parent=parent)
    check_report(data,complete,True)
    assert not any(parent.iterdir())
    # An ordinary run after the interruption demonstrates recovery, not just cleanup.
    data=invoke('actual recovery after interruption',['bash',str(role/'task.sh'),str(parent)],work,0 if complete else 1)
    check_report(data,complete)
    missing=work/'missing-parent'
    assert not missing.exists()
    invoke('missing parent refusal',['bash',str(role/'task.sh'),str(missing)],work,2)
    sentinel=parent/'keep.txt'
    sentinel.write_bytes(b'owned input stays unchanged\n')
    invoke('nonempty parent refusal',['bash',str(role/'task.sh'),str(parent)],work,2)
    assert sentinel.read_bytes()==b'owned input stays unchanged\n'
    sentinel.unlink()
    link=work/(str(PACKS.index(pack))+'-'+profile+' parent-link')
    link.symlink_to(parent,target_is_directory=True)
    invoke('symlink parent refusal',['bash',str(role/'task.sh'),str(link)],work,2)
    assert not any(parent.iterdir()) and link.is_symlink()
    link.unlink()
    invoke('invalid hold refusal',['bash',str(role/'task.sh'),str(parent),'--hold-seconds','16'],work,2)
    assert not any(parent.iterdir()) and outside.read_bytes()==b'outside remains unchanged\n'
    assert before=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in role.iterdir() if p.is_file()}
    PROFILES.append({'pack': pack,'profile': profile,'passed': True,'inputsUnchanged': True,
                         'outsideSentinelPreserved': True,'ownedResourcesRemoved': True,
                         'learnerWorksheetCompletionInferred': False,'actualCases': len(ROWS)-first})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proof',type=Path,required=True)
    args=parser.parse_args()
    args.proof.parent.mkdir(parents=True,exist_ok=True)
    before=source_hashes()
    error=None
    try:
        assert platform.system()=='Linux' and os.geteuid()>0
        with tempfile.TemporaryDirectory(prefix='linux-recovery-native-') as directory:
            work=Path(directory)
            (work/'outside-sentinel').write_bytes(b'outside remains unchanged\n')
            for pack in PACKS:
                for profile in ['starter','solution','completed']:
                    exercise(pack,profile,work)
                    assert source_hashes()==before
        assert not work.exists() and len(PROFILES)==6 and len(ROWS)==48
    except BaseException:
        LOGGER.exception('Native recovery contract failed; retaining raw evidence')
        error=traceback.format_exc()
    proof={'nativePassed': error is None,'platform': platform.system(),'uid': os.geteuid(),
               'sourceHashes': before,'sourceUnchanged': source_hashes()==before,
               'profiles': PROFILES,'actualCases': len(ROWS),'loggedOuterLifecycles': len(EVENTS)//2,
               'actualBackupChildLifecycles': sum(len(json.loads(r['stdout'])['commands']) for r in ROWS if r['stdout']),
               'error': error,'learnerWorksheetCompletionInferred': False}
    args.proof.write_text(json.dumps(proof,indent=2)+'\n')
    args.proof.with_suffix('.observations.json').write_text(json.dumps(ROWS,indent=2)+'\n')
    args.proof.with_suffix('.processes.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in EVENTS))
    if error:
        raise AssertionError(error)
    print(json.dumps({k:v for k,v in proof.items() if k not in ['profiles','sourceHashes']}))


if __name__=='__main__':
    main()
