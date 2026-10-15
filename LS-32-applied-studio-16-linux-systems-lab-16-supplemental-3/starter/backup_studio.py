"""Observe actual cooperating locks, restored attributes and guarded retention."""
import argparse
import base64
import errno
import fcntl
import hashlib
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import time
import uuid
from pathlib import Path

import backup

FILES = ('app.py', 'config.json', 'data.json')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + '\n')
    path.chmod(0o600)


def record_file(path):
    details = path.lstat()
    value = {'path': str(path), 'uid': details.st_uid, 'mode': stat.S_IMODE(details.st_mode),
                 'inode': details.st_ino, 'device': details.st_dev, 'mtimeNs': details.st_mtime_ns}
    if stat.S_ISREG(details.st_mode):
        data = path.read_bytes()
        value.update(sha256=sha(data), bytesBase64=base64.b64encode(data).decode())
    elif path.is_symlink():
        value['link'] = os.readlink(path)
    else:
        raise ValueError('only ordinary files and the declared refused link are observed')
    return value


def record_tree(path):
    return {name: record_file(path / name) for name in FILES}


def lock_rows(path):
    details = path.stat()
    key = f'{os.major(details.st_dev):02x}:{os.minor(details.st_dev):02x}:{details.st_ino}'
    return [line for line in Path('/proc/locks').read_text().splitlines() if key in line.split()]


def probe_lock(path, operation):
    with path.open('rb') as stream:
        try:
            fcntl.flock(stream, operation | fcntl.LOCK_NB)
        except OSError as error:
            if error.errno not in (errno.EACCES, errno.EAGAIN):
                raise
            return {'acquired': False, 'errno': error.errno, 'pid': os.getpid(), 'uid': os.geteuid()}
        fcntl.flock(stream, fcntl.LOCK_UN)
        return {'acquired': True, 'errno': None, 'pid': os.getpid(), 'uid': os.geteuid()}


class Runner:
    def __init__(self, cwd):
        self.cwd, self.commands, self.active = cwd, [], {}

    def start(self, command, case, timeout=15):
        row = {'command': list(map(str, command)), 'case': case, 'cwd': str(self.cwd),
                   'parentPid': os.getpid(), 'startTime': time.time(), 'timeoutSeconds': timeout}
        try:
            child = subprocess.Popen(row['command'], cwd=self.cwd, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, start_new_session=True)
        except PermissionError as error:
            row.update(pid=None, endTime=time.time(), status=None, spawnErrno=error.errno,
                       stdout='', stderr=str(error), cleanup='spawn refused; no child created')
            self.commands.append(row)
            return None, row
        row['pid'] = child.pid
        self.commands.append(row)
        self.active[child.pid] = child, row
        return child, row

    def finish(self, child, row):
        if child is None:
            return row
        try:
            output, errors = child.communicate(timeout=row['timeoutSeconds'])
        except BaseException:
            self.close(child, row)
            raise
        row.update(endTime=time.time(), status=child.returncode,
                   stdout=output.decode(), stderr=errors.decode(),
                   cleanup='owned process exited and reaped')
        self.active.pop(child.pid)
        return row

    def call(self, command, case):
        return self.finish(*self.start(command, case))

    def close(self, child, row):
        if child.pid not in self.active:
            return
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
        try:
            output, errors = child.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            output, errors = child.communicate(timeout=2)
        row.update(endTime=time.time(), status=child.returncode, stdout=output.decode(),
                   stderr=errors.decode(), cleanup='owned process group stopped and reaped')
        self.active.pop(child.pid)

    def cleanup(self):
        errors = []
        for child, row in reversed(list(self.active.values())):
            try:
                self.close(child, row)
            except (OSError, ValueError, KeyError, TypeError, RuntimeError, AssertionError, subprocess.SubprocessError, backup.tarfile.TarError, KeyboardInterrupt) as error:
                errors.append(type(error).__name__ + ': ' + str(error))
        return errors


def checked(row, status=0):
    if row['status'] != status or (status == 0 and row['stderr']):
        raise ValueError('unexpected actual command result: ' + row['case'])
    return json.loads(row['stdout']) if status == 0 else None


def archive_record(path):
    contents, manifest = backup.validate(path)
    return {'file': record_file(path), 'manifest': manifest,
                'payloads': {name: {'sha256': sha(data), 'bytesBase64': base64.b64encode(data).decode()}
                          for name, data in contents.items()}}


