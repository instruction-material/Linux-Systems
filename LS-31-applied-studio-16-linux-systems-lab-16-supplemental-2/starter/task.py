import sys

from backup_studio import run


def restore_attributes(directory, expected):
    # TODO: restore each declared file's ordinary mode and observed mtime.
    return None


if __name__ == "__main__":
    try:
        raise SystemExit(run('attributes', restore_attributes))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
