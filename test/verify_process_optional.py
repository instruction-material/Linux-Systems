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

ROOT = Path(__file__).resolve().parents[1]
PACK_NAMES = ["LS-11-unit-5-processes-and-job-control-supplemental-2", "LS-12-unit-5-processes-and-job-control-supplemental-3"]
parser = argparse.ArgumentParser()
parser.add_argument("--proof", type=Path, required=True)
args = parser.parse_args()
assert platform.system() == "Linux" and os.geteuid() != 0
assert shutil.which("bash") and hasattr(os, "pidfd_open") and hasattr(signal, "pidfd_send_signal")
args.proof = args.proof.resolve()
args.proof.parent.mkdir(parents=True, exist_ok=True)
task = os.environ.get("CLASSES_FAMILY_TASK_ID", "linux-process-optional-source")
observations, processes, profiles = [], [], []


def hashes():
    return {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest()
            for name in PACK_NAMES for f in sorted((ROOT / name).rglob("*")) if f.is_file()}


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
    assert observed["ppid"] == parent and "pipeline_worker.py" in observed["command"]
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
                       HISTFILE="/dev/null", PROMPT_COMMAND="", TERM="dumb")
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


source_before = hashes()
assert len(source_before) == 10
accepted = False


def expired(_number, _frame):
    raise TimeoutError("Owned optional process profile exceeded 60 seconds")


def remember_completed(terminal, path, command, status):
    started = event(path, "started")
    assert started and started["uid"] == os.geteuid() and started["ppid"] == terminal.pid
    record("start", started["pid"], command, terminal.cwd, started["at"],
           actualParentPid=terminal.pid)
    record("end", started["pid"], command, terminal.cwd, started["at"],
           actualParentPid=terminal.pid, endTime=time.time(), exitCode=status,
           childProcessGroupCleanup="foreground Bash pipeline completed and was waited")
    return started


def retain_descendants(evidence, worker, work, parent):
    children = {x["childPid"] for x in evidence if x["event"] == "spawned"}
    children.update(x["child"]["pid"] for x in evidence if x["event"] == "grandchild_observed")
    ended = {x["childPid"]: x for x in evidence if x["event"] in ("reaped", "cleanup_reaped")}
    assert children == set(ended)
    for pid in children:
        begin = next(x for x in evidence if (x["event"] == "spawned" and x["childPid"] == pid)
                     or (x["event"] == "grandchild_observed" and x["child"]["pid"] == pid))
        birth_parent = begin["child"]["ppid"] if begin["event"] == "grandchild_observed" else parent
        record("start", pid, [sys.executable, str(worker)], work, begin["at"],
               actualParentPid=birth_parent, forkedDescendant=True)
        record("end", pid, [sys.executable, str(worker)], work, begin["at"],
               endTime=ended[pid]["at"], exitCode=ended[pid]["status"],
               childProcessGroupCleanup="owned descendant actually waited by adopter", forkedDescendant=True)
    return children


@contextlib.contextmanager
def lost_display(command, cwd, output):
    started = time.time()
    with output.open("wb") as stream:
        child = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE,
                                 stderr=stream, start_new_session=True)
        record("start", child.pid, command, cwd, started)
        try:
            wait_for(lambda: select.select([child.stdout], [], [], 0)[0], "display ready")
            first = child.stdout.readline()
            assert json.loads(first)["event"] == "started"
            stream.write(first)
            stream.flush()
            child.stdout.close()
            yield child
        finally:
            child.stdout.close()
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    child.kill()
            child.wait(timeout=3)
            record("end", child.pid, command, cwd, started, endTime=time.time(),
                   exitCode=child.returncode, childProcessGroupCleanup="owned observer stopped and reaped")


def adopted_terminal_case(terminal, worker, work, role):
    output, saved = work / "tty-adoption.jsonl", work / "tty-adoption-record.jsonl"
    command = [sys.executable, "-u", str(worker), "--hold-seconds", "10", "--record", str(saved)]
    start = len(terminal.buffer)
    terminal.send((shlex.join(command) + " >" + shlex.quote(str(output)) + " 2>&1\n").encode())
    first = wait_for(lambda: event(saved, "zombie_observed"), "terminal zombie")
    observer = event(saved, "started")
    observed = kernel(observer["pid"])
    assert observed and observed["ppid"] == terminal.pid and observed["sid"] == terminal.pid
    assert observed["uid"] == os.geteuid()
    wait_for(lambda: os.tcgetpgrp(terminal.fd) == observed["pgid"], "adopter foreground group")
    terminal.track(observed, command)
    assert kernel(first["child"]["pid"])["state"] == "Z"
    terminal.send(b"\x03")
    terminal.until(lambda terminal=terminal, start=start: terminal.prompt in terminal.buffer[start:], "adopter Ctrl+C prompt")
    result = terminal.command("printf 'ADOPTION_STATUS=%s\\n' \"$?\"")
    assert "ADOPTION_STATUS=130" in result
    terminal.finished(observed, 130)
    assert not same_process(observed) and output.read_bytes() == saved.read_bytes()
    cleanup = event(saved, "cleanup")
    assert cleanup and not cleanup["complete"] and cleanup["noOwnedChildren"] and cleanup["descriptorsClosed"]
    assert event(saved, "interrupted")["signal"] == "SIGINT"
    evidence = rows(saved)
    children = retain_descendants(evidence, worker, work, observed["pid"])
    observations.append({"kind": "adoption-terminal-interruption", "role": role,
                         "events": evidence, "foreground": observed,
                         "status": 130, "childPids": sorted(children), "rawStatus": result})


