"""Observe only freshly created, owned temporary permission examples."""
import argparse
import errno
import hashlib
import json
import os
import stat
import sys
import tempfile
from pathlib import Path


def workspace(value):
    path = Path(value)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or path.is_symlink():
        raise ValueError("Use an existing nonsymlink directory.")
    if info.st_uid != os.getuid() or any(path.iterdir()):
        raise ValueError("Use an empty directory owned by the active account.")
    return path.resolve()


def environment():
    if sys.platform != "linux" or os.getuid() == 0:
        raise ValueError("Use an ordinary Linux account; root bypasses these access checks.")


def require_plain_acl(path):
    if "system.posix_acl_default" in os.listxattr(path):
        raise ValueError("This mode-bit lab requires a directory without an inherited default ACL.")


def restore_owned_tree(path):
    # Restore only the generated tree so cleanup can remove its private entries.
    for root, dirs, _files in os.walk(path, topdown=True):
        os.chmod(root, 0o700)
        for name in dirs:
            os.chmod(Path(root) / name, 0o700)


def octal(mode):
    return format(mode, "04o")


def mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def failure(error, code):
    print(json.dumps({"error": str(error), "observationsCompleted": False}), file=sys.stderr)
    return code


def predicted_unlink(directory_mode, file_mode):
    return bool(file_mode & 0o200) # TODO: use owner write and search on the containing directory.


def attempt(action):
    try:
        value = action()
        return {"succeeded": True, "errno": None, "value": value}
    except PermissionError as error:
        if error.errno != errno.EACCES:
            raise
        return {"succeeded": False, "errno": error.errno, "value": None}


def observe(parent):
    results = []
    with tempfile.TemporaryDirectory(prefix="permission-observation-", dir=parent) as directory:
        lab = Path(directory)
        lab.chmod(0o700)
        require_plain_acl(lab)
        try:
            for name, directory_mode, file_mode in [
                ("read-only file, writable parent", 0o700, 0o400),
                ("writable file, read/search parent", 0o500, 0o600),
                ("read-only file, write/search parent", 0o300, 0o400),
            ]:
                folder = lab / str(len(results))
                folder.mkdir(mode=0o700)
                folder.chmod(0o700)
                target = folder / "document.txt"
                original = b"owned example\n"
                target.write_bytes(original)
                target.chmod(file_mode)
                folder.chmod(directory_mode)
                try:
                    actual_directory_mode = mode(folder)
                    actual_file_mode = mode(target)
                    def append(path=target):
                        with path.open("ab") as stream:
                            return stream.write(b"probe\n")
                    written = attempt(append)
                    after_write = target.read_bytes()
                    listed = attempt(lambda folder=folder: sorted(os.listdir(folder)))
                    removed = attempt(lambda target=target: target.unlink())
                    results.append({
                        "case": name,
                        "directoryMode": octal(actual_directory_mode),
                        "fileMode": octal(actual_file_mode),
                        "beforeSha256": hashlib.sha256(original).hexdigest(),
                        "afterWriteSha256": hashlib.sha256(after_write).hexdigest(),
                        "writeAttempt": written,
                        "listAttempt": listed,
                        "unlinkAttempt": removed,
                        "nameExistsAfterUnlink": target.exists(),
                        "predictedCanUnlink": predicted_unlink(actual_directory_mode, actual_file_mode),
                    })
                finally:
                    folder.chmod(0o700)
        finally:
            restore_owned_tree(lab)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace")
    args = parser.parse_args()
    try:
        environment()
        parent = workspace(args.workspace)
        observations = observe(parent)
        matched = all(row["predictedCanUnlink"] == row["unlinkAttempt"]["succeeded"] for row in observations)
        print(json.dumps({
            "uid": os.getuid(), "workspace": str(parent),
            "observationsCompleted": True, "observations": observations,
            "allPredictionsMatch": matched, "temporaryCasesRemoved": True,
            "learnerWorksheetCompletionInferred": False,
        }, indent=2))
        return 0 if matched else 1
    except (ValueError, OSError) as error:
        return failure(error, 2)
    except KeyboardInterrupt:
        return failure("Interrupted", 130)


if __name__ == "__main__":
    raise SystemExit(main())
