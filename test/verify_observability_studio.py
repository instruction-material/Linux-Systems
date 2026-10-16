"""Accept real own-user timer, journal, artifact and progress observations."""
import argparse
import ast
import base64
import hashlib
import importlib.util
import json
import logging
import os
import platform
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
PACKS=['LS-02-linux-systems-lab-15', 'LS-29-applied-studio-15-linux-systems-lab-15-supplemental-2', 'LS-30-applied-studio-15-linux-systems-lab-15-supplemental-3']
REPAIRS={'LS-02-linux-systems-lab-15': "def artifact_is_current(state, artifact, expected_sha256):\n    import hashlib\n    if state.get('Result') != 'success' or state.get('ExecMainStatus') != '0':\n        return False\n    return (not artifact.is_symlink() and artifact.is_file()\n            and hashlib.sha256(artifact.read_bytes()).hexdigest() == expected_sha256)\n", 'LS-29-applied-studio-15-linux-systems-lab-15-supplemental-2': "def select_completed(rows, invocation):\n    import json\n    selected = []\n    for row in rows:\n        try:\n            message = json.loads(row.get('MESSAGE', ''))\n        except (ValueError, TypeError):\n            continue\n        if (isinstance(message, dict) and message.get('event') == 'end'\n                and message.get('invocation') == invocation):\n            selected.append(row)\n    return selected\n", 'LS-30-applied-studio-15-linux-systems-lab-15-supplemental-3': "def classify_progress(state, events, now_ns, budget_ns):\n    if state.get('ActiveState') == 'failed' or state.get('Result') == 'exit-code':\n        return 'failed'\n    if (state.get('SubState') == 'exited' and state.get('ExecMainStatus') == '0'\n            and any(row['event'] == 'end' for row in events)):\n        return 'complete'\n    starts = [row for row in events if row['event'] == 'start']\n    if starts and now_ns - starts[0]['monotonicNs'] >= budget_ns:\n        return 'overdue'\n    return 'waiting'\n"}
ROWS=[]
EVENTS=[]
PROFILES=[]
LOGGER=logging.getLogger(__name__)


def hashes():
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for pack in PACKS for p in (ROOT/pack).rglob('*') if p.is_file()}


def invoke(case, command, cwd, expected, interrupt_parent=None):
    child=subprocess.Popen(command,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
    entry={'parentTaskId':os.environ.get('CLASSES_FAMILY_TASK_ID','linux-observability-studio-source-ci'),
           'parentPid':os.getpid(),'case':case,'command':command,'cwd':str(cwd),
           'pid':child.pid,'startTime':time.time(),'timeoutSeconds':55}
    EVENTS.append({**entry,'event':'start'})
    cleanup='owned process exited and reaped'
    try:
        if interrupt_parent is not None:
            ready=interrupt_parent/'ready.json'
            deadline=time.monotonic()+25
            while not ready.exists():
                assert child.poll() is None and time.monotonic()<deadline,'live held unit did not become ready'
                time.sleep(0.02)
            record=json.loads(ready.read_text())
            assert record['pid']==child.pid and int(record['workerPid'])>0
            assert re.fullmatch(r'classes-observe-[0-9a-f]{32}\.service',record['unit'])
            os.killpg(child.pid,signal.SIGINT)
        out,err=child.communicate(timeout=55)
    except BaseException:
        cleanup='owned process group terminated and reaped'
        if child.poll() is None:
            os.killpg(child.pid,signal.SIGTERM)
        try:
            out,err=child.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid,signal.SIGKILL)
            out,err=child.communicate()
        raise
    finally:
        EVENTS.append({**entry,'event':'end','endTime':time.time(),
                       'exitCode':child.returncode,'childProcessGroupCleanup':cleanup})
    row={'case':case,'command':command,'cwd':str(cwd),'pid':child.pid,
         'status':child.returncode,'stdout':out.decode(),'stderr':err.decode()}
    ROWS.append(row)
    assert child.returncode==expected,row
    if case.endswith('refusal'):
        assert not out and err, row
        return None
    assert out and not err, row
    return json.loads(out)


def completed(role,repair):
    path=role/'task.py'
    text=path.read_text()
    function=next(node for node in ast.parse(text).body if isinstance(node,ast.FunctionDef))
    lines=text.splitlines(keepends=True)
    path.write_text(''.join(lines[:function.lineno-1])+repair+'\n'+''.join(lines[function.end_lineno:]))


