import sys

from backup_studio import run


def choose_retirements(records, protected, cutoff_ns):
    # TODO: use verified publication time and preserve the protected anchors.
    return sorted(row["path"] for row in records if row["mtimeNs"] < cutoff_ns)


if __name__ == "__main__":
    try:
        raise SystemExit(run('retention', choose_retirements))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
