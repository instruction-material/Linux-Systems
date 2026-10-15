"""Accept actual installed-package queries and saved investigation evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import time

PACK = Path(__file__).resolve().parents[1] / "LS-10-unit-9-package-management-and-software-layout"
parser = argparse.ArgumentParser()
parser.add_argument("--proof", required=True, type=Path)
args = parser.parse_args()
assert platform.system() == "Linux" and os.geteuid() > 0
assert all(shutil.which(name) for name in ("dpkg-query", "bash", "python3"))
args.proof = args.proof.resolve()
args.proof.parent.mkdir(parents=True, exist_ok=True)
records, observations, profiles = [], [], []
task = os.environ.get("CLASSES_FAMILY_TASK_ID", "linux-package-core-source")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hashes():
    return {str(f.relative_to(PACK)): digest(f)
            for f in sorted(PACK.rglob("*")) if f.is_file()}


def run(argv, cwd, env=None):
    started = time.time()
    child = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, start_new_session=True)
    entry = dict(parentTaskId=task, parentPid=os.getpid(), command=argv,
                 cwd=str(cwd), pid=child.pid, startTime=started, timeoutSeconds=25)
    records.append(dict(entry, event="start"))
    cleanup = "owned process exited and reaped"
    try:
        stdout, stderr = child.communicate(timeout=25)
    except BaseException:
        cleanup = "owned process group terminated after failure or interruption"
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


before = hashes()
host_database = Path("/var/lib/dpkg/status")
host_before = digest(host_database)
root = Path(tempfile.mkdtemp(prefix="linux-package-core-"))
try:
    for role in ["starter", "solution", "independent-command-sequence"]:
        cwd = root / role
        shutil.copytree(PACK / ("starter" if role == "independent-command-sequence" else role), cwd)
        launch = ["bash", "task.sh"]
        first = cwd / "first.json"
        assert run(launch + ["--report", str(first)], cwd)[0] == 0
        actual = json.loads(first.read_text())
        assert actual["package"]["Status"].split()[1:] == ["ok", "installed"]
        assert actual["state"]["selection"] == actual["package"]["Status"].split()[0]
        assert actual["state"]["errorFlag"] == "ok" and actual["state"]["current"] == "installed"
        # Query independently, rather than trusting the collector's installed flag.
        status, stdout, _ = run(["dpkg-query", "-W", "-f=${Version}\\n${Architecture}\\n${Status}\\n", "bash"], cwd)
        assert status == 0
        assert stdout.decode().splitlines() == [actual["package"][key] for key in ("Version", "Architecture", "Status")]
        assert actual["platform"] == "Linux" and actual["uid"] == os.geteuid()
        assert actual["hostPackageDatabaseModified"] is False and actual["learnerWorksheetCompletionInferred"] is False
        assert actual["files"] and any(row["category"] == "command" for row in actual["files"])
        assert any(row["category"] == "documentation" for row in actual["files"])
        for row in actual["files"]:
            path = Path(row["path"])
            assert row["exists"] == path.exists() and row["symlink"] == path.is_symlink()
            assert row["directory"] == path.is_dir()
            if path.is_symlink():
                assert row["linkTarget"] == os.readlink(path)
        assert actual["executable"]["tracked"] and "bash" in "\n".join(row["result"] for row in actual["executable"]["ownershipQueries"])
        assert all(row["exitCode"] in (0, 1) and row["pid"] > 0 and row["endTime"] >= row["startTime"] for row in actual["commands"])
        assert first.stat().st_mode & 0o777 == 0o600
        original = first.read_bytes()
        assert run(launch + ["--report", str(first)], cwd)[0] == 1 and first.read_bytes() == original
        changed = cwd / "changed.json"
        assert run(launch + ["--package", "coreutils", "--command", "ls", "--report", str(changed)], cwd)[0] == 0
        second = json.loads(changed.read_text())
        assert second["package"]["binary:Package"].split(":")[0] == "coreutils"
        assert second["executable"]["requested"] == "ls" and second["files"] != actual["files"]
        absent = cwd / "absent.json"
        assert run(launch + ["--package", "linux-course-package-absent-example", "--report", str(absent)], cwd)[0] == 1
        assert not absent.exists()
        invalid = cwd / "invalid.json"
        assert run(launch + ["--package", "bash*", "--report", str(invalid)], cwd)[0] == 2
        assert not invalid.exists()
        missing = cwd / "missing-command.json"
        assert run(launch + ["--command", "linux-course-command-absent", "--report", str(missing)], cwd)[0] == 1
        assert not missing.exists()
        manual = cwd / "bin"
        manual.mkdir()
        program = manual / "layout-owned-example"
        program.write_text("#!/bin/sh\nprintf 'owned manual example\\n'\n")
        program.chmod(0o700)
        untracked = cwd / "untracked.json"
        env = dict(os.environ, PATH=str(manual) + os.pathsep + os.environ["PATH"])
        assert run(launch + ["--command", program.name, "--report", str(untracked)], cwd, env=env)[0] == 0
        independent = json.loads(untracked.read_text())
        assert independent["executable"]["resolved"] == str(program)
        assert not independent["executable"]["tracked"]
        assert all(row["status"] == 1 for row in independent["executable"]["ownershipQueries"])
        if role == "independent-command-sequence":
            for package, executable in [("bash", "bash"), ("coreutils", "ls")]:
                assert run(["dpkg-query", "-L", package], cwd)[0] == 0
                resolved = shutil.which(executable)
                assert resolved and Path(resolved).exists()
        profile = dict(role=role, actualInstalledDatabase=True, filesystemCompared=True,
                       changedPackage=True, untrackedManualCommand=True,
                       existingEvidencePreserved=True, absentPackageRejected=True,
                       invalidNameRejected=True, missingCommandRejected=True,
                       noWorksheetCompletionInferred=True, privateReport=True)
        profiles.append(profile)
        (args.proof.parent / (role + "-package-report.json")).write_bytes(original)
        (args.proof.parent / (role + "-changed-package-report.json")).write_bytes(changed.read_bytes())
        (args.proof.parent / (role + "-untracked-package-report.json")).write_bytes(untracked.read_bytes())
finally:
    shutil.rmtree(root)
    args.proof.with_suffix(".processes.jsonl").write_text("".join(json.dumps(row) + "\n" for row in records))
assert hashes() == before
assert digest(host_database) == host_before
proof = dict(accepted=True, platform=platform.system(), uid=os.geteuid(),
             profiles=profiles, observations=observations, sourceHashes=before,
             sourceUnchanged=True, hostPackageDatabaseUnchanged=True,
             hostDatabaseSha256=host_before, worksheetCompletionNotInferred=True,
             temporaryFilesCleaned=not root.exists(), loggedLifecycles=len(records) // 2)
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps({key: value for key, value in proof.items() if key not in ("observations", "sourceHashes")}))
