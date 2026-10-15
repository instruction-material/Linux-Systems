"""Private, marker-protected workspace and observed command helpers."""
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import stat
import subprocess
import time


def prerequisites():
    if platform.system() != "Linux" or os.geteuid() == 0:
        raise ValueError("use an ordinary account in an owned Debian/Ubuntu Linux lab")
    def terminate(_number, _frame):
        raise InterruptedError("owned lab command interrupted")
    signal.signal(signal.SIGTERM, terminate)


def new_file(path, content, mode=0o600):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, "wb") as stream:
        stream.write(content if isinstance(content, bytes) else content.encode())


def regular(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or path.parent.resolve() != path.parent.absolute():
        raise ValueError("expected an owned regular file: " + str(path))
    return path


def directory(path):
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or path.resolve() != path.absolute():
        raise ValueError("expected an owned directory: " + str(path))
    return path


def init_lab(path, kind):
    path = path.absolute()
    parent = path.parent.resolve(strict=True)
    root = parent / path.name
    root.mkdir(mode=0o700)
    new_file(root / ".owned-layout-lab.json", json.dumps(dict(kind=kind, uid=os.geteuid())) + "\n")
    new_file(root / "operations.jsonl", b"")
    print("OWNED_LAB=" + str(root))
    return root


def lab(path, kind):
    root = directory(path.absolute())
    if root.is_symlink() or root.resolve() != root:
        raise ValueError("use the exact printed canonical lab path")
    marker = regular(root / ".owned-layout-lab.json")
    if json.loads(marker.read_text()) != dict(kind=kind, uid=os.geteuid()):
        raise ValueError("workspace marker does not match this lab and account")
    regular(root / "operations.jsonl")
    return root


def sha(path):
    return hashlib.sha256(regular(path).read_bytes()).hexdigest()


def record(root, row):
    fd = os.open(root / "operations.jsonl", os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
    with os.fdopen(fd, "w") as stream:
        stream.write(json.dumps(row) + "\n")


def run(root, argv, timeout=30):
    started = time.time()
    child = subprocess.Popen(argv, cwd=root, stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             env=dict(os.environ, LC_ALL="C"), start_new_session=True)
    entry = dict(parentTaskId=os.environ.get("CLASSES_FAMILY_TASK_ID", "linux-package-layout"),
                 parentPid=os.getpid(), uid=os.geteuid(), pid=child.pid, command=argv,
                 cwd=str(root), startTime=started, timeoutSeconds=timeout)
    record(root, dict(entry, event="start"))
    cleanup = "owned process exited and reaped"
    try:
        stdout, stderr = child.communicate(timeout=timeout)
    except BaseException:
        cleanup = "owned process group stopped after interruption or timeout"
        os.killpg(child.pid, signal.SIGTERM)
        try:
            stdout, stderr = child.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            stdout, stderr = child.communicate()
        raise
    finally:
        record(root, dict(entry, event="end", endTime=time.time(), exitCode=child.returncode,
                          childProcessGroupCleanup=cleanup))
    record(root, dict(event="output", pid=child.pid, startTime=started,
                     status=child.returncode, stdout=stdout.decode(errors="replace"),
                     stderr=stderr.decode(errors="replace")))
    return child.returncode, stdout, stderr


def checked(root, argv):
    status, stdout, stderr = run(root, argv)
    if status:
        raise RuntimeError(f"command failed ({status}): {stderr.decode(errors='replace').strip()}")
    return stdout
