"""Verify distinct service-transfer and environment/drop-in contracts."""
import argparse
import contextlib
import hashlib
import http.client
import json
import os
import platform
import pwd
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import urlencode

from verify_systemd_service import owned_process as observe_owned_process

TRANSFER = "LS-13-unit-6-services-and-systemd-supplemental-2"
EXTENSION = "LS-14-unit-6-services-and-systemd-supplemental-3"
parser = argparse.ArgumentParser()
parser.add_argument("--source-root", type=Path)
parser.add_argument("--proof", type=Path, required=True)
parser.add_argument("--app-only", action="store_true")
args = parser.parse_args()
ROOT = (args.source_root or Path(__file__).resolve().parents[1]).resolve()
args.proof = args.proof.resolve()
args.proof.parent.mkdir(parents=True, exist_ok=True)
records, processes, profiles = [], [], []
task = os.environ.get("CLASSES_FAMILY_TASK_ID", "linux-systemd-supplemental-ci")


def hashes():
    return {pack + "/" + str(path.relative_to(ROOT / pack)): hashlib.sha256(path.read_bytes()).hexdigest()
            for pack in (TRANSFER, EXTENSION) for path in sorted((ROOT / pack).rglob("*")) if path.is_file()}


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
    result = {"kind": "command", "command": command, "status": child.returncode,
              "stdout": out.decode(errors="replace"), "stderr": err.decode(errors="replace")}
    records.append(result)
    assert expected is None or child.returncode == expected, result
    return result


def control(unit, work, *verbs):
    return run(["systemctl", "--user", *verbs, unit], work, expected=None)


def properties(unit, work):
    result = run(["systemctl", "--user", "show", unit,
                  "--property=LoadState,ActiveState,SubState,MainPID,ExecMainStatus,Result,NRestarts,InvocationID,UnitFileState,EnvironmentFiles,DropInPaths"], work)
    return dict(line.split("=", 1) for line in result["stdout"].splitlines() if "=" in line)


def wait_for(unit, work, condition, timeout=12):
    deadline = time.monotonic() + timeout
    while True:
        state = properties(unit, work)
        if condition(state):
            return state
        assert time.monotonic() < deadline, (unit, state)
        time.sleep(0.1)


def journal(unit, work):
    result = run(["journalctl", "--user", "-u", unit, "--no-pager", "-o", "json", "-n", "100"], work)
    return [json.loads(line) for line in result["stdout"].splitlines() if line.startswith("{")]


def journal_match(unit, work, predicate):
    deadline = time.monotonic() + 8
    while True:
        rows = journal(unit, work)
        matches = [row for row in rows if predicate(row)]
        if matches:
            assert all(row.get("_UID") == str(os.geteuid()) for row in matches)
            records.append({"kind": "journal-evidence", "unit": unit, "rows": matches})
            return matches
        assert time.monotonic() < deadline, (unit, rows)
        time.sleep(0.1)


def owned_process(unit, work, app, previous=None):
    state = wait_for(unit, work, lambda s: s["ActiveState"] == "active" and s["SubState"] == "running" and int(s["MainPID"]) > 0 and (previous is None or int(s["MainPID"]) != previous))
    return observe_owned_process(unit, work, state, app, read_properties=properties, evidence=records)

def fail_state(unit, work, code, word):
    state = wait_for(unit, work, lambda s: s["ActiveState"] == "failed" and s["MainPID"] == "0" and s["ExecMainStatus"] == str(code))
    assert state["NRestarts"] == "0", state
    journal_match(unit, work, lambda r: word.lower() in str(r.get("MESSAGE", "")).lower())
    records.append({"kind": "named-failure", "unit": unit, "status": code, "state": state})
    return state


def heartbeat(unit, work, pid, message, after=0):
    rows = journal_match(unit, work, lambda r: r.get("_PID") == str(pid) and str(r.get("MESSAGE", "")).startswith(message + ": heartbeat ") and int(r.get("__REALTIME_TIMESTAMP", "0")) >= after)
    values = Path("/proc", str(pid), "environ").read_bytes().split(b"\0")
    assert ("HEARTBEAT_MESSAGE=" + message).encode() in values
    records.append({"kind": "actual-environment", "unit": unit, "pid": pid, "message": message, "rows": rows})


def request(port, path, method="GET"):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=4)
    try:
        connection.request(method, path)
        response = connection.getresponse()
        body = response.read()
        result = {"kind": "http", "port": port, "method": method, "path": path,
                  "status": response.status, "headers": dict(response.getheaders()), "body": body.decode()}
        records.append(result)
        return result
    finally:
        connection.close()


