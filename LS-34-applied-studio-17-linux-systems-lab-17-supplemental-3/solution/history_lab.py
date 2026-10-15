"""Equipment for real private archives, recovery-point selection and restore drills."""
import argparse
import base64
import hashlib
import io
import json
import logging
import os
import platform
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

import backup

SOURCE = Path(__file__).resolve().parent
MAX_HOLD = 15
LOGGER = logging.getLogger(__name__)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run_child(report, case, arguments, cwd, expected=0):
    command = [sys.executable, str(SOURCE / 'backup.py'), *map(str, arguments)]
    started = time.time()
    child = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, start_new_session=True)
    cleanup = 'owned process exited and reaped'
    try:
        out, err = child.communicate(timeout=15)
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
        report['commands'].append({'case': case, 'command': command, 'cwd': str(cwd),
            'pid': child.pid, 'uid': os.geteuid(), 'startTime': started, 'endTime': time.time(),
            'status': child.returncode, 'timeoutSeconds': 15, 'cleanup': cleanup,
            'stdout': out.decode() if 'out' in locals() else '',
            'stderr': err.decode() if 'err' in locals() else ''})
    assert child.returncode == expected, (case, child.returncode, err.decode())
    return json.loads(out) if expected == 0 else err.decode()


def file_record(path):
    data = path.read_bytes()
    details = path.stat()
    return {'path': str(path), 'sha256': sha(data), 'bytesBase64': base64.b64encode(data).decode(),
                'mode': oct(stat.S_IMODE(details.st_mode)), 'uid': details.st_uid,
                'mtimeNs': details.st_mtime_ns}


def source_hashes():
    return {p.name:sha(p.read_bytes()) for p in SOURCE.iterdir() if p.is_file()}


def parent_check(path):
    if platform.system() != 'Linux' or os.geteuid() == 0:
        raise ValueError('use an ordinary account in the owned Linux lab')
    if path.is_symlink() or not path.is_dir() or path.stat().st_uid != os.geteuid():
        raise ValueError('provide an existing ordinary owned directory')
    if any(path.iterdir()):
        raise ValueError('provide an empty parent; existing files are preserved')
    return path.resolve()


def corrupt_copy(source, target):
    # Make an actual readable gzip archive whose payload no longer matches its manifest.
    with tarfile.open(source, 'r:gz') as old, tarfile.open(target, 'w:gz') as new:
        for original in old.getmembers():
            data = old.extractfile(original).read()
            if original.name == 'data.json':
                data = b'{"message":"Altered private payload"}\n'
            member = tarfile.TarInfo(original.name)
            member.mode = 0o600
            member.size = len(data)
            member.mtime = original.mtime
            new.addfile(member, io.BytesIO(data))
    target.chmod(0o600)


