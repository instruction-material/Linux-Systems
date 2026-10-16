"""Verify heartbeat contracts and actual owned systemd user-service operation."""
import argparse
import contextlib
import hashlib
import json
import os
import platform
import pwd
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path


def hashes():
    return {str(path.relative_to(PACK)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(PACK.rglob("*")) if path.is_file() and path.name != "verify_systemd_service.py"}


def run(command, cwd, env=None, expected=0, timeout=12):
    started = time.time()
    child = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, start_new_session=True)
    entry = {"parentTaskId": task, "parentPid": os.getpid(), "pid": child.pid,
             "command": command, "cwd": str(cwd), "startTime": started, "timeoutSeconds": timeout}
    processes.append({**entry, "event": "start"})
    cleanup = "process exited"
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
        cleanup = "owned process group terminated"
        raise
    finally:
        processes.append({**entry, "event": "end", "endTime": time.time(),
                          "exitCode": child.returncode, "childProcessGroupCleanup": cleanup})
    record = {"kind": "command", "command": command, "status": child.returncode,
              "stdout": out.decode(errors="replace"), "stderr": err.decode(errors="replace")}
    records.append(record)
    if expected is not None:
        assert child.returncode == expected, record
    return record


def properties(unit, cwd):
    result = run(["systemctl", "--user", "show", unit, "--property=LoadState,ActiveState,SubState,MainPID,ExecMainStatus,Result,NRestarts,InvocationID,UnitFileState"], cwd)
    return dict(line.split("=", 1) for line in result["stdout"].splitlines() if "=" in line)


def journal(unit, cwd):
    result = run(["journalctl", "--user", "-u", unit, "--no-pager", "-o", "json", "-n", "80"], cwd)
    return [json.loads(line) for line in result["stdout"].splitlines() if line.startswith("{")]


def wait_for(unit, cwd, condition, timeout=12):
    deadline = time.monotonic() + timeout
    while True:
        current = properties(unit, cwd)
        if condition(current):
            return current
        assert time.monotonic() < deadline, (unit, current)
        time.sleep(0.1)


def require_rows(unit, cwd, pid, message):
    deadline = time.monotonic() + 8
    while True:
        rows = journal(unit, cwd)
        matched = [row for row in rows if row.get("_PID") == str(pid) and str(row.get("MESSAGE", "")).startswith(message + ": heartbeat ")]
        if len(matched) >= 2:
            assert all(row.get("_UID") == str(os.geteuid()) for row in matched)
            records.append({"kind": "journal-evidence", "unit": unit, "pid": pid, "rows": matched})
            return
        assert time.monotonic() < deadline, (unit, pid, rows)
        time.sleep(0.1)


