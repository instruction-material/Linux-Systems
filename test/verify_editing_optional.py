#!/usr/bin/env python3
"""Exercise actual child environments and bounded multi-file replacements."""

import argparse
import hashlib
import json
import os
import queue
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENT = "LS-09-unit-4-editing-and-configuration-supplemental-2"
REPLACEMENT = "LS-10-unit-4-editing-and-configuration-supplemental-3"
OBSERVATIONS = []
PROFILES = []


def now():
    return datetime.now(timezone.utc).isoformat()


def source_hashes():
    return {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for pack in (ENVIRONMENT, REPLACEMENT)
        for path in sorted((ROOT / pack).rglob("*"))
        if path.is_file()
    }


def run(command, cwd, expected=0, env=None):
    command = [str(x) for x in command]
    start = now()
    child = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    cleanup = "not needed"
    try:
        stdout, stderr = child.communicate(timeout=10)
    except BaseException:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGKILL)
        stdout, stderr = child.communicate()
        cleanup = "owned child group terminated"
        raise
    finally:
        OBSERVATIONS.append(
            {
                "kind": "command",
                "parentTask": "linux-editing-optional-source",
                "parentPid": os.getpid(),
                "cwd": str(cwd),
                "command": command,
                "pid": child.pid,
                "startTime": start,
                "endTime": now(),
                "exitCode": child.returncode,
                "timeoutSeconds": 10,
                "childProcessGroupCleanup": cleanup,
            }
        )
    OBSERVATIONS[-1].update(
        stdout=stdout.decode(errors="replace"), stderr=stderr.decode(errors="replace")
    )
    assert child.returncode == expected, OBSERVATIONS[-1]
    return stdout


@contextmanager
def watched(command, cwd):
    start = now()
    command = [str(x) for x in command]
    child = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    records = queue.Queue()

    def read():
        for line in child.stdout:
            records.put(json.loads(line))

    reader = threading.Thread(target=read, daemon=True)
    reader.start()

    def receive(event):
        record = records.get(timeout=4)
        assert record.get("event") == event and record.get("pid") == child.pid, record
        assert record["uid"] == os.getuid()
        OBSERVATIONS.append({"kind": "actual-environment", **record})
        return record

    cleanup = "TERM requested"
    try:
        first = receive("started")
        yield child, receive, first
    finally:
        if child.poll() is None:
            child.send_signal(signal.SIGTERM)
        try:
            child.wait(timeout=4)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=2)
            cleanup = "owned child group killed after timeout"
        reader.join(timeout=2)
        while not records.empty():
            OBSERVATIONS.append({"kind": "actual-environment", **records.get_nowait()})
        stderr = child.stderr.read()
        child.stdout.close()
        child.stderr.close()
        OBSERVATIONS.append(
            {
                "kind": "watched-lifecycle",
                "parentTask": "linux-editing-optional-source",
                "parentPid": os.getpid(),
                "cwd": str(cwd),
                "command": command,
                "pid": child.pid,
                "uid": os.getuid(),
                "startTime": start,
                "endTime": now(),
                "exitCode": child.returncode,
                "timeoutSeconds": 4,
                "childProcessGroupCleanup": cleanup,
                "processStopped": child.poll() is not None,
                "readerStopped": not reader.is_alive(),
                "stderr": stderr,
            }
        )
        assert child.returncode == 0 and not reader.is_alive(), OBSERVATIONS[-1]


def completed_copy(pack, role_name, destination):
    shutil.copytree(
        ROOT / pack / ("solution" if role_name == "solution" else "starter"),
        destination,
    )
    if role_name != "independent-completion":
        return
    file = destination / "task.sh"
    text = file.read_text()
    if pack == ENVIRONMENT:
        begin, end = "    # EXPORT_BEGIN", "    # EXPORT_END"
        replacement = (
            "    # EXPORT_BEGIN\n    declare -x MESSAGE REPEAT\n    # EXPORT_END"
        )
    else:
        begin, end = "    # REPLACE_BEGIN", "    # REPLACE_END"
        replacement = r"""    # REPLACE_BEGIN
    sed -E "s@^([[:blank:]]*timeout[[:blank:]]*=[[:blank:]]*)[[:digit:]]+([[:blank:]]*(#.*)?)\$@\1${new_value}\2@" "$source" > "$destination"
    # REPLACE_END"""
    first = text.index(begin)
    last = text.index(end, first) + len(end)
    file.write_text(text[:first] + replacement + text[last:])


