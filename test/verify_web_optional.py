"""Exercise actual Nginx, HTTP responses, failure paths and owned cleanup."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
PACKS = ['LS-23-unit-11-web-servers-supplemental-2', 'LS-24-unit-11-web-servers-supplemental-3']
parser = argparse.ArgumentParser()
parser.add_argument('--proof', required=True, type=Path)
args = parser.parse_args()
assert platform.system() == 'Linux' and os.geteuid() > 0
assert shutil.which('nginx')
args.proof.parent.mkdir(parents=True, exist_ok=True)
rows, events, profiles = [], [], []
environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')

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
            assert ready['pid'] > 0 and ready['port'] > 1023
            child.send_signal(signal.SIGINT)
        out, err = child.communicate(timeout=45)
    except BaseException:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGKILL)
        out, err = child.communicate()
        cleanup = 'owned process group killed after failure'
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

def routing(data, target, complete, reverse):
    requests = {r['label']: r for r in data['requests']}
    assert len(requests) == 9
    assert data['explicitDefault'] == complete
    assert data['namedSiteOrder'] == (['beta.test', 'alpha.test'] if reverse else ['alpha.test', 'beta.test'])
    alpha, beta = (target / 'alpha.txt').read_bytes(), (target / 'beta.txt').read_bytes()
    for label, expected in [('named alpha', alpha), ('named beta', beta), ('uppercase name and explicit port', alpha)]:
        row = requests[label]
        assert row['status'] == 200 and body(row) == expected
    for label in ['unmatched name', 'IP host', 'HTTP1.0 without Host']:
        row = requests[label]
        assert row['status'] == (404 if complete else 200)
        if not complete:
            assert body(row) == (beta if reverse else alpha)
        else:
            assert body(row) not in [alpha, beta]
    assert requests['HTTP1.1 without Host']['status'] == 400
    assert requests['known name missing file']['status'] == 404
    head = requests['HEAD known file']
    assert head['status'] == 200 and not body(head) and int(headers(head)['content-length']) == len(alpha)

def conditional(data, target, complete):
    requests = {r['label']: r for r in data['requests']}
    assert len(requests) == 10 and data['etagSetting'] == ('on' if complete else 'off')
    first = requests['initial representation']
    initial = (target / 'resource.txt').read_bytes()
    assert first['status'] == 200 and body(first) == initial
    assert ('etag' in headers(first)) == complete
    assert headers(first)['last-modified']
    assert requests['matching modification date']['status'] == 304 and not body(requests['matching modification date'])
    assert requests['different entity validator']['status'] == 200 and body(requests['different entity validator']) == initial
    head = requests['HEAD representation']
    assert head['status'] == 200 and not body(head) and int(headers(head)['content-length']) == len(initial)
    updated = requests['old validator after changed file']
    changed = initial + b'changed size and timestamp\n'
    assert updated['status'] == 200 and body(updated) == changed
    hidden = requests['same metadata different bytes']
    same_size = bytes([changed[0] ^ 1]) + changed[1:]
    assert hidden['status'] == 200 and body(hidden) == same_size and same_size != changed
    for label in ['matching entity validator', 'current validator after changed file', 'validator after same metadata edit']:
        row = requests[label]
        assert row['status'] == (304 if complete else 200)
        if complete:
            assert not body(row)
    if complete:
        assert headers(first)['etag'] != headers(updated)['etag'] == headers(hidden)['etag']
    assert requests['missing representation']['status'] == 404
    assert all(headers(r)['cache-control'] == 'max-age=0, must-revalidate' for r in requests.values())
    changes = data['fileChanges']
    assert changes['initialSha256'] == digest(initial) and changes['updatedSha256'] == digest(changed)
    assert changes['sameMetadataSha256'] == digest(same_size)
    assert changes['initialSize'] == len(initial) and changes['updatedSize'] == changes['sameMetadataSize'] == len(changed)
    assert changes['updatedMtimeNs'] == changes['sameMetadataMtimeNs'] == changes['initialMtimeNs'] + 2000000000

before = hashes()
assert len(before) == 24
with tempfile.TemporaryDirectory(prefix='linux-web-') as directory:
    work = Path(directory)
    outside = work / 'outside-sentinel'
    outside.write_bytes(b'retain outside bytes\n')
    outside_hash = digest(outside.read_bytes())
    caller = work / 'different caller'
    caller.mkdir()
    for index, pack in enumerate(PACKS):
        for role in ['starter', 'solution', 'completed']:
            initial_count = len(rows)
            target = work / (str(index) + '-' + role + ' quoted workspace')
            shutil.copytree(ROOT / pack / ('starter' if role == 'completed' else role), target)
            if role == 'completed':
                path = target / 'task.py'
                old, new = ('explicit_default = False', 'explicit_default = True') if index == 0 else ("etag_setting = 'off'", "etag_setting = 'on'")
                text = path.read_text()
                assert text.count(old) == 1
                path.write_text(text.replace(old, new))
            copied = {str(f.relative_to(target)): digest(f.read_bytes()) for f in target.rglob('*') if f.is_file()}
            lab = work / (str(index) + '-' + role + ' empty lab')
            lab.mkdir()
            complete = role != 'starter'
            for label, flags, reverse in [('initial native web observation', [], False), ('changed order or repeated conditional observation', ['--reverse'] if index == 0 else [], index == 0)]:
                row = run(label, ['bash', target / 'task.sh', lab, *flags], caller, 0 if complete else 1)
                data = report(row, lab, complete)
                if index == 0:
                    routing(data, target, complete, reverse)
                else:
                    conditional(data, target, complete)
            row = run('actual configuration syntax rejection', ['bash', target / 'task.sh', lab, '--broken-config'], caller, 2)
            data = json.loads(row['stdout'])
            assert not row['stderr'] and not data['serverStarted'] and not data['observationsCompleted']
            assert data['failure'] and 'InvalidCourseDirective' in data['commands'][-1]['stderr']
            assert data['commands'][-1]['returnCode'] != 0 and data['ownedCaseRemoved'] and data['workspaceEmpty']
            row = run('native recovery after configuration rejection', ['bash', target / 'task.sh', lab], target, 0 if complete else 1)
            data = report(row, lab, complete)
            if index == 0:
                routing(data, target, complete, False)
            else:
                conditional(data, target, complete)
            row = run('actual held-server interruption', ['bash', target / 'task.sh', lab, '--hold-seconds', '8'], caller, 130, interrupt=lab)
            report(row, lab, complete, interrupted=True)
            for label, values in [('missing arguments', []), ('invalid hold', [lab, '--hold-seconds', '99']), ('missing workspace', [work / 'absent'])]:
                row = run(label, ['bash', target / 'task.sh', *values], caller, 2)
                assert not row['stdout'] and row['stderr']
            retained = lab / 'retained'
            retained.write_bytes(b'retain this input\n')
            row = run('nonempty workspace retained', ['bash', target / 'task.sh', lab], caller, 2)
            assert not row['stdout'] and row['stderr'] and retained.read_bytes() == b'retain this input\n'
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
                assert not data['serverStarted'] and not data['commands']
            finally:
                lab.chmod(0o700)
            assert not list(lab.iterdir())
            assert copied == {str(f.relative_to(target)): digest(f.read_bytes()) for f in target.rglob('*') if f.is_file()}
            assert digest(outside.read_bytes()) == outside_hash
            assert len(rows) - initial_count == 11
            profiles.append(dict(pack=pack, profile=role, actualCases=11, passed=True, inputsUnchanged=True,
                                 outsideSentinelPreserved=True, ownedResourcesRemoved=True, starterIntentionallyIncomplete=not complete))
assert not work.exists() and hashes() == before and len(rows) == 66 and len(profiles) == 6
reports = [json.loads(r['stdout']) for r in rows if r['stdout'].startswith('{')]
http = sum(len(r['requests']) for r in reports)
servers = [r for r in reports if r['serverStarted']]
assert http == 171 and len(servers) == 24
proof = dict(nativePassed=True, unprivilegedUid=os.geteuid(), sourceHashes=before, sourceUnchanged=True,
             profiles=profiles, actualCases=len(rows), loggedOuterLifecycles=len(events) // 2,
             actualHttpRequests=http, actualNginxLifecycles=len(servers), actualInterruptedNginxLifecycles=6,
             actualSyntaxRejections=6, actualCreationDenials=6,
             temporaryCasesRemoved=True, actualNativeCommands=sum(len(r['commands']) for r in reports))
assert proof['loggedOuterLifecycles'] == 66 and proof['actualNativeCommands'] == 60
args.proof.write_text(json.dumps(proof, indent=2) + '\n')
persist()
print(json.dumps({k: v for k, v in proof.items() if k != 'sourceHashes'}))
