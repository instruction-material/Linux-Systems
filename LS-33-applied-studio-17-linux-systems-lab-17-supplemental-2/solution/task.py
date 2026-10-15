"""The named recovery policy; history_lab supplies the operating equipment."""
import sys

sys.dont_write_bytecode = True


def choose_backup(candidates, cutoff_ns):
    import tarfile

    import backup
    eligible = []
    for path in candidates:
        if not path.name.endswith('.tar.gz'):
            continue
        try:
            _, manifest = backup.validate(path)
        except (OSError, ValueError, KeyError, TypeError, tarfile.TarError):
            continue
        if manifest['createdNs'] <= cutoff_ns:
            eligible.append((manifest['createdNs'], path.name, path))
    return max(eligible, key=lambda item: item[:2])[2] if eligible else None


if __name__ == '__main__':
    from history_lab import main
    raise SystemExit(main(choose_backup, 'selection'))
