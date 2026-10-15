"""Run only uniquely named actual user units and preserve their observations."""
import argparse
import base64
import contextlib
import hashlib
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
import uuid
from pathlib import Path

SOURCE = Path(__file__).resolve().parent
LOGGER = logging.getLogger(__name__)
STOP = False
ENVIRONMENT = {**os.environ, 'LC_ALL': 'C', 'SYSTEMD_COLORS': '0', 'SYSTEMD_PAGER': 'cat'}
PROPERTIES = 'LoadState,ActiveState,SubState,MainPID,ExecMainStatus,Result,InvocationID,LastTriggerUSec'


def stop_requested(signum, frame):
    global STOP
    STOP = True


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source_hashes():
    return {p.name: sha(p.read_bytes()) for p in SOURCE.iterdir() if p.is_file()}


def run(report, case, command):
    child = subprocess.Popen(command, cwd=report['ownedCase'], env=ENVIRONMENT,
                             stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, start_new_session=True)
    entry = {'parentPid': os.getpid(), 'pid': child.pid, 'case': case,
             'command': command, 'cwd': report['ownedCase'], 'startTime': time.time(),
             'timeoutSeconds': 6}
    cleanup = 'owned CLI process exited and reaped'
    try:
        out, err = child.communicate(timeout=6)
    except BaseException:
        cleanup = 'owned CLI process group terminated and reaped'
        with contextlib.suppress(ProcessLookupError):
            os.killpg(child.pid, signal.SIGTERM)
        try:
            out, err = child.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            out, err = child.communicate()
        raise
    finally:
        entry.update(endTime=time.time(), status=child.returncode, cleanup=cleanup)
        report['commands'].append(entry)
    entry.update(stdout=out.decode(), stderr=err.decode())
    return entry


def state(report, unit):
    row = run(report, 'actual manager state', ['systemctl', '--user', 'show', unit, '--property='+PROPERTIES])
    result = dict(line.split('=', 1) for line in row['stdout'].splitlines() if '=' in line)
    if 'LoadState' not in result:
        raise RuntimeError('the user manager cannot inspect the owned unit: '+row['stderr'])
    return result


def wait_for(condition, timeout=7):
    deadline = time.monotonic()+timeout
    while True:
        value = condition()
        if value:
            return value
        if STOP:
            raise InterruptedError('the owned observation was interrupted')
        if time.monotonic() >= deadline:
            raise TimeoutError('the actual unit did not reach the declared observation gate')
        time.sleep(0.02)


