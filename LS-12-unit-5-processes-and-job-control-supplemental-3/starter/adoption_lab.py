"""Observe real zombies and adoption by this disposable Linux subreaper."""
import argparse
import ctypes
import json
import math
import os
import platform
import select
import signal
import sys
import time
from pathlib import Path


def hold_seconds(value):
    try:
        result = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("hold must be a number") from error
    if not math.isfinite(result) or not 0.1 <= result <= 120:
        raise argparse.ArgumentTypeError("hold must be from 0.1 through 120 seconds")
    return result


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--hold-seconds", type=hold_seconds, default=5)
parser.add_argument("--record", type=Path)
args = parser.parse_args()
if platform.system() != "Linux":
    parser.error("this experiment requires Linux /proc and child-subreaper support")
libc = ctypes.CDLL(None, use_errno=True)
libc.prctl.restype = ctypes.c_int
libc.prctl.argtypes = [ctypes.c_int] + [ctypes.c_ulong] * 4
if libc.prctl(36, 1, 0, 0, 0) != 0:
    raise OSError(ctypes.get_errno(), "cannot enable this process's child-subreaper flag")
flag = ctypes.c_int()
if libc.prctl(37, ctypes.addressof(flag), 0, 0, 0) != 0 or flag.value != 1:
    raise RuntimeError("child-subreaper flag was not observed")
observer = os.getpid()
descriptors = set()
try:
    record_stream = args.record.open("x", encoding="utf-8") if args.record else None
except OSError as error:
    parser.error(f"cannot create a new record file: {error}")
output_closed = False


def emit(event, **extra):
    global output_closed
    line = json.dumps({"event": event, "pid": os.getpid(), "uid": os.getuid(),
                       "at": time.time(), **extra}, separators=(",", ":"))
    if record_stream:
        record_stream.write(line + "\n")
        record_stream.flush()
    if not output_closed:
        try:
            print(line, flush=True)
        except BrokenPipeError:
            # A lost display pipe must not interrupt owned-child cleanup.
            output_closed = True
            fd = os.open(os.devnull, os.O_WRONLY)
            try:
                os.dup2(fd, sys.stdout.fileno())
            finally:
                os.close(fd)


def kernel(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        uid = Path(f"/proc/{pid}").stat().st_uid
    except (FileNotFoundError, ProcessLookupError):
        return None
    return {"pid": pid, "ppid": int(fields[1]), "state": fields[0],
            "startTicks": int(fields[19]), "uid": uid}


def wait_for(predicate, label):
    deadline = time.monotonic() + 5
    while True:
        result = predicate()
        if result:
            return result
        if time.monotonic() >= deadline:
            raise TimeoutError(label)
        time.sleep(0.01)


def close_fd(fd):
    if fd in descriptors:
        os.close(fd)
        descriptors.remove(fd)


def pipe():
    pair = os.pipe()
    descriptors.update(pair)
    return pair


def child_defaults():
    for number in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGALRM):
        signal.signal(number, signal.SIG_DFL)
    signal.alarm(150)


class Stopped(Exception):
    def __init__(self, number):
        self.number = number


def interrupted(number, _frame):
    raise Stopped(number)


for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGALRM):
    signal.signal(number, interrupted)
signal.alarm(int(2 * args.hold_seconds + 20))
status = 0
complete = False
try:
    emit("started", subreaperObserved=bool(flag.value), holdSeconds=args.hold_seconds)
    zombie = os.fork()
    if zombie == 0:
        os._exit(7)
    emit("spawned", childPid=zombie, purpose="zombie")
    observed = wait_for(lambda: (state if (state := kernel(zombie)) and state["state"] == "Z" else None), "zombie state")
    assert observed["ppid"] == observer and observed["uid"] == os.getuid()
    emit("zombie_observed", child=observed)
    time.sleep(args.hold_seconds)
    waited, result = os.waitpid(zombie, 0)
    assert waited == zombie and os.waitstatus_to_exitcode(result) == 7
    emit("reaped", childPid=zombie, status=7, purpose="zombie")
    info_read, info_write = pipe()
    middle_read, middle_write = pipe()
    release_read, release_write = pipe()
    middle = os.fork()
    if middle == 0:
        child_defaults()
        for fd in (info_read, middle_write, release_write):
            close_fd(fd)
        grandchild = os.fork()
        if grandchild == 0:
            child_defaults()
            close_fd(middle_read)
            initial = kernel(os.getpid())
            os.write(info_write, (json.dumps(initial) + "\n").encode())
            close_fd(info_write)
            os.read(release_read, 1)
            close_fd(release_read)
            os._exit(9)
        close_fd(info_write)
        close_fd(release_read)
        os.read(middle_read, 1)
        close_fd(middle_read)
        os._exit(0)
    emit("spawned", childPid=middle, purpose="original-parent")
    for fd in (info_write, middle_read, release_read):
        close_fd(fd)
    assert select.select([info_read], [], [], 5)[0], "grandchild readiness"
    payload = b""
    while b"\n" not in payload:
        chunk = os.read(info_read, 4096)
        if not chunk:
            raise RuntimeError("grandchild readiness ended early")
        payload += chunk
    initial = json.loads(payload.split(b"\n", 1)[0])
    assert initial["ppid"] == middle and initial["uid"] == os.getuid()
    current = kernel(initial["pid"])
    assert current and current["ppid"] == middle and current["startTicks"] == initial["startTicks"]
    emit("grandchild_observed", child=current, originalParent=middle)
    close_fd(info_read)
    os.write(middle_write, b"x")
    close_fd(middle_write)
    waited, result = os.waitpid(middle, 0)
    assert waited == middle and os.waitstatus_to_exitcode(result) == 0
    emit("reaped", childPid=middle, status=0, purpose="original-parent")
    adopted = wait_for(lambda: (state if (state := kernel(initial["pid"])) and state["ppid"] == observer else None), "actual adoption")
    assert adopted["startTicks"] == initial["startTicks"] and adopted["uid"] == initial["uid"]
    emit("adopted", child=adopted, originalParent=middle, actualNewParent=observer)
    time.sleep(args.hold_seconds)
    os.write(release_write, b"x")
    close_fd(release_write)
    waited, result = os.waitpid(initial["pid"], 0)
    assert waited == initial["pid"] and os.waitstatus_to_exitcode(result) == 9
    emit("reaped", childPid=waited, status=9, purpose="adopted-child")
    complete = True
except Stopped as error:
    status = 128 + error.number
    emit("interrupted", signal=signal.Signals(error.number).name, status=status)
finally:
    signal.alarm(0)
    for fd in list(descriptors):
        close_fd(fd)
    # Only direct children can be waited here. Killing/reaping an original
    # parent first lets this observed subreaper adopt and clean its descendants.
    deadline = time.monotonic() + 5
    while True:
        children = [int(value) for value in Path(f"/proc/{os.getpid()}/task/{os.getpid()}/children").read_text().split()]
        if not children:
            break
        for child in children:
            before = kernel(child)
            if before is not None and before["ppid"] == observer:
                try:
                    os.kill(child, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        for child in children:
            try:
                waited, result = os.waitpid(child, 0)
                emit("cleanup_reaped", childPid=waited, status=os.waitstatus_to_exitcode(result))
            except ChildProcessError:
                pass
        if time.monotonic() >= deadline:
            raise TimeoutError("owned descendants were not cleaned")
    emit("cleanup", complete=complete, noOwnedChildren=True, descriptorsClosed=not descriptors)
    if record_stream:
        record_stream.close()
raise SystemExit(status)
