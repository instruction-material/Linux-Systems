"""Exercise real Linux backup studio roles, repairs, interruptions and refusals."""
import argparse
import base64
import hashlib
import io
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

PACKS = [
    'LS-03-linux-systems-lab-16',
    'LS-31-applied-studio-16-linux-systems-lab-16-supplemental-2',
    'LS-32-applied-studio-16-linux-systems-lab-16-supplemental-3']
REPAIRS = [
    '''def capture_under_lock(lock_path, capture):
    import fcntl
    import os
    descriptor = os.open(lock_path, os.O_RDONLY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_SH)
        return capture()
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)
''',
    '''def restore_attributes(directory, expected):
    import os
    for name in sorted(expected, reverse=True):
        path = directory / name
        path.chmod(expected[name]["mode"])
        os.utime(path, ns=(path.stat().st_atime_ns, expected[name]["mtimeNs"]))
''',
    '''def choose_retirements(records, protected, cutoff_ns):
    result = []
    for row in records:
        if not row["verified"] or not row["ordinary"] or not row["published"]:
            continue
        if row["path"] in protected or row["createdNs"] >= cutoff_ns:
            continue
        result.append(row["path"])
    return sorted(result)
''']


def digest(data):
    return hashlib.sha256(data).hexdigest()


def actual_bytes(record):
    data = base64.b64decode(record['bytesBase64'], validate=True)
    assert digest(data) == record['sha256']
    return data


def payloads(record):
    with tarfile.open(fileobj=io.BytesIO(actual_bytes(record['file'])), mode='r:gz') as archive:
        members = archive.getmembers()
        assert len(members) == 4 and {m.name for m in members} == {'app.py', 'config.json', 'data.json', 'manifest.json'}
        assert all(m.isfile() and 0 <= m.size <= 1048576 and m.mode == 0o600 for m in members)
        data = {m.name: archive.extractfile(m).read() for m in members}
    manifest = json.loads(data.pop('manifest.json'))
    assert manifest == record['manifest'] and set(manifest) == {'version', 'createdNs', 'files'}
    assert manifest['version'] == 1 and manifest['createdNs'] > 0
    assert {name: digest(value) for name, value in data.items()} == manifest['files']
    assert all(data[name] == actual_bytes(record['payloads'][name]) for name in data)
    return data