def adopted_case(worker, work, role, hold, name, interrupt=False, after_adoption=False, display_closed=False):
    output = work / (name + ".jsonl")
    record_file = work / (name + "-record.jsonl")
    owner = lost_display if display_closed else owned
    evidence_file = record_file if display_closed else output
    with owner([sys.executable, "-u", str(worker), "--hold-seconds", hold, "--record", str(record_file)], work, output) as child:
        started = wait_for(lambda: event(evidence_file, "started"), "adopter start")
        assert started["pid"] == child.pid and started["uid"] == os.geteuid() and started["subreaperObserved"]
        first = wait_for(lambda: event(evidence_file, "zombie_observed"), "real zombie")
        if name != "changed":
            observed = kernel(first["child"]["pid"])
            assert observed and observed["state"] == "Z" and observed["ppid"] == child.pid
            assert observed["startTicks"] == first["child"]["startTicks"] and observed["uid"] == os.geteuid()
            observations.append({"kind": "external-zombie-state", "role": role, "case": name, "observed": observed})
        if interrupt:
            if after_adoption:
                wait_for(lambda: event(evidence_file, "adopted"), "adoption before interrupt")
                os.killpg(child.pid, signal.SIGTERM)
            else:
                child.terminate()
            assert child.wait(timeout=5) == 143
        else:
            adopted = wait_for(lambda: event(evidence_file, "adopted"), "real adoption")
            original = event(evidence_file, "grandchild_observed")
            assert original and original["child"]["ppid"] == adopted["originalParent"]
            assert adopted["actualNewParent"] == child.pid and adopted["child"]["ppid"] == child.pid
            assert all(original["child"][key] == adopted["child"][key] for key in ("pid", "uid", "startTicks"))
            if name != "changed":
                observed = kernel(adopted["child"]["pid"])
                assert observed and observed["ppid"] == child.pid and observed["state"] != "Z"
                assert observed["startTicks"] == adopted["child"]["startTicks"]
                observations.append({"kind": "external-adoption-state", "role": role, "observed": observed})
            assert child.wait(timeout=5) == 0
        if display_closed:
            assert len(rows(output)) == 1 and rows(output)[0] == rows(record_file)[0]
        else:
            assert output.read_bytes() == record_file.read_bytes()
        evidence = rows(evidence_file)
        cleanup = event(evidence_file, "cleanup")
        assert cleanup and cleanup["noOwnedChildren"] and cleanup["descriptorsClosed"]
        if interrupt:
            assert not cleanup["complete"] and event(evidence_file, "interrupted")["status"] == 143
            assert bool(event(evidence_file, "adopted")) == after_adoption
        else:
            assert cleanup["complete"]
            assert [(x["purpose"], x["status"]) for x in evidence if x["event"] == "reaped"] == [
                ("zombie", 7), ("original-parent", 0), ("adopted-child", 9)]
        children = retain_descendants(evidence, worker, work, child.pid)
        observations.append({"kind": "adoption-sequence", "role": role, "case": name,
                             "events": evidence, "childPids": sorted(children),
                             "exitCode": child.returncode, "displayClosed": display_closed,
                             "actualLinuxSubreaper": True})


