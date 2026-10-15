import sys

from backup_studio import run


def capture_under_lock(lock_path, capture):
    import fcntl

    with lock_path.open("rb") as stream:
        fcntl.flock(stream, fcntl.LOCK_SH)
        try:
            return capture()
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


if __name__ == "__main__":
    try:
        raise SystemExit(run('coherence', capture_under_lock))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