def environment_profile(role_name):
    with tempfile.TemporaryDirectory(prefix="unit4-environment-") as temporary:
        base = Path(temporary)
        role = base / "role source"
        completed_copy(ENVIRONMENT, role_name, role)
        settings = base / "owned settings.env"
        original = (role / "settings.env").read_bytes()
        settings.write_bytes(original)
        profile = {"kind": "environment", "role": role_name}
        if role_name == "starter":
            assert run(["bash", "task.sh", settings], role, 78) == b""
            assert "unfinished: export MESSAGE and REPEAT" in OBSERVATIONS[-1]["stderr"]
            assert settings.read_bytes() == original
            profile.update(
                namedUnfinishedStatus=78,
                settingsUnchanged=True,
                childApplicationStarted=False,
            )
        else:
            parent_values = (os.environ.get("MESSAGE"), os.environ.get("REPEAT"))
            outer = dict(os.environ, MESSAGE="Parent-only value", REPEAT="5")
            value = json.loads(run(["bash", "task.sh", settings], role, env=outer))
            assert value["message"] == "Environment baseline" and value["repeat"] == 2
            assert (
                value["pid"] == OBSERVATIONS[-1]["pid"] and value["uid"] == os.getuid()
            )
            with watched(["bash", "task.sh", settings, "--watch"], role) as (
                child,
                receive,
                first,
            ):
                assert (
                    first["message"] == "Environment baseline" and first["repeat"] == 2
                )
                first_pid = child.pid
                settings.write_text("MESSAGE='Changed disk value'\nREPEAT=3\n")
                child.send_signal(signal.SIGUSR1)
                unchanged = receive("snapshot")
                assert (
                    unchanged["message"] == "Environment baseline"
                    and unchanged["repeat"] == 2
                )
            with watched(["bash", "task.sh", settings, "--watch"], role) as (
                child,
                receive,
                first,
            ):
                assert (
                    child.pid != first_pid
                    and first["message"] == "Changed disk value"
                    and first["repeat"] == 3
                )
                second_pid = child.pid
                child.send_signal(signal.SIGUSR1)
                assert (
                    receive("snapshot")["rendered"]
                    == "Changed disk value Changed disk value Changed disk value"
                )
            file_before_override = settings.read_bytes()
            value = json.loads(
                run(
                    ["bash", "task.sh", settings, "--message", "Explicit override"],
                    role,
                )
            )
            assert value["message"] == "Explicit override" and value["repeat"] == 3
            assert (
                value["pid"] == OBSERVATIONS[-1]["pid"]
                and settings.read_bytes() == file_before_override
            )
            assert run(["bash", "task.sh", settings, "--message", ""], role, 2) == b""
            settings.write_text("MESSAGE='unterminated\nREPEAT=2\n")
            assert run(["bash", "task.sh", settings, "--watch"], role, 2) == b""
            assert "invalid environment" not in OBSERVATIONS[-1]["stderr"]
            settings.write_text("MESSAGE='value case'\nREPEAT=9\n")
            run(["bash", "-n", settings], role)
            assert run(["bash", "task.sh", settings, "--watch"], role, 2) == b""
            assert "invalid environment" in OBSERVATIONS[-1]["stderr"]
            settings.write_text("REPEAT=2\n")
            assert run(["bash", "task.sh", settings], role, 2) == b""
            settings.write_text("MESSAGE='Literal $HOME and spaces'\nREPEAT=1\n")
            value = json.loads(run(["bash", "task.sh", settings], role))
            assert (
                value["rendered"] == "Literal $HOME and spaces" and value["repeat"] == 1
            )
            assert (
                os.environ.get("MESSAGE"),
                os.environ.get("REPEAT"),
            ) == parent_values
            linked = base / "linked settings.env"
            linked.symlink_to(settings)
            before = settings.read_bytes()
            run(["bash", "task.sh", linked], role, 73)
            assert settings.read_bytes() == before
            profile.update(
                actualChildEnvironment=True,
                callerValuesIsolated=True,
                parentEnvironmentUnchanged=True,
                actualUid=os.getuid(),
                firstPid=first_pid,
                restartedPid=second_pid,
                fileEditLeavesRunningEnvironment=True,
                restartLoadsNewFile=True,
                explicitOverride=True,
                overrideLeavesFileUnchanged=True,
                syntaxFailureBeforeApplication=True,
                valueFailureDistinct=True,
                missingSettingRejected=True,
                singleQuotesRemainLiteral=True,
                symlinkRefused=True,
                watchedProcessesStopped=True,
            )
        PROFILES.append(profile)
    assert not base.exists()
    OBSERVATIONS.append(
        {
            "kind": "cleanup",
            "pack": ENVIRONMENT,
            "role": role_name,
            "temporaryDirectoryRemoved": True,
            "processesStopped": True,
        }
    )


def backup_path(output):
    paths = [
        Path(line[7:])
        for line in output.decode().splitlines()
        if line.startswith("backup=")
    ]
    assert len(paths) == 1 and (paths[0] / ".complete").is_file()
    return paths[0]


