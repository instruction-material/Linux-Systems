import sys

from backup_studio import run


def choose_retirements(records, protected, cutoff_ns):
    return sorted(row["path"] for row in records
                  if row["verified"] and row["published"] and row["ordinary"]
                  and row["createdNs"] < cutoff_ns and row["path"] not in protected)


if __name__ == "__main__":
    try:
        raise SystemExit(run('retention', choose_retirements))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
