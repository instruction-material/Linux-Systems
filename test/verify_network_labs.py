"""Accept real Linux interfaces, socket ownership, HTTP failures and DNS answers."""
import argparse
import hashlib
import json
import os
import platform
import select
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKS = ["LS-11-unit-10-networking-from-a-systems-view",
         "LS-21-unit-10-networking-from-a-systems-view-supplemental-2",
         "LS-22-unit-10-networking-from-a-systems-view-supplemental-3"]
parser = argparse.ArgumentParser()
parser.add_argument("--proof", required=True, type=Path)
args = parser.parse_args()
assert platform.system() == "Linux" and os.geteuid() > 0
assert all(shutil.which(name) for name in ("bash", "python3", "ip", "ss", "ping", "curl", "dig"))
args.proof = args.proof.resolve()
args.proof.parent.mkdir(parents=True, exist_ok=True)
records, observations, profiles, service_events = [], [], [], []
task = os.environ.get("CLASSES_FAMILY_TASK_ID", "linux-network-source")
environment = dict(os.environ, LC_ALL="C", PYTHONDONTWRITEBYTECODE="1",
                   http_proxy="http://192.0.2.1:9", HTTP_PROXY="http://192.0.2.1:9", ALL_PROXY="http://192.0.2.1:9")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes():
    return {str(file.relative_to(ROOT)): digest(file) for pack in PACKS
            for file in sorted((ROOT / pack).rglob("*")) if file.is_file()}


def lifecycle(argv, cwd, child, timeout):
    return {"parentTaskId": task, "parentPid": os.getpid(), "command": argv, "cwd": str(cwd),
                "pid": child.pid, "startTime": time.time(), "timeoutSeconds": timeout}


def run(argv, cwd, env=None):
    child = subprocess.Popen(argv, cwd=cwd, env=environment if env is None else env,
                             stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, start_new_session=True)
    entry = lifecycle(argv, cwd, child, 20)
    records.append(dict(entry, event="start"))
    cleanup = "owned process exited and reaped"
    try:
        stdout, stderr = child.communicate(timeout=20)
    except BaseException:
        cleanup = "owned process group stopped after failure or interruption"
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
    value = {"command": argv, "cwd": str(cwd), "status": child.returncode,
                 "stdout": stdout.decode(), "stderr": stderr.decode()}
    observations.append(value)
    return value