def check(data,kind,complete,interrupted=False):
    assert data['kind']==kind and data['uid']==os.geteuid() and data['sourceUnchanged']
    assert data['ownedCaseRemoved'] and data['workspaceEmpty'] and data['failure'] is None
    assert not data['cleanupErrors']
    assert data['interrupted']==interrupted and not data['learnerWorksheetCompletionInferred']
    assert re.fullmatch(r'[0-9a-f]{32}',data['bootId'])
    assert len(data['units'])==(1 if interrupted else 3 if kind=='progress' else 2)
    for unit in data['units']:
        assert unit['ownedWorkerPidsGone']
        assert all(s['LoadState']=='not-found' for s in unit['statesAfterCleanup'].values())
        expected={unit['service'],unit['timer']}
        assert set(unit['statesAfterCleanup'])==expected
        for pid in {e['pid'] for e in unit['events']}:
            try:
                os.kill(pid,0)
            except ProcessLookupError:
                continue
            raise AssertionError(('managed worker survived',pid))
        activations=unit['activationEvidence']
        assert len(activations)==len({e['invocation'] for e in unit['events']})
        assert activations[0]['kind']=='timer'
        assert activations[0]['timer']['LoadState']=='loaded'
        assert activations[0]['timer']['LastTriggerUSec'] not in ('','n/a','0')
        for activation in activations:
            assert activation['state']['ActiveState']=='activating'
            assert int(activation['state']['MainPID'])==activation['worker']['pid']==activation['process']['pid']
            assert activation['state']['InvocationID']==activation['worker']['invocation']==activation['process']['invocation']
            gate=base64.b64decode(activation['gate']['bytesBase64'],validate=True)
            assert gate.decode().strip()==activation['job']['run'] and activation['gate']['mode']=='0o600'
            assert activation['worker']['monotonicNs']<=activation['releaseRequestedMonotonicNs']<=activation['releasedMonotonicNs']
        for observed in unit['observations']:
            invocation=observed['state']['InvocationID']
            assert re.fullmatch(r'[0-9a-f]{32}',invocation)
            workers=[e for e in observed['events'] if e['invocation']==invocation]
            assert workers and workers[0]['event']=='start'
            for e in workers:
                assert e['uid']==os.geteuid()
                matches=[]
                for row in observed['journalRows']:
                    try:
                        value=json.loads(row.get('MESSAGE',''))
                    except (ValueError,TypeError):
                        continue
                    if value==e:
                        assert row['_PID']==str(e['pid']) and row['_UID']==str(os.geteuid())
                        assert row['_BOOT_ID']==data['bootId']
                        assert row.get('_SYSTEMD_USER_UNIT',row.get('USER_UNIT'))==unit['service']
                        matches.append(row)
                assert len(matches)==1
            raw=base64.b64decode(observed['output']['bytesBase64'],validate=True)
            assert hashlib.sha256(raw).hexdigest()==observed['output']['sha256']
    for command in data['commands']:
        assert command['cleanup']=='owned CLI process exited and reaped' and command['timeoutSeconds']==6
        assert command['endTime']>=command['startTime']
    if interrupted:
        assert not data['decisions'] and len(data['actualManagedProcesses'])==1
        return
    assert data['targetBehaviorObserved']==complete and all(d['matchedTarget'] for d in data['decisions'])==complete
    if kind=='output':
        assert {d['case'] for d in data['decisions']}=={'good','incomplete'}
        assert all(d['state']['ActiveState']=='active' and d['state']['SubState']=='exited'
                   and d['state']['Result']=='success' and d['state']['ExecMainStatus']=='0' for d in data['decisions'])
        assert all(d['accepted']==(d['expected'] if complete else True) for d in data['decisions'])
        assert all((d['output']['sha256']==d['expectedSha256'])==d['expected'] for d in data['decisions'])
    elif kind=='correlation':
        assert len(data['decisions'])==3 and {d['case'] for d in data['decisions']}=={'current','historical','unrelated'}
        assert all(len(d['expectedRows'])==1 and len(d['selectedRows'])==(1 if complete else 3) for d in data['decisions'])
        assert len({d['invocation'] for d in data['decisions']})==3
        assert sum(c['case']=='actual operator retest restart' for c in data['commands'])==1
    else:
        assert len(data['decisions'])==4 and {d['expected'] for d in data['decisions']}=={'waiting','overdue','complete','failed'}
        assert len(data['actualManagedProcesses'])==3
        for d in data['decisions']:
            if d['expected'] in ['waiting','overdue']:
                assert int(d['state']['MainPID'])>0 and d['state']['ActiveState']=='activating'
                start=next(e for e in d['events'] if e['event']=='start')
                assert (d['nowMonotonicNs']-start['monotonicNs']>=d['budgetNs'])==(d['expected']=='overdue')
            if d['expected']=='failed':
                assert d['state']['ActiveState']=='failed' and d['state']['Result']=='exit-code' and d['state']['ExecMainStatus']=='7'


