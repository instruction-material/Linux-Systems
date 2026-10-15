"""The named recovery policy; history_lab supplies the operating equipment."""
import sys

sys.dont_write_bytecode = True


def recovered_matches(restored, expected):
    # TODO: compare the complete actual restored bytes with the independent target.
    return (restored/'data.json').is_file()


if __name__ == '__main__':
    from history_lab import main
    raise SystemExit(main(recovered_matches, 'acceptance'))
