"""Verify actual owned Apache/Nginx comparison, unfinished task and restoration."""
import argparse
import contextlib
import hashlib
import json
import os
import platform
import shutil
import signal
import socket
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

PACK = Path(__file__).resolve().parents[1] / "LS4-Apache-Virtual-Host-Compare"
parser = argparse.ArgumentParser()
parser.add_argument("--proof", type=Path, required=True)
args = parser.parse_args()
assert platform.system() == "Linux" and os.geteuid() != 0
assert all(shutil.which(name) for name in ("apache2", "nginx", "ss"))
args.proof = args.proof.resolve()
args.proof.parent.mkdir(parents=True, exist_ok=True)
observations, processes, profiles = [], [], []
task_id = os.environ.get("CLASSES_FAMILY_TASK_ID", "linux-apache-source-ci")


def source_hashes():
    return {str(path.relative_to(PACK)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(PACK.rglob("*")) if path.is_file()}


def process_record(event, child, command, cwd, started, **extra):
    entry = {"event": event, "parentTaskId": task_id, "parentPid": os.getpid(),
                 "pid": child.pid, "command": command, "cwd": str(cwd),
                 "startTime": started, "timeoutSeconds": 10}
    entry.update(extra)
    processes.append(entry)


def run(command, cwd, env, expected=0):
    started = time.time()
    child = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, start_new_session=True)
    process_record("start", child, command, cwd, started)
    cleanup = "process exited"
    try:
        out, err = child.communicate(timeout=10)
    except BaseException:
        os.killpg(child.pid, signal.SIGTERM)
        try:
            child.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.communicate()
        cleanup = "process group terminated"
        raise
    finally:
        process_record("end", child, command, cwd, started, endTime=time.time(),
                       exitCode=child.returncode, childProcessGroupCleanup=cleanup)
    observations.append({"kind": "command", "command": command, "status": child.returncode,
                             "stdout": out.decode(errors="replace"),
                             "stderr": err.decode(errors="replace")})
    if expected == "failure":
        assert child.returncode != 0, (command, out, err)
    else:
        assert child.returncode == expected, (command, child.returncode, out, err)
    return out + err


@contextlib.contextmanager
def daemon(command, cwd, env, label):
    stdout = (args.proof.parent / (label + "-stdout.log")).open("wb")
    stderr = (args.proof.parent / (label + "-stderr.log")).open("wb")
    started = time.time()
    child = subprocess.Popen(command, cwd=cwd, env=env, stdout=stdout,
                             stderr=stderr, start_new_session=True)
    process_record("start", child, command, cwd, started, timeoutSeconds=90)
    expired = [False]

    def stop_expired_group():
        if child.poll() is None:
            expired[0] = True
            with contextlib.suppress(ProcessLookupError):
                os.killpg(child.pid, signal.SIGTERM)

    watchdog = threading.Timer(90, stop_expired_group)
    watchdog.daemon = True
    watchdog.start()
    try:
        yield child
    finally:
        watchdog.cancel()
        cleanup = "owned process group terminated"
        with contextlib.suppress(ProcessLookupError):
            os.killpg(child.pid, signal.SIGTERM)
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=3)
            cleanup = "owned process group killed after timeout"
        with contextlib.suppress(ProcessLookupError):
            os.killpg(child.pid, signal.SIGTERM)
        stdout.close()
        stderr.close()
        process_record("end", child, command, cwd, started, endTime=time.time(),
                       exitCode=child.returncode, childProcessGroupCleanup=cleanup,
                       timeoutSeconds=90, timedOut=expired[0])
        assert not expired[0], "Owned web server exceeded its profile deadline"


def unused_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def response(port, host, path="/index.html", method="GET"):
    request = urllib.request.Request("http://127.0.0.1:" + str(port) + path,
                                     headers={"Host": host}, method=method)
    try:
        opened = urllib.request.urlopen(request, timeout=2)
    except urllib.error.HTTPError as error:
        opened = error
    with opened:
        return opened.status, opened.read(), dict(opened.headers.items())


