"""The named recovery policy; history_lab supplies the operating equipment."""
import sys

sys.dont_write_bytecode = True


def recovered_matches(restored, expected):
    import hashlib

    import backup
    if set(expected) != set(backup.REQUIRED):
        return False
    try:
        if {path.name for path in restored.iterdir()} != set(expected):
            return False
        return all(not (restored/name).is_symlink() and (restored/name).is_file()
                   and hashlib.sha256((restored/name).read_bytes()).hexdigest() == digest
                   for name, digest in expected.items())
    except OSError:
        return False


if __name__ == '__main__':
    from history_lab import main
    raise SystemExit(main(recovered_matches, 'acceptance'))