def exercise(parent, policy, kind, reverse, hold):
    before = source_hashes()
    report = {'kind': kind, 'reverse': reverse, 'uid': os.geteuid(), 'commands': [], 'archives': [],
                  'decisions': [], 'restores': [], 'sourceHashes': before, 'sourceUnchanged': False,
                  'learnerWorksheetCompletionInferred': False, 'interrupted': False,
                  'ownedCaseRemoved': False, 'workspaceEmpty': False, 'failure': None}
    ready = parent / 'ready.json'
    case = Path(tempfile.mkdtemp(prefix='recovery-', dir=parent))
    report['ownedCase'] = str(case)
    status = 2
    try:
        current, archives, restored = [case / n for n in ['current', 'archives', 'restored']]
        for directory in [current, archives, restored]:
            directory.mkdir(mode=0o700)
        for name in backup.REQUIRED:
            shutil.copyfile(SOURCE / name, current / name)
        snapshots = []
        for index, message in enumerate(['First fictional state', 'Expected fictional state', 'Later fictional state']):
            (current / 'data.json').write_text(json.dumps({'message':message}, sort_keys=True)+'\n')
            result = run_child(report, 'build generation '+str(index), ['build', current, archives], case)
            archive = Path(result['archive'])
            verified = run_child(report, 'verify generation '+str(index), ['verify', archive], case)
            assert verified['manifest'] == result['manifest']
            if snapshots:
                assert result['manifest']['createdNs'] > snapshots[-1]['manifest']['createdNs'], 'clock moved backward; repeat in a stable lab'
            snapshots.append({'label': ['first','expected','later'][index], 'path': archive,
                                  'manifest': result['manifest'], 'build': result})
        corrupt = archives / 'changed-payload.tar.gz'
        corrupt_copy(snapshots[1]['path'], corrupt)
        tamper_error = run_child(report, 'reject changed payload', ['verify', corrupt], case, 2)
        assert 'digests' in tamper_error
        partial_error = run_child(report, 'reject candidate after write',
                                 ['build', current, archives, '--reject-after-write'], case, 2)
        partials = list(archives.glob('*.partial'))
        assert len(partials) == 1 and 'controlled rejection' in partial_error
        # Deliberately misleading filesystem dates differ from manifest creation order.
        date = time.time_ns()
        for index, snapshot in enumerate(snapshots):
            os.utime(snapshot['path'], ns=(date + (3-index)*1000000000,)*2)
        os.utime(corrupt, ns=(date+5000000000,)*2)
        for snapshot in snapshots:
            report['archives'].append(dict(label=snapshot['label'], manifest=snapshot['manifest'],
                                           build=snapshot['build'], **file_record(snapshot['path'])))
        report['corruptArchive'] = file_record(corrupt)
        report['partialCandidate'] = file_record(partials[0])
        protected = {p.name:sha(p.read_bytes()) for p in archives.iterdir()}
        report['archiveHashesBeforeDecisions'] = protected
        if hold:
            ready.write_text(json.dumps({'pid':os.getpid(), 'uid':os.geteuid(), 'ownedCase':str(case)})+'\n')
            time.sleep(hold)
        order = list(reversed(snapshots)) if reverse else snapshots
        candidates = [item['path'] for item in order]+[corrupt,partials[0]]
        if kind == 'selection':
            for label, target in [('expected', snapshots[1]), ('first', snapshots[0]), ('latest complete', snapshots[2])]:
                cutoff = (backup.validate(partials[0])[1]['createdNs'] if label == 'latest complete'
                          else target['manifest']['createdNs'])
                chosen = policy(candidates, cutoff)
                assert chosen is None or chosen in candidates, 'policy must return a supplied candidate or None'
                passed = chosen == target['path']
                row = {'case': label, 'cutoffNs': cutoff, 'candidates': [str(p) for p in candidates],
                           'selected': str(chosen) if chosen else None, 'expected': str(target['path']),
                           'matchedTarget': passed}
                if chosen:
                    try:
                        _, manifest = backup.validate(chosen)
                        row['selectedManifest'] = manifest
                    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError) as error:
                        row['selectedRejection'] = str(error)
                    else:
                        destination = restored / label
                        result = run_child(report, 'restore selected '+label, ['restore', chosen, destination], case)
                        report['restores'].append({'case': label, 'result': result,
                            'files': {n:file_record(destination/n) for n in backup.REQUIRED}})
                report['decisions'].append(row)
            # There is no eligible recovery point before the first archive.
            chosen = policy(candidates, snapshots[0]['manifest']['createdNs']-1)
            report['decisions'].append({'case': 'no eligible target', 'selected': str(chosen) if chosen else None,
                'expected': None, 'cutoffNs': snapshots[0]['manifest']['createdNs']-1,
                'candidates': [str(p) for p in candidates], 'matchedTarget': chosen is None})
        else:
            destinations = {}
            for snapshot in order:
                destination = restored / snapshot['label']
                result = run_child(report, 'restore '+snapshot['label'], ['restore', snapshot['path'], destination], case)
                destinations[snapshot['label']] = destination
                report['restores'].append({'case': snapshot['label'], 'result': result,
                    'files': {n:file_record(destination/n) for n in backup.REQUIRED}})
            for expected_label in ['expected','first']:
                wanted = next(item for item in snapshots if item['label'] == expected_label)['manifest']['files']
                for snapshot in order:
                    decision = policy(destinations[snapshot['label']], wanted)
                    assert isinstance(decision, bool), 'return a Boolean acceptance decision'
                    expected = snapshot['label'] == expected_label
                    report['decisions'].append({'case': snapshot['label']+' versus '+expected_label,
                        'destination': str(destinations[snapshot['label']]), 'expectedHashes': wanted,
                        'accepted': decision, 'expected': expected, 'matchedTarget': decision == expected})
            missing = destinations['later']
            (missing / 'data.json').unlink()
            decision = policy(missing, snapshots[1]['manifest']['files'])
            report['decisions'].append({'case': 'missing member', 'destination': str(missing),
                'expectedHashes': snapshots[1]['manifest']['files'], 'accepted': decision,
                'expected': False, 'matchedTarget': decision is False})
            destination = destinations['expected']
            original = {n:sha((destination/n).read_bytes()) for n in backup.REQUIRED}
            error = run_child(report, 'reject existing restore destination',
                              ['restore', snapshots[1]['path'], destination], case, 2)
            assert 'new separate destination' in error
            report['existingDestinationUnchanged'] = original == {n:sha((destination/n).read_bytes()) for n in backup.REQUIRED}
        assert {p.name:sha(p.read_bytes()) for p in archives.iterdir()} == protected
        report['archiveHashesAfterDecisions'] = protected
        report['targetBehaviorObserved'] = all(item['matchedTarget'] for item in report['decisions'])
        status = 0 if report['targetBehaviorObserved'] else 1
    except KeyboardInterrupt:
        report['interrupted'] = True
        status = 130
    except BaseException as error:
        LOGGER.exception('Recovery equipment failed; retaining observations')
        report['failure'] = type(error).__name__+': '+str(error)
        status = 2
    finally:
        ready.unlink(missing_ok=True)
        shutil.rmtree(case)
        report['ownedCaseRemoved'] = not case.exists()
        report['workspaceEmpty'] = not any(parent.iterdir())
        report['sourceUnchanged'] = source_hashes() == before
    assert report['ownedCaseRemoved'] and report['workspaceEmpty'] and report['sourceUnchanged']
    print(json.dumps(report, sort_keys=True), flush=True)
    return status


def main(policy, kind):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('parent', type=Path)
    parser.add_argument('--reverse', action='store_true')
    parser.add_argument('--hold-seconds', type=int, default=0)
    args = parser.parse_args()
    try:
        if not 0 <= args.hold_seconds <= MAX_HOLD:
            raise ValueError('hold must be from 0 to '+str(MAX_HOLD))
        parent = parent_check(args.parent)
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2
    return exercise(parent, policy, kind, args.reverse, args.hold_seconds)