def exercise(pack,profile,work):
    index=PACKS.index(pack)
    kind=['output','correlation','progress'][index]
    role=work/(str(index)+'-'+profile+' quoted role')
    shutil.copytree(ROOT/pack/('starter' if profile=='completed' else profile),role)
    if profile=='completed':
        completed(role,REPAIRS[pack])
    before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in role.iterdir() if p.is_file()}
    parent=work/(str(index)+'-'+profile+' quoted parent')
    parent.mkdir(mode=0o700)
    count=len(ROWS)
    complete=profile!='starter'
    for reverse in [False,True]:
        command=['bash',str(role/'task.sh'),str(parent)]+(['--reverse'] if reverse else [])
        data=invoke('actual reversed studio' if reverse else 'actual ordinary studio',command,work,0 if complete else 1)
        check(data,kind,complete)
        assert data['reverse']==reverse and not any(parent.iterdir())
    data=invoke('actual live user-unit interruption',
                ['bash',str(role/'task.sh'),str(parent),'--hold-seconds','15'],work,130,interrupt_parent=parent)
    check(data,kind,complete,True)
    assert not any(parent.iterdir())
    data=invoke('actual studio recovery retest',['bash',str(role/'task.sh'),str(parent)],work,0 if complete else 1)
    check(data,kind,complete)
    missing=work/'missing-parent'
    assert not missing.exists()
    invoke('missing parent refusal',['bash',str(role/'task.sh'),str(missing)],work,2)
    sentinel=parent/'keep.txt'
    sentinel.write_bytes(b'owned input preserved\n')
    invoke('nonempty parent refusal',['bash',str(role/'task.sh'),str(parent)],work,2)
    assert sentinel.read_bytes()==b'owned input preserved\n'
    sentinel.unlink()
    link=work/(str(index)+'-'+profile+' parent-link')
    link.symlink_to(parent,target_is_directory=True)
    invoke('symlink parent refusal',['bash',str(role/'task.sh'),str(link)],work,2)
    assert link.is_symlink() and not any(parent.iterdir())
    link.unlink()
    invoke('invalid hold refusal',['bash',str(role/'task.sh'),str(parent),'--hold-seconds','16'],work,2)
    assert not any(parent.iterdir()) and (work/'outside-sentinel').read_bytes()==b'outside unchanged\n'
    assert before=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in role.iterdir() if p.is_file()}
    PROFILES.append({'pack':pack,'profile':profile,'kind':kind,'passed':True,'inputsUnchanged':True,
                     'ownedResourcesRemoved':True,'outsideSentinelPreserved':True,'actualCases':len(ROWS)-count,
                     'learnerWorksheetCompletionInferred':False})


