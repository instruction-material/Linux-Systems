"""Observe only fresh transient timer/service units in an owned user manager."""
import argparse
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('workspace', type=Path)
parser.add_argument('profile', nargs='?', choices=['short', 'long'], default='short')
parser.add_argument('--seconds', type=float, default=4)
args = parser.parse_args()
if platform.system() != 'Linux' or os.geteuid() == 0:
    parser.error('Use an ordinary account in an owned Linux lab with a user manager.')
if not 1 <= args.seconds <= 10:
    parser.error('Observation seconds must be between1 and10.')
workspace = args.workspace
if workspace.is_symlink() or not workspace.is_dir() or workspace.stat().st_uid != os.getuid() or list(workspace.iterdir()):
    parser.error('Use an empty owned nonsymlink workspace.')
workspace = workspace.resolve()
systemctl, systemd_run = shutil.which('systemctl'), shutil.which('systemd-run')
if not systemctl or not systemd_run:
    parser.error('The installed systemctl and systemd-run commands are required.')
environment = dict(os.environ, LC_ALL='C', SYSTEMD_COLORS='0', SYSTEMD_PAGER='cat')
commands = []
interrupted = False
def request_stop(signum, frame):
    global interrupted
    interrupted = True
signal.signal(signal.SIGINT, request_stop)
signal.signal(signal.SIGTERM, request_stop)
def run(command):
    child = subprocess.Popen(command, env=environment, stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    record = {'parentPid': os.getpid(), 'pid': child.pid, 'command': command,
              'startTime': time.time(), 'timeoutSeconds': 5}
    cleanup = 'owned process exited and reaped'
    try:
        out, err = child.communicate(timeout=5)
    except BaseException:
        cleanup = 'owned CLI process group terminated after failure or deadline'
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
        try:
            child.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.communicate()
        raise
    finally:
        record.update(endTime=time.time(), returnCode=child.returncode, childProcessGroupCleanup=cleanup)
        commands.append(record)
    record.update(stdout=out.decode(), stderr=err.decode())
    return record
def state(unit):
    row = run([systemctl, '--user', 'show', unit, '--property=LoadState', '--property=ActiveState', '--property=SubState'])
    values = dict(line.split('=', 1) for line in row['stdout'].splitlines() if '=' in line)
    if 'LoadState' not in values:
        raise RuntimeError('Cannot inspect the owned user unit: '+row['stderr'])
    return values
def gone(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False
probe = run([systemctl, '--user', 'show', '--property=Version', '--value'])
if probe['returnCode'] or not probe['stdout'].strip():
    parser.error('The user manager is unavailable: '+probe['stderr'])
# Allow a completed oneshot to become inactive before its next timer trigger.
remain_after_exit = 'no'
name = 'classes-scheduling-' + uuid.uuid4().hex
units = [name+'.timer', name+'.service']
if any(state(unit)['LoadState'] != 'not-found' for unit in units):
    parser.error('The generated unit name already exists; no unit was changed.')
worker = Path(__file__).resolve().with_name('timer_worker.py')
duration = '0.10' if args.profile == 'short' else '0.45'
private = None
records = []
states_before_cleanup = {}
states_after_cleanup = {}
ready = workspace/'ready.json'
created = False
failure = None
try:
    private = Path(tempfile.mkdtemp(prefix='timer-case-', dir=workspace))
    events = private/'worker.jsonl'
    command = [systemd_run, '--user', '--quiet', '--collect', '--unit='+name,
               '--property=Type=oneshot', '--property=RemainAfterExit='+remain_after_exit,
               '--property=TimeoutStartSec=3s', '--on-active=200ms', '--on-unit-inactive=350ms',
               '--timer-property=AccuracySec=10ms', '--timer-property=RandomizedDelaySec=0',
               '--', sys.executable, str(worker), str(events), duration]
    created = True
    row = run(command)
    if row['returnCode']:
        raise RuntimeError('Creating the owned timer failed: '+row['stderr'])
    ready.write_text(json.dumps({'unit': name, 'workerEvents': str(events)}))
    deadline = time.monotonic()+args.seconds
    while time.monotonic() < deadline and not interrupted:
        records = [json.loads(line) for line in events.read_text().splitlines()] if events.exists() else []
        if sum(r['event']=='end' for r in records) >= 3:
            break
        time.sleep(0.02)
    states_before_cleanup = {unit:state(unit) for unit in units}
except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
    failure = str(error)
finally:
    if created:
        stop = run([systemctl, '--user', 'stop', *units])
        deadline = time.monotonic()+3
        while True:
            states_after_cleanup = {unit:state(unit) for unit in units}
            if all(s['LoadState']=='not-found' for s in states_after_cleanup.values()):
                break
            if time.monotonic() >= deadline:
                raise RuntimeError('Owned transient units did not unload after stop.')
            time.sleep(0.05)
        if private is not None and (private/'worker.jsonl').exists():
            records = [json.loads(line) for line in (private/'worker.jsonl').read_text().splitlines()]
    worker_pids = {r['pid'] for r in records}
    if not all(gone(pid) for pid in worker_pids):
        raise RuntimeError('An owned timer worker is still running after stop.')
    if ready.exists():
        ready.unlink()
    if private is not None:
        shutil.rmtree(private)
starts = [r for r in records if r['event']=='start']
ends = [r for r in records if r['event']=='end']
completed = {r['pid']:r for r in ends}
nonoverlap = all(starts[i]['pid'] in completed and completed[starts[i]['pid']]['monotonic'] <= starts[i+1]['monotonic'] for i in range(len(starts)-1))
report = {'unit': name, 'uid': os.getuid(), 'workspace': str(workspace),
          'remainAfterExit': remain_after_exit, 'profile': args.profile, 'workerDuration': duration,
          'workerEvents': records, 'completedActivations': len(ends), 'workerPidsGone': True,
          'observationsCompleted': not interrupted and failure is None,
          'interrupted': interrupted, 'failure': failure, 'nonoverlapObserved': nonoverlap,
          'statesBeforeCleanup': states_before_cleanup, 'statesAfterCleanup': states_after_cleanup,
          'ownedUnitsUnloaded': all(s['LoadState']=='not-found' for s in states_after_cleanup.values()),
          'workspaceEmpty': not list(workspace.iterdir()), 'commands': commands,
          'learnerWorksheetCompletionInferred': False}
print(json.dumps(report, indent=2))
sys.exit(130 if interrupted else 2 if failure else 0 if len(ends)>=2 and nonoverlap else 1)
