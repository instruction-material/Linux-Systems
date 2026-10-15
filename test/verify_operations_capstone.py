"""Exercise the real owned capstone service, timer, proxy and restore workflow."""
import argparse
import base64
import hashlib
import io
import json
import logging
import os
import platform
import re
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import traceback
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = 'LS-04-linux-systems-lab-17'
TASK = os.environ.get('CLASSES_FAMILY_TASK_ID', 'linux-operations-capstone-source')
ENV = dict(os.environ, LC_ALL='C', BASH_ENV='/dev/null', ENV='/dev/null')
rows, events, requests, profiles = [], [], [], []
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
logger = logging.getLogger(__name__)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source_hashes():
    return {str(f.relative_to(ROOT)): sha(f.read_bytes())
            for f in sorted((ROOT / PACK).rglob('*')) if f.is_file()}


def launch(label, command, cwd):
    child = subprocess.Popen([str(a) for a in command], cwd=cwd, env=ENV,
                             stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, start_new_session=True)
    entry = {'parentTaskId': TASK, 'parentPid': os.getpid(), 'case': label, 'command': [str(a) for a in command], 'cwd': str(cwd), 'pid': child.pid, 'startTime': time.time(), 'timeoutSeconds': 30}
    events.append(dict(entry, event='start'))
    return child, entry


def finish(child, entry, expected=None, send=None):
    cleanup = 'owned process exited and reaped'
    try:
        if send is not None and child.poll() is None:
            os.killpg(child.pid, send)
        out, err = child.communicate(timeout=30)
    except BaseException:
        cleanup = 'owned process group terminated after failure or deadline'
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
        try:
            child.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.communicate()
        raise
    finally:
        events.append(dict(entry, event='end', endTime=time.time(), exitCode=child.returncode,
                           childProcessGroupCleanup=cleanup))
    try:
        os.killpg(child.pid, 0)
    except ProcessLookupError:
        pass
    else:
        os.killpg(child.pid, signal.SIGKILL)
        raise AssertionError('An owned child process group survived its command')
    row = dict(entry, status=child.returncode, stdout=out.decode(), stderr=err.decode())
    rows.append(row)
    if expected is not None:
        assert row['status'] == expected, row
    return row


def run(label, command, cwd, expected=0):
    return finish(*launch(label, command, cwd), expected=expected)


def admin(label, command, cwd, expected=0):
    return run(label, ['sudo', '-n', *command], cwd, expected)


def fields(row):
    return dict(line.split('=', 1) for line in row['stdout'].splitlines() if '=' in line)


def http(label, port, path='/health'):
    record = {'case': label, 'host': '127.0.0.1', 'port': port, 'path': path, 'at': time.time()}
    try:
        with opener.open('http://127.0.0.1:' + str(port) + path, timeout=2) as response:
            record.update(status=response.status, bodyBase64=base64.b64encode(response.read()).decode(),
                          headers=dict(response.headers))
    except urllib.error.HTTPError as response:
        record.update(status=response.code, bodyBase64=base64.b64encode(response.read()).decode(),
                      headers=dict(response.headers))
    except urllib.error.URLError as error:
        record.update(status=0, bodyBase64='', transportError=str(error.reason),
                      errno=getattr(error.reason, 'errno', None))
    requests.append(record)
    return record


def body(record):
    return json.loads(base64.b64decode(record['bodyBase64']))


def wait_until(action, predicate, seconds=12):
    deadline = time.monotonic() + seconds
    while True:
        result = action()
        if predicate(result):
            return result
        assert time.monotonic() < deadline, result
        time.sleep(0.1)


def port_pair():
    with socket.socket() as first, socket.socket() as second:
        first.bind(('127.0.0.1', 0))
        second.bind(('127.0.0.1', 0))
        return first.getsockname()[1], second.getsockname()[1]


def birth(pid):
    try:
        return Path('/proc/' + str(pid) + '/stat').read_text().rsplit(')', 1)[1].split()[19]
    except FileNotFoundError:
        return None