def events(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def file_record(path):
    data = path.read_bytes()
    info = path.stat()
    return {'path': str(path), 'sha256': sha(data), 'bytesBase64': base64.b64encode(data).decode(),
            'mode': oct(stat.S_IMODE(info.st_mode)), 'uid': info.st_uid}


def decoded_worker_rows(rows):
    result = []
    for row in rows:
        try:
            payload = json.loads(row.get('MESSAGE', ''))
        except (ValueError, TypeError):
            continue
        if isinstance(payload, dict) and payload.get('event') in ['start', 'end'] and 'invocation' in payload:
            result.append((row, payload))
    return result


def journal(report, units, minimum):
    command = ['journalctl', '--user', '--no-pager', '-o', 'json', '-n', '100']
    for unit in units:
        command.extend(['-u', unit])

    def capture():
        row = run(report, 'actual scoped journal', command)
        if row['status']:
            raise RuntimeError('the own-user journal is unavailable: '+row['stderr'])
        rows = [json.loads(line) for line in row['stdout'].splitlines() if line.startswith('{')]
        return rows if len(decoded_worker_rows(rows)) >= minimum else None
    return wait_for(capture)


class Unit:
    def __init__(self, report, case, mode, value, units):
        self.report = report
        self.name = 'classes-observe-'+uuid.uuid4().hex
        self.service, self.timer = self.name+'.service', self.name+'.timer'
        self.root = Path(report['ownedCase'])/self.name
        self.root.mkdir(mode=0o700)
        self.config = self.root/'config.json'
        self.output = self.root/'output.json'
        self.events = self.root/'events.jsonl'
        self.case = case
        self.output.write_text('{"run":"earlier-run","value":"earlier-value"}\n')
        self.output.chmod(0o600)
        self.before = file_record(self.output)
        self.configure(mode, value)
        self.registered = False
        self.observations = []
        units.append(self)

    def configure(self, mode, value):
        self.job = {'run': uuid.uuid4().hex, 'mode': mode, 'value': value}
        self.config.write_text(json.dumps(self.job, sort_keys=True)+'\n')
        self.config.chmod(0o600)

    def start(self):
        assert all(state(self.report, unit)['LoadState']=='not-found' for unit in [self.service, self.timer])
        command = ['systemd-run', '--user', '--quiet', '--unit='+self.name,
                   '--property=Type=oneshot', '--property=RemainAfterExit=yes',
                   '--property=TimeoutStartSec=30s', '--property=TimeoutStopSec=1s',
                   '--on-active=200ms', '--timer-property=AccuracySec=1ms',
                   '--timer-property=RandomizedDelaySec=0', '--timer-property=RemainAfterElapse=yes',
                   '--', sys.executable, str(SOURCE/'studio_worker.py'),
                   str(self.config), str(self.output), str(self.events)]
        self.registered = True
        row = run(self.report, 'create actual owned user timer', command)
        if row['status']:
            raise RuntimeError('the owned user timer could not be created: '+row['stderr'])
        return self.finish_or_start()

    def finish_or_start(self):
        started = wait_for(lambda: [e for e in events(self.events) if e['event']=='start' and e['run']==self.job['run']])
        invocation = started[0]['invocation']
        assert re.fullmatch(r'[0-9a-f]{32}', invocation)
        if self.job['mode'] == 'hang':
            current = wait_for(lambda: self.running_state(invocation))
            pid = int(current['MainPID'])
            assert str(SOURCE/'studio_worker.py').encode() in Path('/proc', str(pid), 'cmdline').read_bytes()
            info = Path('/proc', str(pid), 'status').read_text()
            uids = next(line.split()[1:] for line in info.splitlines() if line.startswith('Uid:'))
            assert all(int(uid)==os.geteuid() for uid in uids)
            self.report['actualManagedProcesses'].append({'pid': pid, 'uid': os.geteuid(),
                'unit': self.service, 'invocation': invocation, 'cmdlineBase64': base64.b64encode(Path('/proc', str(pid), 'cmdline').read_bytes()).decode()})
        else:
            current = wait_for(lambda: self.finished_state(invocation))
        return self.capture(current)

    def running_state(self, invocation):
        value = state(self.report, self.service)
        return value if value.get('InvocationID')==invocation and int(value.get('MainPID','0'))>0 else None

    def finished_state(self, invocation):
        value = state(self.report, self.service)
        return value if value.get('InvocationID')==invocation and value.get('ActiveState') in ['active','failed'] and value.get('SubState') in ['exited','failed'] else None

    def capture(self, current=None):
        current = current or state(self.report, self.service)
        observed = events(self.events)
        self.observations.append({'state': current, 'timer': state(self.report, self.timer),
            'events': observed, 'output': file_record(self.output), 'job': self.job.copy(),
            'nowMonotonicNs': time.monotonic_ns(),
            'journalRows': journal(self.report,[self.service],len(observed))})
        return self.observations[-1]

    def restart(self, mode, value):
        old = self.observations[-1]['state']['InvocationID']
        self.configure(mode, value)
        row = run(self.report, 'actual operator retest restart', ['systemctl','--user','restart',self.service])
        assert row['status']==0, row
        fresh = self.finish_or_start()
        assert fresh['state']['InvocationID']!=old
        return fresh

    def cleanup(self):
        if not self.registered:
            return
        before = {unit:state(self.report,unit) for unit in [self.timer,self.service]}
        loaded = [unit for unit,value in before.items() if value['LoadState']!='not-found']
        if loaded:
            row = run(self.report, 'stop exact owned units', ['systemctl','--user','stop',*loaded])
            assert row['status']==0, row
        current = state(self.report, self.service)
        if current.get('ActiveState')=='failed':
            row = run(self.report, 'reset exact owned failed unit', ['systemctl','--user','reset-failed',self.service])
            assert row['status']==0, row
        # Cleanup continues even when the user requested interruption.
        deadline = time.monotonic()+5
        while True:
            states = {unit:state(self.report, unit) for unit in [self.timer,self.service]}
            if all(s['LoadState']=='not-found' for s in states.values()):
                break
            if time.monotonic()>=deadline:
                raise RuntimeError('an owned transient unit did not unload')
            time.sleep(0.02)
        observed = events(self.events)
        for pid in {e['pid'] for e in observed}:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                continue
            raise RuntimeError('the owned managed worker is still present')
        self.report['units'].append({'case':self.case, 'service':self.service, 'timer':self.timer,
            'beforeOutput':self.before, 'observations':self.observations, 'events':observed,
            'statesAfterCleanup':states, 'ownedWorkerPidsGone':True})


def exercise(parent, policy, kind, reverse, hold, budget):
    before = source_hashes()
    case = Path(tempfile.mkdtemp(prefix='observability-', dir=parent))
    report = {'kind':kind, 'reverse':reverse, 'uid':os.geteuid(), 'ownedCase':str(case),
              'sourceHashes':before, 'commands':[], 'units':[], 'decisions':[],
              'actualManagedProcesses':[], 'interrupted':False, 'failure':None,
              'learnerWorksheetCompletionInferred':False,
              'bootId':Path('/proc/sys/kernel/random/boot_id').read_text().strip().replace('-','')}
    units = []
    ready = parent/'ready.json'
    status = 2
    try:
        probe = run(report, 'actual ordinary user manager availability', ['systemctl','--user','show','--property=Version','--value'])
        if probe['status'] or not probe['stdout'].strip():
            raise RuntimeError('an available own-user manager is required: '+probe['stderr'])
        if hold:
            paused = Unit(report, 'interrupted live worker', 'hang', 'held fixture', units)
            paused.start()
            ready.write_text(json.dumps({'pid':os.getpid(),'unit':paused.service,'workerPid':paused.observations[-1]['state']['MainPID']})+'\n')
            until = time.monotonic()+hold
            while time.monotonic()<until and not STOP:
                time.sleep(0.02)
            if STOP:
                raise InterruptedError('the owned live worker observation was interrupted')
            paused.cleanup()
            paused.registered = False
        if kind=='output':
            modes = ['good','incomplete'] if not reverse else ['incomplete','good']
            for mode in modes:
                unit = Unit(report,mode,mode,'changed payload' if reverse else 'first payload',units)
                observed = unit.start()
                wanted = sha((json.dumps({'run':observed['job']['run'],'value':observed['job']['value']},sort_keys=True)+'\n').encode())
                actual = policy(observed['state'],unit.output,wanted)
                assert isinstance(actual,bool)
                report['decisions'].append({'case':mode,'state':observed['state'],
                    'output':observed['output'],'expectedSha256':wanted,'accepted':actual,
                    'expected':mode=='good','matchedTarget':actual==(mode=='good')})
        elif kind=='correlation':
            unit = Unit(report,'historical scheduled run','old-error','old payload',units)
            old = unit.start()
            fresh = unit.restart('good','changed payload' if reverse else 'first payload')
            other = Unit(report,'unrelated scheduled run','old-error','unrelated payload',units)
            unrelated = other.start()
            rows = journal(report,[unit.service,other.service],6)
            report['journalRows'] = rows
            anchors = [('current',fresh),('historical',old),('unrelated',unrelated)]
            if reverse:
                anchors.reverse()
            for label,observation in anchors:
                invocation = observation['state']['InvocationID']
                actual = policy(rows,invocation)
                expected = [r for r,payload in decoded_worker_rows(rows) if payload['event']=='end' and payload['invocation']==invocation]
                assert isinstance(actual,list) and len(expected)==1
                report['decisions'].append({'case':label,'invocation':invocation,'selectedRows':actual,
                    'expectedRows':expected,'matchedTarget':actual==expected})
        else:
            modes = ['good','hang','fail'] if not reverse else ['fail','hang','good']
            for mode in modes:
                unit = Unit(report,mode,mode,'deadline fixture',units)
                observed = unit.start()
                if mode=='hang':
                    active = [e for e in observed['events'] if e['invocation']==observed['state']['InvocationID']]
                    age = observed['nowMonotonicNs']-active[0]['monotonicNs']
                    assert age < budget, 'the early sample missed its budget; repeat in a less delayed lab'
                    snapshots = [(observed,'waiting')]
                    while time.monotonic_ns()-active[0]['monotonicNs']<budget+100000000:
                        if STOP:
                            raise InterruptedError('the owned progress observation was interrupted')
                        time.sleep(0.02)
                    snapshots.append((unit.capture(),'overdue'))
                else:
                    snapshots = [(observed,'complete' if mode=='good' else 'failed')]
                for observation,expected in snapshots:
                    invocation = observation['state']['InvocationID']
                    selected = [e for e in observation['events'] if e['invocation']==invocation]
                    actual = policy(observation['state'],selected,observation['nowMonotonicNs'],budget)
                    report['decisions'].append({'case':mode+' '+expected,'state':observation['state'],
                        'events':selected,'nowMonotonicNs':observation['nowMonotonicNs'],'budgetNs':budget,
                        'classification':actual,'expected':expected,'matchedTarget':actual==expected})
        report['targetBehaviorObserved'] = all(d['matchedTarget'] for d in report['decisions'])
        status = 0 if report['targetBehaviorObserved'] else 1
    except InterruptedError:
        report['interrupted'] = True
        status = 130
    except BaseException as error:
        LOGGER.exception('Observability equipment failed; retaining actual evidence')
        report['failure'] = type(error).__name__+': '+str(error)
        status = 2
    finally:
        cleanup_errors = []
        for unit in reversed(units):
            try:
                unit.cleanup()
            except (OSError, RuntimeError, ValueError, AssertionError, subprocess.SubprocessError) as error:
                LOGGER.exception('An owned unit cleanup failed; continuing the other owned cleanups')
                cleanup_errors.append(str(error))
        report['cleanupErrors'] = cleanup_errors
        if cleanup_errors:
            report['failure'] = 'owned cleanup failed: '+'; '.join(cleanup_errors)
            status = 2
        else:
            ready.unlink(missing_ok=True)
            shutil.rmtree(case)
        report['sourceUnchanged'] = source_hashes()==before
        report['ownedCaseRemoved'] = not case.exists()
        report['workspaceEmpty'] = not any(parent.iterdir())
    if STOP:
        report['interrupted'] = True
        if report['failure'] is None:
            status = 130
    assert report['sourceUnchanged']
    if not report['cleanupErrors']:
        assert report['ownedCaseRemoved'] and report['workspaceEmpty']
    print(json.dumps(report,sort_keys=True),flush=True)
    return status


def main(policy, kind):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('parent',type=Path)
    parser.add_argument('--reverse',action='store_true')
    parser.add_argument('--hold-seconds',type=int,default=0)
    parser.add_argument('--budget-seconds',type=float,choices=[0.8,1.2,2.0],default=1.2)
    args = parser.parse_args()
    parent = args.parent
    if platform.system()!='Linux' or os.geteuid()==0:
        parser.error('use an ordinary account in the owned Linux lab with an available user manager')
    if parent.is_symlink() or not parent.is_dir() or parent.stat().st_uid!=os.geteuid() or any(parent.iterdir()):
        parser.error('provide an existing empty owned nonsymlink parent')
    if not 0<=args.hold_seconds<=15:
        parser.error('hold must be from 0 to 15 seconds')
    if not all(shutil.which(tool) for tool in ['systemctl','systemd-run','journalctl']):
        parser.error('systemctl, systemd-run and journalctl are required')
    signal.signal(signal.SIGINT,stop_requested)
    signal.signal(signal.SIGTERM,stop_requested)
    return exercise(parent.resolve(),policy,kind,args.reverse,args.hold_seconds,int(args.budget_seconds*1000000000))