def http_ready(unit, work, pid, port):
    deadline = time.monotonic() + 8
    while True:
        try:
            result = request(port, "/health")
            if result["status"] == 200:
                break
        except OSError:
            pass
        assert time.monotonic() < deadline
        time.sleep(0.1)
    expected = '{"service": "linux-toy-app", "status": "ok"}\n'
    assert result["body"] == expected and result["headers"]["Content-Length"] == str(len(expected.encode()))
    head = request(port, "/health", "HEAD")
    assert head["status"] == 200 and head["body"] == "" and head["headers"]["Content-Length"] == result["headers"]["Content-Length"]
    assert head["headers"]["Content-Type"] == result["headers"]["Content-Type"]
    target = "/inspect?" + urlencode([("word", "café"), ("word", "two")])
    inspection = request(port, target)
    payload = json.loads(inspection["body"])
    assert inspection["status"] == 200 and payload["query"] == {"word": ["café", "two"]} and payload["peer"] == "127.0.0.1"
    assert request(port, "/missing")["status"] == 404
    post = request(port, "/health", "POST")
    assert post["status"] == 405 and post["headers"]["Allow"] == "GET, HEAD"
    sockets = run(["ss", "-ltnp", "sport = :" + str(port)], work)["stdout"]
    listeners = [line.split() for line in sockets.splitlines()[1:] if line.strip()]
    assert len(listeners) == 1 and listeners[0][3] == "127.0.0.1:" + str(port), sockets
    assert "pid=" + str(pid) + "," in sockets, sockets
    journal_match(unit, work, lambda r: r.get("_PID") == str(pid) and "Listening on http://127.0.0.1:" + str(port) in str(r.get("MESSAGE", "")))
    records.append({"kind": "owned-loopback-readiness", "unit": unit, "pid": pid, "port": port, "actualSocketAndHttp": True})


def reload(work):
    run(["systemctl", "--user", "daemon-reload"], work)


