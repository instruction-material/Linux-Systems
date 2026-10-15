"""Exercise actual source builds, owned releases and isolated dpkg recovery."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
MANUAL = "LS-19-unit-9-package-management-and-software-layout-supplemental-2"
DEPENDENCY = "LS-20-unit-9-package-management-and-software-layout-supplemental-3"
parser = argparse.ArgumentParser()
parser.add_argument("--proof", required=True, type=Path)
args = parser.parse_args()
assert platform.system() == "Linux" and os.geteuid() > 0
assert all(shutil.which(name) for name in ["cc", "dpkg", "dpkg-deb", "dpkg-query", "bash"])
args.proof = args.proof.resolve()
args.proof.parent.mkdir(parents=True, exist_ok=True)
task = os.environ.get("CLASSES_FAMILY_TASK_ID", "linux-package-optional-source")
records, observations, profiles = [], [], []


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hashes():
    return {str(f.relative_to(ROOT)): digest(f)
            for pack in [MANUAL, DEPENDENCY] for f in sorted((ROOT / pack).rglob("*")) if f.is_file()}


def run(argv, cwd):
    started = time.time()
    child = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    entry = dict(parentTaskId=task, parentPid=os.getpid(), pid=child.pid, command=argv,
                 cwd=str(cwd), startTime=started, timeoutSeconds=45)
    records.append(dict(entry, event="start"))
    cleanup = "owned process exited and reaped"
    try:
        stdout, stderr = child.communicate(timeout=45)
    except BaseException:
        cleanup = "owned process group stopped after failure or interruption"
        os.killpg(child.pid, signal.SIGTERM)
        try:
            stdout, stderr = child.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            stdout, stderr = child.communicate()
        raise
    finally:
        records.append(dict(entry, event="end", endTime=time.time(), exitCode=child.returncode,
                            childProcessGroupCleanup=cleanup))
    observations.append(dict(command=argv, cwd=str(cwd), status=child.returncode,
                             stdout=stdout.decode(errors="replace"), stderr=stderr.decode(errors="replace")))
    return child.returncode, stdout, stderr


def invoke(cwd, lab, action, version=None, status=0):
    argv = ["bash", "task.sh", action, "--lab", str(lab)]
    if version:
        argv += ["--version", version]
    observed, stdout, stderr = run(argv, cwd)
    assert observed == status, (action, version, observed, stdout.decode(), stderr.decode())
    return stdout


def query(cwd, lab, package, state=None, version=None):
    status, stdout, stderr = run(["dpkg-query", "--admindir=" + str(lab / "root/var/lib/dpkg"),
                                  "-W", "-f=${Version}\\n${Status}\\n", package], cwd)
    if state:
        assert status == 0 and stdout.decode().splitlines() == [version, state], (package, status, stdout, stderr)
    else:
        assert status in (0, 1), (package, status, stdout, stderr)
        if status == 0:
            values = stdout.decode().splitlines()
            assert len(values) == 2 and values[1].split()[-1] == 'not-installed', (package, values)
        else:
            assert not stdout.strip(), (package, stdout)
    return dict(status=status, stdout=stdout.decode(), stderr=stderr.decode())


def retained_log(lab, filename):
    content = (lab / "operations.jsonl").read_bytes()
    entries = [json.loads(line) for line in content.decode().splitlines()]
    starts = {(x['pid'], x['startTime']) for x in entries if x['event'] == 'start'}
    ends = {(x['pid'], x['startTime']) for x in entries if x['event'] == 'end'}
    assert starts == ends and starts
    assert all(x['exitCode'] is not None and x['childProcessGroupCleanup'] for x in entries if x['event'] == 'end')
    (args.proof.parent / filename).write_bytes(content)
    return len(starts)


before = hashes()
assert len(before) == 20
host_database = Path('/var/lib/dpkg/status')
host_before = digest(host_database)
temporary = Path(tempfile.mkdtemp(prefix='linux-package-optional-'))
try:
    for role in ['starter', 'solution', 'independent-command-sequence']:
        source_role = 'starter' if role == 'independent-command-sequence' else role
        cwd = temporary / ('manual-' + role)
        shutil.copytree(ROOT / MANUAL / source_role, cwd)
        lab = temporary / ('manual-lab-' + role)
        sentinel = temporary / ('manual-outside-' + role)
        sentinel.write_bytes(b'outside manual sentinel\n')
        invoke(cwd, lab, 'init')
        marker = (lab / '.owned-layout-lab.json').read_bytes()
        invoke(cwd, lab, 'init', status=1)
        assert (lab / '.owned-layout-lab.json').read_bytes() == marker
        for version in ['1.0', '2.0']:
            invoke(cwd, lab, 'build', version)
            binary = lab / 'builds' / version / 'layout-demo'
            assert run([str(binary), '--version'], cwd)[:2] == (0, (version + '\n').encode())
            assert run([str(binary), '--status'], cwd)[:2] == (0, ('manual-source build version=' + version + '\n').encode())
            assert run([str(binary), '--bad-option'], cwd)[0] == 2
            invoke(cwd, lab, 'archive', version)
            archive = lab / 'archives' / (version + '.tar.gz')
            raw = archive.read_bytes()
            with tarfile.open(fileobj=io.BytesIO(raw)) as stream:
                assert {x.name for x in stream.getmembers()} == {'bin/layout-demo', 'share/layout-demo/manifest.json'}
                assert stream.extractfile('bin/layout-demo').read() == binary.read_bytes()
            invoke(cwd, lab, 'archive', version, status=1)
            assert archive.read_bytes() == raw
            archive.write_bytes(raw + b'changed')
            invoke(cwd, lab, 'install', version, status=1)
            assert not (lab / 'releases' / version).exists()
            archive.write_bytes(raw)
            invoke(cwd, lab, 'install', version)
            invoke(cwd, lab, 'activate', version)
            actual = json.loads(invoke(cwd, lab, 'check'))
            assert actual['version'] == version and actual['ownershipStatus'] == 1
            assert not actual['packageManaged'] and not actual['manualReceiptIsAuthenticityProof']
            assert not actual['learnerWorksheetCompletionInferred']
            assert actual['binarySha256'] == digest(binary)
            assert (lab / 'current').readlink().as_posix() == 'releases/' + version
        invoke(cwd, lab, 'activate', '1.0')
        assert json.loads(invoke(cwd, lab, 'check'))['version'] == '1.0'
        binary = lab / 'releases/1.0/bin/layout-demo'
        old_binary = binary.read_bytes()
        binary.write_bytes(old_binary + b'changed')
        invoke(cwd, lab, 'check', status=1)
        binary.write_bytes(old_binary)
        (lab / 'current').unlink()
        (lab / 'current').symlink_to(str(sentinel.parent))
        invoke(cwd, lab, 'check', status=1)
        (lab / 'current').unlink()
        (lab / 'current').symlink_to('releases/1.0')
        invoke(cwd, lab, 'remove', '2.0')
        assert not (lab / 'releases/2.0').exists()
        assert json.loads(invoke(cwd, lab, 'check'))['version'] == '1.0'
        invoke(cwd, lab, 'remove', '1.0')
        invoke(cwd, lab, 'check', status=1)
        assert not (lab / 'current').is_symlink() and not (lab / 'releases/1.0').exists()
        assert len(list((lab / 'archives').glob('*.tar.gz'))) == 2
        assert sentinel.read_bytes() == b'outside manual sentinel\n'
        lifecycles = retained_log(lab, role + '-manual-operations.jsonl')
        profiles.append(dict(kind='manual', role=role, actualC17Builds=2, actualRuntimeVersions=['1.0', '2.0', '1.0'],
                             actualOwnershipQuery=True, untrackedManualInstall=True, archiveBytesExact=True,
                             changedArchiveRejected=True, duplicateArchivePreserved=True,
                             alteredInstalledBinaryRejected=True, unknownActiveLinkRejected=True,
                             actualRollback=True, boundedRemoval=True, outsideSentinelUnchanged=True,
                             archivesAndEvidenceRetained=True, worksheetCompletionNotInferred=True,
                             loggedInnerLifecycles=lifecycles))
    for role in ['starter', 'solution', 'independent-command-sequence']:
        source_role = 'starter' if role == 'independent-command-sequence' else role
        cwd = temporary / ('dependency-' + role)
        shutil.copytree(ROOT / DEPENDENCY / source_role, cwd)
        lab = temporary / ('dependency-lab-' + role)
        sentinel = temporary / ('dependency-outside-' + role)
        sentinel.write_bytes(b'outside dependency sentinel\n')
        invoke(cwd, lab, 'init')
        invoke(cwd, lab, 'build')
        archive = lab / 'packages/linux-layout-app-1.0.deb'
        original_archive = archive.read_bytes()
        database = lab / 'root/var/lib/dpkg/status'
        original_database = database.read_bytes()
        archive.write_bytes(original_archive + b'changed')
        invoke(cwd, lab, 'install-app', status=1)
        assert database.read_bytes() == original_database
        archive.write_bytes(original_archive)
        invoke(cwd, lab, 'install-app', status=1)
        assert (lab / 'root/usr/bin/linux-layout-demo.py').is_file()
        query(cwd, lab, 'linux-layout-app', 'install ok unpacked', '1.0')
        absent_base = query(cwd, lab, 'linux-layout-base')
        assert not (lab / 'root/usr/share/linux-layout-lab/base-version.txt').exists()
        assert b'linux-layout-app' in invoke(cwd, lab, 'audit')
        invoke(cwd, lab, 'run', status=1)
        invoke(cwd, lab, 'install-base', '1.0')
        query(cwd, lab, 'linux-layout-base', 'install ok installed', '1.0')
        invoke(cwd, lab, 'configure-app', status=1)
        query(cwd, lab, 'linux-layout-app', 'install ok unpacked', '1.0')
        invoke(cwd, lab, 'run', status=2)
        invoke(cwd, lab, 'install-base', '2.0')
        query(cwd, lab, 'linux-layout-app', 'install ok unpacked', '1.0')
        assert invoke(cwd, lab, 'run') == b'dependency-demo ready base=2.0\n'
        invoke(cwd, lab, 'configure-app')
        query(cwd, lab, 'linux-layout-app', 'install ok installed', '1.0')
        query(cwd, lab, 'linux-layout-base', 'install ok installed', '2.0')
        assert invoke(cwd, lab, 'audit').strip() == b''
        invoke(cwd, lab, 'remove-base', status=1)
        query(cwd, lab, 'linux-layout-app', 'install ok installed', '1.0')
        query(cwd, lab, 'linux-layout-base', 'deinstall ok installed', '2.0')
        assert invoke(cwd, lab, 'run') == b'dependency-demo ready base=2.0\n'
        invoke(cwd, lab, 'remove-app')
        invoke(cwd, lab, 'remove-base')
        query(cwd, lab, 'linux-layout-app')
        query(cwd, lab, 'linux-layout-base')
        assert not (lab / 'root/usr/bin/linux-layout-demo.py').exists()
        assert not (lab / 'root/usr/share/linux-layout-lab/base-version.txt').exists()
        assert invoke(cwd, lab, 'audit').strip() == b''
        # Exercise a symlinked intermediate database path and retain an outside sentinel.
        (lab / 'root/var').rename(lab / 'root/var.saved')
        (lab / 'root/var').symlink_to(sentinel.parent)
        invoke(cwd, lab, 'query', status=1)
        (lab / 'root/var').unlink()
        (lab / 'root/var.saved').rename(lab / 'root/var')
        changed = temporary / ('dependency-base-first-' + role)
        invoke(cwd, changed, 'init')
        invoke(cwd, changed, 'build')
        invoke(cwd, changed, 'install-base', '2.0')
        invoke(cwd, changed, 'install-app')
        query(cwd, changed, 'linux-layout-app', 'install ok installed', '1.0')
        query(cwd, changed, 'linux-layout-base', 'install ok installed', '2.0')
        assert invoke(cwd, changed, 'run') == b'dependency-demo ready base=2.0\n'
        invoke(cwd, changed, 'remove-app')
        invoke(cwd, changed, 'remove-base')
        assert invoke(cwd, changed, 'audit').strip() == b''
        assert sentinel.read_bytes() == b'outside dependency sentinel\n'
        (args.proof.parent / (role + '-dependency-dpkg.log')).write_bytes((lab / 'dpkg.log').read_bytes())
        lifecycles = retained_log(lab, role + '-dependency-operations.jsonl')
        lifecycles += retained_log(changed, role + '-dependency-base-first-operations.jsonl')
        profiles.append(dict(kind='dependency', role=role, actualDpkg=True, separateOwnedRoot=True,
                             absentDependencyInstallRejected=True, actualUnpackedState=True,
                             wrongVersionConfigureRejected=True, runtimeWrongVersionStatus=2,
                             runtimeWorksBeforeConfiguration=True, actualConfiguredState=True,
                             actualUpgrade=True, consistencyAuditClean=True,
                             dependentRemovalRejected=True, reverseOrderRemoval=True,
                             requestedRemovalDistinctFromInstalledState=True,
                             actualPayloadsRemoved=True, changedBaseFirstSequence=True,
                             alteredArchiveRejectedBeforeChange=True, intermediateSymlinkRejected=True,
                             outsideSentinelUnchanged=True, worksheetCompletionNotInferred=True,
                             loggedInnerLifecycles=lifecycles))
finally:
    try:
        for path in temporary.glob('*/operations.jsonl'):
            (args.proof.parent / (path.parent.name + '-operations.jsonl')).write_bytes(path.read_bytes())
        args.proof.with_suffix('.observations.json').write_text(json.dumps(observations, indent=2) + '\n')
        args.proof.with_suffix('.processes.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in records))
    finally:
        shutil.rmtree(temporary)
assert hashes() == before and digest(host_database) == host_before
proof = dict(accepted=True, platform=platform.system(), uid=os.geteuid(), profiles=profiles,
             observations=observations, sourceHashes=before, sourceUnchanged=True,
             hostPackageDatabaseUnchanged=True, hostDatabaseSha256=host_before,
             worksheetCompletionNotInferred=True, temporaryFilesCleaned=not temporary.exists(),
             loggedLifecycles=len(records) // 2)
args.proof.write_text(json.dumps(proof, indent=2) + '\n')
print(json.dumps({key:value for key,value in proof.items() if key not in ('observations','sourceHashes')}))