def source_tree(root, role, generation):
    root.mkdir(mode=0o700)
    for name in FILES:
        shutil.copyfile(role / name, root / name)
        (root / name).chmod(0o600)
    for name in ['config.json', 'data.json']:
        write_json(root / name, {'generation': generation, 'message': 'Fictional state ' + str(generation)})
    return root


def wait_until(predicate, description):
    deadline = time.monotonic() + 6
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise TimeoutError(description)


def hold(parent, proof, args):
    if not args.hold:
        return
    marker = parent / 'backup-studio-ready.json'
    write_json(marker, {'pid': os.getpid(), 'uid': os.geteuid(), 'kind': proof['kind'],
                            'phase': proof['phase'], 'ownedCase': proof['ownedCase']})
    proof['holdReady'] = record_file(marker)
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        time.sleep(0.02)


def writer(arguments):
    source, lock, phase, release = map(Path, arguments[:4])
    generation, reverse = int(arguments[4]), arguments[5] == '1'
    with lock.open('rb+') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        order = ['data.json', 'config.json'] if reverse else ['config.json', 'data.json']
        write_json(source / order[0], {'generation': generation, 'message': 'Fictional state ' + str(generation)})
        write_json(phase, {'pid': os.getpid(), 'uid': os.geteuid(), 'first': order[0],
                              'monotonicNs': time.monotonic_ns(), 'lockInode': lock.stat().st_ino})
        deadline = time.monotonic() + 12
        while not release.exists():
            if time.monotonic() > deadline:
                raise TimeoutError('owned writer release was not observed')
            time.sleep(0.01)
        write_json(source / order[1], {'generation': generation, 'message': 'Fictional state ' + str(generation)})
        print(json.dumps({'pid': os.getpid(), 'uid': os.geteuid(), 'generation': generation,
                              'first': order[0], 'last': order[1], 'finishedMonotonicNs': time.monotonic_ns()}), flush=True)


def coherence(role, case, runner, proof, args, policy):
    source = source_tree(case / 'source', role, 0)
    destination = case / 'archives'
    destination.mkdir(mode=0o700)
    lock, phase, release, attempted = [case / name for name in ['state.lock', 'writer-phase.json', 'release', 'capture-attempt.json']]
    lock.write_bytes(b'owned cooperating lock\n')
    lock.chmod(0o600)
    proof['initialSource'] = record_tree(source)
    worker, worker_row = runner.start([sys.executable, __file__, '--writer', source, lock, phase, release,
                                      str(args.generation), str(int(args.reverse))], 'actual cooperating writer')
    wait_until(phase.exists, 'actual writer did not expose its first write')
    proof.update(writerPhase=json.loads(phase.read_text()), partialSource=record_tree(source),
                 writerLockRows=lock_rows(lock), independentSharedProbe=probe_lock(lock, fcntl.LOCK_SH))
    assert not proof['independentSharedProbe']['acquired']
    assert any('WRITE' in row.split() and str(worker.pid) in row.split() for row in proof['writerLockRows'])
    capture, capture_row = runner.start([sys.executable, role / 'task.py', '--capture-child', source,
                                        destination, lock, attempted], 'actual snapshot policy process')
    wait_until(attempted.exists, 'actual snapshot process did not start')
    def observed():
        return capture.poll() is not None or any('->' in row.split() and 'READ' in row.split()
                                                and str(capture.pid) in row.split() for row in lock_rows(lock))
    wait_until(observed, 'no completed capture or actual pending shared lock')
    proof.update(captureAttempt=json.loads(attempted.read_text()), lockRowsBeforeRelease=lock_rows(lock),
                 captureFinishedBeforeRelease=capture.poll() is not None, phase='actual writer holds the exclusive lock')
    hold(case.parent, proof, args)
    proof['releaseRequestedMonotonicNs'] = time.monotonic_ns()
    release.write_text('release owned writer\n')
    proof['writerResult'] = checked(runner.finish(worker, worker_row))
    captured = checked(runner.finish(capture, capture_row))
    proof['captureResult'] = captured
    proof['archive'] = archive_record(Path(captured['archive']))
    proof['finalSource'] = record_tree(source)
    target = case / 'restored'
    proof['restore'] = checked(runner.call([sys.executable, role / 'backup.py', 'restore', captured['archive'], target], 'actual separate snapshot restore'))
    proof['restored'] = record_tree(target)
    app = runner.call([sys.executable, target / 'app.py'], 'actual restored application')
    generations = [json.loads(base64.b64decode(proof['archive']['payloads'][name]['bytesBase64']))['generation']
                   for name in ['config.json', 'data.json']]
    coherent = generations == [args.generation, args.generation]
    assert app['status'] == (0 if coherent else 2)
    if coherent:
        assert app['stdout'] == 'RECOVERED=' + str(args.generation) + '\n' and not app['stderr']
    proof.update(observedGenerations=generations, targetBehaviorObserved=coherent,
                 lockAfterWorkers=lock_rows(lock), independentExclusiveProbe=probe_lock(lock, fcntl.LOCK_EX))
    assert proof['independentExclusiveProbe']['acquired'] and not proof['lockAfterWorkers']


