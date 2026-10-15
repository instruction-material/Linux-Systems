"""Observe actual file metadata, mounted filesystem and a bounded byte read."""
import argparse
import base64
import datetime
import hashlib
import json
import os
import platform
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

LIMIT = 4096
commands = []
completed = []


class ToolFailure(Exception):
    pass


def content_is_empty(reported_size, observed_bytes):
    return reported_size == 0 # TODO: use the count from the actual successful read.


def tool(argv):
    child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, start_new_session=True,
                             env=dict(os.environ, LC_ALL="C"))
    entry = {"parentTaskId": os.environ.get("CLASSES_FAMILY_TASK_ID", "filesystem-observation"),
             "parentPid": os.getpid(), "command": argv, "cwd": os.getcwd(), "pid": child.pid,
             "startTime": time.time(), "timeoutSeconds": 15}
    cleanup = "owned process exited and reaped"
    out, err = b"", b""
    timed_out = False
    try:
        out, err = child.communicate(timeout=15)
    except BaseException as error:
        cleanup = "owned process group terminated after timeout or interruption"
        if child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        try:
            out, err = child.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            out, err = child.communicate()
        if isinstance(error, subprocess.TimeoutExpired):
            timed_out = True
        else:
            raise
    finally:
        entry.update({"endTime": time.time(), "exitCode": child.returncode,
                      "childProcessGroupCleanup": cleanup, "timedOut": timed_out,
                      "stdoutBase64": base64.b64encode(out).decode(),
                      "stderr": err.decode(errors="replace")})
        commands.append(entry)
    if timed_out:
        raise ToolFailure("A native command timed out; no complete result is available.")
    if child.returncode:
        raise ToolFailure("A native observation command failed; no complete result is available.")
    return out


def observe(value):
    if value == "-":
        raise ValueError("A path cannot select standard input (-).")
    path = Path(value).resolve(strict=True)
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("Use a regular file or a readable kernel pseudo-file.")
    raw = tool(["stat", "-L", "--printf=%s:%d:%i", "--", str(path)]).decode()
    size, device, inode = map(int, raw.split(":"))
    mounts = json.loads(tool(["findmnt", "--json", "--target", str(path),
                              "--output", "TARGET,FSTYPE,SOURCE"]))["filesystems"]
    if len(mounts) != 1:
        raise ValueError("The selected path did not produce one actual mount record.")
    data = tool(["head", "--bytes=" + str(LIMIT + 1), "--", str(path)])
    return {"inputPath": value, "resolvedPath": str(path),
            "reportedSize": size, "device": device, "inode": inode,
            "filesystem": mounts[0], "bytesRead": len(data), "captureLimit": LIMIT,
            "truncated": len(data) > LIMIT,
            "capturedBase64": base64.b64encode(data[:LIMIT]).decode(),
            "capturedSha256": hashlib.sha256(data[:LIMIT]).hexdigest(),
            "contentEmpty": content_is_empty(size, len(data)),
            "observedAt": datetime.datetime.now(datetime.timezone.utc).isoformat()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args()
    if platform.system() != "Linux" or os.geteuid() == 0:
        raise ValueError("Use an ordinary account in an owned Linux lab.")
    for value in args.paths:
        completed.append(observe(value))
    print(json.dumps({"observationsCompleted": True, "observations": completed,
                      "commands": commands, "learnerWorksheetCompletionInferred": False},
                     indent=2))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(json.dumps({"error": "Interrupted", "completed": completed,
                          "commands": commands}), file=sys.stderr)
        raise SystemExit(130)
    except ToolFailure as error:
        print(json.dumps({"error": str(error), "completed": completed,
                          "commands": commands}), file=sys.stderr)
        raise SystemExit(1)
    except (ValueError, OSError) as error:
        print(json.dumps({"error": str(error), "completed": completed,
                          "commands": commands}), file=sys.stderr)
        raise SystemExit(2)