@contextmanager
def server(cwd, *options):
    argv = ["bash", "task.sh", *options]
    child = subprocess.Popen(argv, cwd=cwd, env=environment, stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    entry = lifecycle(argv, cwd, child, 90)
    records.append(dict(entry, event="start"))
    cleanup = "owned foreground listener interrupted, closed and reaped"
    try:
        assert select.select([child.stdout], [], [], 10)[0], "server did not become ready"
        ready = json.loads(child.stdout.readline())
        assert ready["event"] == "ready" and ready["pid"] == child.pid
        assert ready["address"] in ("127.0.0.1", "127.0.0.2") and 1024 <= ready["port"] <= 65535
        service_events.append(ready)
        yield ready
        assert time.time() - entry["startTime"] < 90
    finally:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
        try:
            stdout, stderr = child.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            cleanup = "owned foreground listener group killed after timeout"
            os.killpg(child.pid, signal.SIGKILL)
            stdout, stderr = child.communicate()
        records.append(dict(entry, event="end", endTime=time.time(), exitCode=child.returncode,
                            childProcessGroupCleanup=cleanup))
        if child.returncode == 0:
            end = json.loads(stderr.decode().splitlines()[-1])
            assert end["event"] == "end" and end["pid"] == child.pid
            assert end["childProcessGroupCleanup"] and end["endTime"] >= end["startTime"]
            service_events.append(end)
        assert child.returncode == 0, (stdout, stderr, child.returncode)
        try:
            os.kill(child.pid, 0)
        except ProcessLookupError:
            pass
        else:
            raise AssertionError("serving process still exists after cleanup")


def inspect(cwd, name, *options):
    record = run(["bash", "task.sh", "inspect", *options, "--report", name + ".json"], cwd)
    assert record["status"] == 0, record
    path = cwd / (name + ".json")
    report = json.loads(path.read_text())
    assert report["platform"] == "Linux" and report["uid"] == os.geteuid()
    assert report["learnerWorksheetCompletionInferred"] is False
    assert path.stat().st_mode & 0o777 == 0o600
    assert all(row["pid"] > 0 and row["exitCode"] is not None and row["childProcessGroupCleanup"]
               and row["endTime"] >= row["startTime"] for row in report["commands"])
    assert report["selectedRoute"][0]["dev"] == "lo"
    assert report["interface"][0]["ifname"] == "lo"
    (args.proof.parent / (cwd.name + "-" + name + ".json")).write_bytes(path.read_bytes())
    return report


def tcp_options(ready, address="127.0.0.1", path="/health"):
    return ["--port", str(ready["port"]), "--address", address, "--path", path]


def check_http(report, status, curl_status, pid=None, label=None):
    assert report["http"]["httpStatus"] == status
    assert report["http"]["curlStatus"] == curl_status
    if pid:
        assert f"pid={pid}," in report["listeners"]
        assert report["http"]["body"] == f"{label} pid={pid}\n"
    else:
        assert report["http"]["body"] == ""


def absent_listener(cwd, ready):
    option = "-lunp" if ready["protocol"] == "udp" else "-ltnp"
    observed = run(["ss", "-H", option, "sport = :" + str(ready["port"])], cwd)
    assert observed["status"] == 0 and not observed["stdout"].strip(), observed


def direct_http(cwd, ready, status=0, label="ready", address="127.0.0.1"):
    observed = run(["curl", "--noproxy", "*", "--silent", "--show-error", "--fail-with-body",
                    "--connect-timeout", "1", "--max-time", "2", f"http://{address}:{ready['port']}/health"], cwd)
    assert observed["status"] == status and observed["stdout"] == f"{label} pid={ready['pid']}\n"


def main_snapshot(cwd):
    result = {}
    for name, argv in [("addresses", ["ip", "-j", "address", "show", "dev", "lo"]),
                       ("routes", ["ip", "-j", "route", "show", "table", "main"])]:
        actual = run(argv, cwd)
        assert actual["status"] == 0
        result[name] = json.loads(actual["stdout"])
    return result


before = source_hashes()
temporary = Path(tempfile.mkdtemp(prefix="linux-network-native-"))
try:
    host_before = main_snapshot(temporary)
    for index, pack in enumerate(PACKS):
        for role in ["starter", "solution", "independent-command-sequence"]:
            cwd = temporary / (str(index) + "-" + role)
            shutil.copytree(ROOT / pack / ("starter" if role == "independent-command-sequence" else role), cwd)
            if index == 0:
                with server(cwd, "serve") as ready:
                    first = inspect(cwd, "first", *tcp_options(ready))
                    check_http(first, 200, 0, ready["pid"], "ready")
                    assert first["icmp"]["exitCode"] == 0
                    independent = main_snapshot(cwd)
                    assert first["interface"] == independent["addresses"] and first["mainRoutes"] == independent["routes"]
                    actual_ss = run(["ss", "-H", "-ltnp", "sport = :" + str(ready["port"])], cwd)
                    assert f"pid={ready['pid']}," in actual_ss["stdout"]
                    direct_http(cwd, ready)
                    original = (cwd / "first.json").read_bytes()
                    assert run(["bash", "task.sh", "inspect", *tcp_options(ready), "--report", "first.json"], cwd)["status"] == 1
                    assert (cwd / "first.json").read_bytes() == original
                    (cwd / "linked.json").symlink_to("first.json")
                    assert run(["bash", "task.sh", "inspect", *tcp_options(ready), "--report", "linked.json"], cwd)["status"] == 1
                    assert (cwd / "first.json").read_bytes() == original
                    check_http(inspect(cwd, "missing", *tcp_options(ready, path="/missing")), 404, 22, ready["pid"], "missing")
                    assert run(["bash", "task.sh", "inspect", "--address", "192.0.2.1", "--port", "80", "--report", "foreign.json"], cwd)["status"] == 2
                    assert not (cwd / "foreign.json").exists()
                    assert run([sys.executable, "network_lab.py", "inspect", *tcp_options(ready), "--report", "no-tools.json"], cwd, env=dict(environment, PATH="/linux-course-missing-tools"))["status"] == 1
                    assert not (cwd / "no-tools.json").exists()
                absent_listener(cwd, ready)
                stopped = inspect(cwd, "stopped", *tcp_options(ready))
                check_http(stopped, 0, 7)
                assert not stopped["listeners"].strip()
                with server(cwd, "serve") as restored:
                    check_http(inspect(cwd, "restored", *tcp_options(restored)), 200, 0, restored["pid"], "ready")
                absent_listener(cwd, restored)
            elif index == 1:
                with server(cwd, "serve", "--bind", "127.0.0.2") as wrong:
                    report = inspect(cwd, "wrong-bind", *tcp_options(wrong))
                    check_http(report, 0, 7)
                    assert "127.0.0.2:" + str(wrong["port"]) in report["listeners"]
                    assert f"pid={wrong['pid']}," in report["listeners"]
                    assert report["icmp"]["exitCode"] == 0
                    check_http(inspect(cwd, "changed-target", *tcp_options(wrong, "127.0.0.2")), 200, 0, wrong["pid"], "ready")
                    direct_http(cwd, wrong, address="127.0.0.2")
                absent_listener(cwd, wrong)
                with server(cwd, "serve", "--mode", "unavailable") as unavailable:
                    check_http(inspect(cwd, "unavailable", *tcp_options(unavailable)), 503, 22, unavailable["pid"], "unavailable")
                    check_http(inspect(cwd, "missing-path", *tcp_options(unavailable, path="/missing")), 404, 22, unavailable["pid"], "missing")
                    direct_http(cwd, unavailable, status=22, label="unavailable")
                absent_listener(cwd, unavailable)
                with server(cwd, "serve") as restored:
                    check_http(inspect(cwd, "recovered", *tcp_options(restored)), 200, 0, restored["pid"], "ready")
                absent_listener(cwd, restored)
            else:
                with server(cwd, "serve") as web:
                    for iteration, mode in enumerate(["ready", "wrong", "missing", "ready"]):
                        with server(cwd, "dns", "--answer", mode) as dns:
                            report = inspect(cwd, str(iteration) + "-dns-" + mode, "--dns-port", str(dns["port"]), "--http-port", str(web["port"]))
                            expected = "NXDOMAIN" if mode == "missing" else "NOERROR"
                            assert report["dns"]["status"] == expected
                            assert f"pid={dns['pid']}," in report["dnsListener"] and f"pid={web['pid']}," in report["httpListener"]
                            direct = run(["dig", "-r", "@127.0.0.1", "-p", str(dns["port"]), "lab.invalid.", "A", "+noedns", "+norecurse", "+notcp", "+nosearch", "+time=1", "+tries=1"], cwd)
                            assert direct["status"] == 0 and "status: " + expected + "," in direct["stdout"]
                            if mode == "missing":
                                assert report["dns"]["answers"] == [] and report["selectedAddressRequest"] is None
                            else:
                                assert report["dns"]["answers"] == ["127.0.0.2" if mode == "wrong" else "127.0.0.1"]
                                assert report["selectedAddressRequest"]["curlStatus"] == (7 if mode == "wrong" else 0)
                                assert report["selectedAddressRequest"]["httpStatus"] == (0 if mode == "wrong" else 200)
                            assert report["explicitBypassRequest"]["httpStatus"] == 200
                            assert report["explicitBypassRequest"]["body"] == f"ready pid={web['pid']}\n"
                            assert report["bypassRepairsSystemResolver"] is False
                            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as malformed:
                                malformed.settimeout(0.15)
                                malformed.sendto(b"bad", ("127.0.0.1", dns["port"]))
                                try:
                                    malformed.recvfrom(512)
                                except TimeoutError:
                                    pass
                                else:
                                    raise AssertionError("malformed query received a response")
                        absent_listener(cwd, dns)
                    direct_http(cwd, web)
                absent_listener(cwd, web)
            notes = next(cwd.glob("*-notes.md"))
            assert notes.read_bytes() == (ROOT / pack / ("starter" if role == "independent-command-sequence" else role) / notes.name).read_bytes()
            profiles.append({"pack": pack, "role": role, "actualLinuxTools": True,
                                 "independentLiveComparison": True, "ownedTcpAndUdpOnly": True,
                                 "changedCases": True, "cleanupObserved": True, "notesUnchanged": True})
    assert main_snapshot(temporary) == host_before
finally:
    shutil.rmtree(temporary)
    args.proof.with_suffix(".processes.jsonl").write_text("".join(json.dumps(row) + "\n" for row in records))
assert source_hashes() == before
starts = {(row["pid"], row["startTime"]) for row in records if row["event"] == "start"}
ends = {(row["pid"], row["startTime"]) for row in records if row["event"] == "end"}
assert starts == ends
proof = {"accepted": True, "platform": platform.system(), "uid": os.geteuid(), "profiles": profiles,
             "observations": observations, "serviceEvents": service_events, "sourceHashes": before,
             "sourceUnchanged": True, "loopbackAddressesAndMainRoutesUnchanged": True,
             "temporaryFilesCleaned": not temporary.exists(), "worksheetCompletionNotInferred": True,
             "loggedLifecycles": len(starts), "foregroundServicesClosed": len(service_events) // 2}
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps({key: value for key, value in proof.items() if key not in ("observations", "serviceEvents", "sourceHashes")}))