def owned_process(unit, cwd, state, app, timeout=8, *, read_properties=None, evidence=None):
    properties_reader = read_properties or properties
    if evidence is None:
        evidence = records
    pid = int(state["MainPID"])
    assert state["ActiveState"] == "active" and state["SubState"] == "running" and pid > 0
    expected = [b"/usr/bin/python3", b"-u", os.fsencode(app)]
    deadline = time.monotonic() + timeout
    attempts = []
    while True:
        current = properties_reader(unit, cwd)
        assert current["ActiveState"] == "active" and current["SubState"] == "running" and int(current["MainPID"]) == pid, current
        process = Path("/proc", str(pid))
        try:
            before_start = process.joinpath("stat").read_text().rsplit(") ", 1)[1].split()[19]
            argv = process.joinpath("cmdline").read_bytes().removesuffix(b"\0").split(b"\0")
            status = process.joinpath("status").read_text()
            uids = [int(value) for value in next(line.split()[1:] for line in status.splitlines() if line.startswith("Uid:"))]
            executable = process.joinpath("exe").resolve()
            after_start = process.joinpath("stat").read_text().rsplit(") ", 1)[1].split()[19]
        except FileNotFoundError:
            attempt = {"kind": "process-identity-pending", "unit": unit, "pid": pid,
                       "reason": "process identity not yet readable", "state": current}
        else:
            ready = argv == expected and executable == Path("/usr/bin/python3").resolve() and before_start == after_start
            attempt = {"kind": "process-identity-ready" if ready else "process-identity-pending", "unit": unit, "pid": pid, "state": current,
                       "observedArgv": [os.fsdecode(value) for value in argv], "observedUids": uids,
                       "executable": str(executable), "startTicks": after_start, "identityReady": ready}
            evidence.append(attempt)
            attempts.append(attempt)
            assert all(value == os.geteuid() for value in uids), attempt
            if ready:
                confirmed = properties_reader(unit, cwd)
                assert confirmed["ActiveState"] == "active" and confirmed["SubState"] == "running" and int(confirmed["MainPID"]) == pid, confirmed
                evidence.append({"kind": "managed-process", "unit": unit, "pid": pid, "uid": os.geteuid(),
                                "state": confirmed, "commandPath": str(app), "observedArgv": attempt["observedArgv"],
                                "startTicks": after_start, "identityAttempts": len(attempts)})
                return pid
            assert time.monotonic() < deadline, {"unit": unit, "pid": pid, "identityAttempts": attempts}
            time.sleep(0.05)
            continue
        evidence.append(attempt)
        attempts.append(attempt)
        assert time.monotonic() < deadline, {"unit": unit, "pid": pid, "identityAttempts": attempts}
        time.sleep(0.05)


