"""Verify scoped incidents, structured responses and actual owned log rotation."""
import argparse
import contextlib
import gzip
import hashlib
import json
import os
import platform
import shutil
import signal
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

CORE = 'LS-09-unit-7-logging-and-observability'
TRANSFER = 'LS-15-unit-7-logging-and-observability-supplemental-2'
RETENTION = 'LS-16-unit-7-logging-and-observability-supplemental-3'
parser = argparse.ArgumentParser()
parser.add_argument('--source-root', type=Path)
parser.add_argument('--proof', required=True, type=Path)
parser.add_argument('--offline-only', action='store_true')
args = parser.parse_args()
ROOT = (args.source_root or Path(__file__).resolve().parents[1]).resolve()
args.proof = args.proof.resolve()
args.proof.parent.mkdir(parents=True, exist_ok=True)
records, processes, profiles = [], [], []
task = os.environ.get('CLASSES_FAMILY_TASK_ID', 'linux-logging-source-ci')


def hashes():
    return {pack + '/' + str(f.relative_to(ROOT / pack)): hashlib.sha256(f.read_bytes()).hexdigest()
            for pack in (CORE, TRANSFER, RETENTION) for f in sorted((ROOT / pack).rglob('*')) if f.is_file()}


def run(command, cwd, expected=0, timeout=12):
    child = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, start_new_session=True)
    entry = {"parentTaskId": task, "parentPid": os.getpid(), "pid": child.pid, "command": command, "cwd": str(cwd), "startTime": time.time(), "timeoutSeconds": timeout}
    processes.append(dict(entry, event='start'))
    cleanup = 'process exited'
    try:
        out, err = child.communicate(timeout=timeout)
    except BaseException:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(child.pid, signal.SIGTERM)
        try:
            child.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.communicate()
        cleanup = 'owned process group terminated'
        raise
    finally:
        processes.append(dict(entry, event='end', endTime=time.time(), exitCode=child.returncode,
                              childProcessGroupCleanup=cleanup))
    result = {"kind": 'command', "command": command, "status": child.returncode, "stdout": out.decode(errors='replace'), "stderr": err.decode(errors='replace')}
    records.append(result)
    assert expected is None or child.returncode == expected, result
    return result


def prepare(pack, role, parent):
    work = parent / (pack + '-' + role)
    original = ROOT / pack / ('starter' if role == 'independent-completion' else role)
    shutil.copytree(original, work)
    if role == 'independent-completion':
        if pack == CORE:
            file = work / 'task.sh'
            text = file.read_text()
            unfinished = '    # TODO: require the requested unit, boot and inclusive time window.\n    return None'
            replacement = '    selected_unit = row.get("_SYSTEMD_USER_UNIT") or row.get("USER_UNIT")\n    if selected_unit != unit or row.get("_BOOT_ID") != boot:\n        return False\n    stamp = int(row["__REALTIME_TIMESTAMP"])\n    return stamp >= begin and stamp <= end'
            assert text.count(unfinished) == 1
            file.write_text(text.replace(unfinished, replacement))
        elif pack == TRANSFER:
            file = work / 'task.sh'
            text = file.read_text()
            unfinished = '    # TODO: classify completed server-error responses from their numeric status.\n    return None'
            replacement = '    if row["event"] != "complete":\n        return False\n    status = row["status"]\n    return status >= 500 and status < 600'
            assert text.count(unfinished) == 1
            file.write_text(text.replace(unfinished, replacement))
        else:
            file = work / 'logrotate.conf'
            text = file.read_text()
            assert text.count('rotate TODO') == 1
            file.write_text(text.replace('rotate TODO', 'rotate 2'))
    return work


def analyze_core(work, file, unit='linux-observe-demo.service', boot='a' * 32, begin=100, end=500, expected=0):
    result = run(['bash', 'task.sh', str(file), unit, boot, str(begin), str(end)], work, expected)
    return json.loads(result['stdout']) if expected == 0 else result


def analyze_transfer(work, file, request='case-7', expected=0):
    result = run(['bash', 'task.sh', str(file), request], work, expected)
    return json.loads(result['stdout']) if expected == 0 else result


def write_rows(file, rows):
    file.write_text(''.join(json.dumps(row) + '\n' for row in rows))