def file_record(path):
    details = path.stat()
    data = path.read_bytes()
    return {'path': str(path), 'uid': details.st_uid, 'gid': details.st_gid, 'mode': oct(stat.S_IMODE(details.st_mode)), 'sha256': sha(data), 'bytesBase64': base64.b64encode(data).decode()}


class Lab:
    def __init__(self, profile, role, work):
        self.profile, self.role, self.work = profile, role, work
        self.id = uuid.uuid4().hex
        self.root = Path('/srv/classes-capstone-' + self.id)
        self.unit = 'cls-cap-' + self.id[:12]
        self.app_port, self.proxy_port = port_pair()
        self.installed, self.created, self.nginx = {}, False, None
        self.app_pids, self.evidence = {}, {}
        self.dropin = Path('/run/systemd/system') / (self.unit + '.service.d')
        self.dropin_created = False

    def ctl(self, label, *args, expected=0):
        return admin(self.profile + ' ' + label, ['systemctl', '--system', *args], self.work, expected)

    def state(self, suffix='.service'):
        return self.ctl('manager state ' + suffix, 'show', self.unit + suffix,
                        '-p', 'LoadState', '-p', 'ActiveState', '-p', 'SubState', '-p', 'MainPID',
                        '-p', 'Result', '-p', 'ExecMainStatus', '-p', 'NRestarts', '-p', 'InvocationID',
                        '-p', 'DynamicUser', '-p', 'User', '-p', 'WorkingDirectory', '-p', 'ControlGroup',
                        '-p', 'LastTriggerUSec', expected=None)

    def journal(self, suffix='.service'):
        row = admin(self.profile + ' scoped journal ' + suffix,
                    ['journalctl', '--no-pager', '-u', self.unit + suffix, '-o', 'json', '-n', '200'], self.work)
        parsed = [json.loads(line) for line in row['stdout'].splitlines() if line.strip()]
        assert parsed
        return parsed

    def prepare(self):
        assert re.fullmatch(r'/srv/classes-capstone-[0-9a-f]{32}', str(self.root))
        assert not self.root.exists() and not self.root.is_symlink() and not self.dropin.exists()
        assert fields(self.state()).get('LoadState') == 'not-found'
        admin(self.profile + ' create fresh root', ['mkdir', '--', self.root], self.work)
        self.created = True
        admin(self.profile + ' assign operator ownership', ['chown', str(os.geteuid()) + ':' + str(os.getegid()), '--', self.root], self.work)
        self.root.chmod(0o755)
        marker = self.root / 'outside-marker'
        marker.write_bytes(b'preserve a nonempty input\n')
        command = ['bash', self.role/'task.sh', 'render', '--root', self.root, '--id', self.id,
                   '--app-port', self.app_port, '--proxy-port', self.proxy_port]
        run(self.profile + ' reject nonempty render target', command, self.work, 2)
        assert marker.read_bytes() == b'preserve a nonempty input\n'
        marker.unlink()
        rendered = json.loads(run(self.profile + ' render fresh scoped tree', command, self.work)['stdout'])
        assert rendered['root'] == str(self.root) and rendered['unit'] == self.unit and rendered['renderedOnly']
        for source, suffix in [('signal-garden.service', '.service'), ('signal-garden-backup.service', '-backup.service'), ('signal-garden-backup.timer', '-backup.timer')]:
            target = Path('/run/systemd/system') / (self.unit + suffix)
            assert not target.exists() and not target.is_symlink()
            content = (self.root/'staging'/source).read_bytes()
            assert b'@@' not in content
            admin(self.profile + ' install scoped unit ' + suffix,
                  ['install', '-m', '0644', self.root/'staging'/source, target], self.work)
            self.installed[target] = content
            assert target.read_bytes() == content and target.stat().st_uid == 0
        admin(self.profile + ' actual unit verification', ['systemd-analyze', 'verify', *self.installed], self.work)
        self.ctl('reload new units', 'daemon-reload')
        run(self.profile + ' actual Nginx configuration check',
            ['nginx', '-t', '-p', str(self.root/'nginx')+'/', '-c', self.root/'staging/nginx.conf'], self.work)
        self.nginx = launch(self.profile + ' owned foreground Nginx',
                            ['nginx', '-p', str(self.root/'nginx')+'/', '-c', self.root/'staging/nginx.conf'], self.work)
        self.evidence['rendered'] = rendered
        self.evidence['initialFiles'] = {name:file_record(self.root/'current'/name) for name in ['app.py','config.json','data.json']}
        self.evidence['backupDirectoryMode'] = oct(stat.S_IMODE((self.root/'backups').stat().st_mode))
        assert self.evidence['backupDirectoryMode'] == '0o700'

    def healthy(self, label):
        request = wait_until(lambda:http(self.profile + ' ' + label, self.app_port), lambda item:item['status']==200)
        data = body(request)
        state = fields(self.state())
        assert state['ActiveState'] == 'active' and state['DynamicUser'] == 'yes', state
        assert data['pid'] == int(state['MainPID']) and data['uid'] not in (0,os.geteuid()) and data['gid'] > 0
        assert re.fullmatch(r'[0-9a-f]{32}', data['invocationId']) and data['invocationId'] == state['InvocationID']
        assert data['codeWriteProbe']['denied'] and data['codeWriteProbe']['errno'] in (13,30,1)
        assert data['codeSha256'] == sha((self.root/'current/app.py').read_bytes())
        assert data['cwd'] == str((self.root/'current').resolve()) and data['host'] == '127.0.0.1'
        start = birth(data['pid'])
        assert start is not None
        self.app_pids[data['pid']] = start
        self.evidence[label] = {'http': request, 'manager': state, 'processStartTicks': start}
        return data

    def snapshot(self, changed=False, incomplete=False):
        label = 'changed' if changed else 'initial'
        old = {str(path):sha(path.read_bytes()) for path in (self.root/'backups').glob('*.tar.gz')}
        previous_trigger=fields(self.state('-backup.timer')).get('LastTriggerUSec')
        previous_invocation=fields(self.state('-backup.service')).get('InvocationID')
        self.ctl(label+' activate actual backup timer', 'enable','--runtime','--now',self.unit+'-backup.timer')
        timer = wait_until(lambda:fields(self.state('-backup.timer')),
                           lambda item:item.get('LastTriggerUSec') not in (None,'','n/a','0',previous_trigger))
        backup = wait_until(lambda:fields(self.state('-backup.service')),
                            lambda item:item.get('ActiveState') in ('failed','inactive') and item.get('Result') in ('success','exit-code') and item.get('InvocationID') not in (None,'','0'*32,previous_invocation))
        # Require the actual service invocation to have ended before disabling its timer.
        self.ctl(label+' disable observed backup timer', 'disable','--runtime','--now',self.unit+'-backup.timer')
        journal = self.journal('-backup.service')
        self.evidence[label+'ScheduledBackup'] = {'timer': timer, 'manager': backup, 'journal': journal}
        assert all(sha(Path(path).read_bytes())==digest for path,digest in old.items())
        if incomplete:
            assert backup['Result']=='exit-code' and backup['ExecMainStatus']=='2',backup
            assert any('select every declared project file' in str(row.get('MESSAGE','')) for row in journal)
            assert {str(path):sha(path.read_bytes()) for path in (self.root/'backups').glob('*.tar.gz')}==old
            return None
        assert backup['Result']=='success' and backup['ExecMainStatus']=='0',backup
        fresh=[path for path in (self.root/'backups').glob('*.tar.gz') if str(path) not in old]
        assert len(fresh)==1,fresh
        archive=fresh[0]
        record=file_record(archive)
        assert record['mode']=='0o600' and record['uid']==os.geteuid()
        messages=[]
        for row in journal:
            try:
                message=json.loads(row.get('MESSAGE',''))
            except (ValueError,TypeError):
                continue
            if message.get('archive')==str(archive):
                assert int(row['_UID'])==os.geteuid()
                assert message['sha256']==record['sha256'] and message['publishedAfterValidation']
                messages.append(message)
        assert len(messages)==1,messages
        self.evidence[label+'ScheduledBackup']['archive']=record
        return archive

    def close(self):
        failures = []
        if self.installed:
            for label, args in [('disable runtime units', ['disable','--runtime','--now',self.unit+'-backup.timer',self.unit+'.service']),
                                ('stop backup', ['stop',self.unit+'-backup.service'])]:
                try:
                    self.ctl(label, *args, expected=None)
                except BaseException as error:
                    logger.exception("Owned capstone cleanup failed")
                    failures.append(str(error))
            if any(birth(pid)==started for pid,started in self.app_pids.items()):
                self.ctl('terminate only surviving owned service children','kill','--kill-whom=all',self.unit+'.service',expected=None)
                self.ctl('finish owned service stop','stop',self.unit+'.service',expected=None)
        if self.nginx:
            try:
                self.evidence['nginxExit'] = finish(*self.nginx, expected=0, send=signal.SIGINT)
            except BaseException as error:
                logger.exception("Owned capstone cleanup failed")
                failures.append(str(error))
        if self.dropin_created:
            try:
                target = self.dropin/'failed-workdir.conf'
                assert target.read_text() == '[Service]\nWorkingDirectory='+str(self.root)+'/missing-release\n'
                admin(self.profile+' remove owned failure drop-in', ['rm','--',target], self.work)
                admin(self.profile+' remove owned drop-in directory', ['rmdir','--',self.dropin], self.work)
            except BaseException as error:
                logger.exception("Owned capstone cleanup failed")
                failures.append(str(error))
        for target, content in self.installed.items():
            try:
                assert target.read_bytes() == content
                admin(self.profile+' remove owned unit', ['rm','--',target], self.work)
            except BaseException as error:
                logger.exception("Owned capstone cleanup failed")
                failures.append(str(error))
        if self.installed:
            self.ctl('reload after removal', 'daemon-reload', expected=None)
            self.ctl('reset only owned failed states', 'reset-failed', self.unit+'.service', self.unit+'-backup.service', expected=None)
            for suffix in ['.service','-backup.service','-backup.timer']:
                result = fields(self.state(suffix))
                if result.get('LoadState') != 'not-found' or result.get('ActiveState') != 'inactive':
                    failures.append(str(result))
        for pid, start in self.app_pids.items():
            if birth(pid)==start:
                failures.append(str((pid,'owned application survived cleanup')))
        for port in [self.app_port,self.proxy_port]:
            if http(self.profile+' cleanup listener probe',port)['status'] != 0:
                failures.append(str((port,'owned listener survived cleanup')))
        if self.created:
            assert not self.root.is_symlink() and self.root.stat().st_uid in (0,os.geteuid())
            admin(self.profile+' remove exact owned lab tree', ['rm','-r','--',self.root], self.work)
            assert not self.root.exists()
        assert not failures, failures
        assert all(not path.exists() for path in self.installed)
        for path in [Path('/run/systemd/system/multi-user.target.wants')/(self.unit+'.service'), Path('/run/systemd/system/timers.target.wants')/(self.unit+'-backup.timer')]:
            assert not path.exists() and not path.is_symlink()
        self.evidence['ownedResourcesRemoved'] = True


