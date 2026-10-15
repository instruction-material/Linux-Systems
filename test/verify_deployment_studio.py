"""Actual release readiness, manifest and independent publisher-lock acceptance."""
import argparse,base64,errno,hashlib,json,os
from pathlib import Path
import platform,shutil,signal,subprocess,tempfile,time
ROOT=Path(__file__).resolve().parents[1]
PACKS=['LS-01-linux-systems-lab-14', 'LS-27-applied-studio-14-linux-systems-lab-14-supplemental-2', 'LS-28-applied-studio-14-linux-systems-lab-14-supplemental-3']
parser=argparse.ArgumentParser();parser.add_argument('--proof',required=True,type=Path);args=parser.parse_args()
assert platform.system()=='Linux' and os.geteuid()>0 and shutil.which('nginx')
args.proof.parent.mkdir(parents=True,exist_ok=True)
rows,events,profiles=[],[],[]
environment=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')


def digest(data):
    return hashlib.sha256(data).hexdigest()

def hashes(root=ROOT):
    return {str(f.relative_to(root)): digest(f.read_bytes()) for pack in PACKS for f in sorted((root / pack).rglob('*')) if f.is_file() and '__pycache__' not in f.parts}

def persist():
    args.proof.with_suffix('.observations.json').write_text(json.dumps(rows, indent=2) + '\n')
    args.proof.with_suffix('.processes.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events))

def run(label, command, cwd, expected, interrupt=None):
    command = [str(x) for x in command]
    started = time.time()
    child = subprocess.Popen(command, cwd=cwd, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    start = dict(parentTask='Linux optional web source acceptance', parentPid=os.getpid(), cwd=str(cwd), command=command,
                 pid=child.pid, startTime=started, timeoutSeconds=45, event='start')
    events.append(start)
    cleanup = 'owned process exited and reaped'
    try:
        if interrupt:
            deadline = time.monotonic() + 10
            while not (interrupt / 'ready.json').exists():
                assert child.poll() is None, 'The observer exited before interruption readiness'
                assert time.monotonic() < deadline, 'No actual owned Nginx readiness record'
                time.sleep(0.01)
            ready = json.loads((interrupt / 'ready.json').read_text())
            assert ready['pid'] > 0
            child.send_signal(signal.SIGINT)
        out, err = child.communicate(timeout=45)
    except BaseException:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
        try:
            out, err = child.communicate(timeout=8)
            cleanup = 'owned process group terminated after failure'
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            out, err = child.communicate()
            cleanup = 'owned process group killed after failure deadline'
        raise
    finally:
        events.append(dict(start, event='end', endTime=time.time(), exitCode=child.returncode, childProcessGroupCleanup=cleanup))
        if child.returncode is not None:
            rows.append(dict(case=label, command=command, cwd=str(cwd), pid=child.pid, status=child.returncode,
                             stdout=out.decode(errors='replace'), stderr=err.decode(errors='replace')))
        persist()
    row = rows[-1]
    assert row['status'] == expected, row
    return row

def headers(row):
    return {key.lower(): value for key, value in row['headers']}

def body(row):
    value = base64.b64decode(row['bodyBase64'], validate=True)
    assert digest(value) == row['bodySha256']
    return value

def report(row, workspace, complete, interrupted=False):
    assert not row['stderr']
    data = json.loads(row['stdout'])
    assert data['uid'] == os.getuid() and data['workspace'] == str(workspace.resolve())
    assert not data['failure'] and not data['learnerWorksheetCompletionInferred']
    assert data['interrupted'] == interrupted and data['observationsCompleted'] == (not interrupted)
    assert data['serverStarted'] and data['serverUid'] == os.getuid() and data['serverPid'] > 0
    assert data['serverParentPid'] == row['pid'] and data['serverTimeoutSeconds'] == 60
    assert data['serverEndTime'] >= data['serverStartTime'] and data['serverReturnCode'] == 0
    assert data['serverCleanup'] == 'owned process exited and reaped'
    assert data['serverPidGone'] and data['listenerClosed'] and data['ownedCaseRemoved'] and data['workspaceEmpty']
    assert not list(workspace.iterdir()) and not (Path('/proc') / str(data['serverPid'])).exists()
    assert len(data['commands']) == 2 and all(c['returnCode'] == 0 and c['pid'] > 0 and c['parentPid'] == row['pid'] for c in data['commands'])
    assert '-v' in data['commands'][0]['command'] and data['commands'][0]['stderr'].startswith('nginx version:')
    assert '-t' in data['commands'][1]['command'] and 'test is successful' in data['commands'][1]['stderr']
    assert '127.0.0.1:' + str(data['port']) in data['configuration']
    assert 'daemon off;' in data['configuration'] and 'master_process off;' in data['configuration']
    if interrupted:
        assert row['status'] == 130 and not data['requests']
    else:
        assert row['status'] == (0 if complete else 1) and data['targetBehaviorObserved'] == complete
        assert data['accessLog']
    for request in data['requests']:
        assert request['peer'] == ['127.0.0.1', data['port']]
        assert request['endTime'] >= request['startTime'] >= data['serverStartTime']
        assert request['endTime'] <= data['serverEndTime']
        assert base64.b64decode(request['requestBase64'], validate=True).endswith(b'\r\n\r\n')
        body(request)
    return data


def readiness(data, target, complete, reverse):
    requests = {row['label']: row for row in data['requests']}
    assert len(requests) == 8 and len(data['deploymentSteps']) == 3
    initial, good = ('release-b', 'release-a') if reverse else ('release-a', 'release-b')
    assert data['initialTarget'] == initial and data['goodTarget'] == good
    expected_health = (target / (good + '-health.txt')).read_bytes()
    expected_page = (target / (good + '-index.txt')).read_bytes()
    assert body(requests['initial health']) == (target / (initial + '-health.txt')).read_bytes()
    assert body(requests['initial page']) == (target / (initial + '-index.txt')).read_bytes()
    good_step, wrong, missing = data['deploymentSteps']
    assert good_step['candidate'] == good and good_step['beforeTarget'] == initial
    assert good_step['readinessAccepted'] and not good_step['rolledBack'] and good_step['afterTarget'] == good
    assert body(requests['good health']) == expected_health and body(requests['good page after decision']) == expected_page
    assert requests['wrong identity health']['status'] == 200
    assert body(requests['wrong identity health']) == (target / 'release-a-health.txt').read_bytes()
    assert base64.b64decode(wrong['expectedHealthBase64']) == b'release=wrong\n'
    assert wrong['readinessAccepted'] == (not complete) and wrong['rolledBack'] == complete
    assert wrong['afterTarget'] == (good if complete else 'wrong')
    assert body(requests['wrong identity page after decision']) == (expected_page if complete else b'Wrong release page.\n')
    assert requests['missing health health']['status'] == 404
    assert not missing['readinessAccepted'] and missing['rolledBack']
    assert missing['beforeTarget'] == missing['afterTarget'] == (good if complete else 'wrong')
    assert body(requests['missing health page after decision']) == (expected_page if complete else b'Wrong release page.\n')
    assert 'open_file_cache off;' in data['configuration']
    assert all(r['status'] == 200 for label, r in requests.items() if label != 'missing health health')


def integrity(data, target, complete, reverse):
    requests = {row['label']: row for row in data['requests']}
    assert len(requests) == 10 and len(data['integritySteps']) == 4
    manifest = json.loads((target / 'release-manifest.json').read_text())
    assert data['manifest'] == manifest and set(manifest) == {'health.txt', 'index.txt'}
    altered = 'health.txt' if reverse else 'index.txt'
    assert data['alteredMember'] == altered
    assert [s['label'] for s in data['integritySteps']] == ['intact', 'tampered', 'missing', 'restored']
    assert [s['integrityAccepted'] for s in data['integritySteps']] == [True, not complete, False, True]
    for step in data['integritySteps']:
        for name, item in step['inspectedFiles'].items():
            original = (target / ('release-b-' + name)).read_bytes()
            assert digest(original) == manifest[name] == item['expected']
            if step['label'] == 'missing' and name == 'index.txt':
                assert not item['exists'] and item['sha256'] is item['contentBase64'] is None
            else:
                expected = original + (b'altered payload\n' if step['label'] == 'tampered' and name == altered else b'')
                assert item['exists'] and base64.b64decode(item['contentBase64']) == expected
                assert digest(expected) == item['sha256']
        assert step['afterTarget'] == ('release-b' if step['integrityAccepted'] else 'release-a')
        for kind in ['health', 'index']:
            label = step['label'] + ' ' + ('page' if kind == 'index' else kind)
            assert requests[label]['status'] == 200
            release = 'release-b' if step['integrityAccepted'] else 'release-a'
            expected = (target / (release + '-' + kind + '.txt')).read_bytes()
            if not complete and step['label'] == 'tampered' and kind + '.txt' == altered:
                expected += b'altered payload\n'
            assert body(requests[label]) == expected


def locking(row, workspace, complete, interrupted=False):
    assert not row['stderr']
    data = json.loads(row['stdout'])
    assert data['uid'] == os.getuid() and data['workspace'] == str(workspace.resolve())
    assert not data['failure'] and not data['learnerWorksheetCompletionInferred']
    assert data['workspaceEmpty'] and data['ownedCaseRemoved'] and data['workerPidsGone']
    assert not list(workspace.iterdir()) and data['interrupted'] == interrupted
    assert data['observationsCompleted'] == (not interrupted)
    for worker in data['workers']:
        assert worker['parentPid'] == row['pid'] and worker['pid'] > 0 and worker['endTime'] >= worker['startTime']
        assert worker['childProcessGroupCleanup'] == 'owned process exited and reaped'
        assert not worker['stderr'] and not (Path('/proc') / str(worker['pid'])).exists()
        result = json.loads(worker['stdout'])
        assert result['pid'] == worker['pid'] and result['parentPid'] == row['pid'] and result['uid'] == os.getuid()
        assert result['lockInode'] == data['lockInode'] and result['descriptorClosed']
        assert result['ended'] >= result['started']
    if interrupted:
        assert row['status'] == 130 and len(data['workers']) == 1 and data['workers'][0]['returnCode'] == 143
        assert len(data['probes']) == 1
    else:
        assert row['status'] == (0 if complete else 1) and data['targetBehaviorObserved'] == complete
        assert len(data['workers']) == 5 and len(data['probes']) == 3
        assert [w['returnCode'] for w in data['workers']] == [0, 75 if complete else 0, 0, 130, 0]
        assert data['secondAcquiredWhileFirstHeld'] == (not complete)
        assert [s['state']['generation'] for s in data['snapshots']] == [0, 1, 1, 2, 2, 3]
        first, second, retry, stopped, recovered = [json.loads(w['stdout']) for w in data['workers']]
        assert first['published'] and first['observedGeneration'] == 0
        assert second['published'] == (not complete) and second['lockAcquired'] == (not complete)
        if not complete:
            assert second['observedGeneration'] == 0 and second['publishedState']['generation'] == 1
            assert data['snapshots'][2]['state']['release'] == second['actor']
        assert retry['published'] and retry['observedGeneration'] == 1 and retry['publishedState']['generation'] == 2
        assert stopped['interrupted'] and not stopped['published'] and stopped['signal'] == signal.SIGINT
        assert recovered['published'] and recovered['observedGeneration'] == 2 and recovered['publishedState']['generation'] == 3
    for probe in data['probes']:
        assert probe['pid'] == row['pid'] and probe['inode'] == data['lockInode']
        blocked = complete and probe['label'] != 'after every publisher exited'
        assert probe['blocked'] == blocked
        assert probe['errno'] in ([errno.EAGAIN, errno.EACCES] if blocked else [None])
    return data


before = hashes()
assert len(before) == 45
with tempfile.TemporaryDirectory(prefix='linux-deployment-studio-') as directory:
    work = Path(directory)
    outside = work / 'outside-sentinel'
    outside.write_bytes(b'outside studio source remains unchanged\n')
    outside_hash = digest(outside.read_bytes())
    caller = work / 'different caller'
    caller.mkdir()
    for index, pack in enumerate(PACKS):
        for role in ['starter', 'solution', 'completed']:
            initial_count = len(rows)
            target = work / (str(index) + '-' + role + ' quoted workspace')
            shutil.copytree(ROOT / pack / ('starter' if role == 'completed' else role), target)
            if role == 'completed':
                path = target / ('publisher.py' if index == 2 else 'task.py')
                old, new = [
                    ("return reply['status'] == 200", "return reply['status'] == 200 and base64.b64decode(reply['bodyBase64']) == expected_health"),
                    ("return all((directory / name).is_file() for name in manifest)", "return all((directory / name).is_file() and hashlib.sha256((directory / name).read_bytes()).hexdigest() == expected for name, expected in manifest.items())"),
                    ('    # TODO: acquire a nonblocking exclusive kernel lock on this open file.\n    return True', '    try:\n        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)\n    except BlockingIOError:\n        return False\n    return True')][index]
                text = path.read_text()
                assert text.count(old) == 1
                path.write_text(text.replace(old, new))
            copied = {str(f.relative_to(target)): digest(f.read_bytes()) for f in target.rglob('*') if f.is_file()}
            lab = work / (str(index) + '-' + role + ' empty lab')
            lab.mkdir()
            complete = role != 'starter'
            scenarios = [('initial studio observation', []), ('changed studio case', ['--reverse'])]
            if index < 2:
                scenarios.append(('studio recovery after syntax rejection', []))
            for label, flags in scenarios:
                if label == 'studio recovery after syntax rejection':
                    rejected = run('actual configuration syntax rejection', ['bash', target / 'task.sh', lab, '--broken-config'], caller, 2)
                    data = json.loads(rejected['stdout'])
                    assert not rejected['stderr'] and not data['serverStarted'] and data['failure']
                    assert 'InvalidCourseDirective' in data['commands'][-1]['stderr'] and data['commands'][-1]['returnCode'] != 0
                    assert data['workspaceEmpty'] and data['ownedCaseRemoved']
                row = run(label, ['bash', target / 'task.sh', lab, *flags], caller, 0 if complete else 1)
                data = locking(row, lab, complete) if index == 2 else report(row, lab, complete)
                if index == 0:
                    readiness(data, target, complete, '--reverse' in flags)
                if index == 1:
                    integrity(data, target, complete, '--reverse' in flags)
            row = run('actual studio observer interruption', ['bash', target / 'task.sh', lab, '--hold-seconds', '8'], caller, 130, interrupt=lab)
            if index == 2:
                locking(row, lab, complete, interrupted=True)
            else:
                report(row, lab, complete, interrupted=True)
            for label, values in [('missing arguments', []), ('invalid hold', [lab, '--hold-seconds', '99']), ('missing workspace', [work / 'absent'])]:
                row = run(label, ['bash', target / 'task.sh', *values], caller, 2)
                assert not row['stdout'] and row['stderr']
            retained = lab / 'retained'
            retained.write_bytes(b'keep this input\n')
            row = run('nonempty workspace retained', ['bash', target / 'task.sh', lab], caller, 2)
            assert not row['stdout'] and row['stderr'] and retained.read_bytes() == b'keep this input\n'
            retained.unlink()
            link = work / (str(index) + '-' + role + ' symlink')
            link.symlink_to(lab, target_is_directory=True)
            row = run('symlink workspace rejected', ['bash', target / 'task.sh', link], caller, 2)
            assert not row['stdout'] and row['stderr'] and link.is_symlink()
            lab.chmod(0o500)
            try:
                row = run('actual private-prefix creation denial', ['bash', target / 'task.sh', lab], caller, 2)
                data = json.loads(row['stdout'])
                assert not row['stderr'] and 'Permission denied' in data['failure'] and data['workspaceEmpty'] and data['ownedCaseRemoved']
                assert not data.get('serverStarted') and not data.get('workers')
            finally:
                lab.chmod(0o700)
            assert not list(lab.iterdir())
            assert copied == {str(f.relative_to(target)): digest(f.read_bytes()) for f in target.rglob('*') if f.is_file()}
            assert digest(outside.read_bytes()) == outside_hash
            expected_cases = 9 if index == 2 else 11
            assert len(rows) - initial_count == expected_cases
            profiles.append(dict(pack=pack, profile=role, actualCases=expected_cases, passed=True, inputsUnchanged=True,
                                 outsideSentinelPreserved=True, ownedResourcesRemoved=True, starterIntentionallyIncomplete=not complete))
assert not work.exists() and hashes() == before and len(rows) == 93 and len(profiles) == 9
reports = [json.loads(row['stdout']) for row in rows if row['stdout'].startswith('{')]
servers = [r for r in reports if r.get('serverStarted')]
workers = [w for r in reports for w in r.get('workers', [])]
http = sum(len(r.get('requests', [])) for r in reports)
assert len(servers) == 24 and len(workers) == 33 and http == 162
proof = dict(nativePassed=True, unprivilegedUid=os.geteuid(), sourceHashes=before, sourceUnchanged=True,
             profiles=profiles, actualCases=93, loggedOuterLifecycles=len(events)//2, actualHttpRequests=http,
             actualNginxLifecycles=len(servers), actualPublisherLifecycles=len(workers), actualObserverInterruptions=9,
             actualPublisherSigintCases=sum(w['returnCode']==130 for w in workers), actualPublisherCleanupTerminations=sum(w['returnCode']==143 for w in workers),
             actualContentionExits=sum(w['returnCode']==75 for w in workers), actualSyntaxRejections=6, actualCreationDenials=9,
             actualNativeCommands=sum(len(r.get('commands', [])) for r in reports), temporaryCasesRemoved=True)
assert proof['loggedOuterLifecycles']==93 and proof['actualNativeCommands']==60 and proof['actualPublisherSigintCases']==6
assert proof['actualPublisherCleanupTerminations']==3 and proof['actualContentionExits']==4
args.proof.write_text(json.dumps(proof,indent=2)+'\n')
persist()
print(json.dumps({k:v for k,v in proof.items() if k!='sourceHashes'}))