signal.signal(signal.SIGALRM, expired)
try:
    for role in ("starter", "solution", "independent-command-sequence"):
        signal.alarm(60)
        selected = "starter" if role == "independent-command-sequence" else role
        with tempfile.TemporaryDirectory(prefix="optional-process-owned-") as directory:
            work = Path(directory)
            worker = ROOT / PACK_NAMES[0] / selected / "pipeline_worker.py"
            terminal = Terminal(work, args.proof.parent / (role + "-pipeline-terminal.log"))
            try:
                terminal.until(lambda terminal=terminal: terminal.prompt in terminal.buffer, "fresh interactive shell")
                terminal.command("stty -echo")
                terminal.command("unset PROMPT_COMMAND")
                assert re.search(r"^monitor\s+on\s*$", terminal.command("set -o"), re.MULTILINE)
                terminal.command("set +o pipefail")
                assert not re.search(r"\[\d+\]", terminal.command("jobs -l"))
                producer, consumer, received = [work / name for name in ("producer.jsonl", "consumer.jsonl", "received.jsonl")]
                producer_command = [sys.executable, "-u", str(worker), "produce", "--lifetime", "30"]
                consumer_command = [sys.executable, "-u", str(worker), "consume", "--lifetime", "30"]
                pipeline = shlex.join(producer_command) + " 2>" + shlex.quote(str(producer)) + " | " + shlex.join(consumer_command) + " >" + shlex.quote(str(received)) + " 2>" + shlex.quote(str(consumer))
                terminal.command(pipeline + " &")
                last = terminal.command("printf 'LAST_PID=%s\\n' \"$!\"")
                first = identity(producer, terminal.pid)
                second = identity(consumer, terminal.pid)
                terminal.track(first, producer_command)
                terminal.track(second, consumer_command)
                assert first["pid"] != second["pid"]
                assert first["pgid"] == second["pgid"] == first["pid"]
                assert first["sid"] == second["sid"] == terminal.pid
                assert "LAST_PID=" + str(second["pid"]) in last
                leader = terminal.command("jobs -p")
                assert re.search(r"^" + str(first["pid"]) + r"\r?$", leader, re.MULTILINE)
                wait_for(lambda received=received: len(rows(received)) >= 2, "actual pipeline data")
                prior_count = len(rows(received))
                terminal.command("kill -STOP %1")
                stopped = [wait_for(lambda pid=before["pid"]: (item if (item := kernel(pid)) and item["state"] == "T" else None), "stopped pipeline member") for before in (first, second)]
                assert all(item["pgid"] == first["pgid"] for item in stopped)
                jobs = terminal.command("jobs -l")
                assert str(first["pid"]) in jobs and str(second["pid"]) in jobs and "Stopped" in jobs
                terminal.command("bg %1")
                terminal.command("kill -USR1 %1")
                for path, before in ((producer, first), (consumer, second)):
                    assert wait_for(lambda path=path: event(path, "continued"), "both continued")["pid"] == before["pid"]
                    assert wait_for(lambda path=path: event(path, "snapshot"), "both snapshots")["pid"] == before["pid"]
                wait_for(lambda received=received, prior_count=prior_count: len(rows(received)) > prior_count, "resumed data flow")
                start = len(terminal.buffer)
                terminal.send(b"fg %1\n")
                wait_for(lambda terminal=terminal, first=first: os.tcgetpgrp(terminal.fd) == first["pgid"], "pipeline foreground group")
                terminal.send(b"\x03")
                terminal.until(lambda terminal=terminal, start=start: terminal.prompt in terminal.buffer[start:], "prompt after pipeline Ctrl+C")
                foreground = terminal.command("printf 'FG_STATUS=%s\\n' \"$?\"")
                assert "FG_STATUS=130" in foreground
                for path, before in ((producer, first), (consumer, second)):
                    assert event(path, "stopped")["signal"] == "SIGINT"
                    assert event(path, "stopped")["status"] == 130
                    assert not same_process(before)
                    terminal.finished(before, 130)
                observations.append({"kind": "pipeline-job-control", "role": role,
                                     "before": [first, second], "stopped": stopped,
                                     "lastPid": second["pid"], "groupLeader": first["pid"],
                                     "jobs": jobs, "foregroundStatus": 130,
                                     "producerEvents": rows(producer), "consumerEvents": rows(consumer),
                                     "received": rows(received), "actualControllingTerminal": True})
                for early, checked in ((False, False), (False, True), (True, False), (True, True)):
                    name = ("early" if early else "failure") + ("-checked" if checked else "-default")
                    p_log, c_log, data = [work / (name + suffix) for suffix in ("-producer.jsonl", "-consumer.jsonl", "-received.jsonl")]
                    p_command = [sys.executable, "-u", str(worker), "produce", "--lifetime", "5"]
                    c_command = [sys.executable, "-u", str(worker), "consume", "--lifetime", "5"]
                    if early:
                        c_command += ["--take", "1"]
                    else:
                        p_command += ["--count", "3", "--exit-code", "7"]
                    terminal.command("set -o pipefail" if checked else "set +o pipefail")
                    command = shlex.join(p_command) + " 2>" + shlex.quote(str(p_log)) + " | " + shlex.join(c_command) + " >" + shlex.quote(str(data)) + " 2>" + shlex.quote(str(c_log))
                    result = terminal.command(command + "\nprintf 'PIPELINE_STATUS=%s COMPONENTS=%s\\n' \"$?\" \"${PIPESTATUS[*]}\"")
                    match = re.search(r"PIPELINE_STATUS=(\d+) COMPONENTS=(\d+) (\d+)", result)
                    expected = 141 if early else 7
                    assert match and tuple(map(int, match.groups())) == (expected if checked else 0, expected, 0)
                    p_start = remember_completed(terminal, p_log, p_command, expected)
                    c_start = remember_completed(terminal, c_log, c_command, 0)
                    assert p_start["pgid"] == c_start["pgid"] and p_start["pid"] != c_start["pid"]
                    values = rows(data)
                    assert len(values) == (1 if early else 3)
                    assert all(x["pid"] == c_start["pid"] and x["producerPid"] == p_start["pid"] for x in values)
                    if early:
                        assert not event(p_log, "stopped") and event(c_log, "stopped")["signal"] == "take"
                    else:
                        assert event(p_log, "stopped")["status"] == 7 and event(c_log, "stopped")["signal"] == "eof"
                    observations.append({"kind": "pipeline-status", "role": role, "case": name,
                                         "pipefail": checked, "earlyReader": early,
                                         "status": int(match.group(1)), "components": [expected, 0],
                                         "producerEvents": rows(p_log), "consumerEvents": rows(c_log),
                                         "received": values, "rawStatus": result})
                assert not re.search(r"\[\d+\]", terminal.command("jobs -l"))
                adopted_terminal_case(terminal, ROOT / PACK_NAMES[1] / selected / "adoption_lab.py", work, role)
            finally:
                terminal.close()
            profiles.append({"kind": "pipeline", "role": role,
                             "twoActualKernelIdentities": True, "lastPidDiffersFromGroupLeader": True,
                             "groupStopAndResume": True, "dataFlowResumed": True,
                             "actualForegroundGroup": True, "componentStatusesObserved": True,
                             "actualSigpipe": True, "allOwnedJobsReaped": True,
                             "worksheetCompletionNotInferred": True})
            worker = ROOT / PACK_NAMES[1] / selected / "adoption_lab.py"
            adopted_case(worker, work, role, "1", "normal")
            adopted_case(worker, work, role, "0.2", "changed")
            adopted_case(worker, work, role, "10", "interrupted", interrupt=True)
            adopted_case(worker, work, role, "1", "interrupted-adoption", interrupt=True, after_adoption=True)
            adopted_case(worker, work, role, "1", "lost-display", display_closed=True)
            existing = work / "existing-record.jsonl"
            existing.write_bytes(b"preserved earlier observation\n")
            rejected = work / "existing-record-error.log"
            with owned([sys.executable, str(worker), "--record", str(existing)], work, rejected) as child:
                assert child.wait(timeout=3) == 2
            assert existing.read_bytes() == b"preserved earlier observation\n"
            assert "cannot create a new record file" in rejected.read_text() and '"event":"started"' not in rejected.read_text()
            observations.append({"kind": "existing-record-rejected", "role": role, "status": 2,
                                 "priorEvidenceUnchanged": True, "diagnostic": rejected.read_text()})
            bad = work / "invalid-hold.log"
            with owned([sys.executable, str(worker), "--hold-seconds", "nan"], work, bad) as child:
                assert child.wait(timeout=3) == 2
            assert "hold must be" in bad.read_text() and '"event":"started"' not in bad.read_text()
            observations.append({"kind": "invalid-hold", "role": role, "status": 2, "diagnostic": bad.read_text()})
            profiles.append({"kind": "adoption", "role": role,
                             "actualZombieBeforeWait": True, "actualSubreaperFlag": True,
                             "handshakeKeepsOriginalParentAlive": True,
                             "sameBirthIdentityWithNewParent": True, "actualAdoptedWait": True,
                             "changedTiming": True, "interruptionDistinctAndCleaned": True,
                             "invalidArgumentBeforeStart": True, "allOwnedChildrenReaped": True,
                             "actualTerminalCtrlC": True, "closedDisplayRetainsEvidence": True,
                             "existingRecordPreserved": True,
                             "worksheetCompletionNotInferred": True})
        assert not work.exists()
        observations.append({"kind": "cleanup", "role": role,
                             "allOwnedProcessesReaped": True, "temporaryDirectoryRemoved": True})
    assert len(profiles) == 6 and hashes() == source_before
    accepted = True
finally:
    signal.alarm(0)
    args.proof.with_suffix(".processes.jsonl").write_text("".join(json.dumps(x) + "\n" for x in processes))
    args.proof.write_text(json.dumps({"accepted": accepted, "platform": platform.system().lower(),
                                     "sourceHashes": source_before, "sourceUnchanged": hashes() == source_before,
                                     "profiles": profiles, "observations": observations,
                                     "worksheetCompletionNotInferred": True}, indent=2) + "\n")
print(json.dumps({"accepted": accepted, "profiles": len(profiles), "observations": len(observations)}))