def observe(data, complete, interrupted):
    assert data['uid'] == os.geteuid() and data['failure'] is None and not data['cleanupErrors']
    assert data['sourceUnchanged'] and data['ownedCaseRemoved'] and data['workspaceEmpty'] and data['ownedWorkerPidsGone']
    assert data['interrupted'] == interrupted and not data['learnerWorksheetCompletionInferred']
    assert all(row['endTime'] >= row['startTime'] and row['cwd'] == data['ownedCase'] for row in data['commands'])
    for row in data['commands']:
        if row['pid'] is None:
            assert row['spawnErrno'] == 13 and row['cleanup'] == 'spawn refused; no child created'
        else:
            assert row['pid'] > 0 and row['parentPid'] == data['pid']
            assert row['cleanup'] in ['owned process exited and reaped', 'owned process group stopped and reaped']
    if data['kind'] == 'coherence':
        assert not data['independentSharedProbe']['acquired']
        assert any('WRITE' in row.split() and str(data['writerPhase']['pid']) in row.split() for row in data['writerLockRows'])
        assert data['cleanupExclusiveProbe']['acquired'] and not data['cleanupLockRows']
        pending = any('->' in row.split() and 'READ' in row.split() and str(data['captureAttempt']['pid']) in row.split() for row in data['lockRowsBeforeRelease'])
        assert pending == complete and data['captureFinishedBeforeRelease'] == (not complete)
    if interrupted:
        return
    if data['kind'] == 'coherence':
        restored = payloads(data['archive'])
        observed = [json.loads(restored[name])['generation'] for name in ['config.json', 'data.json']]
        assert observed == data['observedGenerations']
        assert (observed == [data['generation'], data['generation']]) == complete
        assert all(actual_bytes(data['restored'][name]) == value for name, value in restored.items())
        assert data['independentExclusiveProbe']['acquired'] and not data['lockAfterWorkers']
        if complete:
            assert data['captureResult']['finishedMonotonicNs'] >= data['writerResult']['finishedMonotonicNs'] >= data['releaseRequestedMonotonicNs']
        else:
            assert data['captureResult']['finishedMonotonicNs'] <= data['releaseRequestedMonotonicNs']
    elif data['kind'] == 'attributes':
        archived = payloads(data['archive'])
        for name, expected in data['expectedAttributes'].items():
            assert expected == {key: data['source'][name][key] for key in ['mode', 'mtimeNs']}
            assert data['beforeAttributes'][name]['mode'] == 0o600
            assert actual_bytes(data['beforeAttributes'][name]) == actual_bytes(data['afterAttributes'][name]) == archived[name]
        exact = all(all(data['afterAttributes'][name][key] == value for key, value in expected.items())
                    for name, expected in data['expectedAttributes'].items())
        assert exact == complete
        executions = [r for r in data['commands'] if 'executable' in r['case']]
        assert len(executions) == 2 and executions[0]['spawnErrno'] == 13
        assert (executions[1].get('status') == 0) == complete
    else:
        generations = [payloads(record) for record in data['generations']]
        assert [json.loads(row['data.json'])['generation'] for row in generations] == [data['generation'] + i for i in range(3)]
        all_paths = {r['path'] for r in data['records']}
        assert len(all_paths) == 6 and sum(r['verified'] for r in data['records']) == 3
        assert data['protected'] == [data['generations'][i]['file']['path'] for i in [0, 2]]
        expected = {r['path'] for r in data['records'] if r['verified'] and r['createdNs'] < data['cutoffNs'] and r['path'] not in data['protected']}
        assert set(data['expectedRetirements']) == expected
        assert data['executionGuardAccepted'] == complete
        removed = set(data['beforeRetention']) - set(data['afterRetention'])
        assert removed == (expected if complete else set())
        assert {r['path'] for r in data['actualDeletions']} == removed
        assert all(row['absentAfter'] for row in data['actualDeletions'])
        assert all(data['afterRetention'][name] == value for name, value in data['beforeRetention'].items() if name not in removed)
        assert data['sentinelBefore'] == data['sentinelAfter']
        assert len(data['anchorRestores']) == 2
        for index, restored in enumerate(data['anchorRestores']):
            assert all(actual_bytes(restored['files'][name]) == value for name, value in generations[[0, 2][index]].items())
    assert data['targetBehaviorObserved'] == complete


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proof', type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != 'linux' or os.geteuid() == 0:
        raise RuntimeError('native acceptance requires ordinary Linux')
    root = Path(__file__).resolve().parents[1]
    names = ['README.md'] + [role + '/' + name for role in ['starter', 'solution']
                            for name in ['backup-notes.md', 'task.sh', 'task.py', 'backup_studio.py',
                                         'backup.py', 'app.py', 'config.json', 'data.json']]
    original = {pack + '/' + name: digest((root / pack / name).read_bytes()) for pack in PACKS for name in names}
    assert len(original) == 51
    rows, events, profiles = [], [], []
    args.proof.parent.mkdir(parents=True, exist_ok=True)
    error = "native run did not complete"
    try:
        with tempfile.TemporaryDirectory(prefix='linux-backup-studio ') as temporary:
            work = Path(temporary)
            sentinel = work / 'outside sentinel.txt'
            sentinel.write_bytes(b'preserve independent outside source sentinel\n')
            for index, pack in enumerate(PACKS):
                for profile in ['starter', 'solution', 'completed']:
                    role = work / (str(index) + '-' + profile + ' quoted role')
                    shutil.copytree(root / pack / ('starter' if profile == 'completed' else profile), role)
                    if profile == 'completed':
                        source = (role / 'task.py').read_text()
                        a = source.index('def ')
                        b = source.index('\n\nif __name__', a)
                        (role / 'task.py').write_text(source[:a] + REPAIRS[index] + source[b:])
                    role_hashes = {p.name: digest(p.read_bytes()) for p in role.iterdir() if p.is_file()}
                    count = 0
                    cases = [('actual ordinary studio', []), ('actual reversed studio', ['--reverse', '--generation', '7']),
                             ('actual studio interruption', ['--hold']), ('actual studio recovery retest', ['--generation', '5'])]
                    if index == 2:
                        cases.append(('actual no eligible retirement', ['--keep-all']))
                    cases += [('missing parent refusal', []), ('nonempty parent refusal', []),
                              ('symlink parent refusal', []), ('invalid generation refusal', ['--generation', '0'])]
                    for case, options in cases:
                        parent = work / ('case ' + str(len(rows)))
                        parent.mkdir()
                        supplied = parent
                        if case == 'missing parent refusal':
                            supplied = parent / 'missing'
                        elif case == 'nonempty parent refusal':
                            (parent / 'preserve.txt').write_bytes(b'keep existing file\n')
                        elif case == 'symlink parent refusal':
                            supplied = work / ('link ' + str(len(rows)))
                            supplied.symlink_to(parent)
                        command = ['bash', str(role / 'task.sh'), str(supplied), *options]
                        started = time.time()
                        child = subprocess.Popen(command, cwd=role, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
                        events.append({'event': 'start', 'command': command, 'case': case, 'cwd': str(role), 'pid': child.pid,
                                           'parentPid': os.getpid(), 'startTime': started, 'timeoutSeconds': 60})
                        held = None
                        try:
                            if '--hold' in options:
                                deadline = time.monotonic() + 10
                                marker = parent / 'backup-studio-ready.json'
                                while not marker.exists() and child.poll() is None and time.monotonic() < deadline:
                                    time.sleep(0.01)
                                assert marker.exists(), 'no actual interruption phase'
                                held = json.loads(marker.read_text())
                                assert held['pid'] == child.pid and held['uid'] == os.geteuid()
                                owned = Path(held['ownedCase'])
                                assert owned.parent == parent and owned.is_dir()
                                if index == 0:
                                    writer = json.loads((owned / 'writer-phase.json').read_text())
                                    assert Path('/proc/' + str(writer['pid'])).is_dir()
                                    details = (owned / 'state.lock').stat()
                                    key = f'{os.major(details.st_dev):02x}:{os.minor(details.st_dev):02x}:{details.st_ino}'
                                    held['actualKernelLockRows'] = [r for r in Path('/proc/locks').read_text().splitlines() if key in r.split()]
                                    assert any('WRITE' in r.split() and str(writer['pid']) in r.split() for r in held['actualKernelLockRows'])
                                os.killpg(child.pid, signal.SIGINT)
                            output, diagnostics = child.communicate(timeout=60)
                        except BaseException:
                            if child.poll() is None:
                                os.killpg(child.pid, signal.SIGTERM)
                            try:
                                child.communicate(timeout=3)
                            except subprocess.TimeoutExpired:
                                os.killpg(child.pid, signal.SIGKILL)
                                child.communicate(timeout=3)
                            raise
                        ended = time.time()
                        events.append({'event': 'end', 'pid': child.pid, 'startTime': started, 'endTime': ended, 'exitCode': child.returncode,
                                           'childProcessGroupCleanup': 'owned process exited and reaped'})
                        row = {'case': case, 'command': command, 'cwd': str(role), 'pid': child.pid, 'status': child.returncode,
                                   'stdout': output.decode(), 'stderr': diagnostics.decode(), 'holdObservation': held}
                        rows.append(row)
                        if case.endswith('refusal'):
                            assert child.returncode == 2 and not output and diagnostics
                            if case == 'nonempty parent refusal':
                                assert (parent / 'preserve.txt').read_bytes() == b'keep existing file\n'
                            else:
                                assert not any(parent.iterdir())
                        else:
                            assert not diagnostics and output
                            data = json.loads(output)
                            observe(data, profile != 'starter', '--hold' in options)
                            assert child.returncode == (130 if '--hold' in options else 1 if profile == 'starter' else 0)
                            assert not any(parent.iterdir())
                        assert {p.name: digest(p.read_bytes()) for p in role.iterdir() if p.is_file()} == role_hashes
                        assert sentinel.read_bytes() == b'preserve independent outside source sentinel\n'
                        if supplied.is_symlink():
                            supplied.unlink()
                        shutil.rmtree(parent)
                        count += 1
                    profiles.append({'pack': pack, 'profile': profile, 'actualCases': count, 'passed': True,
                                         'inputsUnchanged': True, 'outsideSentinelPreserved': True, 'ownedResourcesRemoved': True,
                                         'learnerWorksheetCompletionInferred': False})
        assert len(rows) == 75 and len(profiles) == 9
        error = None
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, AssertionError, subprocess.SubprocessError, tarfile.TarError, KeyboardInterrupt) as exception:
        error = type(exception).__name__ + ': ' + str(exception)
    finally:
        unchanged = original == {name: digest((root / name).read_bytes()) for name in original}
        observations = [json.loads(row['stdout']) for row in rows if row['stdout']]
        commands = [command for data in observations for command in data['commands']]
        proof = {'nativePassed': error is None and unchanged, 'error': error, 'platform': platform.system(), 'uid': os.geteuid(),
                     'sourceHashes': original, 'sourceUnchanged': unchanged, 'profiles': profiles, 'actualCases': len(rows),
                     'loggedOuterLifecycles': len(rows), 'actualCommandObservations': len(commands),
                     'actualChildLifecycles': sum(row['pid'] is not None for row in commands),
                     'actualSpawnRefusals': sum(row['pid'] is None for row in commands),
                     'actualPublishedArchives': sum('archive' in data for data in observations) + sum('interruptedCaptureArchive' in data for data in observations) + sum(len(data.get('generations', [])) for data in observations),
                     'actualDeletions': sum(len(data.get('actualDeletions', [])) for data in observations),
                     'actualSeparateRestores': sum('restore' in data for data in observations) + sum(len(data.get('anchorRestores', [])) for data in observations),
                     'actualInterruptions': sum(data['interrupted'] for data in observations),
                     'learnerWorksheetCompletionInferred': False}
        args.proof.with_suffix('.observations.json').write_text(json.dumps(rows, indent=2) + '\n')
        args.proof.with_suffix('.processes.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events))
        args.proof.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps(proof, sort_keys=True))
    return 0 if proof['nativePassed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