def attributes(role, case, runner, proof, args, policy):
    source = source_tree(case / 'source', role, args.generation)
    destination = case / 'archives'
    destination.mkdir(mode=0o700)
    before = time.time_ns() - 10_000_000_000
    for number, name in enumerate(FILES):
        (source / name).chmod([0o750, 0o600, 0o640][number])
        os.utime(source / name, ns=(before, before + number * 1_000_000))
    source_evidence = record_tree(source)
    metadata = {name: {'mode': row['mode'], 'mtimeNs': row['mtimeNs']} for name, row in source_evidence.items()}
    if args.reverse:
        metadata = dict(reversed(list(metadata.items())))
    built = checked(runner.call([sys.executable, role / 'backup.py', 'build', source, destination], 'actual attribute backup'))
    target = case / 'restored'
    restored = checked(runner.call([sys.executable, role / 'backup.py', 'restore', built['archive'], target], 'actual attribute restore'))
    proof.update(source=source_evidence, expectedAttributes=metadata, archive=archive_record(Path(built['archive'])),
                 restore=restored, beforeAttributes=record_tree(target), phase='actual private restore before attribute repair')
    refused = runner.call([target / 'app.py'], 'actual executable before attribute repair')
    assert refused['pid'] is None and refused['spawnErrno'] == errno.EACCES
    hold(case.parent, proof, args)
    policy(target, metadata)
    proof['afterAttributes'] = record_tree(target)
    exact = all(all(proof['afterAttributes'][name][key] == value for key, value in desired.items())
                for name, desired in metadata.items())
    assert all(proof['afterAttributes'][name]['sha256'] == row['sha256'] for name, row in source_evidence.items())
    executed = runner.call([target / 'app.py'], 'actual executable after attribute repair')
    if exact:
        assert executed['status'] == 0 and executed['stdout'] == 'RECOVERED=' + str(args.generation) + '\n' and not executed['stderr']
    proof['targetBehaviorObserved'] = exact


