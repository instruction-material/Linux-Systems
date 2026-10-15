"""Observe only freshly created, owned temporary permission examples."""
import argparse
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


def predicted_file_mode(mask):
    return 0o666 & ~mask


def parse_mask(value):
    if len(value) not in (3, 4) or any(char not in "01234567" for char in value):
        raise ValueError("Use a three- or four-digit octal mask from 0000 through 0777.")
    mask = int(value, 8)
    if mask > 0o777:
        raise ValueError("Use only owner/group/other permission mask bits.")
    return mask


def observe(parent, mask):
    with tempfile.TemporaryDirectory(prefix="creation-observation-", dir=parent) as directory:
        lab = Path(directory)
        lab.chmod(0o700)
        require_plain_acl(lab)
        existing = lab / "existing.txt"
        original = b"existing data\n"
        existing.write_bytes(original)
        existing.chmod(0o640)
        before = mode(existing)
        inherited = os.umask(mask)
        try:
            created_file = lab / "new.txt"
            created_directory = lab / "new-directory"
            descriptor = os.open(created_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
            os.close(descriptor)
            created_directory.mkdir(mode=0o777)
            actual_file = mode(created_file)
            actual_directory = mode(created_directory)
            after = mode(existing)
            existing_hash = hashlib.sha256(existing.read_bytes()).hexdigest()
        finally:
            os.umask(inherited)
            restore_owned_tree(lab)
        restored = os.umask(inherited)
    prediction = predicted_file_mode(mask)
    return {
        "requestedFileMode": "0666", "requestedDirectoryMode": "0777",
        "mask": octal(mask), "actualFileMode": octal(actual_file),
        "actualDirectoryMode": octal(actual_directory),
        "predictedFileMode": octal(prediction),
        "fileHasExecutableBits": bool(actual_file & 0o111),
        "existingModeBefore": octal(before), "existingModeAfter": octal(after),
        "existingSha256": existing_hash,
        "existingBytesUnchanged": existing_hash == hashlib.sha256(original).hexdigest(),
        "inheritedUmask": octal(inherited), "restoredUmask": octal(restored),
        "allPredictionsMatch": prediction == actual_file,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace")
    parser.add_argument("mask")
    args = parser.parse_args()
    try:
        environment()
        parent = workspace(args.workspace)
        result = observe(parent, parse_mask(args.mask))
        print(json.dumps({
            "uid": os.getuid(), "workspace": str(parent),
            "observationsCompleted": True, "observation": result,
            "temporaryCasesRemoved": True,
            "learnerWorksheetCompletionInferred": False,
        }, indent=2))
        return 0 if result["allPredictionsMatch"] else 1
    except (ValueError, OSError) as error:
        return failure(error, 2)
    except KeyboardInterrupt:
        return failure("Interrupted", 130)


if __name__ == "__main__":
    raise SystemExit(main())