def pair(lab):
    return {
        name: (lab / name).read_bytes() for name in ("primary.conf", "secondary.conf")
    }


def expected_pair(original, value):
    return {
        "primary.conf": original["primary.conf"].replace(
            b"timeout = 10  #", f"timeout = {value}  #".encode()
        ),
        "secondary.conf": original["secondary.conf"].replace(
            b"timeout=20#", f"timeout={value}#".encode()
        ),
    }


def replacement_profile(role_name):
    with tempfile.TemporaryDirectory(prefix="unit4-replacement-") as temporary:
        base = Path(temporary)
        role, lab = base / "role source", base / "owned lab with spaces"
        completed_copy(REPLACEMENT, role_name, role)
        lab.mkdir()
        run(["bash", "task.sh", "init", lab], role)
        original = pair(lab)
        for name, mode in (("primary.conf", 0o640), ("secondary.conf", 0o600)):
            os.chmod(lab / name, mode)
        profile = {"kind": "replacement", "role": role_name}
        if role_name == "starter":
            for action in ("preview", "apply"):
                run(["bash", "task.sh", action, lab, "25"], role, 78)
                assert (
                    "unfinished: implement the anchored timeout replacement"
                    in OBSERVATIONS[-1]["stderr"]
                )
                assert (
                    pair(lab) == original
                    and not list(lab.glob("backup.*"))
                    and not list(lab.glob(".edit.*"))
                )
            profile.update(
                namedUnfinishedStatus=78,
                currentFilesUnchanged=True,
                noBackupCreated=True,
                stagingRemoved=True,
            )
        else:
            output = run(["bash", "task.sh", "preview", lab, "25"], role)
            assert b"--- " in output and b"+++ " in output and pair(lab) == original
            assert not list(lab.glob("backup.*")) and not list(lab.glob(".edit.*"))
            backup = backup_path(run(["bash", "task.sh", "apply", lab, "25"], role))
            assert pair(backup) == original and pair(lab) == expected_pair(original, 25)
            assert (lab / "primary.conf").stat().st_mode & 0o777 == 0o640
            assert (lab / "secondary.conf").stat().st_mode & 0o777 == 0o600
            run(["bash", "task.sh", "rollback", lab, backup], role)
            assert pair(lab) == original
            for bad in (
                original["secondary.conf"] + b"timeout=2\n",
                original["secondary.conf"].replace(
                    b"timeout=20#secondary budget\n", b""
                ),
            ):
                (lab / "secondary.conf").write_bytes(bad)
                before = pair(lab)
                backups = {x.name for x in lab.glob("backup.*")}
                run(["bash", "task.sh", "apply", lab, "30"], role, 2)
                assert (
                    pair(lab) == before
                    and {x.name for x in lab.glob("backup.*")} == backups
                )
                assert not list(lab.glob(".edit.*"))
                (lab / "secondary.conf").write_bytes(original["secondary.conf"])
            for value in ("0", "61", "2x", "-1"):
                run(["bash", "task.sh", "apply", lab, value], role, 64)
                assert pair(lab) == original
            changed = b"# timeout=59 is only an example\nname=changed10\n\ttimeout\t=\t1\t # new comment60\nnote=Keep 1 and 60 unchanged\n"
            (lab / "primary.conf").write_bytes(changed)
            changed_original = pair(lab)
            changed_backup = backup_path(
                run(["bash", "task.sh", "apply", lab, "60"], role)
            )
            assert (lab / "primary.conf").read_bytes() == changed.replace(
                b"\t1\t #", b"\t60\t #"
            )
            assert (lab / "secondary.conf").read_bytes() == expected_pair(original, 60)[
                "secondary.conf"
            ]
            run(["bash", "task.sh", "rollback", lab, changed_backup], role)
            assert pair(lab) == changed_original
            (lab / "primary.conf").write_bytes(original["primary.conf"])
            wrapper = base / "fault tools"
            wrapper.mkdir()
            real_mv = shutil.which("mv")
            assert real_mv
            move = wrapper / "mv"
            move.write_text(
                '#!/usr/bin/env bash\nfor last; do :; done\ncase "$last" in */secondary.conf) exit 99;; esac\nexec '
                + shlex.quote(real_mv)
                + ' "$@"\n'
            )
            move.chmod(0o755)
            fault_env = dict(
                os.environ, PATH=str(wrapper) + os.pathsep + os.environ["PATH"]
            )
            failed_backup = backup_path(
                run(["bash", "task.sh", "apply", lab, "35"], role, 99, env=fault_env)
            )
            assert pair(failed_backup) == original
            assert (lab / "primary.conf").read_bytes() == expected_pair(original, 35)[
                "primary.conf"
            ]
            assert (lab / "secondary.conf").read_bytes() == original["secondary.conf"]
            OBSERVATIONS.append(
                {
                    "kind": "forced-second-rename-failure",
                    "role": role_name,
                    "status": 99,
                    "firstFileChanged": True,
                    "secondFileUnchanged": True,
                    "completeBackupExact": True,
                }
            )
            run(["bash", "task.sh", "rollback", lab, failed_backup], role)
            assert pair(lab) == original
            foreign = base / "backup.foreign"
            shutil.copytree(backup, foreign)
            run(["bash", "task.sh", "rollback", lab, foreign], role, 73)
            assert pair(lab) == original
            outside = base / "outside evidence.conf"
            outside.write_bytes(original["secondary.conf"])
            (lab / "secondary.conf").unlink()
            (lab / "secondary.conf").symlink_to(outside)
            run(["bash", "task.sh", "apply", lab, "25"], role, 73)
            assert outside.read_bytes() == original["secondary.conf"]
            (lab / "secondary.conf").unlink()
            (lab / "secondary.conf").write_bytes(original["secondary.conf"])
            (backup / "secondary.conf").write_text("invalid backup")
            run(["bash", "task.sh", "rollback", lab, backup], role, 2)
            assert pair(lab) == original and not list(lab.glob(".edit.*"))
            run(["bash", "task.sh", "init", lab], role, 73)
            profile.update(
                previewLeavesBytesUnchanged=True,
                exactAnchoredEdits=True,
                commentsAndUnrelatedNumbersPreserved=True,
                completeBackupsExact=True,
                modesPreserved=True,
                missingAndDuplicateRejectedBeforeApply=True,
                invalidRequestedValuesRejected=True,
                changedWhitespaceCase=True,
                actualSecondRenameFailure=True,
                explicitRollbackRestoresBoth=True,
                outsideBackupRefused=True,
                symlinkRefused=True,
                invalidBackupLeavesCurrentUnchanged=True,
                stagingRemoved=True,
            )
        PROFILES.append(profile)
    assert not base.exists()
    OBSERVATIONS.append(
        {
            "kind": "cleanup",
            "pack": REPLACEMENT,
            "role": role_name,
            "temporaryDirectoryRemoved": True,
            "processesStopped": True,
        }
    )