def retention(role, case, runner, proof, args, policy):
    source = source_tree(case / 'source', role, args.generation)
    destination = case / 'archives'
    destination.mkdir(mode=0o700)
    generations = []
    for number in range(3):
        write_json(source / 'data.json', {'generation': args.generation + number, 'message': 'Fictional state ' + str(args.generation + number)})
        write_json(source / 'config.json', {'generation': args.generation + number, 'message': 'Fictional state ' + str(args.generation + number)})
        built = checked(runner.call([sys.executable, role / 'backup.py', 'build', source, destination], 'actual retained generation ' + str(number)))
        generations.append(archive_record(Path(built['archive'])))
        time.sleep(0.002)
    corrupt, partial, link = [destination / name for name in ['snapshot-corrupt.tar.gz', 'snapshot-unpublished.partial', 'snapshot-link.tar.gz']]
    corrupt.write_bytes(b'invalid private archive\n')
    partial.write_bytes(b'unpublished private candidate\n')
    link.symlink_to(case / 'outside-retention-sentinel')
    (case / 'outside-retention-sentinel').write_bytes(b'preserve independent retention sentinel\n')
    protected = [generations[0]['file']['path'], generations[-1]['file']['path']]
    cutoff = generations[0 if args.keep_all else -1]['manifest']['createdNs']
    ordered = list(destination.iterdir())
    if args.reverse:
        ordered.reverse()
    records = []
    before = {}
    for number, path in enumerate(ordered):
        if not path.is_symlink():
            os.utime(path, ns=(cutoff - 90_000_000_000 - number, cutoff - 90_000_000_000 - number))
        item = record_file(path)
        before[str(path)] = item
        record = {'path': str(path), 'mtimeNs': item['mtimeNs'], 'verified': False, 'createdNs': None,
                      'published': path.name.endswith('.tar.gz'), 'ordinary': not path.is_symlink()}
        if record['published'] and record['ordinary']:
            check = runner.call([sys.executable, role / 'backup.py', 'verify', path], 'actual retention verification ' + path.name)
            if check['status'] == 0:
                verified = checked(check)
                record.update(verified=True, createdNs=verified['manifest']['createdNs'])
            else:
                assert check['status'] == 2 and check['stderr'] and not check['stdout']
        records.append(record)
    proof.update(generations=generations, records=records, beforeRetention=before, protected=protected,
                 cutoffNs=cutoff, sentinelBefore=record_file(case / 'outside-retention-sentinel'),
                 phase='actual verified history before retention planning')
    hold(case.parent, proof, args)
    selected = policy(records, protected, cutoff)
    assert isinstance(selected, list) and all(isinstance(name, str) for name in selected)
    expected = [] if args.keep_all else [generations[1]['file']['path']]
    allowed = {r['path'] for r in records if r['verified'] and r['published'] and r['ordinary']
               and r['createdNs'] < cutoff and r['path'] not in protected}
    valid = len(selected) == len(set(selected)) and set(selected) <= allowed
    proof.update(selected=selected, expectedRetirements=expected, executionGuardAccepted=valid, actualDeletions=[])
    if valid:
        for name in selected:
            path = Path(name)
            assert path.parent == destination and not path.is_symlink() and path.stat().st_uid == os.geteuid()
            original = record_file(path)
            assert original['sha256'] == before[name]['sha256'] and original['inode'] == before[name]['inode']
            path.unlink()
            proof['actualDeletions'].append({'path': name, 'before': original, 'absentAfter': not path.exists()})
    proof['afterRetention'] = {str(path): record_file(path) for path in destination.iterdir()}
    proof['anchorRestores'] = []
    for number, archive in enumerate(protected):
        target = case / ('anchor-restore-' + str(number))
        result = checked(runner.call([sys.executable, role / 'backup.py', 'restore', archive, target], 'actual retained anchor restore ' + str(number)))
        proof['anchorRestores'].append({'result': result, 'files': record_tree(target)})
    proof['sentinelAfter'] = record_file(case / 'outside-retention-sentinel')
    assert proof['sentinelBefore'] == proof['sentinelAfter']
    removed = set(before) - set(proof['afterRetention'])
    assert removed == (set(selected) if valid else set())
    assert all(proof['afterRetention'][name] == value for name, value in before.items() if name not in removed)
    proof['targetBehaviorObserved'] = valid and set(selected) == set(expected)


