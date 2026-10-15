import sys

from backup_studio import run


def restore_attributes(directory, expected):
    import os

    for name, attributes in expected.items():
        path = directory / name
        os.chmod(path, attributes["mode"])
        os.utime(path, ns=(path.stat().st_atime_ns, attributes["mtimeNs"]))


if __name__ == "__main__":
    try:
        raise SystemExit(run('attributes', restore_attributes))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