def offline_core(work, role):
    if role == 'starter':
        result = analyze_core(work, work / 'sample.log', expected=78)
        assert 'Complete in_scope' in result['stderr']
        return {"namedUnfinishedStatus": 78}
    report = analyze_core(work, work / 'sample.log')
    assert report['eventCount'] == 5 and report['errors'] == 1
    assert report['firstError'] == 'case: event=config_missing' and report['firstErrorTime'] == '200'
    assert report['recovered'] and report['recoveryTime'] == '400'
    assert not analyze_core(work, work / 'sample.log', end=300)['recovered']
    assert analyze_core(work, work / 'sample.log', unit='other.service')['eventCount'] == 0
    assert analyze_core(work, work / 'sample.log', boot='c' * 32)['eventCount'] == 0
    analyze_core(work, work / 'missing.log', expected=2)
    analyze_core(work, work / 'sample.log', begin=500, end=100, expected=2)
    rows = [json.loads(line) for line in (work / 'sample.log').read_text().splitlines()]
    changed = work / 'changed.log'
    write_rows(changed, list(reversed(rows)))
    assert analyze_core(work, changed) == report
    rows[3]['_SYSTEMD_INVOCATION_ID'] = rows[1]['_SYSTEMD_INVOCATION_ID']
    write_rows(changed, rows)
    assert not analyze_core(work, changed)['recovered']
    rows[3]['_SYSTEMD_INVOCATION_ID'] = 'new'
    rows[3]['__REALTIME_TIMESTAMP'] = '200'
    write_rows(changed, rows)
    assert not analyze_core(work, changed)['recovered']
    latest_rows = [json.loads(line) for line in (work / 'sample.log').read_text().splitlines()]
    latest_rows.append(dict(latest_rows[1], __REALTIME_TIMESTAMP='480', MESSAGE='case: event=config_invalid', _SYSTEMD_INVOCATION_ID='later-failure'))
    write_rows(changed, latest_rows)
    reopened = analyze_core(work, changed)
    assert reopened['firstError'] == 'case: event=config_missing' and reopened['latestError'] == 'case: event=config_invalid' and not reopened['recovered']
    latest_rows.append(dict(latest_rows[3], __REALTIME_TIMESTAMP='490', _SYSTEMD_INVOCATION_ID='new-retest'))
    write_rows(changed, latest_rows)
    assert analyze_core(work, changed)['recovered']
    changed.write_text('not-json\n')
    analyze_core(work, changed, expected=2)
    changed.write_text('')
    assert analyze_core(work, changed)['eventCount'] == 0
    return {"exactRedactedTimeline": True, "scopeAndTimeBoundaries": True, "priorityNotMessageWords": True, "shuffledInput": True, "sameInvocationNotRecovery": True, "equalTimestampNotRecovery": True, "emptySelectionNotHealth": True, "invalidInputVisible": True}


def offline_transfer(work, role):
    if role == 'starter':
        result = analyze_transfer(work, work / 'sample.log', expected=78)
        assert 'Complete is_server_failure' in result['stderr']
        return {"namedUnfinishedStatus": 78}
    report = analyze_transfer(work, work / 'sample.log')
    assert report == {"request": 'case-7', "events": 4, "serverFailures": 1, "statuses": [503, 200], "lastStatus": 200, "recovered": True}
    assert analyze_transfer(work, work / 'sample.log', 'absent')['lastStatus'] is None
    analyze_transfer(work, work / 'absent.log', expected=2)
    rows = [json.loads(line) for line in (work / 'sample.log').read_text().splitlines()]
    changed = work / 'changed.log'
    write_rows(changed, list(reversed(rows)))
    assert analyze_transfer(work, changed) == report
    rows[1]['status'] = 400
    write_rows(changed, rows)
    assert analyze_transfer(work, changed)['serverFailures'] == 0
    rows[1]['status'] = 599
    rows[3]['time'] = '2026-01-01T13:00:03+01:00'
    write_rows(changed, rows)
    assert analyze_transfer(work, changed)['serverFailures'] == 1
    assert analyze_transfer(work, changed)['recovered']
    write_rows(changed, rows[:3])
    assert not analyze_transfer(work, changed)['recovered']
    latest_rows = [*rows, {"time": '2026-01-01T12:00:04Z', "request": 'case-7', "event": 'complete', "status": 503, "message": 'dependency failed again'}]
    write_rows(changed, latest_rows)
    reopened = analyze_transfer(work, changed)
    assert reopened['lastStatus'] == 503 and not reopened['recovered']
    latest_rows.append({"time": '2026-01-01T12:00:05Z', "request": 'case-7', "event": 'complete', "status": 200, "message": 'latest retry completed'})
    write_rows(changed, latest_rows)
    assert analyze_transfer(work, changed)['recovered']
    rows[1]['status'] = True
    write_rows(changed, rows)
    analyze_transfer(work, changed, expected=2)
    rows[1]['status'] = '503'
    write_rows(changed, rows)
    analyze_transfer(work, changed, expected=2)
    rows[1]['status'] = 503
    rows[1]['time'] = '2026-01-01T12:00:01'
    write_rows(changed, rows)
    analyze_transfer(work, changed, expected=2)
    changed.write_text('not-json\n')
    analyze_transfer(work, changed, expected=2)
    return {"exactRequestTimeline": True, "numericCompletedStatuses": True, "clientStatusNotServerFailure": True, "boundary599": True, "unrelatedRequestExcluded": True, "shuffledInput": True, "offsetTimeComparedAsInstant": True, "incompleteRetryNotRecovery": True, "invalidInputVisible": True}