def run(kind, policy):
    if sys.platform != 'linux' or os.geteuid() == 0:
        raise ValueError('use an ordinary Linux account')
    if len(sys.argv) > 1 and sys.argv[1] == '--capture-child':
        source, destination, lock, attempted = map(Path, sys.argv[2:])
        write_json(attempted, {'pid': os.getpid(), 'uid': os.geteuid(), 'monotonicNs': time.monotonic_ns()})
        started = time.monotonic_ns()
        result = policy(lock, lambda: backup.build(source, destination))
        result.update(pid=os.getpid(), uid=os.geteuid(), startedMonotonicNs=started, finishedMonotonicNs=time.monotonic_ns())
        print(json.dumps(result, sort_keys=True), flush=True)
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('parent', type=Path)
    parser.add_argument('--reverse', action='store_true')
    parser.add_argument('--hold', action='store_true')
    def generation_value(value):
        result = int(value)
        if not 1 <= result <= 9999:
            raise argparse.ArgumentTypeError('generation must be from1 through9999')
        return result
    parser.add_argument('--generation', type=generation_value, default=2, metavar='1..9999')
    parser.add_argument('--keep-all', action='store_true')
    args = parser.parse_args()
    parent = args.parent.absolute()
    if parent.is_symlink() or not parent.is_dir() or parent.stat().st_uid != os.geteuid() or parent.resolve() == Path('/') or any(parent.iterdir()):
        raise ValueError('expected an existing empty ordinary owned parent')
    parent = parent.resolve()
    role = Path(__file__).resolve().parent
    hashes = {path.name: sha(path.read_bytes()) for path in role.iterdir() if path.is_file() and path.suffix in ['.py', '.sh', '.json', '.md']}
    case = parent / ('backup-studio-' + uuid.uuid4().hex)
    case.mkdir(mode=0o700)
    write_json(case / 'owned-case.json', {'owner': os.geteuid(), 'parentPid': os.getpid()})
    runner = Runner(case)
    proof = {'kind': kind, 'uid': os.geteuid(), 'pid': os.getpid(), 'ownedCase': str(case), 'reverse': args.reverse,
                 'generation': args.generation, 'commands': runner.commands, 'phase': 'initializing', 'sourceHashes': hashes,
                 'interrupted': False, 'failure': None, 'targetBehaviorObserved': False, 'learnerWorksheetCompletionInferred': False}
    try:
        {'coherence': coherence, 'attributes': attributes, 'retention': retention}[kind](role, case, runner, proof, args, policy)
    except KeyboardInterrupt:
        proof['interrupted'] = True
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, AssertionError, subprocess.SubprocessError, backup.tarfile.TarError) as error:
        proof['failure'] = type(error).__name__ + ': ' + str(error)
    finally:
        errors = runner.cleanup()
        if kind == 'coherence' and 'archive' not in proof:
            for command in runner.commands:
                if command['case'] == 'actual snapshot policy process' and command.get('status') == 0:
                    try:
                        captured = json.loads(command['stdout'])
                        proof['interruptedCaptureArchive'] = archive_record(Path(captured['archive']))
                    except (OSError, ValueError, KeyError, TypeError, RuntimeError, AssertionError, subprocess.SubprocessError, backup.tarfile.TarError, KeyboardInterrupt) as error:
                        errors.append(type(error).__name__ + ': ' + str(error))
        lock = case / 'state.lock'
        try:
            if lock.exists():
                proof['cleanupLockRows'] = lock_rows(lock)
                proof['cleanupExclusiveProbe'] = probe_lock(lock, fcntl.LOCK_EX)
                if proof['cleanupLockRows'] or not proof['cleanupExclusiveProbe']['acquired']:
                    errors.append('owned cooperating lock is still held')
        except (OSError, ValueError, KeyError, TypeError, RuntimeError, AssertionError, subprocess.SubprocessError, backup.tarfile.TarError, KeyboardInterrupt) as error:
            errors.append(type(error).__name__ + ': ' + str(error))
        proof['ownedWorkerPidsGone'] = all(row['pid'] is None or not Path('/proc/' + str(row['pid'])).exists() for row in runner.commands)
        if not proof['ownedWorkerPidsGone']:
            errors.append('an owned child PID is still present')
        try:
            marker = parent / 'backup-studio-ready.json'
            if marker.exists():
                assert json.loads(marker.read_text())['pid'] == os.getpid()
                marker.unlink()
            assert json.loads((case / 'owned-case.json').read_text()) == {'owner': os.geteuid(), 'parentPid': os.getpid()}
            if not errors:
                shutil.rmtree(case)
        except (OSError, ValueError, KeyError, TypeError, RuntimeError, AssertionError, subprocess.SubprocessError, backup.tarfile.TarError, KeyboardInterrupt) as error:
            errors.append(type(error).__name__ + ': ' + str(error))
        proof.update(ownedCaseRemoved=not case.exists(), workspaceEmpty=not any(parent.iterdir()),
                     cleanupErrors=errors, sourceUnchanged=hashes == {name: sha((role / name).read_bytes()) for name in hashes})
    print(json.dumps(proof, sort_keys=True), flush=True)
    return 2 if proof['failure'] or proof['cleanupErrors'] else 130 if proof['interrupted'] else 0 if proof['targetBehaviorObserved'] else 1


if __name__ == '__main__':
    if sys.argv[1] != '--writer':
        raise SystemExit('writer equipment requires its private controller arguments')
    writer(sys.argv[2:])
