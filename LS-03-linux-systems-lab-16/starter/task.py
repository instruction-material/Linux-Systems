import sys

from backup_studio import run


def capture_under_lock(lock_path, capture):
    # TODO: hold a shared cooperating lock for the entire capture callback.
    return capture()


if __name__ == "__main__":
    try:
        raise SystemExit(run('coherence', capture_under_lock))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