def properties(unit, work):
    text = run(['systemctl', '--user', 'show', unit, '-p',
                'LoadState,ActiveState,SubState,ExecMainStatus,InvocationID'], work)['stdout']
    return dict(line.split('=', 1) for line in text.splitlines() if '=' in line)


def native_core(work, role):
    lab = work / 'actual incident with spaces'
    lab.mkdir(mode=0o700)
    shutil.copy2(work / 'incident_app.sh', lab / 'incident_app.sh')
    unit = 'linux-observe-ci-' + uuid.uuid4().hex + '.service'
    unit_file = Path.home() / '.config/systemd/user' / unit
    unit_file.parent.mkdir(parents=True, exist_ok=True)
    assert not unit_file.exists()
    unit_file.write_text((work / 'linux-logging-case.service').read_text().replace('__LAB__', str(lab)))
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip().replace('-', '')
    begin = time.time_ns() // 1000
    try:
        run(['systemctl', '--user', 'daemon-reload'], work)
        first = run(['systemctl', '--user', 'start', unit], work, expected=None)
        assert first['status'] != 0
        state = properties(unit, work)
        assert state['ActiveState'] == 'failed' and state['ExecMainStatus'] == '2'
        failed_invocation = state['InvocationID']
        (lab / 'case.conf').write_text('enabled=yes\n')
        run(['systemctl', '--user', 'reset-failed', unit], work)
        run(['systemctl', '--user', 'start', unit], work)
        ready = properties(unit, work)
        assert ready['ActiveState'] == 'active' and ready['SubState'] == 'exited' and ready['ExecMainStatus'] == '0'
        assert ready['InvocationID'] and ready['InvocationID'] != failed_invocation
        end = time.time_ns() // 1000
        deadline = time.monotonic() + 8
        while True:
            output = run(['journalctl', '--user', '-u', unit, '-b', '--no-pager', '-o', 'json'], work)['stdout']
            rows = [json.loads(line) for line in output.splitlines() if line.startswith('{')]
            application = [row for row in rows if row.get('SYSLOG_IDENTIFIER') == 'linux-observe-case']
            errors = [row for row in application if row.get('MESSAGE') == 'case: event=config_missing']
            healthy = [row for row in application if row.get('MESSAGE') == 'case: event=ready']
            if errors and healthy:
                break
            assert time.monotonic() < deadline, rows
            time.sleep(0.1)
        assert all(row.get('_UID') == str(os.geteuid()) and row.get('_BOOT_ID') == boot and int(row['_PID']) > 0 for row in application)
        assert errors[0]['PRIORITY'] == '3' and healthy[0]['PRIORITY'] == '6'
        assert errors[0]['_SYSTEMD_INVOCATION_ID'] != healthy[0]['_SYSTEMD_INVOCATION_ID']
        end = max(time.time_ns() // 1000, max(int(row['__REALTIME_TIMESTAMP']) for row in rows))
        export = lab / 'incident.log'
        export.write_text(output)
        if role == 'starter':
            analyze_core(work, export, unit, boot, begin, end, expected=78)
        else:
            report = analyze_core(work, export, unit, boot, begin, end)
            assert report['firstError'] == 'case: event=config_missing' and report['recovered']
            assert report['firstErrorTime'] == errors[0]['__REALTIME_TIMESTAMP']
            assert report['recoveryTime'] == healthy[0]['__REALTIME_TIMESTAMP']
        run(['systemctl', '--user', 'stop', unit], work)
        (lab / 'case.conf').write_text('enabled=no\n')
        broken = run(['systemctl', '--user', 'start', unit], work, expected=None)
        assert broken['status'] != 0 and properties(unit, work)['ExecMainStatus'] == '2'
        deadline = time.monotonic() + 8
        while True:
            output2 = run(['journalctl', '--user', '-u', unit, '-b', '--no-pager', '-o', 'json'], work)['stdout']
            if any(row.get('MESSAGE') == 'case: event=config_invalid' for row in [json.loads(line) for line in output2.splitlines() if line.startswith('{')]):
                break
            assert time.monotonic() < deadline
            time.sleep(0.1)
        if role != 'starter':
            export.write_text(output2)
            latest_rows = [json.loads(line) for line in output2.splitlines() if line.startswith('{')]
            latest_end = max(time.time_ns() // 1000, max(int(row['__REALTIME_TIMESTAMP']) for row in latest_rows))
            reopened = analyze_core(work, export, unit, boot, begin, latest_end)
            assert reopened['latestError'] == 'case: event=config_invalid' and not reopened['recovered']
            records.append({'kind': 'latest-failure-analysis', 'role': role, 'unit': unit, 'report': reopened})
        (lab / 'case.conf').write_text('enabled=yes\n')
        run(['systemctl', '--user', 'reset-failed', unit], work)
        run(['systemctl', '--user', 'start', unit], work)
        assert properties(unit, work)['ExecMainStatus'] == '0'
        records.append({"kind": 'actual-journal', "role": role, "unit": unit, "uid": os.geteuid(), "boot": boot, "applicationRows": application, "missingState": state, "readyState": ready})
        return {"actualManager": True, "actualJournal": True, "actualUidPidBoot": True, "actualPriority": True, "missingConfigurationExit2": True, "newInvocationRecovery": True, "invalidConfigurationAndRecovery": True, "spaceContainingPaths": True}
    finally:
        run(['systemctl', '--user', 'stop', unit], work, expected=None)
        unit_file.unlink(missing_ok=True)
        run(['systemctl', '--user', 'daemon-reload'], work)
        run(['systemctl', '--user', 'reset-failed', unit], work, expected=None)
        state = properties(unit, work)
        assert state['LoadState'] == 'not-found' and state['ActiveState'] == 'inactive'
        shutil.rmtree(lab)
        records.append({"kind": 'cleanup', "role": role, "unit": unit, "unitRemoved": not unit_file.exists(), "inactive": True, "installRemoved": not lab.exists()})


def native_rotation(work, role, parent):
    lab = work / 'actual retention with spaces'
    lab.mkdir(mode=0o700)
    marker = lab / '.linux-log-lab'
    marker.write_text('linux-log-retention-v1\n')
    active = lab / 'app.log'
    active.write_text('batch-one\n')
    sentinel = parent / ('unrelated-' + role + '.log')
    sentinel.write_text('outside log unchanged\n')
    before = hashlib.sha256(sentinel.read_bytes()).hexdigest()
    try:
        if role == 'starter':
            result = run(['bash', 'task.sh', str(lab)], work, expected=1)
            assert 'bad rotation count' in result['stderr'].lower(), result
            assert active.read_text() == 'batch-one\n' and not list(lab.glob('app.log.*'))
            return {"namedPolicyFailure": True, "failedBeforeRotation": True, "actualLogrotate": True, "spaceContainingPaths": True}
        for number, word in enumerate(['one', 'two', 'three'], 1):
            if number > 1:
                active.write_text('batch-' + word + '\n')
            run(['bash', 'task.sh', str(lab)], work)
            created_mode = active.stat().st_mode & 0o777
            assert active.read_bytes() == b'' and created_mode == 0o600
            assert gzip.decompress((lab / 'app.log.1.gz').read_bytes()) == ('batch-' + word + '\n').encode()
        assert sorted(file.name for file in lab.glob('app.log.*')) == ['app.log.1.gz', 'app.log.2.gz']
        assert gzip.decompress((lab / 'app.log.2.gz').read_bytes()) == b'batch-two\n'
        snapshot = {file.name: hashlib.sha256(file.read_bytes()).hexdigest() for file in lab.glob('app.log.*')}
        run(['bash', 'task.sh', str(lab)], work)
        assert snapshot == {file.name: hashlib.sha256(file.read_bytes()).hexdigest() for file in lab.glob('app.log.*')}
        state = (lab / 'rotation.state').read_bytes()
        active.write_text('batch-four\n')
        run(['logrotate', '--debug', '--state', str(lab / 'rotation.state'), str(lab / 'rotation.conf')], work)
        assert active.read_text() == 'batch-four\n' and (lab / 'rotation.state').read_bytes() == state
        assert snapshot == {file.name: hashlib.sha256(file.read_bytes()).hexdigest() for file in lab.glob('app.log.*')}
        marker.unlink()
        run(['bash', 'task.sh', str(lab)], work, expected=2)
        marker.write_text('linux-log-retention-v1\n')
        active.unlink()
        active.symlink_to(sentinel)
        run(['bash', 'task.sh', str(lab)], work, expected=2)
        active.unlink()
        active.write_text('batch-four\n')
        assert hashlib.sha256(sentinel.read_bytes()).hexdigest() == before
        records.append({"kind": 'actual-retention', "role": role, "archiveHashes": snapshot, "retainedNewest": b'batch-three\n'.decode(), "retainedOlder": b'batch-two\n'.decode(), "createdActiveMode": oct(created_mode), "sentinelHash": before})
        return {"actualLogrotate": True, "actualCompressedContents": True, "twoArchiveRetention": True, "oldestExpired": True, "privateActiveFileCreated": True, "emptyRunLeavesArchives": True, "debugDoesNotRotateOrChangeState": True, "activeFileWritable": True, "sentinelUnchanged": True, "missingMarkerRejected": True, "symlinkRejectedBeforeRotation": True, "spaceContainingPaths": True}
    finally:
        assert hashlib.sha256(sentinel.read_bytes()).hexdigest() == before
        shutil.rmtree(lab)
        records.append({"kind": 'cleanup', "role": role, "retentionRemoved": not lab.exists(), "sentinelUnchanged": True})


before = hashes()
accepted = False
finished = False
try:
    if not args.offline_only:
        assert platform.system() == 'Linux' and os.geteuid() != 0
        for command in ['systemctl', 'journalctl', 'logrotate', 'stat', 'bash']:
            assert shutil.which(command), command
        run(['systemctl', '--user', 'show-environment'], ROOT)
        manager = run(['systemctl', '--version'], ROOT)['stdout'].splitlines()[0]
        rotation_version = run(['logrotate', '--version'], ROOT)['stdout'].splitlines()[0]
    else:
        manager = rotation_version = None
    with tempfile.TemporaryDirectory(prefix='linux-logging-contracts-') as directory:
        parent = Path(directory)
        for pack, kind in [(CORE, 'journal'), (TRANSFER, 'application'), (RETENTION, 'retention')]:
            for role in ['starter', 'solution', 'independent-completion']:
                work = prepare(pack, role, parent)
                if kind == 'journal':
                    result = offline_core(work, role)
                    if not args.offline_only:
                        result.update(native_core(work, role))
                elif kind == 'application':
                    result = offline_transfer(work, role)
                elif args.offline_only:
                    continue
                else:
                    result = native_rotation(work, role, parent)
                profiles.append(dict(kind=kind, role=role, **result))
    assert not parent.exists()
    assert hashes() == before
    assert len(profiles) == (6 if args.offline_only else 9)
    finished = True
    accepted = not args.offline_only
finally:
    proof = {"accepted": accepted, "offlineOnly": args.offline_only, "preflightPassed": finished and hashes() == before, "managerVersion": locals().get('manager'), "logrotateVersion": locals().get('rotation_version'), "platform": platform.platform(), "profiles": profiles, "observations": records, "sourceHashes": before, "sourceUnchanged": hashes() == before, "temporaryFilesCleaned": not locals().get('parent', Path('/')).exists()}
    args.proof.write_text(json.dumps(proof, indent=2) + '\n')
    args.proof.with_suffix('.processes.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in processes))
print(json.dumps({'accepted': accepted, 'offlineOnly': args.offline_only, 'profiles': len(profiles), 'observations': len(records), 'sourceFiles': len(before)}))