def completed_role(role):
    config=role/'config.json'
    value=json.loads(config.read_text())
    assert value['listen_host']=='0.0.0.0' and value['release_id']=='TODO'
    value.update(listen_host='127.0.0.1',release_id='release-a')
    config.write_text(json.dumps(value,indent=2)+'\n')
    for name,old,new in [
        ('signal-garden.service','# TODO: select the rendered current release directory.\nWorkingDirectory=@@ROOT@@/missing-release','WorkingDirectory=@@ROOT@@/current'),
        ('backup.py',"    # TODO: include every declared project member.\n    return ('config.json',)",'    return REQUIRED')]:
        target=role/name
        text=target.read_text()
        assert text.count(old)==1
        target.write_text(text.replace(old,new))


def snapshot_result(profile,lab,archive,changed=False):
    label='changed' if changed else 'initial'
    tool=lab.root/'operator/backup.py'
    check=json.loads(run(profile+' '+label+' validate actual archive',[sys.executable,tool,'verify',archive],lab.work)['stdout'])
    expected={name:sha((lab.root/'current'/name).read_bytes()) for name in ['app.py','config.json','data.json']}
    assert check['manifest']['files']==expected and check['actualSha256']==sha(archive.read_bytes())
    target=lab.root/'restore'/('changed-drill' if changed else 'initial-drill')
    result=json.loads(run(profile+' '+label+' separate-path restore',[sys.executable,tool,'restore',archive,target],lab.work)['stdout'])
    actual={name:file_record(target/name) for name in expected}
    assert result['separateDestinationCreated'] and result['files']==expected and result['uid']==os.geteuid()
    assert all(record['sha256']==expected[name] and record['mode']=='0o600' and record['uid']==os.geteuid() for name,record in actual.items())
    lab.evidence[label+'RestoredFiles']=actual
    run(profile+' refuse existing restore destination',[sys.executable,tool,'restore',archive,target],lab.work,2)
    assert all((target/name).read_bytes()==base64.b64decode(actual[name]['bytesBase64']) for name in actual)
    return check