def main():
    global args, PACK, records, processes, profiles, task
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    parser.add_argument("--proof", type=Path, required=True)
    parser.add_argument("--app-only", action="store_true")
    args = parser.parse_args()
    PACK = (args.source or Path(__file__).resolve().parents[1] / "LS5-Systemd-Toy-Service").resolve()
    args.proof = args.proof.resolve()
    args.proof.parent.mkdir(parents=True, exist_ok=True)
    records, processes, profiles = [], [], []
    task = os.environ.get("CLASSES_FAMILY_TASK_ID", "linux-systemd-source-ci")

    before = hashes()
    assert len(before) == 9
    accepted = False
    manager_version = None
    try:
        if not args.app_only:
            assert platform.system() == "Linux" and os.geteuid() != 0
            assert Path.home() == Path(pwd.getpwuid(os.geteuid()).pw_dir)
            assert all(shutil.which(name) for name in ("systemctl", "systemd-analyze", "journalctl"))
            manager_version = run(["systemctl", "--user", "show", "--property=Version", "--value"], PACK)["stdout"].strip()
            assert manager_version
        for role in ("starter", "solution", "independent-completion"):
            with tempfile.TemporaryDirectory(prefix="heartbeat-app-") as directory:
                work = Path(directory)
                selected = PACK / ("starter" if role == "independent-completion" else role)
                source = (selected / "heartbeat_app.py").read_text()
                if role == "independent-completion":
                    assert source.count("    return None") == 1
                    source = source.replace("    return None", '    return "{}: heartbeat {}".format(message, number)', 1)
                app = work / "heartbeat_app.py"
                app.write_text(source)
                env = dict(os.environ, HEARTBEAT_INTERVAL="0.1", HEARTBEAT_MESSAGE="sample", HEARTBEAT_LIMIT="2")
                expected = 78 if role == "starter" else 0
                result = run([sys.executable, str(app)], work, env, expected)
                assert result["stdout"] == ("" if role == "starter" else "sample: heartbeat 1\nsample: heartbeat 2\n")
                for interval in ("0", "nan", "inf", "-1", "01", "1e0", "60.01"):
                    invalid = run([sys.executable, str(app)], work, dict(env, HEARTBEAT_INTERVAL=interval), 2)
                    assert not invalid["stdout"] and "HEARTBEAT_INTERVAL" in invalid["stderr"]
                for limit in ("-1", "01", "10000", "abc"):
                    invalid = run([sys.executable, str(app)], work, dict(env, HEARTBEAT_LIMIT=limit), 2)
                    assert not invalid["stdout"] and "HEARTBEAT_LIMIT" in invalid["stderr"]
                for message in ("", "two\nlines", "x" * 129):
                    invalid = run([sys.executable, str(app)], work, dict(env, HEARTBEAT_MESSAGE=message), 2)
                    assert not invalid["stdout"] and "HEARTBEAT_MESSAGE" in invalid["stderr"]
                unicode_case = run([sys.executable, str(app)], work, dict(env, HEARTBEAT_MESSAGE="café", HEARTBEAT_LIMIT="1"), expected)
                assert unicode_case["stdout"] == ("" if role == "starter" else "café: heartbeat 1\n")
                if args.app_only:
                    profiles.append({"role": role, "appOnly": True})
                    continue
                name = "linux-heartbeat-ci-" + uuid.uuid4().hex
                unit = name + ".service"
                install = Path.home() / ".local/share" / name
                unit_root = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "systemd/user"
                unit_root.mkdir(parents=True, exist_ok=True)
                unit_file = unit_root / unit
                assert not install.exists() and not unit_file.exists()
                install.mkdir(parents=True)
                installed_app = install / "heartbeat_app.py"
                installed_app.write_text(source)
                env_file = install / "heartbeat.env"
                message = "native-" + role
                good_env = "HEARTBEAT_INTERVAL=0.1\nHEARTBEAT_MESSAGE=" + message + "\nHEARTBEAT_LIMIT=0\n"
                env_file.write_text(good_env)
                unit_text = (selected / "linux-heartbeat.service").read_text()
                prefix = "%h/.local/share/linux-heartbeat"
                assert unit_text.count(prefix) == 3
                unit_file.write_text(unit_text.replace(prefix, "%h/.local/share/" + name))

                try:
                    run(["systemd-analyze", "--user", "verify", str(unit_file)], work)
                    run(["systemctl", "--user", "daemon-reload"], work)
                    run(["systemctl", "--user", "start", unit], work)
                    if role == "starter":
                        failed = wait_for(unit, work, lambda s: s["ActiveState"] == "failed" and s["ExecMainStatus"] == "78")
                        assert failed["MainPID"] == "0" and failed["NRestarts"] == "0"
                        rows = journal(unit, work)
                        assert any("unfinished render_heartbeat task" in str(row.get("MESSAGE", "")) for row in rows)
                        profiles.append({"role": role, "actualManager": True, "namedUnfinishedStatus": 78, "restartLoopPrevented": True})
                        continue
                    state = wait_for(unit, work, lambda s: s["ActiveState"] == "active" and s["SubState"] == "running")
                    pid = owned_process(unit, work, state, installed_app)
                    require_rows(unit, work, pid, message)
                    run(["systemctl", "--user", "enable", unit], work)
                    assert run(["systemctl", "--user", "is-enabled", unit], work)["stdout"].strip() == "enabled"
                    assert (unit_root / "default.target.wants" / unit).is_symlink()
                    run(["systemctl", "--user", "stop", unit], work)
                    stopped = wait_for(unit, work, lambda s: s["ActiveState"] == "inactive" and s["MainPID"] == "0")
                    assert stopped["UnitFileState"] == "enabled"
                    run(["systemctl", "--user", "start", unit], work)
                    state = wait_for(unit, work, lambda s: s["ActiveState"] == "active" and int(s["MainPID"]) > 0)
                    first = owned_process(unit, work, state, installed_app)
                    run(["systemctl", "--user", "restart", unit], work)
                    state = wait_for(unit, work, lambda s, previous=first: s["ActiveState"] == "active" and int(s["MainPID"]) > 0 and int(s["MainPID"]) != previous)
                    manual_pid = owned_process(unit, work, state, installed_app)
                    require_rows(unit, work, manual_pid, message)
                    run(["systemctl", "--user", "reset-failed", unit], work)
                    state = properties(unit, work)
                    before_restart = int(state["NRestarts"])
                    os.kill(manual_pid, signal.SIGKILL)
                    state = wait_for(unit, work, lambda s, previous=manual_pid, count=before_restart: s["ActiveState"] == "active" and int(s["MainPID"]) > 0 and int(s["MainPID"]) != previous and int(s["NRestarts"]) > count)
                    automatic_pid = owned_process(unit, work, state, installed_app)
                    require_rows(unit, work, automatic_pid, message)
                    env_file.write_text("HEARTBEAT_INTERVAL=0\nHEARTBEAT_MESSAGE=broken-lab\nHEARTBEAT_LIMIT=0\n")
                    run(["systemctl", "--user", "restart", unit], work, expected=None)
                    failed = wait_for(unit, work, lambda s: s["ActiveState"] == "failed" and s["MainPID"] == "0" and s["ExecMainStatus"] == "2" and int(s["NRestarts"]) >= 2)
                    failed_rows = journal(unit, work)
                    assert any("HEARTBEAT_INTERVAL" in str(row.get("MESSAGE", "")) for row in failed_rows)
                    assert any("Start request repeated too quickly" in str(row.get("MESSAGE", "")) for row in failed_rows)
                    time.sleep(1.2)
                    stable = properties(unit, work)
                    assert stable["ActiveState"] == "failed" and stable["MainPID"] == "0"
                    assert stable["NRestarts"] == failed["NRestarts"]
                    records.append({"kind": "start-limit-evidence", "unit": unit, "reportedResult": failed["Result"], "state": stable, "journalRows": failed_rows})
                    env_file.write_text(good_env)
                    run(["systemctl", "--user", "reset-failed", unit], work)
                    run(["systemctl", "--user", "start", unit], work)
                    state = wait_for(unit, work, lambda s: s["ActiveState"] == "active" and s["SubState"] == "running")
                    recovered = owned_process(unit, work, state, installed_app)
                    require_rows(unit, work, recovered, message)
                    profiles.append({"role": role, "actualManager": True, "actualJournal": True,
                                     "manualRestart": True, "automaticRestart": True, "persistentEnable": True,
                                     "enabledAndStopped": True, "invalidEnvironmentFailure": True, "recovered": True})
                finally:
                    run(["systemctl", "--user", "stop", unit], work, expected=None)
                    run(["systemctl", "--user", "disable", unit], work, expected=None)
                    run(["systemctl", "--user", "reset-failed", unit], work, expected=None)
                    unit_file.unlink(missing_ok=True)
                    run(["systemctl", "--user", "daemon-reload"], work)
                    assert not (unit_root / "default.target.wants" / unit).exists()
                    final = properties(unit, work)
                    assert final["LoadState"] == "not-found" and final["MainPID"] == "0"
                    shutil.rmtree(install)
                    records.append({"kind": "cleanup", "unit": unit, "unitRemoved": True, "processStopped": True, "activationRemoved": True, "installRemoved": True})
        assert len(profiles) == 3 and hashes() == before
        accepted = True
    finally:
        args.proof.with_suffix(".processes.jsonl").write_text("".join(json.dumps(row) + "\n" for row in processes))
        args.proof.write_text(json.dumps({"accepted": accepted, "appOnly": args.app_only,
                                         "managerVersion": manager_version, "platform": platform.platform(),
                                         "sourceHashes": before, "profiles": profiles, "observations": records,
                                         "independentLearnerCompletions": 1, "sourceUnchanged": hashes() == before}, indent=2) + "\n")
    print(json.dumps({"accepted": accepted, "appOnly": args.app_only, "profiles": len(profiles), "observations": len(records)}))


if __name__ == "__main__":
    main()
