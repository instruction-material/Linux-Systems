"""Observe the installed systemd calendar parser without changing a clock."""
import argparse
import datetime
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import time

if platform.system() != 'Linux' or os.geteuid() == 0:
    print('Use an ordinary account in an owned Linux lab.', file=sys.stderr)
    sys.exit(2)
parser = argparse.ArgumentParser()
parser.add_argument('base')
parser.add_argument('expression')
args = parser.parse_args()
binary = shutil.which('systemd-analyze')
if not binary:
    parser.error('The installed systemd-analyze command is required.')
# Apply the supplied anchor to the actual parser invocation.
include_base = True
command = [binary, 'calendar', '--iterations=3']
if include_base:
    command.append('--base-time=' + args.base)
command.extend(['--', args.expression])
environment = dict(os.environ, LC_ALL='C', TZ='UTC', SYSTEMD_COLORS='0', SYSTEMD_PAGER='cat')
started = time.time()
child = subprocess.Popen(command, env=environment, stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
cleanup = 'owned process exited and reaped'
timed_out = False
try:
    out, err = child.communicate(timeout=5)
except subprocess.TimeoutExpired:
    timed_out = True
    cleanup = 'owned calendar process group terminated after deadline'
    os.killpg(child.pid, signal.SIGTERM)
    try:
        out, err = child.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid, signal.SIGKILL)
        out, err = child.communicate()
except BaseException:
    if child.poll() is None:
        os.killpg(child.pid, signal.SIGTERM)
    try:
        child.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid, signal.SIGKILL)
        child.communicate()
    raise
record = {'parentPid': os.getpid(), 'pid': child.pid, 'command': command,
          'startTime': started, 'endTime': time.time(), 'timeoutSeconds': 5,
          'returnCode': child.returncode, 'childProcessGroupCleanup': cleanup,
          'stdout': out.decode(), 'stderr': err.decode(), 'timedOut': timed_out}
report = {'requestedBase': args.base, 'expression': args.expression,
          'baseApplied': include_base, 'tool': record,
          'observedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'systemClockChanged': False, 'schedulerInstalled': False,
          'learnerWorksheetCompletionInferred': False}
print(json.dumps(report, indent=2))
sys.exit(124 if timed_out else child.returncode if child.returncode >= 0 else 128-child.returncode)