def exercise(profile,role,work):
    lab=Lab(profile,role,work)
    record={'profile': profile, 'pack': PACK, 'labId': lab.id, 'unit': lab.unit, 'root': str(lab.root), 'operatorUid': os.geteuid(), 'starterIntentionallyIncomplete': profile == 'starter', 'learnerWorksheetCompletionInferred': False}
    profiles.append(record)
    initial_rows=len(rows)
    try:
        if profile=='starter':
            run(profile+' reject unsafe raw configuration',['bash',role/'task.sh','check'],work,2)
            run(profile+' reject unsafe raw startup before binding',['bash',role/'task.sh','app','--port',lab.app_port],work,2)
            assert http(profile+' rejected raw startup has no listener',lab.app_port)['status']==0
            # A configuration-only repair isolates the two remaining real native faults.
            config=json.loads((role/'config.json').read_text())
            config.update(listen_host='127.0.0.1',release_id='release-a')
            (role/'config.json').write_text(json.dumps(config,indent=2)+'\n')
            record['privateConfigurationRepairOnly']=True
        original={f.name:sha(f.read_bytes()) for f in role.iterdir() if f.is_file()}
        run(profile+' actual corrected configuration check',['bash',role/'task.sh','check'],work)
        lab.prepare()
        lab.ctl('enable real application','enable','--runtime','--now',lab.unit+'.service',expected=None if profile=='starter' else 0)
        if profile=='starter':
            failure=wait_until(lambda:fields(lab.state()),lambda item:item.get('ActiveState')=='failed')
            assert failure['ExecMainStatus']=='200' and int(failure['NRestarts'])>=2,failure
            journal=lab.journal()
            assert any('CHDIR' in str(row.get('MESSAGE','')) or 'working directory' in str(row.get('MESSAGE','')).lower() for row in journal)
            assert http(profile+' actual failed app listener',lab.app_port)['status']==0
            proxy=wait_until(lambda:http(profile+' proxy observes failed app',lab.proxy_port),lambda item:item['status']==502)
            assert b'502' in base64.b64decode(proxy['bodyBase64'])
            # A separately labelled reference baseline is not credited to the starter.
            baseline=json.loads(run(profile+' reference-only prior trusted baseline',
                                    [sys.executable,ROOT/PACK/'solution/backup.py','build',lab.root/'current',lab.root/'backups'],work)['stdout'])
            trusted=Path(baseline['archive'])
            before=trusted.read_bytes()
            lab.snapshot(incomplete=True)
            assert trusted.read_bytes()==before
            lab.evidence.update(actualWorkingDirectoryFailure=failure,workingDirectoryJournal=journal,
                                referenceOnlyTrustedBaseline=file_record(trusted))
        else:
            first=lab.healthy('initialHealth')
            assert first['release']=='release-a' and first['message']=='Fictional signal garden lab data'
            journal=lab.journal()
            matching=[row for row in journal if row.get('_SYSTEMD_INVOCATION_ID')==first['invocationId'] and row.get('_PID')==str(first['pid'])]
            assert any(int(row['_UID'])==first['uid'] and json.loads(row['MESSAGE']).get('event')=='started' for row in matching if str(row.get('MESSAGE','')).startswith('{'))
            lab.evidence['initialJournal']=journal
            direct_missing=http(profile+' actual app missing route',lab.app_port,'/missing')
            assert direct_missing['status']==404 and body(direct_missing)=={'error':'not found'}
            proxied=wait_until(lambda:http(profile+' actual proxied health',lab.proxy_port),lambda item:item['status']==200)
            assert body(proxied)==body(lab.evidence['initialHealth']['http'])
            assert http(profile+' proxied missing route',lab.proxy_port,'/missing')['status']==404
            run(profile+' actual loopback sockets',['ss','-ltnp'],work)
            initial_archive=lab.snapshot()
            initial_bytes=initial_archive.read_bytes()
            snapshot_result(profile,lab,initial_archive)
            tool=lab.root/'operator/backup.py'
            run(profile+' reject candidate after actual archive write',[sys.executable,tool,'build',lab.root/'current',lab.root/'backups','--reject-after-write'],work,2)
            partials=list((lab.root/'backups').glob('*.partial'))
            assert len(partials)==1 and initial_archive.read_bytes()==initial_bytes
            lab.evidence['rejectedPartial']=file_record(partials[0])
            tampered=lab.root/'backups/tampered.tar.gz'
            with tarfile.open(initial_archive,'r:gz') as source,tarfile.open(tampered,'w:gz') as output:
                for member in source.getmembers():
                    content=source.extractfile(member).read()
                    if member.name=='data.json':
                        content=b'{"message":"tampered payload"}\n'
                        member.size=len(content)
                    output.addfile(member,io.BytesIO(content))
            run(profile+' actual tamper verification refusal',[sys.executable,tool,'verify',tampered],work,2)
            bad_restore=lab.root/'restore/must-not-exist'
            run(profile+' actual tamper restore refusal',[sys.executable,tool,'restore',tampered,bad_restore],work,2)
            assert not bad_restore.exists() and initial_archive.read_bytes()==initial_bytes
            lab.evidence['tamperedArchive']=file_record(tampered)
            assert not lab.dropin.exists()
            admin(profile+' create owned failure drop-in directory',['mkdir','--',lab.dropin],work)
            lab.dropin_created=True
            failed=work/(profile+'-failed-workdir.conf')
            failed.write_text('[Service]\nWorkingDirectory='+str(lab.root)+'/missing-release\n')
            admin(profile+' install exact failure drop-in',['install','-m','0644',failed,lab.dropin/'failed-workdir.conf'],work)
            lab.ctl('load actual failure configuration','daemon-reload')
            lab.ctl('restart into actual working-directory failure','restart',lab.unit+'.service',expected=None)
            failure=wait_until(lambda:fields(lab.state()),lambda item:item.get('ActiveState')=='failed')
            assert failure['ExecMainStatus']=='200' and int(failure['NRestarts'])>=2,failure
            failure_journal=lab.journal()
            assert any('CHDIR' in str(row.get('MESSAGE','')) or 'working directory' in str(row.get('MESSAGE','')).lower() for row in failure_journal)
            assert http(profile+' direct refusal during incident',lab.app_port)['status']==0
            assert http(profile+' actual proxy502 during incident',lab.proxy_port)['status']==502
            lab.evidence.update(actualWorkingDirectoryFailure=failure,workingDirectoryJournal=failure_journal)
            admin(profile+' remove owned failed working-directory override',['rm','--',lab.dropin/'failed-workdir.conf'],work)
            admin(profile+' remove owned override directory',['rmdir','--',lab.dropin],work)
            lab.dropin_created=False
            lab.ctl('reload original service','daemon-reload')
            lab.ctl('reset scoped failure','reset-failed',lab.unit+'.service')
            lab.ctl('restart corrected service','restart',lab.unit+'.service')
            recovered=lab.healthy('recoveredHealth')
            assert recovered['invocationId']!=first['invocationId'] and recovered['message']==first['message']
            assert initial_archive.read_bytes()==initial_bytes
            lab.ctl('clean stop','stop',lab.unit+'.service')
            assert fields(lab.state())['MainPID']=='0' and http(profile+' clean stop refuses app connection',lab.app_port)['status']==0
            lab.ctl('clean start','start',lab.unit+'.service')
            clean=lab.healthy('cleanStartHealth')
            assert clean['invocationId']!=recovered['invocationId']
            data=lab.root/'current/data.json'
            data.chmod(0o644)
            data.write_text(json.dumps({'message':'Changed fictional capstone input'},indent=2)+'\n')
            data.chmod(0o444)
            cached=lab.healthy('beforeChangedRestartHealth')
            assert cached['message']==first['message'] and cached['invocationId']==clean['invocationId']
            lab.ctl('restart after changed fictional input','restart',lab.unit+'.service')
            changed=lab.healthy('changedHealth')
            assert changed['message']=='Changed fictional capstone input' and changed['invocationId']!=clean['invocationId']
            changed_archive=lab.snapshot(changed=True)
            assert changed_archive!=initial_archive and initial_archive.read_bytes()==initial_bytes
            assert lab.evidence['changedScheduledBackup']['timer']['LastTriggerUSec']!=lab.evidence['initialScheduledBackup']['timer']['LastTriggerUSec']
            snapshot_result(profile,lab,changed_archive,changed=True)
            assert initial_archive.read_bytes()==initial_bytes
        assert original=={f.name:sha(f.read_bytes()) for f in role.iterdir() if f.is_file()}
        record['inputsUnchanged']=True
        record['passed']=True
    finally:
        try:
            lab.close()
        finally:
            record['evidence']=lab.evidence
            record['actualCommandCases']=len(rows)-initial_rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proof',type=Path,required=True)
    args=parser.parse_args()
    assert platform.system()=='Linux' and os.geteuid()>0
    assert Path('/proc/1/comm').read_text().strip()=='systemd'
    assert all(shutil.which(tool) for tool in ['sudo','systemctl','systemd-analyze','journalctl','nginx','ss'])
    args.proof=args.proof.resolve()
    args.proof.parent.mkdir(parents=True,exist_ok=True)
    before=source_hashes()
    assert len(before)==23
    error=None
    try:
        with tempfile.TemporaryDirectory(prefix='linux-operations-capstone-') as temporary:
            work=Path(temporary)
            outside=work/'outside-sentinel'
            outside.write_bytes(b'outside remains unchanged\n')
            run('actual ordinary operator environment',['id'],work)
            admin('approved disposable manager availability',['systemctl','--system','show','-p','Version'],work)
            for profile in ['starter','solution','completed']:
                role=work/(profile+' quoted workspace')
                shutil.copytree(ROOT/PACK/('starter' if profile=='completed' else profile),role)
                if profile=='completed':
                    completed_role(role)
                exercise(profile,role,work)
                assert outside.read_bytes()==b'outside remains unchanged\n'
                assert source_hashes()==before
        assert not work.exists()
        assert len(profiles)==3 and all(p['passed'] and p['inputsUnchanged'] and p['evidence']['ownedResourcesRemoved'] for p in profiles)
        assert len(events)==2*len(rows) and len({r['pid'] for r in rows})==len(rows)
    except BaseException:
        error=traceback.format_exc()
        logger.exception("Native capstone failed; retaining raw evidence")
    proof={'nativePassed': error is None, 'unprivilegedUid': os.geteuid(), 'sourceHashes': before, 'sourceUnchanged': source_hashes() == before, 'profiles': profiles, 'actualCommandCases': len(rows), 'actualHttpRequests': len(requests), 'loggedCommandLifecycles': len(events) // 2, 'realSystemManager': True, 'learnerWorksheetCompletionInferred': False, 'error': error}
    args.proof.write_text(json.dumps(proof,indent=2)+'\n')
    args.proof.with_suffix('.observations.json').write_text(json.dumps({'commands':rows,'http':requests},indent=2)+'\n')
    args.proof.with_suffix('.processes.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
    if error:
        raise AssertionError(error)
    print(json.dumps({k:v for k,v in proof.items() if k not in ['sourceHashes','profiles']}))


if __name__=='__main__':
    main()
