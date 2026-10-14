#!/usr/bin/env python3
"""Verify the actual disposable configuration process and file-edit contract."""

import argparse
import hashlib
import json
import os
import queue
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
PACK = ROOT / "LS-07-unit-4-editing-and-configuration"
TASK = "linux-unit4-editing-source"
OBSERVATIONS = []
PROFILES = []


def now():
    return datetime.now(timezone.utc).isoformat()


def hashes():
    return {
        str(path.relative_to(PACK)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(PACK.rglob("*"))
        if path.is_file()
    }


def run(command, cwd, expected=0):
    start = now()
    process = subprocess.Popen(
        [str(x) for x in command],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    cleanup = "not needed"
    try:
        stdout, stderr = process.communicate(timeout=10)
    except BaseException:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        cleanup = "owned child group terminated"
        raise
    finally:
        OBSERVATIONS.append(
            {
                "kind": "command",
                "parentTask": TASK,
                "parentPid": os.getpid(),
                "cwd": str(cwd),
                "command": [str(x) for x in command],
                "pid": process.pid,
                "startTime": start,
                "endTime": now(),
                "exitCode": process.returncode,
                "timeoutSeconds": 10,
                "childProcessGroupCleanup": cleanup,
            }
        )
    OBSERVATIONS[-1].update(
        stdout=stdout.decode(errors="replace"), stderr=stderr.decode(errors="replace")
    )
    assert process.returncode == expected, OBSERVATIONS[-1]
    return stdout


@contextmanager
def application(role, lab):
    command = [sys.executable, "config_app.py", "run", str(lab / "config.json")]
    start = now()
    process = subprocess.Popen(
        command,
        cwd=role,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    records = queue.Queue()

    def read():
        for line in process.stdout:
            try:
                records.put(json.loads(line))
            except ValueError:
                records.put({"unparsed": line})

    reader = threading.Thread(target=read, daemon=True)
    reader.start()

    def receive(event):
        record = records.get(timeout=4)
        assert record.get("event") == event and record.get("pid") == process.pid, record
        OBSERVATIONS.append(dict(kind="actual-process-output", **record))
        return record

    cleanup = "TERM requested"
    try:
        receive("started")
        yield process, receive
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
        try:
            process.wait(timeout=4)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=2)
            cleanup = "owned child group killed after timeout"
        reader.join(timeout=2)
        while not records.empty():
            OBSERVATIONS.append(
                dict(kind="actual-process-output", **records.get_nowait())
            )
        stderr = process.stderr.read()
        process.stdout.close()
        process.stderr.close()
        OBSERVATIONS.append(
            {
                "kind": "process-lifecycle",
                "parentTask": TASK,
                "parentPid": os.getpid(),
                "cwd": str(role),
                "command": command,
                "pid": process.pid,
                "uid": os.getuid(),
                "startTime": start,
                "endTime": now(),
                "exitCode": process.returncode,
                "timeoutSeconds": 4,
                "childProcessGroupCleanup": cleanup,
                "processStopped": process.poll() is not None,
                "readerStopped": not reader.is_alive(),
                "stderr": stderr,
            }
        )
        assert process.returncode == 0 and not reader.is_alive(), OBSERVATIONS[-1]


def snapshot(process, receive):
    process.send_signal(signal.SIGUSR1)
    return receive("snapshot")


def reload(process, receive, event="reloaded"):
    process.send_signal(signal.SIGHUP)
    return receive(event)


def write_config(path, message="Edited configuration", repeat=2):
    path.write_text(json.dumps({"message": message, "repeat": repeat}) + "\n")


def independent_completion(role):
    path = role / "task.sh"
    script = path.read_text()
    begin = script.index("        # APPLY_BEGIN")
    end = script.index("        # APPLY_END", begin) + len("        # APPLY_END")
    completion = """        # APPLY_BEGIN
        for proposed in "$lab/config.json" "$lab/candidate.json"; do
            python3 "$app" validate "$proposed"
        done
        next_file=$(mktemp "$lab/.learner.XXXXXX")
        trap 'rm -f -- "$next_file"' EXIT
        cp -- "$lab/candidate.json" "$next_file"
        chmod --reference="$lab/config.json" "$next_file"
        cp -p -- "$lab/config.json" "$lab/config.before.json"
        mv -- "$next_file" "$lab/config.json"
        # APPLY_END"""
    path.write_text(script[:begin] + completion + script[end:])
    write_config(role / "candidate.json")


def offline_checks():
    for role in ("starter", "solution"):
        cwd = PACK / role
        run(["bash", "-n", "task.sh"], cwd)
        run([sys.executable, "config_app.py", "validate", "config.json"], cwd)
        run(
            [sys.executable, "config_app.py", "validate", "candidate.json"],
            cwd,
            expected=2 if role == "starter" else 0,
        )
    invalid = [
        "{",
        '{"message":"x","repeat":1,"repeat":2}',
        '{"message":"x","repeat":true}',
        '{"message":"x","repeat":"2"}',
        '{"message":"x","repeat":0}',
        '{"message":"x","repeat":6}',
        '{"message":"","repeat":1}',
        '{"message":"x\\ny","repeat":1}',
        '{"message":"x","repeat":1,"extra":0}',
        '{"repeat":1}',
    ]
    with tempfile.TemporaryDirectory(prefix="unit4-invalid-") as temporary:
        path = Path(temporary) / "changed.json"
        for value in invalid:
            path.write_text(value)
            run(
                [sys.executable, "config_app.py", "validate", path],
                PACK / "solution",
                expected=2,
            )


def native_profile(role_name):
    with tempfile.TemporaryDirectory(prefix="unit4-owned-") as temporary:
        base = Path(temporary)
        role = base / "role source"
        shutil.copytree(
            PACK / ("starter" if role_name != "solution" else "solution"), role
        )
        if role_name == "independent-completion":
            independent_completion(role)
        lab = base / "owned lab with spaces"
        lab.mkdir()
        run(["bash", "task.sh", "init", lab], role)
        current, candidate, backup = (
            lab / name
            for name in ("config.json", "candidate.json", "config.before.json")
        )
        baseline = current.read_bytes()
        os.chmod(current, 0o640)
        write_config(candidate)
        result = {
            "role": role_name,
            "actualOwnedProcess": True,
            "ownedUid": os.getuid(),
        }
        with application(role, lab) as (process, receive):
            assert snapshot(process, receive)["rendered"] == "Baseline ready"
            if role_name == "starter":
                output = run(["bash", "task.sh", "apply", lab], role, expected=78)
                assert (
                    output == b""
                    and current.read_bytes() == baseline
                    and not backup.exists()
                )
                assert (
                    "unfinished: implement the validated apply step"
                    in OBSERVATIONS[-1]["stderr"]
                )
                assert snapshot(process, receive)["rendered"] == "Baseline ready"
                result.update(
                    namedUnfinishedStatus=78,
                    unfinishedLeavesActiveBytes=True,
                    backupUncreated=True,
                )
            else:
                run(["bash", "task.sh", "apply", lab], role)
                accepted = candidate.read_bytes()
                assert (
                    current.read_bytes() == accepted and backup.read_bytes() == baseline
                )
                assert current.stat().st_mode & 0o777 == 0o640
                assert snapshot(process, receive)["rendered"] == "Baseline ready"
                assert (
                    reload(process, receive)["rendered"]
                    == "Edited configuration Edited configuration"
                )
                assert (
                    snapshot(process, receive)["rendered"]
                    == "Edited configuration Edited configuration"
                )
                for invalid in (
                    '{"message":"bad","repeat":0}',
                    '{"message":"bad","repeat":1,"repeat":2}',
                ):
                    candidate.write_text(invalid)
                    run(["bash", "task.sh", "apply", lab], role, expected=2)
                    assert (
                        current.read_bytes() == accepted
                        and backup.read_bytes() == baseline
                    )
                assert snapshot(process, receive)["repeat"] == 2
                current.write_text('{"message":"broken","repeat":99}')
                write_config(candidate)
                broken = current.read_bytes()
                run(["bash", "task.sh", "apply", lab], role, expected=2)
                assert (
                    current.read_bytes() == broken and backup.read_bytes() == baseline
                )
                rejected = reload(process, receive, "reload-rejected")
                assert rejected["repeat"] == 2 and "integer" in rejected["reason"]
                run(["bash", "task.sh", "rollback", lab], role)
                assert current.read_bytes() == baseline
                assert snapshot(process, receive)["repeat"] == 2
                assert reload(process, receive)["rendered"] == "Baseline ready"
                write_config(candidate, "A changed case", 3)
                run(["bash", "task.sh", "apply", lab], role)
                assert (
                    reload(process, receive)["rendered"]
                    == "A changed case A changed case A changed case"
                )
                active_bytes, backup_bytes = current.read_bytes(), backup.read_bytes()
                outside = base / "outside evidence.json"
                outside.write_bytes(baseline)
                candidate.unlink()
                candidate.symlink_to(outside)
                run(["bash", "task.sh", "apply", lab], role, expected=73)
                assert (
                    outside.read_bytes() == baseline
                    and current.read_bytes() == active_bytes
                )
                assert backup.read_bytes() == backup_bytes
                candidate.unlink()
                write_config(candidate)
                backup.write_text("invalid backup")
                run(["bash", "task.sh", "rollback", lab], role, expected=2)
                assert current.read_bytes() == active_bytes
                run(["bash", "task.sh", "init", lab], role, expected=73)
                result.update(
                    exactBackupAndApply=True,
                    cachedBeforeReload=True,
                    validReload=True,
                    invalidCandidateNoWrite=True,
                    invalidCurrentPreservesBackup=True,
                    invalidReloadKeepsProcess=True,
                    exactRollback=True,
                    changedCase=True,
                    modePreserved=True,
                    symlinkBoundary=True,
                    invalidBackupRejected=True,
                    nonemptyInitializationRejected=True,
                )
        result["processStopped"] = True
        PROFILES.append(result)
    OBSERVATIONS.append(
        {
            "kind": "cleanup",
            "role": role_name,
            "processStopped": True,
            "temporaryDirectoryRemoved": not base.exists(),
        }
    )
    assert not base.exists()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proof", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--offline-only", action="store_true")
    mode.add_argument("--local-process-preflight", action="store_true")
    args = parser.parse_args()
    original = hashes()
    failure = None
    try:
        offline_checks()
        if not args.offline_only:
            assert os.geteuid() != 0, "use an ordinary account"
            assert args.local_process_preflight or sys.platform == "linux", (
                "native acceptance requires Linux"
            )
            for role in ("starter", "solution", "independent-completion"):
                native_profile(role)
    except BaseException as error:
        failure = repr(error)
        raise
    finally:
        unchanged = original == hashes()
        accepted = (
            failure is None
            and unchanged
            and not args.offline_only
            and not args.local_process_preflight
            and sys.platform == "linux"
            and len(PROFILES) == 3
        )
        proof = {
            "accepted": accepted,
            "offlineOnly": args.offline_only,
            "localProcessPreflight": args.local_process_preflight,
            "platform": sys.platform,
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
                    "offlineOnly": args.offline_only,
                    "profiles": len(PROFILES),
                    "observations": len(OBSERVATIONS),
                }
            )
        )


if __name__ == "__main__":
    main()
