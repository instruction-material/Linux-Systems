"""Owned, regular-file backup equipment for the three storage investigations."""
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import stat
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path, PurePosixPath

TASK = os.environ.get("CLASSES_FAMILY_TASK_ID", "linux-storage-lab")
NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,39}\Z")


def guard():
    if platform.system() != "Linux" or os.geteuid() == 0:
        raise ValueError("Use an ordinary account in the owned Linux lab")
    if not all(shutil.which(name) for name in ("tar", "df", "du", "sha256sum")):
        raise RuntimeError("GNU tar, df, du and sha256sum must already be available")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def name(value):
    if not NAME.fullmatch(value):
        raise ValueError("Use a lowercase name of at most 40 letters, digits or hyphens")
    return value


def private_json(path, value):
    data = (json.dumps(value, indent=2) + "\n").encode()
    descriptor, temporary = tempfile.mkstemp(prefix=".record-", dir=path.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_lab(value, kind):
    path = Path(value)
    if not path.is_absolute() or path.is_symlink() or path.resolve() != path:
        raise ValueError("Use the exact absolute owned lab path printed by init")
    if path.stat().st_uid != os.geteuid() or not path.is_dir():
        raise ValueError("The lab must be a directory owned by this account")
    for file in [path, *path.rglob("*")]:
        info = file.lstat()
        if info.st_uid != os.geteuid() or not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
            raise ValueError("Lab entries must be owned regular files or directories")
    marker = json.loads((path / ".owned-storage-lab.json").read_text())
    if marker != {"format": 1, "kind": kind, "uid": os.geteuid()}:
        raise ValueError("The owned lab marker does not match this investigation")
    return path


def initialize(value, kind):
    path = Path(value)
    if not path.is_absolute() or path.parent.resolve() != path.parent or path.parent.stat().st_uid != os.geteuid():
        raise ValueError("Create a private parent with mktemp -d and use its absolute child path")
    path.mkdir(mode=0o700)
    private_json(path / ".owned-storage-lab.json", {"format": 1, "kind": kind, "uid": os.geteuid()})
    for relative in ["data", "data/nested", "data/empty", "data/cache", "backups", "restores", "reports"]:
        (path / relative).mkdir(mode=0o750)
        (path / relative).chmod(0o750)
    for relative, content, mode in [
        ("report.txt", b"version one\n", 0o640),
        ("nested/a file.txt", "a path with spaces; café\n".encode(), 0o600),
        ("binary.bin", bytes(range(256)), 0o600),
        ("cache/session.tmp", b"transient; explicitly excluded\n", 0o600),
    ]:
        file = path / "data" / relative
        file.write_bytes(content)
        file.chmod(mode)
    with (path / "data/sparse.bin").open("xb") as stream:
        stream.truncate(1024 * 1024)
    (path / "data/sparse.bin").chmod(0o600)
    return {"lab": str(path), "kind": kind, "source": str(path / "data"), "excludes": ["cache"], "worksheetComplete": False}


def snapshot(root):
    result = {}
    for file in [root, *sorted(root.rglob("*"))]:
        relative = file.relative_to(root).as_posix()
        if relative == "cache" or relative.startswith("cache/"):
            continue
        info = file.lstat()
        if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
            raise ValueError("Only regular files and directories belong in this backup")
        value = {"type": "directory" if file.is_dir() else "file", "mode": stat.S_IMODE(info.st_mode), "uid": info.st_uid}
        if value["type"] == "file":
            value.update(size=info.st_size, sha256=digest(file))
        result[relative] = value
    return result


def run(argv, lab):
    environment = dict(os.environ, LC_ALL="C", PYTHONDONTWRITEBYTECODE="1")
    # GNU tar also accepts options from this variable. The experiment's explicit
    # flags and owned paths remain the complete command being observed.
    environment.pop("TAR_OPTIONS", None)
    child = subprocess.Popen(argv, cwd=lab, env=environment, stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    record = {"parentTaskId": TASK, "parentPid": os.getpid(), "cwd": str(lab), "command": argv,
              "pid": child.pid, "startTime": time.time(), "timeoutSeconds": 20}
    cleanup = "owned query exited and reaped"
    output = error = b""
    try:
        output, error = child.communicate(timeout=20)
    except BaseException:
        cleanup = "owned command group terminated after interruption or timeout"
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
        try:
            output, error = child.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            output, error = child.communicate()
        raise
    finally:
        record.update(endTime=time.time(), exitCode=child.returncode, stdout=output.decode(errors="replace"),
                      stderr=error.decode(errors="replace"), childProcessGroupCleanup=cleanup)
        descriptor = os.open(lab / "operations.jsonl", os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(descriptor, "a") as stream:
            stream.write(json.dumps(record) + "\n")
    if child.returncode:
        raise RuntimeError("Native command failed: " + json.dumps(record))
    return record


def observe(lab, report):
    report = name(report) + ".json"
    root = lab / "data"
    commands = [
        ["df", "--block-size=1", "--output=source,fstype,size,used,avail,pcent,target", "--", str(root)],
        ["df", "--output=source,itotal,iused,iavail,ipcent,target", "--", str(root)],
        ["du", "--block-size=1", "--summarize", "--", str(root)],
        ["du", "--apparent-size", "--block-size=1", "--summarize", "--", str(root)],
    ]
    value = {"platform": platform.system(), "uid": os.geteuid(), "source": str(root),
             "commands": [run(argv, lab) for argv in commands], "backupInventory": snapshot(root),
             "sparseFile": {"size": (root / "sparse.bin").stat().st_size,
                            "allocatedBytes": (root / "sparse.bin").stat().st_blocks * 512},
             "worksheetComplete": False}
    private_json(lab / "reports" / report, value)
    return value


def backups(lab):
    values = []
    for directory in sorted((lab / "backups").iterdir()):
        if directory.name.startswith(".pending-"):
            raise RuntimeError("An incomplete backup staging directory needs investigation")
        name(directory.name)
        if not directory.is_dir() or {file.name for file in directory.iterdir()} != {"archive.tar", "manifest.json"}:
            raise ValueError("Unexpected backup directory contents")
        manifest = json.loads((directory / "manifest.json").read_text())
        if manifest["name"] != directory.name or not isinstance(manifest["sequence"], int) or manifest["sequence"] < 1:
            raise ValueError("Invalid backup identity")
        values.append((directory, manifest))
    if len({value["sequence"] for _, value in values}) != len(values):
        raise ValueError("Duplicate backup sequence")
    return sorted(values, key=lambda row: row[1]["sequence"])


def archive_check(lab, backup_name):
    directory = lab / "backups" / name(backup_name)
    manifest = next(value for path, value in backups(lab) if path == directory)
    return validate_archive(lab, directory, manifest)


def validate_archive(lab, directory, manifest):
    archive = directory / "archive.tar"
    actual = digest(archive)
    if actual != manifest["archiveSha256"]:
        raise RuntimeError("Archive SHA-256 differs from the retained manifest; restore refused")
    checksum = run(["sha256sum", "--", str(archive)], lab)
    if checksum["stdout"].split()[0] != actual:
        raise RuntimeError("Independent archive checksum disagrees")
    seen = {}
    with tarfile.open(archive, "r:") as source:
        for member in source:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or not (member.isdir() or member.isfile()):
                raise ValueError("Archive contains an unsupported path or entry type")
            relative = path.as_posix()
            if relative in seen or relative not in manifest["inventory"]:
                raise ValueError("Archive member set differs from the retained inventory")
            expected = manifest["inventory"][relative]
            value = {"type": "directory" if member.isdir() else "file", "mode": member.mode, "uid": manifest["uid"]}
            if member.mode & 0o7000:
                raise ValueError("Special permission bits are outside this lab")
            if member.isfile():
                stream = source.extractfile(member)
                value.update(size=member.size, sha256=hashlib.file_digest(stream, "sha256").hexdigest())
            if value != expected:
                raise RuntimeError("Archive content or mode differs from the retained inventory")
            seen[relative] = value
    if seen != manifest["inventory"]:
        raise RuntimeError("Archive omits declared files or directories")
    return directory, manifest


def backup(lab, backup_name, reserve):
    backup_name = name(backup_name)
    if reserve < 0:
        raise ValueError("Reserve bytes must be nonnegative")
    entries = backups(lab)
    destination = lab / "backups" / backup_name
    if destination.exists():
        raise FileExistsError("An earlier backup name is preserved")
    before = snapshot(lab / "data")
    needed = sum(row.get("size", 0) for row in before.values()) + 1024 * 1024 + reserve
    filesystem = os.statvfs(lab / "backups")
    available = filesystem.f_bavail * filesystem.f_frsize
    if available < needed:
        raise RuntimeError(f"Available {available} bytes is below the requested {needed}; no archive published")
    temporary = Path(tempfile.mkdtemp(prefix=".pending-", dir=lab / "backups"))
    try:
        archive = temporary / "archive.tar"
        archive.touch(mode=0o600)
        run(["tar", "--create", "--format=posix", "--file", str(archive), "--exclude=./cache",
             "--directory", str(lab / "data"), "."], lab)
        if snapshot(lab / "data") != before:
            raise RuntimeError("Source changed during archive creation; candidate discarded")
        sequence = max((row["sequence"] for _, row in entries), default=0) + 1
        manifest = {"format": 1, "name": backup_name, "sequence": sequence, "uid": os.geteuid(),
                    "createdAt": time.time(), "source": str(lab / "data"), "excludes": ["cache"],
                    "inventory": before, "archiveSha256": digest(archive), "availableBytesAtCheck": available,
                    "reservedBytes": reserve, "estimatedNeededBytes": needed}
        private_json(temporary / "manifest.json", manifest)
        validate_archive(lab, temporary, manifest)
        # The owned directory is private and its destination was checked above.
        # A second creator for this name fails against the nonempty directory.
        temporary.rename(destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return manifest


def restore(lab, backup_name, destination):
    target = lab / "restores" / name(destination)
    if target.exists():
        raise FileExistsError("Restore needs a new destination")
    directory, manifest = archive_check(lab, backup_name)
    before = snapshot(lab / "data")
    target.mkdir(mode=0o700)
    try:
        run(["tar", "--extract", "--file", str(directory / "archive.tar"), "--directory", str(target),
             "--no-same-owner", "--same-permissions"], lab)
        if snapshot(target) != manifest["inventory"]:
            raise RuntimeError("Restored bytes, paths or permissions do not match")
    except BaseException:
        shutil.rmtree(target)
        raise
    if snapshot(lab / "data") != before:
        raise RuntimeError("Source changed during the separate restore")
    return {"backup": backup_name, "destination": str(target), "inventoryExact": True,
            "sourceUnchanged": True, "uid": os.geteuid(), "worksheetComplete": False}


def retention_state(lab):
    result = []
    for directory, _ in backups(lab):
        _, manifest = archive_check(lab, directory.name)
        result.append({"name": directory.name, "sequence": manifest["sequence"],
                       "archiveSha256": digest(directory / "archive.tar"),
                       "manifestSha256": digest(directory / "manifest.json")})
    return result


def retention_plan(lab, keep, report):
    if keep < 1:
        raise ValueError("Retain at least one backup")
    state = retention_state(lab)
    if not state:
        raise ValueError("No verified backups are available")
    result = {"format": 1, "lab": str(lab), "keep": keep, "state": state,
              "remove": [row["name"] for row in state[:-keep]],
              "retain": [row["name"] for row in state[-keep:]], "planningDeletesNothing": True}
    private_json(lab / "reports" / (name(report) + ".json"), result)
    return result


def apply_retention(lab, report):
    plan = json.loads((lab / "reports" / (name(report) + ".json")).read_text())
    state = retention_state(lab)
    keep = plan["keep"]
    if not isinstance(keep, int) or keep < 1 or plan["lab"] != str(lab) or plan["state"] != state:
        raise ValueError("The retention plan is stale or invalid; nothing removed")
    if plan["remove"] != [row["name"] for row in state[:-keep]] or plan["retain"] != [row["name"] for row in state[-keep:]]:
        raise ValueError("The planned selection is invalid; nothing removed")
    for backup_name in plan["remove"]:
        directory = lab / "backups" / name(backup_name)
        (directory / "archive.tar").unlink()
        (directory / "manifest.json").unlink()
        directory.rmdir()
    return {"removed": plan["remove"], "retained": retention_state(lab), "worksheetComplete": False}
