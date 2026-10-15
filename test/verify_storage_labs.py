"""Accept actual GNU capacity, archive, restore, corruption and retention behavior."""
import argparse
import hashlib
import json
import os
import platform
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKS = ["LS-12-unit-12-storage-backups-and-reliability",
         "LS-25-unit-12-storage-backups-and-reliability-supplemental-2",
         "LS-26-unit-12-storage-backups-and-reliability-supplemental-3"]
parser = argparse.ArgumentParser()
parser.add_argument("--proof", required=True, type=Path)
args = parser.parse_args()
assert platform.system() == "Linux" and os.geteuid() > 0
assert all(shutil.which(name) for name in ("bash", "python3", "tar", "df", "du", "sha256sum"))
args.proof = args.proof.resolve()
args.proof.parent.mkdir(parents=True, exist_ok=True)
environment = dict(os.environ, LC_ALL="C", PYTHONDONTWRITEBYTECODE="1", TAR_OPTIONS="--exclude=*")
records, observations, profiles, inner = [], [], [], []
task = os.environ.get("CLASSES_FAMILY_TASK_ID", "linux-storage-source")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_hashes():
    return {str(file.relative_to(ROOT)): digest(file) for pack in PACKS
            for file in sorted((ROOT / pack).rglob("*")) if file.is_file()}


def run(argv, cwd, expected=0, env=None):
    child = subprocess.Popen(argv, cwd=cwd, env=environment if env is None else env,
                             stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, start_new_session=True)
    entry = {"parentTaskId": task, "parentPid": os.getpid(), "cwd": str(cwd), "command": argv,
                 "pid": child.pid, "startTime": time.time(), "timeoutSeconds": 30}
    records.append(dict(entry, event="start"))
    cleanup = "owned process exited and reaped"
    try:
        stdout, stderr = child.communicate(timeout=30)
    except BaseException:
        cleanup = "owned process group terminated"
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
        try:
            child.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.communicate()
        raise
    finally:
        records.append(dict(entry, event="end", endTime=time.time(), exitCode=child.returncode,
                            childProcessGroupCleanup=cleanup))
    value = {"command": argv, "cwd": str(cwd), "status": child.returncode, "stdout": stdout.decode(), "stderr": stderr.decode()}
    observations.append(value)
    assert child.returncode == expected, value
    return value


def execute(cwd, lab, command, *options, expected=0, env=None):
    value = run(["bash", "task.sh", command, "--lab", str(lab), *options], cwd, expected, env)
    return json.loads(value["stdout"] if value["status"] == 0 else value["stderr"])


def restored(lab, destination, text):
    root = lab / "restores" / destination
    assert (root / "report.txt").read_text() == text + "\n"
    assert (root / "binary.bin").read_bytes() == bytes(range(256))
    assert (root / "nested/a file.txt").read_text() == "a path with spaces; café\n"
    assert (root / "sparse.bin").stat().st_size == 1024 * 1024
    assert (root / "sparse.bin").read_bytes() == bytes(1024 * 1024)
    assert (root / "empty").is_dir() and not list((root / "empty").iterdir())
    assert not (root / "cache").exists()
    assert stat.S_IMODE((root / "report.txt").stat().st_mode) == 0o640
    assert stat.S_IMODE((root / "nested/a file.txt").stat().st_mode) == 0o600
    assert all(file.stat().st_uid == os.geteuid() for file in [root, *root.rglob("*")])


def archive_hashes(lab):
    return {str(file.relative_to(lab)): digest(file) for file in sorted((lab / "backups").rglob("*")) if file.is_file()}


