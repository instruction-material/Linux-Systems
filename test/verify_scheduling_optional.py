"""Accept actual calendar parsing and short, owned, transient user timers."""
import argparse
import datetime
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

ROOT=Path(__file__).resolve().parents[1]
PACKS=['LS-17-unit-8-scheduling-and-automation-supplemental-2','LS-18-unit-8-scheduling-and-automation-supplemental-3']
parser=argparse.ArgumentParser()
parser.add_argument('--proof',type=Path,required=True)
args=parser.parse_args()
assert platform.system()=='Linux' and os.geteuid()>0
assert all(shutil.which(n) for n in ['bash','python3','systemd-analyze','systemd-run','systemctl'])
args.proof=args.proof.resolve()
args.proof.parent.mkdir(parents=True,exist_ok=True)
environment=dict(os.environ,LC_ALL='C',PYTHONDONTWRITEBYTECODE='1',BASH_ENV='/dev/null')
observations,events,profiles=[],[],[]
wall_before,mono_before=time.time(),time.monotonic()
def digest(raw):
    return hashlib.sha256(raw).hexdigest()
def hashes():
    return {str(f.relative_to(ROOT)):digest(f.read_bytes()) for p in PACKS for f in sorted((ROOT/p).rglob('*')) if f.is_file()}