def expect_page(port, host, status, body=None, path="/index.html", method="GET"):
    actual, content, headers = response(port, host, path, method)
    assert actual == status, (port, host, path, actual, content)
    if body is not None:
        assert content == body, (port, host, path, content, body)
    observations.append({"kind": "http", "port": port, "host": host, "path": path,
                             "method": method, "status": actual, "bodySha256": hashlib.sha256(content).hexdigest(),
                             "headers": headers})
    return headers


def wait_page(port, host, status, body, child):
    deadline = time.monotonic() + 5
    while True:
        assert child.poll() is None, (child.args, child.returncode)
        try:
            actual, content, _ = response(port, host)
            if actual == status and (body is None or content == body):
                return
        except (OSError, urllib.error.URLError):
            pass
        assert time.monotonic() < deadline, (port, host, status, body)
        time.sleep(0.1)


before = source_hashes()
assert len(before) == 11
accepted = False
try:
    for command in (["apache2", "-v"], ["apache2", "-l"], ["nginx", "-v"], ["ss", "-V"]):
        run(command, PACK, os.environ)
    for role in ("starter", "solution", "independent-completion"):
        with tempfile.TemporaryDirectory(prefix="apache-comparison-") as directory:
            work = Path(directory)
            selected = PACK / ("starter" if role == "independent-completion" else role)
            for name in ("run", "logs", "public", "second", "unfinished"):
                (work / name).mkdir()
            primary = (selected / "index.html").read_bytes()
            secondary = (selected / "second.html").read_bytes()
            (work / "public/index.html").write_bytes(primary)
            (work / "second/index.html").write_bytes(secondary)
            apache = (selected / "linux-systems-apache.conf").read_text()
            if role == "independent-completion":
                unfinished = 'DocumentRoot "${LAB_ROOT}/unfinished"'
                assert apache.count(unfinished) == 1
                apache = apache.replace(unfinished, 'DocumentRoot "${LAB_ROOT}/public"', 1)
            apache_port, nginx_port = unused_port(), unused_port()
            assert apache_port != nginx_port
            nginx = (selected / "linux-systems-nginx.conf").read_text()
            assert nginx.count("127.0.0.1:18081") == 2
            nginx = nginx.replace("127.0.0.1:18081", "127.0.0.1:" + str(nginx_port))
            (work / "apache.conf").write_text(apache)
            (work / "nginx.conf").write_text(nginx)
            env = dict(os.environ, LAB_ROOT=str(work), APACHE_PORT=str(apache_port),
                       LAB_UID=str(os.geteuid()), LAB_GID=str(os.getegid()))
            apache_command = ["apache2", "-f", str(work / "apache.conf")]
            nginx_command = ["nginx", "-p", str(work) + "/", "-c", "nginx.conf"]
            run(apache_command + ["-t"], work, env)
            assert b"linux-systems.test" in run(apache_command + ["-S"], work, env)
            run(nginx_command + ["-t"], work, env)
            assert b"second.test" in run(nginx_command + ["-T"], work, env)
            primary_status = 404 if role == "starter" else 200
            primary_body = None if role == "starter" else primary
            with daemon(apache_command + ["-DFOREGROUND"], work, env, role + "-apache") as a, daemon(nginx_command + ["-g", "daemon off;"], work, env, role + "-nginx") as n:
                wait_page(apache_port, "linux-systems.test", primary_status, primary_body, a)
                wait_page(nginx_port, "linux-systems.test", 200, primary, n)
                for label, port, child in (("apache", apache_port, a), ("nginx", nginx_port, n)):
                    assert int((work / "run" / (label + ".pid")).read_text()) == child.pid
                    sockets = run(["ss", "-H", "-ltnp", "sport = :" + str(port)], work, env)
                    assert ("127.0.0.1:" + str(port)).encode() in sockets
                    assert ("pid=" + str(child.pid) + ",").encode() in sockets
                    rows = [line.split() for line in sockets.decode().splitlines()]
                    assert rows and all(row[3] == "127.0.0.1:" + str(port) for row in rows)
                    status = primary_status if label == "apache" else 200
                    body = primary_body if label == "apache" else primary
                    expect_page(port, "linux-systems.test", status, body)
                    expect_page(port, "second.test", 200, secondary)
                    expect_page(port, "other.test", status, body)
                    expect_page(port, "linux-systems.test", 404, path="/missing.txt")
                    if status == 200:
                        headers = expect_page(port, "linux-systems.test", 200, b"", method="HEAD")
                        assert int(headers["Content-Length"]) == len(primary)
                for name, text, command, port, child, status, body, invalid in (
                    ("apache.conf", apache, apache_command, apache_port, a, primary_status, primary_body, "InvalidOwnedLabDirective\n"),
                    ("nginx.conf", nginx, nginx_command, nginx_port, n, 200, primary, "invalid_owned_lab_directive;\n")
                ):
                    (work / name).write_text(text + invalid)
                    run(command + ["-t"], work, env, expected="failure")
                    assert child.poll() is None
                    expect_page(port, "linux-systems.test", status, body)
                    (work / name).write_text(text)
                    run(command + ["-t"], work, env)
                changed_and_restored = False
                if role != "starter":
                    changed_apache = apache.replace('DocumentRoot "${LAB_ROOT}/public"', 'DocumentRoot "${LAB_ROOT}/second"', 1)
                    changed_nginx = nginx.replace("root public;", "root second;", 1)
                    assert changed_apache != apache and changed_nginx != nginx
                    for a_text, n_text, expected_body in ((changed_apache, changed_nginx, secondary), (apache, nginx, primary)):
                        (work / "apache.conf").write_text(a_text)
                        (work / "nginx.conf").write_text(n_text)
                        run(apache_command + ["-t"], work, env)
                        run(nginx_command + ["-t"], work, env)
                        os.kill(a.pid, signal.SIGUSR1)
                        os.kill(n.pid, signal.SIGHUP)
                        wait_page(apache_port, "linux-systems.test", 200, expected_body, a)
                        wait_page(nginx_port, "linux-systems.test", 200, expected_body, n)
                        for port, label, child in ((apache_port, "apache", a), (nginx_port, "nginx", n)):
                            expect_page(port, "linux-systems.test", 200, expected_body)
                            expect_page(port, "second.test", 200, secondary)
                            assert int((work / "run" / (label + ".pid")).read_text()) == child.pid
                    changed_and_restored = True
                for name in ("apache-access.log", "nginx-access.log"):
                    assert b"GET /index.html" in (work / "logs" / name).read_bytes()
            for port in (apache_port, nginx_port):
                assert not run(["ss", "-H", "-ltnp", "sport = :" + str(port)], work, env).strip()
            profiles.append({"role": role, "apachePort": apache_port, "nginxPort": nginx_port,
                                 "actualLinuxSockets": True, "exactPages": True, "namedLearnerFailure": role == "starter",
                                 "rejectedSyntaxLeavesServing": True, "changedAndRestored": changed_and_restored,
                                 "ownedListenersRemoved": True})
    assert len(profiles) == 3 and source_hashes() == before
    accepted = True
finally:
    args.proof.with_suffix(".processes.jsonl").write_text("".join(json.dumps(p) + "\n" for p in processes))
    args.proof.write_text(json.dumps({"accepted": accepted, "platform": platform.platform(), "uid": os.geteuid(),
                                         "sourceHashes": before, "profiles": profiles, "observations": observations,
                                         "independentLearnerCompletions": 1, "sourceUnchanged": source_hashes() == before}, indent=2) + "\n")
print(json.dumps({"accepted": accepted, "profiles": len(profiles), "observations": len(observations)}))