def interrupted_backup(cwd, lab, parent):
    # Fault injection controls the short-lived tar creation window. Successful
    # creation and every restoration elsewhere use the real GNU tar binary.
    tools = parent / "fault-tools"
    tools.mkdir()
    ready = parent / "partial-ready"
    fake = tools / "tar"
    fake.write_text("#!" + sys.executable + "\nimport os,pathlib,sys,time\na=sys.argv[1:]\np=pathlib.Path(a[a.index('--file')+1]);p.write_bytes(b'partial')\nr=pathlib.Path(" + repr(str(ready)) + ");t=r.with_suffix('.tmp');t.write_text(str(os.getpid()));t.rename(r)\ntime.sleep(25)\n")
    fake.chmod(0o700)
    argv = ["bash", "task.sh", "backup", "--lab", str(lab), "--name", "interrupted"]
    child = subprocess.Popen(argv, cwd=cwd, env=dict(environment, PATH=str(tools) + os.pathsep + environment["PATH"]),
                             stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    entry = {"parentTaskId": task, "parentPid": os.getpid(), "cwd": str(cwd), "command": argv, "pid": child.pid, "startTime": time.time(), "timeoutSeconds": 15}
    records.append(dict(entry, event="start"))
    tool_pid = None
    try:
        deadline = time.monotonic() + 10
        while not ready.exists():
            assert child.poll() is None and time.monotonic() < deadline
            time.sleep(0.01)
        tool_pid = int(ready.read_text())
        child.send_signal(signal.SIGTERM)
        stdout, stderr = child.communicate(timeout=3)
        assert child.returncode == 130, (stdout, stderr)
        assert json.loads(stderr)["error"] == "interrupted"
    finally:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.communicate()
        if tool_pid is not None:
            try:
                os.kill(tool_pid, 0)
            except ProcessLookupError:
                pass
            else:
                os.killpg(tool_pid, signal.SIGKILL)
                raise AssertionError("injected tar process survived driver cleanup")
        records.append(dict(entry, event="end", endTime=time.time(), exitCode=child.returncode,
                            childProcessGroupCleanup="owned driver and tar group interrupted and reaped"))
    assert not (lab / "backups/interrupted").exists()
    assert not list((lab / "backups").glob(".pending-*"))
    observations.append({"kind": "injected-partial-archive-interruption", "status": child.returncode,
                             "candidateDiscarded": True, "childCleanupRecorded": True})


before = source_hashes()
host_storage = {name: Path(name).read_bytes() for name in ["/proc/self/mountinfo", "/etc/fstab"] if Path(name).exists()}
temporary = Path(tempfile.mkdtemp(prefix="linux-storage-native-"))
sentinel = temporary / "outside-sentinel"
sentinel.write_bytes(b"outside the selected lab\n")
try:
    for index, pack in enumerate(PACKS):
        for role in ["starter", "solution", "independent-command-sequence"]:
            cwd = temporary / (str(index) + "-" + role)
            shutil.copytree(ROOT / pack / ("starter" if role == "independent-command-sequence" else role), cwd)
            lab = cwd / "owned-lab"
            execute(cwd, lab, "init")
            execute(cwd, lab, "init", expected=2)
            initial_source = (lab / "data/report.txt").read_bytes()
            observation = execute(cwd, lab, "observe", "--report", "first")
            assert observation["uid"] == os.geteuid() and observation["worksheetComplete"] is False
            assert len(observation["commands"]) == 4
            assert [row["command"][0] for row in observation["commands"]] == ["df", "df", "du", "du"]
            assert all(row["exitCode"] == 0 and row["pid"] > 0 for row in observation["commands"])
            assert observation["sparseFile"]["size"] == 1024 * 1024
            first_report = (lab / "reports/first.json").read_bytes()
            execute(cwd, lab, "observe", "--report", "first", expected=2)
            assert (lab / "reports/first.json").read_bytes() == first_report
            baseline = execute(cwd, lab, "backup", "--name", "baseline")
            assert baseline["inventory"]["report.txt"]["sha256"] == hashlib.sha256(initial_source).hexdigest()
            assert baseline["excludes"] == ["cache"] and "cache" not in baseline["inventory"]
            original = archive_hashes(lab)
            execute(cwd, lab, "backup", "--name", "baseline", expected=2)
            assert archive_hashes(lab) == original
            # The direct native checksum is independent of the helper's comparison.
            checksum = run(["sha256sum", "--", str(lab / "backups/baseline/archive.tar")], cwd)
            assert checksum["stdout"].split()[0] == baseline["archiveSha256"]
            execute(cwd, lab, "restore", "--name", "baseline", "--destination", "baseline")
            restored(lab, "baseline", "version one")
            assert (lab / "data/cache/session.tmp").exists()
            if index == 0:
                execute(cwd, lab, "change", "--text", "version two")
                execute(cwd, lab, "restore", "--name", "baseline", "--destination", "earlier")
                restored(lab, "earlier", "version one")
                assert (lab / "data/report.txt").read_text() == "version two\n"
                capacity = os.statvfs(lab)
                reserve = capacity.f_bavail * capacity.f_frsize + 1024 * 1024 * 1024
                rejected = execute(cwd, lab, "backup", "--name", "no-space", "--reserve-bytes", str(reserve), expected=1)
                assert "below the requested" in rejected["error"] and archive_hashes(lab) == original
                execute(cwd, lab, "backup", "--name", "changed")
                execute(cwd, lab, "restore", "--name", "changed", "--destination", "changed")
                restored(lab, "changed", "version two")
                execute(cwd, lab, "restore", "--name", "changed", "--destination", "changed", expected=2)
                restored(lab, "changed", "version two")
                before_fault = archive_hashes(lab)
                interrupted_backup(cwd, lab, cwd)
                assert archive_hashes(lab) == before_fault
            elif index == 1:
                for mode in ["flip", "truncate"]:
                    execute(cwd, lab, "backup", "--name", mode)
                    manifest = (lab / "backups" / mode / "manifest.json").read_bytes()
                    execute(cwd, lab, "damage", "--name", mode, "--mode", mode)
                    assert (lab / "backups" / mode / "manifest.json").read_bytes() == manifest
                    run(["tar", "--list", "--file", str(lab / "backups" / mode / "archive.tar")], cwd,
                        expected=0 if mode == "flip" else 2, env=dict(environment, TAR_OPTIONS=""))
                    execute(cwd, lab, "verify", "--name", mode, expected=1)
                    execute(cwd, lab, "restore", "--name", mode, "--destination", mode, expected=1)
                    assert not (lab / "restores" / mode).exists()
                    assert all(digest(lab / name) == value for name, value in original.items())
                    assert (lab / "data/report.txt").read_bytes() == initial_source
                execute(cwd, lab, "change", "--text", "repaired version")
                execute(cwd, lab, "backup", "--name", "repaired")
                execute(cwd, lab, "restore", "--name", "repaired", "--destination", "repaired")
                restored(lab, "repaired", "repaired version")
            else:
                # baseline is sequence 1; names intentionally do not sort by age.
                execute(cwd, lab, "change", "--text", "version two")
                execute(cwd, lab, "backup", "--name", "v2")
                execute(cwd, lab, "change", "--text", "version three")
                execute(cwd, lab, "backup", "--name", "v3")
                before_plan = archive_hashes(lab)
                plan = execute(cwd, lab, "plan", "--keep", "2", "--report", "first-plan")
                assert plan["planningDeletesNothing"] and plan["remove"] == ["baseline"]
                assert plan["retain"] == ["v2", "v3"] and archive_hashes(lab) == before_plan
                execute(cwd, lab, "plan", "--keep", "0", "--report", "zero", expected=2)
                execute(cwd, lab, "change", "--text", "version four")
                execute(cwd, lab, "backup", "--name", "a-fourth")
                before_apply = archive_hashes(lab)
                execute(cwd, lab, "apply", "--report", "first-plan", expected=2)
                assert archive_hashes(lab) == before_apply
                current = execute(cwd, lab, "plan", "--keep", "2", "--report", "current-plan")
                assert current["remove"] == ["baseline", "v2"] and current["retain"] == ["v3", "a-fourth"]
                result = execute(cwd, lab, "apply", "--report", "current-plan")
                assert result["removed"] == ["baseline", "v2"]
                assert {path.name for path in (lab / "backups").iterdir()} == {"v3", "a-fourth"}
                for path, value in archive_hashes(lab).items():
                    assert before_apply[path] == value
                execute(cwd, lab, "apply", "--report", "current-plan", expected=2)
                execute(cwd, lab, "restore", "--name", "v3", "--destination", "third")
                execute(cwd, lab, "restore", "--name", "a-fourth", "--destination", "fourth")
                restored(lab, "third", "version three")
                restored(lab, "fourth", "version four")
                execute(cwd, lab, "restore", "--name", "baseline", "--destination", "lost", expected=1)
                assert not (lab / "restores/lost").exists()
            assert sentinel.read_bytes() == b"outside the selected lab\n"
            notes = next(cwd.glob("*-notes.md"))
            source_role = "starter" if role == "independent-command-sequence" else role
            assert notes.read_bytes() == (ROOT / pack / source_role / notes.name).read_bytes()
            operations = [json.loads(line) for line in (lab / "operations.jsonl").read_text().splitlines()]
            assert operations and all(row["exitCode"] is not None and row["endTime"] >= row["startTime"] and row["childProcessGroupCleanup"] for row in operations)
            inner.extend(dict(row, pack=pack, role=role) for row in operations)
            (args.proof.parent / (str(index) + "-" + role + "-storage-operations.jsonl")).write_text("".join(json.dumps(row) + "\n" for row in operations))
            (args.proof.parent / (str(index) + "-" + role + "-storage-observation.json")).write_bytes(first_report)
            profiles.append({"pack": pack, "role": role, "actualGnuTools": True, "independentChecksum": True,
                                 "exactSeparateRestore": True, "excludedCachePreserved": True, "actualModesAndOwnership": True,
                                 "changedCases": True, "failuresPreserved": True, "notesUnchanged": True, "outsideSentinelUnchanged": True})
finally:
    shutil.rmtree(temporary)
    args.proof.with_suffix(".processes.jsonl").write_text("".join(json.dumps(row) + "\n" for row in records))
assert before == source_hashes()
assert host_storage == {name: Path(name).read_bytes() for name in host_storage}
starts = {(row["pid"], row["startTime"]) for row in records if row["event"] == "start"}
ends = {(row["pid"], row["startTime"]) for row in records if row["event"] == "end"}
assert starts == ends
proof = {"accepted": True, "platform": platform.system(), "uid": os.geteuid(), "profiles": profiles,
             "observations": observations, "sourceHashes": before, "sourceUnchanged": True,
             "temporaryFilesCleaned": not temporary.exists(), "worksheetCompletionNotInferred": True,
             "loggedOuterLifecycles": len(starts), "nativeCommandRecords": len(inner),
             "partialArchiveInterruptionProfiles": sum(row.get("kind") == "injected-partial-archive-interruption" for row in observations),
             "hostStorageHashes": {name: hashlib.sha256(data).hexdigest() for name, data in host_storage.items()},
             "hostStorageConfigurationUnchanged": True}
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps({key: value for key, value in proof.items() if key not in ("observations", "sourceHashes")}))
