"""The named recovery policy; history_lab supplies the operating equipment."""
import sys

sys.dont_write_bytecode = True


def choose_backup(candidates, cutoff_ns):
    # TODO: select an intact published snapshot meeting the recorded cutoff.
    return max(candidates, key=lambda path: path.stat().st_mtime_ns) if candidates else None


if __name__ == '__main__':
    from history_lab import main
    raise SystemExit(main(choose_backup, 'selection'))
