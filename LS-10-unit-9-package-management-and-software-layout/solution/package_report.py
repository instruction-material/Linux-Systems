#!/usr/bin/env python3
"""Collect read-only installed Debian package and filesystem evidence."""
import argparse
import datetime
import json
import os
import platform
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time


def command(argv, records, missing_ok=False):
    started = time.time()
    child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             env=dict(os.environ, LC_ALL="C"), start_new_session=True)
    entry = dict(parentTaskId=os.environ.get("CLASSES_FAMILY_TASK_ID", "package-layout-investigation"),
                 parentPid=os.getpid(), pid=child.pid, cwd=str(Path.cwd()),
                 command=argv, startTime=started, timeoutSeconds=15)
    cleanup = "owned query exited and reaped"
    try:
        stdout, stderr = child.communicate(timeout=15)
    except BaseException:
        cleanup = "owned query group terminated after failure or interruption"
        os.killpg(child.pid, signal.SIGTERM)
        try:
            stdout, stderr = child.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            stdout, stderr = child.communicate()
        raise
    finally:
        records.append(dict(entry, endTime=time.time(), exitCode=child.returncode,
                            childProcessGroupCleanup=cleanup))
    if child.returncode and not (missing_ok and child.returncode == 1):
        raise RuntimeError(f"query failed ({child.returncode}): {stderr.decode(errors='replace').strip()}")
    return stdout.decode()


def category(name):
    """Describe conventional paths, without assuming every package uses them."""
    if name.startswith(("/etc/",)):
        return "configuration"
    if name.startswith(("/usr/lib/systemd/", "/lib/systemd/")):
        return "service-management"
    if name.startswith(("/bin/", "/sbin/", "/usr/bin/", "/usr/sbin/")):
        return "command"
    if name.startswith(("/usr/lib/", "/lib/", "/lib64/")):
        return "library-or-support"
    if name.startswith(("/usr/share/doc/", "/usr/share/man/")):
        return "documentation"
    return "other"


def collect(package, executable):
    records = []
    fields = ["binary:Package", "Version", "Architecture", "Status", "Depends", "Source"]
    fmt = "".join("${" + name + "}\\n" for name in fields)
    values = command(["dpkg-query", "--show", "--showformat=" + fmt, package], records).splitlines()
    if len(values) != len(fields):
        raise RuntimeError("unexpected package metadata shape")
    metadata = dict(zip(fields, values))
    if metadata["Status"] != "install ok installed":
        raise RuntimeError("package is not fully installed: " + metadata["Status"])
    names = command(["dpkg-query", "--listfiles", package], records).splitlines()
    listed = []
    for name in names:
        if not name.startswith("/"):
            # dpkg-query can append diversion descriptions; they are not paths.
            continue
        path = Path(name)
        entry = dict(path=name, category=category(name), exists=path.exists(),
                     symlink=path.is_symlink(), directory=path.is_dir())
        if entry["symlink"]:
            entry["linkTarget"] = os.readlink(path)
        listed.append(entry)
    resolved = shutil.which(executable)
    if resolved is None:
        raise RuntimeError("command is absent from PATH: " + executable)
    resolved = str(Path(resolved).resolve(strict=True))
    candidates = [resolved]
    for merged, old in [("/usr/bin/", "/bin/"), ("/usr/sbin/", "/sbin/")]:
        if resolved.startswith(merged):
            alias = old + resolved[len(merged):]
            if Path(alias).exists() and os.path.samefile(alias, resolved):
                candidates.append(alias)
    ownership = []
    for candidate in candidates:
        output = command(["dpkg-query", "--search", candidate], records, missing_ok=True).strip()
        ownership.append(dict(path=candidate, status=records[-1]["exitCode"], result=output))
    # On merged-/usr hosts the database can retain an equivalent /bin path.
    # A successful search identifies an owner, which can differ from --package.
    return dict(schemaVersion=1, capturedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                platform=platform.system(), uid=os.geteuid(), package=metadata,
                files=listed, executable=dict(requested=executable, resolved=resolved,
                                            ownershipQueries=ownership,
                                            tracked=any(row["status"] == 0 for row in ownership)),
                commands=records, hostPackageDatabaseModified=False,
                learnerWorksheetCompletionInferred=False,
                provenanceLimit="Installed metadata and path ownership do not prove repository origin or authenticity.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", default="bash")
    parser.add_argument("--command", default="bash")
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    if platform.system() != "Linux" or os.geteuid() == 0:
        parser.error("use an ordinary account in a Debian/Ubuntu Linux lab")
    if not shutil.which("dpkg-query"):
        parser.error("dpkg-query is required; use the documented RPM-family investigation separately")
    if not re.fullmatch(r"[a-z0-9][a-z0-9+.-]+(?::[a-z0-9][a-z0-9-]*)?", args.package):
        parser.error("supply one literal package name, optionally with :architecture")
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.+-]*", args.command):
        parser.error("supply one literal executable name")
    def interrupted(_number, _frame):
        raise InterruptedError("collection interrupted; owned query stopped")
    signal.signal(signal.SIGTERM, interrupted)
    try:
        report = collect(args.package, args.command)
        payload = (json.dumps(report, indent=2) + "\n").encode()
        descriptor = os.open(args.report, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
    except (OSError, RuntimeError, UnicodeError) as error:
        print("No completed report: " + str(error), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("No completed report: collection interrupted", file=sys.stderr)
        return 130
    print(f"Collected installed metadata, {len(report['files'])} paths and executable ownership in {args.report}")
    print("Complete the prediction, comparison and change-plan tasks in package-notes.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