def save_observations():
    args.proof.with_suffix('.observations.json').write_text(json.dumps(observations,indent=2)+'\n')
    args.proof.with_suffix('.processes.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
def run(case,command,cwd,expected=None,env=None,interrupt_workspace=None):
    child=subprocess.Popen([str(x) for x in command],cwd=cwd,env=environment if env is None else env,
                           stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
    entry={'parentTaskId':os.environ.get('CLASSES_FAMILY_TASK_ID','linux-scheduling-source'),'parentPid':os.getpid(),
           'pid':child.pid,'cwd':str(cwd),'command':[str(x) for x in command],'startTime':time.time(),'timeoutSeconds':30}
    events.append(dict(entry,event='start'))
    cleanup='owned process exited and reaped'
    try:
        if interrupt_workspace is not None:
            deadline=time.monotonic()+8
            ready=interrupt_workspace/'ready.json'
            while True:
                assert child.poll() is None and time.monotonic()<deadline
                if ready.exists():
                    data=json.loads(ready.read_text())
                    worker=Path(data['workerEvents'])
                    if worker.exists() and worker.read_text().strip():break
                time.sleep(0.01)
            os.kill(child.pid,signal.SIGINT)
        out,err=child.communicate(timeout=30)
    except BaseException:
        cleanup='owned process group terminated after failure or timeout'
        if child.poll() is None:os.killpg(child.pid,signal.SIGTERM)
        try:child.communicate(timeout=8)
        except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.communicate()
        raise
    finally:
        events.append(dict(entry,event='end',endTime=time.time(),exitCode=child.returncode,childProcessGroupCleanup=cleanup))
        save_observations()
    try:os.killpg(child.pid,0)
    except ProcessLookupError:pass
    else:
        os.killpg(child.pid,signal.SIGKILL)
        raise AssertionError('The caller left an owned subprocess running')
    row={'case':case,'command':[str(x) for x in command],'cwd':str(cwd),'status':child.returncode,'stdout':out.decode(),'stderr':err.decode()}
    observations.append(row)
    save_observations()
    if expected is not None:assert row['status']==expected,row
    return row
def dates(report):
    return re.findall(r'(?:Next elapse|Iter(?:ation|\.) #\d+):\s+\S+ (\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}) UTC',report['tool']['stdout'])
def calendar_report(row,base,expression,complete):
    assert not row['stderr']
    report=json.loads(row['stdout'])
    assert report['requestedBase']==base and report['expression']==expression and report['baseApplied']==complete
    assert not report['systemClockChanged'] and not report['schedulerInstalled'] and not report['learnerWorksheetCompletionInferred']
    tool=report['tool']
    assert tool['pid']>0 and tool['parentPid']>0 and tool['timeoutSeconds']==5
    assert tool['endTime']>=tool['startTime'] and not tool['timedOut']
    assert tool['childProcessGroupCleanup']=='owned process exited and reaped'
    assert tool['command'][1:3]==['calendar','--iterations=3'] and tool['command'][-2:]==['--',expression]
    assert ('--base-time='+base in tool['command'])==complete
    assert row['status']==tool['returnCode']
    assert abs(datetime.datetime.fromisoformat(report['observedAt']).timestamp()-time.time())<30
    return report
def timer_report(row,workspace,complete,interrupted=False):
    assert not row['stderr']
    data=json.loads(row['stdout'])
    assert data['uid']==os.getuid() and data['workspace']==str(workspace.resolve())
    assert data['remainAfterExit']==('no' if complete else 'yes')
    assert data['interrupted']==interrupted and data['observationsCompleted']==(not interrupted)
    assert data['failure'] is None and data['ownedUnitsUnloaded'] and data['workerPidsGone'] and data['workspaceEmpty']
    assert not data['learnerWorksheetCompletionInferred'] and data['nonoverlapObserved']
    assert not list(workspace.iterdir())
    assert len(data['statesAfterCleanup'])==2 and all(s['LoadState']=='not-found' for s in data['statesAfterCleanup'].values())
    assert data['unit'].startswith('classes-scheduling-')
    assert all(c['pid']>0 and c['timeoutSeconds']==5 and c['endTime']>=c['startTime'] and c['childProcessGroupCleanup']=='owned process exited and reaped' for c in data['commands'])
    create=[c for c in data['commands'] if Path(c['command'][0]).name=='systemd-run']
    assert len(create)==1 and create[0]['returnCode']==0
    assert '--user' in create[0]['command'] and '--property=RemainAfterExit='+data['remainAfterExit'] in create[0]['command']
    assert '--on-unit-inactive=350ms' in create[0]['command'] and '--timer-property=AccuracySec=10ms' in create[0]['command']
    starts={r['pid']:r for r in data['workerEvents'] if r['event']=='start'}
    ends={r['pid']:r for r in data['workerEvents'] if r['event']=='end'}
    assert starts and set(ends)<=set(starts) and data['completedActivations']==len(ends)
    for pid,start in starts.items():
        assert start['uid']==os.getuid()
        if pid in ends:assert ends[pid]['monotonic']>=start['monotonic'] and ends[pid]['uid']==os.getuid()
        try:os.kill(pid,0)
        except ProcessLookupError:pass
        else:raise AssertionError('The user timer left a worker alive')
    if interrupted:assert row['status']==130
    elif complete:assert row['status']==0 and len(ends)>=2
    else:
        assert row['status']==1 and len(ends)==1
        assert data['statesBeforeCleanup'][data['unit']+'.service']['ActiveState']=='active'
        assert data['statesBeforeCleanup'][data['unit']+'.service']['SubState']=='exited'
    return data
before=hashes()
assert len(before)==16
with tempfile.TemporaryDirectory(prefix='linux-scheduling-') as tmp:
    work=Path(tmp)
    outside=work/'outside-sentinel';outside.write_bytes(b'outside stays unchanged\n');outside_hash=digest(outside.read_bytes())
    caller=work/'another caller';caller.mkdir()
    row=run('actual user manager version',['systemctl','--user','show','--property=Version','--value'],work,0)
    assert row['stdout'].strip() and not row['stderr']
    for index,pack in enumerate(PACKS):
        for role in ['starter','solution','completed']:
            initial=len(observations)
            target=work/(str(index)+'-'+role+' quoted workspace')
            shutil.copytree(ROOT/pack/('starter' if role=='completed' else role),target)
            task=target/'task.sh'
            if role=='completed':
                source=target/('calendar_observer.py' if index==0 else 'timer_observer.py')
                old,new=('include_base = False','include_base = True') if index==0 else ("remain_after_exit = 'yes'","remain_after_exit = 'no'")
                text=source.read_text();assert text.count(old)==1;source.write_text(text.replace(old,new))
            copied={str(f.relative_to(target)):digest(f.read_bytes()) for f in target.rglob('*') if f.is_file()}
            complete=role!='starter'
            if index==0:
                cases=[('anchored daily','2000-01-01 11:59:59 UTC','*-*-* 12:00:00 UTC',[('2000-01-01','12:00:00'),('2000-01-02','12:00:00'),('2000-01-03','12:00:00')]),
                       ('anchored weekday','2000-01-07 09:00:01 UTC','Mon..Fri *-*-* 09:00:00 UTC',[('2000-01-10','09:00:00'),('2000-01-11','09:00:00'),('2000-01-12','09:00:00')]),
                       ('anchored leap days','2000-02-28 13:00:00 UTC','*-02-29 12:00:00 UTC',[('2000-02-29','12:00:00'),('2004-02-29','12:00:00'),('2008-02-29','12:00:00')])]
                for label,base,expression,expected_dates in cases:
                    row=run(label,['bash',task,base,expression],caller,0)
                    report=calendar_report(row,base,expression,complete)
                    actual=dates(report);assert len(actual)==3,{'case':label,'actual':actual,'rawToolOutput':report['tool']['stdout']}
                    if complete:assert actual==expected_dates
                    else:assert actual!=expected_dates and all(int(x[0][:4])>=2026 for x in actual)
                base,expression=cases[0][1:3]
                row=run('explicit UTC with changed caller timezone',['bash',task,base,expression],target,0,env=dict(environment,TZ='Pacific/Honolulu'))
                report=calendar_report(row,base,expression,complete)
                if complete:assert dates(report)==cases[0][3]
                row=run('actual invalid calendar',['bash',task,base,'not-a-calendar'],target)
                report=calendar_report(row,base,'not-a-calendar',complete);assert row['status']!=0 and report['tool']['stderr']
                row=run('actual invalid anchor',['bash',task,'not-a-timestamp',expression],target)
                report=calendar_report(row,'not-a-timestamp',expression,complete)
                if complete:assert row['status']!=0 and report['tool']['stderr']
                else:assert row['status']==0 and not report['tool']['stderr']
                for case in ['quoted absolute caller recovery','repeat same calendar anchor']:
                    row=run(case,['bash',task,base,expression],caller,0)
                    report=calendar_report(row,base,expression,complete)
                    if complete:assert dates(report)==cases[0][3]
                for values in [[],[base],[base,expression,'extra']]:
                    row=run('invalid calendar argument count',['bash',task,*values],target,2)
                    assert not row['stdout'] and row['stderr']
                assert len(observations)-initial==11
            else:
                lab=work/(role+' timer lab');lab.mkdir()
                for profile in ['short','long']:
                    row=run('actual repeating timer '+profile,['bash',task,lab,profile],caller,0 if complete else 1)
                    report=timer_report(row,lab,complete);assert report['profile']==profile
                    assert report['workerDuration']==('0.10' if profile=='short' else '0.45')
                row=run('actual foreground interruption',['bash',task,lab,'long','--seconds','8'],caller,130,interrupt_workspace=lab)
                timer_report(row,lab,complete,interrupted=True)
                row=run('missing timer workspace',['bash',task,work/'absent'],caller,2);assert not row['stdout'] and row['stderr']
                sentinel=lab/'retained';sentinel.write_bytes(b'retain me\n')
                row=run('nonempty timer workspace retained',['bash',task,lab],caller,2);assert sentinel.read_bytes()==b'retain me\n' and not row['stdout'] and row['stderr'];sentinel.unlink()
                link=work/(role+' linked lab');link.symlink_to(lab,target_is_directory=True)
                row=run('symlink timer workspace rejected',['bash',task,link],caller,2);assert link.is_symlink() and not row['stdout'] and row['stderr']
                for case,values in [('invalid timer profile',[lab,'invalid']),('missing timer arguments',[]),('invalid timer observation window',[lab,'--seconds','99'])]:
                    row=run(case,['bash',task,*values],caller,2);assert not row['stdout'] and row['stderr']
                lab.chmod(0o500)
                try:
                    row=run('actual timer workspace creation denial',['bash',task,lab],caller,2)
                    report=json.loads(row['stdout']);assert 'Permission denied' in report['failure'] and report['workspaceEmpty'] and report['workerPidsGone'] and report['ownedUnitsUnloaded']
                finally:lab.chmod(0o700)
                assert not list(lab.iterdir()) and len(observations)-initial==10
            assert copied=={str(f.relative_to(target)):digest(f.read_bytes()) for f in target.rglob('*') if f.is_file()}
            assert digest(outside.read_bytes())==outside_hash
            profiles.append({'pack':pack,'profile':role,'actualCases':len(observations)-initial,'passed':True,
                             'inputsUnchanged':True,'outsideSentinelPreserved':True,'ownedResourcesRemoved':True,
                             'starterIntentionallyIncomplete':role=='starter'})
    assert hashes()==before and len(profiles)==6
assert not work.exists() and len(observations)==64
assert abs((time.time()-wall_before)-(time.monotonic()-mono_before))<2
calendar_records=[json.loads(r['stdout'])['tool'] for r in observations if r['stdout'].startswith('{') and '"requestedBase"' in r['stdout']]
timer_records=[json.loads(r['stdout']) for r in observations if r['case'].startswith('actual repeating timer') or r['case']=='actual foreground interruption']
assert len(calendar_records)==24 and len(timer_records)==9
proof={'nativePassed':True,'unprivilegedUid':os.geteuid(),'sourceHashes':before,'sourceUnchanged':True,
       'profiles':profiles,'actualCases':64,'calendarToolLifecycles':24,'actualUserTimerLifecycles':9,
       'actualInterruptedTimerLifecycles':3,'loggedOuterLifecycles':len(events)//2,
       'actualWorkerEvents':sum(len(r['workerEvents']) for r in timer_records),
       'temporaryCasesRemoved':True,'systemClockProgressionPreserved':True}
assert proof['loggedOuterLifecycles']==64
args.proof.write_text(json.dumps(proof,indent=2)+'\n')
args.proof.with_suffix('.observations.json').write_text(json.dumps(observations,indent=2)+'\n')
args.proof.with_suffix('.processes.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
print(json.dumps({k:v for k,v in proof.items() if k!='sourceHashes'}))
