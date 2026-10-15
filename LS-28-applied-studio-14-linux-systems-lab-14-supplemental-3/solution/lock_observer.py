"""Observe actual publisher contention and cleanup in one private case."""
import argparse
import errno
import fcntl
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('workspace')
    parser.add_argument('--reverse', action='store_true')
    parser.add_argument('--hold-seconds', default='0')
    args = parser.parse_args()
    path = Path(args.workspace)
    if platform.system() != 'Linux' or os.geteuid() == 0:
        parser.error('Use an ordinary account in the owned Linux lab')
    if not re.fullmatch(r'(?:[0-7](?:\.[0-9]{1,2})?|8(?:\.0{1,2})?)', args.hold_seconds):
        parser.error('hold-seconds must be a decimal from 0 through 8')
    if path.is_symlink() or not path.is_dir() or path.stat().st_uid != os.getuid() or list(path.iterdir()):
        parser.error('workspace must be an existing empty owned nonsymlink directory')
    workspace = path.resolve()
    data = dict(uid=os.getuid(), workspace=str(workspace), workers=[], snapshots=[], probes=[], failure=None,
                observationsCompleted=False, learnerWorksheetCompletionInferred=False, interrupted=False)
    children = []
    root = None
    ready_created = False
    interrupted = []
    old_handlers = {number: signal.signal(number, lambda signum, frame: interrupted.append(signum)) for number in (signal.SIGINT, signal.SIGTERM)}

    def check():
        if interrupted:
            raise InterruptedError('The caller interrupted the observation')

    def start(actor):
        check()
        command = [sys.executable, str(Path(__file__).with_name('publisher.py')), str(root), actor]
        started = time.time()
        child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        row = dict(parentTask='Linux concurrent deployment observation', parentPid=os.getpid(), command=command,
                   cwd=str(Path.cwd()), pid=child.pid, actor=actor, startTime=started, timeoutSeconds=15)
        children.append((child, row))
        deadline = time.monotonic() + 5
        ready = root / ('ready-' + actor + '.json')
        while not ready.exists() and child.poll() is None:
            check()
            if time.monotonic() >= deadline:
                raise RuntimeError('The publisher did not reach its actual lock decision')
            time.sleep(0.01)
        if ready.exists():
            row['ready'] = json.loads(ready.read_text())
            assert row['ready']['pid'] == child.pid and row['ready']['uid'] == os.getuid()
        return child, row

    def collect(pair):
        child, row = pair
        if 'endTime' in row:
            return row
        try:
            out, err = child.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            out, err = child.communicate()
            row['childProcessGroupCleanup'] = 'owned process group killed after deadline'
        row.update(endTime=time.time(), returnCode=child.returncode, stdout=out.decode(errors='replace'),
                   stderr=err.decode(errors='replace'), childProcessGroupCleanup=row.get('childProcessGroupCleanup', 'owned process exited and reaped'))
        data['workers'].append(row)
        return row

    def release(pair):
        check()
        (root / ('go-' + pair[1]['actor'])).write_text('publish\n')
        return collect(pair)

    def snapshot(label):
        current = json.loads((root / 'current.json').read_text())
        data['snapshots'].append(dict(label=label, state=current, at=time.time()))
        return current

    def probe(label):
        row = dict(label=label, pid=os.getpid(), at=time.time())
        with (root / 'activation.lock').open('a+') as stream:
            row['inode'] = os.fstat(stream.fileno()).st_ino
            row['device'] = os.fstat(stream.fileno()).st_dev
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                row.update(blocked=False, errno=None)
                fcntl.flock(stream, fcntl.LOCK_UN)
            except BlockingIOError as error:
                assert error.errno in (errno.EAGAIN, errno.EACCES)
                row.update(blocked=True, errno=error.errno)
        data['probes'].append(row)
        return row

    status = 2
    try:
        root = Path(tempfile.mkdtemp(prefix='classes-deploy-lock-', dir=workspace))
        (root / 'activation.lock').touch()
        (root / 'current.json').write_text(json.dumps(dict(generation=0, release='initial')))
        data['lockInode'] = (root / 'activation.lock').stat().st_ino
        first_name, second_name = ('beta', 'alpha') if args.reverse else ('alpha', 'beta')
        first = start(first_name)
        assert 'ready' in first[1]
        initial_probe = probe('while first publisher is held')
        data['firstActor'] = first_name
        ready_source = root / 'observer-ready.json'
        ready_source.write_text(json.dumps(dict(pid=first[0].pid, inode=data['lockInode'])))
        os.link(ready_source, workspace / 'ready.json')
        ready_created = True
        deadline = time.monotonic() + float(args.hold_seconds)
        while time.monotonic() < deadline:
            check()
            time.sleep(0.01)
        second = start(second_name)
        data['secondAcquiredWhileFirstHeld'] = 'ready' in second[1]
        snapshot('before any publication')
        release(first)
        snapshot('after first publication')
        if 'ready' in second[1]:
            release(second)
        else:
            assert collect(second)['returnCode'] == 75
        snapshot('after second decision')
        retry = start('retry')
        release(retry)
        snapshot('after retry')
        held = start('interrupt')
        assert 'ready' in held[1]
        probe('while interrupted publisher is held')
        held[0].send_signal(signal.SIGINT)
        assert collect(held)['returnCode'] == 130
        snapshot('after interruption')
        recovery = start('recovery')
        release(recovery)
        final = snapshot('after recovery')
        final_probe = probe('after every publisher exited')
        data['targetBehaviorObserved'] = bool(initial_probe['blocked'] and not data['secondAcquiredWhileFirstHeld'] and final['generation'] == 3 and not final_probe['blocked'])
        data['observationsCompleted'] = True
        status = 0 if data['targetBehaviorObserved'] else 1
    except InterruptedError:
        data['interrupted'] = True
        status = 130
    except (OSError, ValueError, RuntimeError, AssertionError) as error:
        data['failure'] = type(error).__name__ + ': ' + str(error)
    finally:
        for child, row in children:
            if child.poll() is None:
                child.send_signal(signal.SIGTERM)
            collect((child, row))
        data['workerPidsGone'] = all(not (Path('/proc') / str(child.pid)).exists() for child, _ in children)
        if root:
            shutil.rmtree(root)
        if ready_created:
            (workspace / 'ready.json').unlink()
        data['ownedCaseRemoved'] = root is None or not root.exists()
        data['workspaceEmpty'] = not list(workspace.iterdir())
        for number, old in old_handlers.items():
            signal.signal(number, old)
    print(json.dumps(data, indent=2))
    return status


if __name__ == '__main__':
    raise SystemExit(main())
