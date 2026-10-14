"""Observe owned Linux processes and actual interactive Bash job control."""
import argparse
import contextlib
import hashlib
import json
import os
import platform
import pty
import re
import select
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PACK = Path(__file__).resolve().parents[1] / "LS-08-unit-5-processes-and-job-control"
parser = argparse.ArgumentParser()
parser.add_argument("--proof", type=Path, required=True)
args = parser.parse_args()
assert platform.system() == "Linux" and os.geteuid() != 0
assert shutil.which("bash") and shutil.which("ps")
assert hasattr(os, "pidfd_open") and hasattr(signal, "pidfd_send_signal")
args.proof = args.proof.resolve()
args.proof.parent.mkdir(parents=True, exist_ok=True)
task = os.environ.get("CLASSES_FAMILY_TASK_ID", "linux-process-core-source")
observations, processes, profiles = [], [], []


def hashes():
    return {str(f.relative_to(PACK)): hashlib.sha256(f.read_bytes()).hexdigest()
            for f in sorted(PACK.rglob("*")) if f.is_file()}


def kernel(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        uid = Path(f"/proc/{pid}").stat().st_uid
        command = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode()
    except (FileNotFoundError, ProcessLookupError):
        return None
    return {"pid": pid, "state": fields[0], "ppid": int(fields[1]),
            "pgid": int(fields[2]), "sid": int(fields[3]),
            "tty": int(fields[4]), "terminalPgid": int(fields[5]),
            "startTicks": int(fields[19]), "uid": uid, "command": command}


def same_process(before):
    now = kernel(before["pid"])
    return now is not None and now["startTicks"] == before["startTicks"]


def wait_for(predicate, label, timeout=5):
    deadline = time.monotonic() + timeout
    while True:
        result = predicate()
        if result:
            return result
        assert time.monotonic() < deadline, label
        time.sleep(0.02)


def rows(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines(keepends=True)
            if line.endswith("\n")]


def event(path, name):
    return next((row for row in reversed(rows(path)) if row["event"] == name), None)


def identity(path, parent):
    started = wait_for(lambda: event(path, "started"), (str(path), "ready"))
    observed = kernel(started["pid"])
    assert observed and observed["uid"] == os.geteuid()
    assert observed["ppid"] == parent and "process_worker.py" in observed["command"]
    assert all(started[key] == observed[key] for key in ("pid", "ppid", "uid", "pgid", "sid"))
    observations.append({"kind": "kernel-identity", "reported": started, "observed": observed})
    return observed


def record(event_name, pid, command, cwd, started, **extra):
    processes.append({"event": event_name, "parentTaskId": task,
                      "parentPid": os.getpid(), "pid": pid, "command": command,
                      "cwd": str(cwd), "startTime": started,
                      "timeoutSeconds": 45, **extra})


@contextlib.contextmanager
def owned(command, cwd, output):
    started = time.time()
    with output.open("wb") as stream:
        child = subprocess.Popen(command, cwd=cwd, stdout=stream,
                                 stderr=subprocess.STDOUT, start_new_session=True)
        record("start", child.pid, command, cwd, started)
        try:
            yield child
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    child.kill()
            child.wait(timeout=3)
            record("end", child.pid, command, cwd, started, endTime=time.time(),
                   exitCode=child.returncode, childProcessGroupCleanup="owned child stopped and reaped")


class Terminal:
    prompt = b"__OWNED_JOB_PROMPT__ "

    def __init__(self, cwd, trace):
        self.cwd, self.trace = cwd, trace
        self.buffer = bytearray()
        self.identities = []
        self.child_records = {}
        self.command_counter = 0
        self.started = time.time()
        self.command_line = ["bash", "--noprofile", "--norc", "-i"]
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            os.chdir(cwd)
            env = dict(os.environ, PS1=self.prompt.decode(), PS2="", LC_ALL="C",
                       HISTFILE="/dev/null", TERM="dumb")
            os.execvpe("bash", self.command_line, env)
        record("start", self.pid, self.command_line, cwd, self.started)
        os.set_blocking(self.fd, False)

    def pump(self):
        ready, _, _ = select.select([self.fd], [], [], 0.02)
        if ready:
            with contextlib.suppress(BlockingIOError):
                self.buffer.extend(os.read(self.fd, 65536))

    def until(self, predicate, label):
        deadline = time.monotonic() + 5
        while not predicate():
            self.pump()
            assert time.monotonic() < deadline, (label, bytes(self.buffer[-2000:]))

    def send(self, data):
        os.write(self.fd, data)

    def command(self, text):
        start = len(self.buffer)
        self.command_counter += 1
        marker = f"__COMMAND_{self.command_counter}_DONE__".encode()
        # A fresh per-command marker cannot be confused with an asynchronous
        # job notification and its redisplayed prompt. First-line $? is intact.
        trailer = b"printf '\\n" + marker + b"\\n'\n"
        self.send(text.encode() + b"\n" + trailer)
        expected = b"\r\n" + marker + b"\r\n"
        self.until(lambda: expected in self.buffer[start:], text)
        end = self.buffer.index(expected, start) + len(expected)
        self.until(lambda: self.prompt in self.buffer[end:], "prompt after command marker")
        return bytes(self.buffer[start:]).decode(errors="replace")

    def track(self, observed, command):
        self.identities.append(observed)
        started = time.time()
        self.child_records[observed["pid"]] = [command, started, None]
        record("start", observed["pid"], command, self.cwd, started,
               actualParentPid=self.pid)

    def finished(self, observed, status):
        self.child_records[observed["pid"]][2] = status

    def close(self):
        # pidfds address only an observed worker even if its numeric PID is reused.
        for before in self.identities:
            with contextlib.suppress(ProcessLookupError, FileNotFoundError):
                fd = os.pidfd_open(before["pid"])
                try:
                    now = kernel(before["pid"])
                    if now and now["sid"] == self.pid and now["startTicks"] == before["startTicks"]:
                        signal.pidfd_send_signal(fd, signal.SIGKILL)
                finally:
                    os.close(fd)
        with contextlib.suppress(OSError):
            self.send(b"exit\n")
        status = None
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            pid, result = os.waitpid(self.pid, os.WNOHANG)
            if pid:
                status = result
                break
            time.sleep(0.02)
        if status is None:
            os.kill(self.pid, signal.SIGKILL)
            _, status = os.waitpid(self.pid, 0)
        os.close(self.fd)
        self.trace.write_bytes(self.buffer)
        record("end", self.pid, self.command_line, self.cwd, self.started,
               endTime=time.time(), exitCode=os.waitstatus_to_exitcode(status),
               childProcessGroupCleanup="owned terminal session stopped and reaped")
        assert all(not same_process(before) for before in self.identities)
        for before in self.identities:
            command, started, status = self.child_records[before["pid"]]
            record("end", before["pid"], command, self.cwd, started,
                   actualParentPid=self.pid, endTime=time.time(), exitCode=status,
                   childProcessGroupCleanup="owned terminal job stopped and reaped")


before = hashes()
assert len(before) == 5
accepted = False

def profile_expired(_number, _frame):
    raise TimeoutError("Owned process profile exceeded 45 seconds")

signal.signal(signal.SIGALRM, profile_expired)
try:
    for role in ("starter", "solution", "independent-command-sequence"):
        signal.alarm(45)
        selected = PACK / ("starter" if role == "independent-command-sequence" else role)
        worker = selected / "process_worker.py"
        with tempfile.TemporaryDirectory(prefix="process-core-owned-") as directory:
            work = Path(directory)
            cooperative = work / "cooperative.jsonl"
            with owned([sys.executable, str(worker), "--lifetime", "15"], work, cooperative) as child:
                first = identity(cooperative, os.getpid())
                child.send_signal(signal.SIGUSR1)
                snapshot = wait_for(lambda: event(cooperative, "snapshot"), "snapshot")
                assert snapshot["pid"] == child.pid and snapshot["signal"] == "SIGUSR1"
                ps_path = work / "ps.txt"
                with owned(["ps", "-p", str(child.pid), "-o", "pid,ppid,uid,pgid,sid,stat,args"], work, ps_path) as ps:
                    assert ps.wait(timeout=5) == 0
                observations.append({"kind": "ps", "role": role, "pid": child.pid, "stdout": ps_path.read_text()})
                child.terminate()
                assert child.wait(timeout=3) == 0
                assert event(cooperative, "stopped")["signal"] == "SIGTERM"
                assert not same_process(first)
            observations.append({"kind": "cooperative", "role": role, "events": rows(cooperative), "waitStatus": 0})
            expired = work / "deadline.jsonl"
            with owned([sys.executable, str(worker), "--lifetime", "0.3"], work, expired) as child:
                deadline_identity = wait_for(lambda: event(expired, "started"), "deadline start")
                assert deadline_identity["pid"] == child.pid and deadline_identity["uid"] == os.geteuid()
                assert child.wait(timeout=3) == 0
                assert event(expired, "stopped")["signal"] == "deadline"
            observations.append({"kind": "deadline", "role": role, "events": rows(expired)})
            for bad in ("nan", "inf", "-1", "1801"):
                path = work / ("invalid-" + bad + ".log")
                with owned([sys.executable, str(worker), "--lifetime", bad], work, path) as child:
                    assert child.wait(timeout=3) == 2
                diagnostic = path.read_text()
                assert "lifetime must be" in diagnostic and '"event":"started"' not in diagnostic
                observations.append({"kind": "invalid-lifetime", "role": role, "value": bad, "status": 2, "diagnostic": diagnostic})
            terminal = Terminal(work, args.proof.parent / (role + "-process-terminal.log"))
            try:
                terminal.until(lambda: terminal.prompt in terminal.buffer, "interactive prompt")
                terminal.command("stty -echo")
                assert re.search(r"^monitor\s+on\s*$", terminal.command("set -o"), re.M)
                assert not re.search(r"\[\d+\]", terminal.command("jobs -l"))
                interactive = work / "interactive.jsonl"
                command = shlex.join([sys.executable, "-u", str(worker), "--lifetime", "30"])
                start = len(terminal.buffer)
                terminal.send((command + " >" + shlex.quote(str(interactive)) + " 2>&1\n").encode())
                active = identity(interactive, terminal.pid)
                terminal.track(active, shlex.split(command))
                assert active["sid"] == terminal.pid and active["tty"] != 0
                wait_for(lambda: os.tcgetpgrp(terminal.fd) == active["pgid"], "worker foreground")
                terminal.send(b"\x1a")
                terminal.until(lambda: terminal.prompt in terminal.buffer[start:], "prompt after Ctrl+Z")
                stopped = wait_for(lambda: (state if (state := kernel(active["pid"])) and state["state"] == "T" else None), "stopped kernel state")
                jobs = terminal.command("jobs -l")
                assert str(active["pid"]) in jobs and "Stopped" in jobs
                terminal.command("bg %1")
                continued = wait_for(lambda: event(interactive, "continued"), "background continuation")
                assert continued["pid"] == active["pid"] and os.tcgetpgrp(terminal.fd) == terminal.pid
                terminal.command("kill -USR1 %1")
                assert wait_for(lambda: event(interactive, "snapshot"), "jobspec snapshot")["pid"] == active["pid"]
                start = len(terminal.buffer)
                terminal.send(b"fg %1\n")
                wait_for(lambda: os.tcgetpgrp(terminal.fd) == active["pgid"], "fg controls terminal")
                terminal.send(b"\x03")
                terminal.until(lambda: terminal.prompt in terminal.buffer[start:], "prompt after Ctrl+C")
                status_output = terminal.command("printf 'FG_STATUS=%s\\n' \"$?\"")
                assert "FG_STATUS=130" in status_output
                assert not re.search(r"\[\d+\]", terminal.command("jobs -l"))
                assert event(interactive, "stopped")["signal"] == "SIGINT"
                assert not same_process(active)
                terminal.finished(active, 130)
                observations.append({"kind": "interactive-job-control", "role": role,
                                     "started": active, "stopped": stopped, "jobs": jobs,
                                     "foregroundStatus": 130, "statusOutput": status_output,
                                     "events": rows(interactive), "actualControllingTerminal": True})
                for mode, status in (("cooperative", 0), ("stubborn", 137)):
                    path = work / (mode + "-bash.jsonl")
                    launch = [sys.executable, "-u", str(worker), "--lifetime", "30"]
                    if mode == "stubborn":
                        launch.append("--ignore-term")
                    terminal.command(shlex.join(launch) + " >" + shlex.quote(str(path)) + " 2>&1 &")
                    terminal.command("lab_child=$!")
                    observed = identity(path, terminal.pid)
                    terminal.track(observed, launch)
                    terminal.command('kill -TERM "$lab_child"')
                    if mode == "stubborn":
                        assert wait_for(lambda: event(path, "ignored"), "actual ignored TERM")["signal"] == "SIGTERM"
                        assert same_process(observed)
                        terminal.command('kill -KILL "$lab_child"')
                    terminal.command('if wait "$lab_child"; then lab_status=0; else lab_status=$?; fi')
                    result = terminal.command("printf 'WAIT_STATUS=%s\\n' \"$lab_status\"")
                    assert "WAIT_STATUS=" + str(status) in result
                    if mode == "cooperative":
                        assert event(path, "stopped")["signal"] == "SIGTERM"
                    else:
                        assert not event(path, "stopped")
                    assert not same_process(observed)
                    terminal.finished(observed, status)
                    observations.append({"kind": "bash-wait", "role": role, "mode": mode,
                                         "identity": observed, "waitStatus": status,
                                         "statusOutput": result, "events": rows(path)})
                assert not re.search(r"\[\d+\]", terminal.command("jobs -l"))
            finally:
                terminal.close()
            profiles.append({"role": role, "actualLinuxIdentity": True,
                             "cooperativeSignalAndReaping": True, "changedDeadline": True,
                             "invalidArgumentsBeforeStart": True, "actualPtyJobControl": True,
                             "stopBgFgSameIdentity": True, "actualForegroundStatus": 130,
                             "actualBashWaitStatuses": [0, 137], "ownedSessionCleaned": True,
                             "worksheetCompletionNotInferred": True})
        assert not work.exists()
        observations.append({"kind": "cleanup", "role": role,
                             "allOwnedProcessesReaped": True, "temporaryDirectoryRemoved": True})
    assert len(profiles) == 3 and hashes() == before
    accepted = True
finally:
    signal.alarm(0)
    args.proof.with_suffix(".processes.jsonl").write_text("".join(json.dumps(x) + "\n" for x in processes))
    args.proof.write_text(json.dumps({"accepted": accepted, "platform": platform.system().lower(),
                                     "sourceHashes": before, "sourceUnchanged": hashes() == before,
                                     "profiles": profiles, "observations": observations,
                                     "worksheetCompletionNotInferred": True}, indent=2) + "\n")
print(json.dumps({"accepted": accepted, "profiles": len(profiles), "observations": len(observations)}))