def offline_checks():
    for pack in (ENVIRONMENT, REPLACEMENT):
        for role in ("starter", "solution"):
            cwd = ROOT / pack / role
            run(["bash", "-n", "task.sh"], cwd)
            if pack == ENVIRONMENT:
                run(["bash", "-n", "settings.env"], cwd)
                value = json.loads(
                    run(
                        [sys.executable, "environment_app.py"],
                        cwd,
                        env={
                            "PATH": os.environ["PATH"],
                            "MESSAGE": "Direct value",
                            "REPEAT": "3",
                        },
                    )
                )
                assert value["rendered"] == "Direct value Direct value Direct value"
            else:
                for name in ("primary.conf", "secondary.conf"):
                    run([sys.executable, "validate_config.py", name], cwd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proof", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--offline-only", action="store_true")
    mode.add_argument("--local-process-preflight", action="store_true")
    args = parser.parse_args()
    original = source_hashes()
    failure = None
    native_gnu = False
    try:
        offline_checks()
        if not args.offline_only:
            assert os.geteuid() != 0, "use an ordinary account"
            assert args.local_process_preflight or sys.platform == "linux", (
                "native acceptance requires Linux"
            )
            if not args.local_process_preflight:
                assert b"GNU sed" in run(["sed", "--version"], ROOT)
                assert b"GNU coreutils" in run(["chmod", "--version"], ROOT)
                native_gnu = True
            for role in ("starter", "solution", "independent-completion"):
                environment_profile(role)
                replacement_profile(role)
    except BaseException as error:
        failure = repr(error)
        raise
    finally:
        unchanged = original == source_hashes()
        accepted = (
            failure is None
            and unchanged
            and native_gnu
            and len(PROFILES) == 6
            and not args.offline_only
            and not args.local_process_preflight
        )
        proof = {
            "accepted": accepted,
            "offlineOnly": args.offline_only,
            "localProcessPreflight": args.local_process_preflight,
            "platform": sys.platform,
            "nativeGNUVerified": native_gnu,
            "sourceHashes": original,
            "sourceUnchanged": unchanged,
            "profiles": PROFILES,
            "observations": OBSERVATIONS,
            "failure": failure,
        }
        args.proof.parent.mkdir(parents=True, exist_ok=True)
        args.proof.write_text(json.dumps(proof, indent=2) + "\n")
        print(
            json.dumps(
                {
                    "accepted": accepted,
                    "profiles": len(PROFILES),
                    "observations": len(OBSERVATIONS),
                }
            )
        )


if __name__ == "__main__":
    main()