before = hashes()
assert len(before) == 22
accepted = False
manager_version = None
try:
    if not args.app_only:
        assert platform.system() == "Linux" and os.geteuid() != 0
        assert Path.home() == Path(pwd.getpwuid(os.geteuid()).pw_dir)
        assert all(shutil.which(name) for name in ("systemctl", "systemd-analyze", "journalctl", "ss"))
        manager_version = run(["systemctl", "--user", "show", "--property=Version", "--value"], ROOT)["stdout"].strip()
        assert manager_version
    for pack, kind in ((TRANSFER, "transfer"), (EXTENSION, "extension")):
        for role in ("starter", "solution", "independent-completion"):
            selected = ROOT / pack / ("starter" if role == "independent-completion" else role)
            with tempfile.TemporaryDirectory(prefix="systemd-supplemental-") as directory:
                work = Path(directory)
                app_name = "transfer_app.py" if kind == "transfer" else "heartbeat_app.py"
                app = work / app_name
                app.write_bytes((selected / app_name).read_bytes())
                if kind == "transfer":
                    invalid = run([sys.executable, str(app)], work, dict(os.environ, APP_PORT="0"), 2)
                    assert not invalid["stdout"] and "APP_PORT" in invalid["stderr"]
                else:
                    direct = run([sys.executable, str(app)], work, dict(os.environ, HEARTBEAT_INTERVAL="0.1", HEARTBEAT_MESSAGE="sample", HEARTBEAT_LIMIT="2"))
                    assert direct["stdout"] == "sample: heartbeat 1\nsample: heartbeat 2\n"
                if args.app_only:
                    profiles.append({"kind": kind, "role": role, "appOnly": True})
                    continue
                name = "linux-service-" + kind + "-ci-" + uuid.uuid4().hex
                unit = name + ".service"
                install = Path.home() / ".local/share" / name
                unit_root = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "systemd/user"
                unit_root.mkdir(parents=True, exist_ok=True)
                unit_file = unit_root / unit
                drop_dir = unit_root / (unit + ".d")
                assert not install.exists() and not unit_file.exists() and not drop_dir.exists()
                install.mkdir(parents=True)
                installed_app = install / app_name
                shutil.copyfile(app, installed_app)
                prefix = "%h/.local/share/linux-service-" + kind
                source_unit = (selected / ("linux-service-" + kind + ".service")).read_text()
                assert source_unit.count(prefix) == 3
                unit_text = source_unit.replace(prefix, "%h/.local/share/" + name)
                unit_file.write_text(unit_text)
                if kind == "transfer":
                    with socket.socket() as sock:
                        sock.bind(("127.0.0.1", 0))
                        port = sock.getsockname()[1]
                    (install / "transfer.env").write_text("APP_PORT=" + str(port) + "\n")
                else:
                    shutil.copyfile(selected / "base.env.example", install / "base.env")
                    shutil.copyfile(selected / "override.env.example", install / "override.env")
                try:
                    run(["systemd-analyze", "--user", "verify", str(unit_file)], work)
                    reload(work)
                    control(unit, work, "start")
                    if kind == "transfer":
                        if role != "solution":
                            fail_state(unit, work, 200, "CHDIR")
                            if role == "starter":
                                profiles.append({"kind": kind, "role": role, "actualManager": True, "namedWorkingDirectoryFailure": True, "restartLoopPrevented": True})
                                continue
                            unit_text = unit_text.replace("/TODO-working-directory", "")
                            unit_file.write_text(unit_text)
                            reload(work)
                            control(unit, work, "reset-failed")
                            control(unit, work, "start")
                            fail_state(unit, work, 2, "TODO-transfer_app.py")
                            unit_text = unit_text.replace("TODO-transfer_app.py", "transfer_app.py")
                            unit_file.write_text(unit_text)
                            reload(work)
                            control(unit, work, "reset-failed")
                            control(unit, work, "start")
                        base_hash = hashlib.sha256(unit_file.read_bytes()).hexdigest()
                        pid = owned_process(unit, work, installed_app)
                        http_ready(unit, work, pid, port)
                        control(unit, work, "restart")
                        pid = owned_process(unit, work, installed_app, pid)
                        http_ready(unit, work, pid, port)
                        control(unit, work, "reset-failed")
                        restart_count = int(properties(unit, work)["NRestarts"])
                        records.append({"kind": "owned-signal", "unit": unit, "pid": pid, "signal": "SIGKILL"})
                        os.kill(pid, signal.SIGKILL)
                        next_pid = owned_process(unit, work, installed_app, pid)
                        assert int(properties(unit, work)["NRestarts"]) > restart_count
                        http_ready(unit, work, next_pid, port)
                        drop_dir.mkdir()
                        fault = drop_dir / "90-lab-fault.conf"
                        fault.write_text("[Service]\nWorkingDirectory=" + str(install / "missing-directory") + "\n")
                        reload(work)
                        control(unit, work, "reset-failed")
                        control(unit, work, "restart")
                        fail_state(unit, work, 200, "CHDIR")
                        fault.unlink()
                        drop_dir.rmdir()
                        reload(work)
                        control(unit, work, "reset-failed")
                        control(unit, work, "start")
                        restored = owned_process(unit, work, installed_app)
                        http_ready(unit, work, restored, port)
                        assert hashlib.sha256(unit_file.read_bytes()).hexdigest() == base_hash
                        control(unit, work, "enable")
                        assert (unit_root / "default.target.wants" / unit).is_symlink()
                        control(unit, work, "stop")
                        stopped = wait_for(unit, work, lambda s: s["ActiveState"] == "inactive" and s["MainPID"] == "0")
                        assert stopped["UnitFileState"] == "enabled"
                        profiles.append({"kind": kind, "role": role, "actualManager": True, "actualHttpAndSocket": True, "actualJournal": True, "manualRestart": True, "automaticRestart": True, "workingDirectoryFaultAndRecovery": True, "baseUnitUnchanged": True, "enabledAndStopped": True, "independentNamedTaskCompletion": role == "independent-completion"})
                    else:
                        base_hash = hashlib.sha256(unit_file.read_bytes()).hexdigest()
                        pid = owned_process(unit, work, installed_app)
                        heartbeat(unit, work, pid, "base-heartbeat")
                        drop_dir.mkdir()
                        drop = drop_dir / "20-lab-settings.conf"
                        drop_text = (selected / "20-lab-settings.conf").read_text()
                        if role == "independent-completion":
                            assert "EnvironmentFile=" not in drop_text
                            drop_text += "EnvironmentFile=\nEnvironmentFile=" + prefix + "/override.env\n"
                        drop.write_text(drop_text.replace(prefix, "%h/.local/share/" + name))
                        reload(work)
                        control(unit, work, "restart")
                        pid = owned_process(unit, work, installed_app, pid)
                        expected = "base-heartbeat" if role == "starter" else "extension-heartbeat"
                        heartbeat(unit, work, pid, expected)
                        current = properties(unit, work)
                        assert str(drop) in current["DropInPaths"]
                        selected_env = str(install / ("base.env" if role == "starter" else "override.env"))
                        assert selected_env in current["EnvironmentFiles"]
                        if role != "starter":
                            assert str(install / "base.env") not in current["EnvironmentFiles"]
                            good = (install / "override.env").read_text()
                            edited_at = time.time_ns() // 1000
                            (install / "override.env").write_text(good.replace("extension-heartbeat", "edited-heartbeat"))
                            time.sleep(0.25)
                            assert int(properties(unit, work)["MainPID"]) == pid
                            heartbeat(unit, work, pid, "extension-heartbeat", after=edited_at)
                            control(unit, work, "restart")
                            pid = owned_process(unit, work, installed_app, pid)
                            heartbeat(unit, work, pid, "edited-heartbeat")
                            (install / "override.env").write_text(good.replace("HEARTBEAT_INTERVAL=0.1", "HEARTBEAT_INTERVAL=0"))
                            control(unit, work, "reset-failed")
                            control(unit, work, "restart")
                            fail_state(unit, work, 2, "HEARTBEAT_INTERVAL")
                            (install / "override.env").write_text(good)
                            control(unit, work, "reset-failed")
                            control(unit, work, "start")
                            pid = owned_process(unit, work, installed_app)
                            heartbeat(unit, work, pid, "extension-heartbeat")
                        else:
                            (install / "override.env").write_text("HEARTBEAT_INTERVAL=0\nHEARTBEAT_MESSAGE=ignored-invalid\nHEARTBEAT_LIMIT=0\n")
                            control(unit, work, "restart")
                            pid = owned_process(unit, work, installed_app, pid)
                            heartbeat(unit, work, pid, "base-heartbeat")
                        drop.unlink()
                        drop_dir.rmdir()
                        reload(work)
                        control(unit, work, "reset-failed")
                        control(unit, work, "restart")
                        pid = owned_process(unit, work, installed_app, pid)
                        heartbeat(unit, work, pid, "base-heartbeat")
                        current = properties(unit, work)
                        assert str(install / "base.env") in current["EnvironmentFiles"] and not current["DropInPaths"]
                        assert hashlib.sha256(unit_file.read_bytes()).hexdigest() == base_hash
                        profiles.append({"kind": kind, "role": role, "actualManager": True, "actualJournal": True, "actualProcessEnvironment": True, "namedPrecedenceMismatch": role == "starter", "resetAndReplacementObserved": role != "starter", "fileEditNeedsRestart": role != "starter", "invalidOverrideFailureAndRecovery": role != "starter", "ignoredInvalidOverrideObserved": role == "starter", "dropInRemovalRestoresBase": True, "baseUnitUnchanged": True, "independentNamedTaskCompletion": role == "independent-completion"})
                finally:
                    control(unit, work, "stop")
                    control(unit, work, "disable")
                    control(unit, work, "reset-failed")
                    if drop_dir.exists():
                        for child in drop_dir.iterdir():
                            child.unlink()
                        drop_dir.rmdir()
                    unit_file.unlink(missing_ok=True)
                    reload(work)
                    final = properties(unit, work)
                    assert final["LoadState"] == "not-found" and final["MainPID"] == "0"
                    assert not (unit_root / "default.target.wants" / unit).exists()
                    shutil.rmtree(install)
                    records.append({"kind": "cleanup", "unit": unit, "unitRemoved": True, "processStopped": True, "activationRemoved": True, "dropInRemoved": True, "installRemoved": True})
    assert len(profiles) == 6 and hashes() == before
    accepted = True
finally:
    args.proof.with_suffix(".processes.jsonl").write_text("".join(json.dumps(row) + "\n" for row in processes))
    args.proof.write_text(json.dumps({"accepted": accepted, "appOnly": args.app_only,
                                     "managerVersion": manager_version, "platform": platform.platform(),
                                     "sourceHashes": before, "profiles": profiles, "observations": records,
                                     "independentLearnerCompletions": 2, "sourceUnchanged": hashes() == before}, indent=2) + "\n")
print(json.dumps({"accepted": accepted, "appOnly": args.app_only, "profiles": len(profiles), "observations": len(records)}))