def check_gate_publication(work):
    """Check complete/private publication, collision refusal and failure cleanup."""
    records=[]
    for index,(pack,role) in enumerate((pack,role) for pack in PACKS for role in ['starter','solution']):
        source=ROOT/pack/role/'studio_observer.py'
        spec=importlib.util.spec_from_file_location('observer_gate_'+str(index),source)
        module=importlib.util.module_from_spec(spec)
        sys.dont_write_bytecode=True
        spec.loader.exec_module(module)
        directory=work/('publication-'+str(index));directory.mkdir(mode=0o700)
        token='new-complete-private-permit-'+str(index)
        gate=directory/'permit.marker'
        replace=os.replace
        publications=[]
        def observed_replace(staging,destination,expected_gate=gate,expected_token=token,prior_replace=replace,observations=publications):
            assert destination==expected_gate and not expected_gate.exists()
            assert staging.read_bytes()==(expected_token+'\n').encode()
            assert stat.S_IMODE(staging.stat().st_mode)==0o600
            observations.append({'destinationWasAbsent':True,'completeBeforePublication':True,'mode':'0o600'})
            return prior_replace(staging,destination)
        with mock.patch.object(module.os,'replace',side_effect=observed_replace):
            module.publish_gate(gate,token)
        assert len(publications)==1 and gate.read_bytes()==(token+'\n').encode()
        assert stat.S_IMODE(gate.stat().st_mode)==0o600 and not gate.with_name(gate.name+'.pending').exists()
        records.append({'pack':pack,'role':role,'case':'complete-private-publication','evidence':publications[0]})
        gate.unlink()
        staging=gate.with_name(gate.name+'.pending');staging.write_bytes(b'existing sentinel\n')
        try:
            module.publish_gate(gate,token)
        except FileExistsError:
            pass
        else:
            raise AssertionError('preexisting staging file was overwritten')
        assert staging.read_bytes()==b'existing sentinel\n' and not gate.exists()
        records.append({'pack':pack,'role':role,'case':'existing-staging-refused','sentinelUnchanged':True})
        staging.unlink()
        with mock.patch.object(module.os,'replace',side_effect=OSError('controlled publication refusal')):
            try:
                module.publish_gate(gate,token)
            except OSError as error:
                assert str(error)=='controlled publication refusal'
            else:
                raise AssertionError('publication failure was not reported')
        assert not gate.exists() and not staging.exists()
        records.append({'pack':pack,'role':role,'case':'publication-failure-cleanup','privateTemporaryRemoved':True})
    assert len(records)==18
    return records


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proof',type=Path,required=True)
    parser.add_argument('--gate-only',action='store_true',help='Check private atomic publication only; not native manager acceptance')
    args=parser.parse_args()
    args.proof.parent.mkdir(parents=True,exist_ok=True)
    before=hashes()
    if args.gate_only:
        with tempfile.TemporaryDirectory(prefix='linux-observation-gate-') as directory:
            gate_records=check_gate_publication(Path(directory))
        assert not Path(directory).exists() and hashes()==before
        result={'gateOnlyPassed':True,'nativePassed':False,'copies':6,'cases':18,
                'sourceUnchanged':True,'atomicGatePublication':gate_records}
        args.proof.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({k:v for k,v in result.items() if k!='atomicGatePublication'}))
        return
    gate_records=[]
    error=None
    try:
        assert platform.system()=='Linux' and os.geteuid()>0
        with tempfile.TemporaryDirectory(prefix='linux-observability-native-') as directory:
            work=Path(directory)
            gate_records=check_gate_publication(work)
            (work/'outside-sentinel').write_bytes(b'outside unchanged\n')
            for pack in PACKS:
                for profile in ['starter','solution','completed']:
                    exercise(pack,profile,work)
                    assert hashes()==before
        assert not work.exists() and len(PROFILES)==9 and len(ROWS)==72
    except BaseException:
        LOGGER.exception('Native studio acceptance failed; retaining raw evidence')
        error=traceback.format_exc()
    reports=[json.loads(r['stdout']) for r in ROWS if r['stdout']]
    units=[u for r in reports for u in r['units']]
    invocations={e['invocation'] for u in units for e in u['events']}
    proof={'nativePassed':error is None,'platform':platform.system(),'uid':os.geteuid(),
           'sourceHashes':before,'sourceUnchanged':hashes()==before,'profiles':PROFILES,
           'actualCases':len(ROWS),'loggedOuterLifecycles':len(EVENTS)//2,
           'actualNativeCliLifecycles':sum(len(r['commands']) for r in reports),
           'actualOwnedTimers':len(units),'actualServiceInvocations':len(invocations),
           'actualWorkerEvents':sum(len(u['events']) for u in units),
           'actualPolicyDecisions':sum(len(r['decisions']) for r in reports),
           'actualManagedProcessObservations':sum(len(r['actualManagedProcesses']) for r in reports),
           'actualObservationGates':sum(len(u['activationEvidence']) for u in units),
           'actualScheduledGateObservations':sum(a['kind']=='timer' for u in units for a in u['activationEvidence']),
           'actualOperatorRetests':sum(a['kind']=='operator-retest' for u in units for a in u['activationEvidence']),
           'atomicGatePublication':gate_records,'atomicGateCopies':6,'atomicGateCases':len(gate_records),
           'error':error,'learnerWorksheetCompletionInferred':False}
    args.proof.write_text(json.dumps(proof,indent=2)+'\n')
    args.proof.with_suffix('.observations.json').write_text(json.dumps(ROWS,indent=2)+'\n')
    args.proof.with_suffix('.processes.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in EVENTS))
    if error:
        raise AssertionError(error)
    print(json.dumps({k:v for k,v in proof.items() if k not in ['profiles','sourceHashes']}))


if __name__=='__main__':
    main()
