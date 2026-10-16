"""Exercise the exact identity gate against real Type=simple user services."""
import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import threading
import time
import uuid
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--proof", type=Path, required=True)
args = parser.parse_args()
args.proof.parent.mkdir(parents=True, exist_ok=True)
source = Path(__file__).with_name("verify_systemd_service.py")
spec = importlib.util.spec_from_file_location("owned_systemd_contract", source)
assert spec and spec.loader
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)
contract.records, contract.processes, contract.task = [], [], "linux-systemd-identity-regression"
run, properties, owned_process = contract.run, contract.properties, contract.owned_process
records = contract.records
proof = {"accepted": False, "verifierSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
         "actualManager": True, "cases": [], "records": records, "processes": contract.processes}


def save():
    args.proof.write_text(json.dumps(proof, indent=2) + "\n")


def wait(unit, work, condition):
    deadline = time.monotonic() + 6
    while True:
        state = properties(unit, work)
        if condition(state):
            return state
        assert time.monotonic() < deadline, state
        time.sleep(0.03)


assert sys.platform == "linux" and os.geteuid() != 0
home = Path.home()
unit_root = home / ".config/systemd/user"
unit_root.mkdir(parents=True, exist_ok=True)
save()
try:
    for label in ("delayed-exec", "misleading-argv", "wrong-script", "wrong-managed-pid"):
        name = "course-identity-" + uuid.uuid4().hex[:12]
        work = home / ".local/share" / name
        work.mkdir(parents=True)
        unit, unit_file = name + ".service", unit_root / (name + ".service")
        app, launcher, gate = work / "heartbeat_app.py", work / "preexec.py", work / "permit"
        app.write_text("import time\nwhile True:\n time.sleep(0.1)\n")
        launcher.write_text("import os,time\nfrom pathlib import Path\n"
                            f"target=Path({str(app)!r});gate=target.with_name('permit')\n"
                            "while not gate.exists():time.sleep(0.01)\n"
                            "os.execv('/usr/bin/python3',['/usr/bin/python3','-u',str(target)])\n")
        app_argument = "" if label == "delayed-exec" else " " + str(app)
        unit_file.write_text("[Unit]\nDescription=Owned process identity regression\n[Service]\nType=simple\n"
                             f"ExecStart=/usr/bin/python3 -u {launcher}{app_argument}\nRestart=no\n")
        row = {"case": label, "unit": unit, "work": str(work), "accepted": False}
        proof["cases"].append(row)
        save()
        releaser = None
        start = len(records)
        try:
            run(["systemctl", "--user", "daemon-reload"], work)
            run(["systemctl", "--user", "start", unit], work)
            state = wait(unit, work, lambda state: state["ActiveState"] == "active" and int(state["MainPID"]) > 0)
            pid = int(state["MainPID"])
            deadline = time.monotonic() + 5
            while True:
                before = Path("/proc", str(pid), "cmdline").read_bytes().removesuffix(b"\0").split(b"\0")
                if os.fsencode(launcher) in before:
                    break
                assert time.monotonic() < deadline
                time.sleep(0.01)
            assert (os.fsencode(app) in before) is (label != "delayed-exec")
            row.update(pid=pid, initialArgv=[os.fsdecode(value) for value in before], managerBefore=state,
                       oldImmediateSubstringAssertionWouldPass=os.fsencode(app) in b"\0".join(before))
            if label in ("delayed-exec", "misleading-argv"):
                def release_after_observation(gate=gate, launcher=launcher, start=start):
                    deadline = time.monotonic() + 4
                    while time.monotonic() < deadline:
                        if any(record.get("kind") == "process-identity-pending" and os.fsdecode(launcher) in record.get("observedArgv", []) for record in records[start:]):
                            gate.write_text("permit owned exec\n")
                            return
                        time.sleep(0.01)
                releaser = threading.Thread(target=release_after_observation)
                releaser.start()
                callback_reads = []

                def callback_properties(unit, cwd, calls=callback_reads):
                    calls.append(unit)
                    return properties(unit, cwd)

                if label == "misleading-argv":
                    actual = owned_process(unit, work, state, app, timeout=5,
                                           read_properties=callback_properties, evidence=records)
                    assert len(callback_reads) >= 2
                    row["explicitCallbacksVerified"] = True
                else:
                    actual = owned_process(unit, work, state, app, timeout=5)
                assert actual == pid and gate.exists()
                after = Path("/proc", str(pid), "cmdline").read_bytes().removesuffix(b"\0").split(b"\0")
                assert after == [b"/usr/bin/python3", b"-u", os.fsencode(app)]
                row.update(finalArgv=[os.fsdecode(value) for value in after], sameManagedPID=True, delayedIdentityObserved=True)
            else:
                requested = dict(state)
                if label == "wrong-managed-pid":
                    requested["MainPID"] = str(os.getpid())
                try:
                    owned_process(unit, work, requested, app, timeout=0.35)
                except AssertionError:
                    row["strictRejection"] = True
                else:
                    raise AssertionError("wrong script or unmanaged PID was accepted")
                assert not gate.exists() and properties(unit, work)["MainPID"] == str(pid)
            row["accepted"] = True
        finally:
            if releaser:
                releaser.join(timeout=5)
                assert not releaser.is_alive()
            run(["systemctl", "--user", "stop", unit], work, expected=None)
            stopped = wait(unit, work, lambda state: state["MainPID"] == "0" and state["ActiveState"] == "inactive")
            row["stopped"] = stopped
            unit_file.unlink(missing_ok=True)
            run(["systemctl", "--user", "daemon-reload"], work)
            removed = properties(unit, work)
            assert removed["LoadState"] == "not-found" and removed["MainPID"] == "0"
            row["removed"] = removed
            shutil.rmtree(work)
            row["cleanup"] = {"unitRemoved": not unit_file.exists(), "directoryRemoved": not work.exists(), "processStopped": True}
            save()
    assert len(proof["cases"]) == 4 and all(row["accepted"] for row in proof["cases"])
    proof["accepted"] = True
finally:
    save()
print(json.dumps({"accepted": proof["accepted"], "actualManager": True, "cases": len(proof["cases"])}))
