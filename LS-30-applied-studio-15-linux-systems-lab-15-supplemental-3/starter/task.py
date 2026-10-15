"""The named policy; studio_observer supplies the operating equipment."""
import sys

sys.dont_write_bytecode = True


def classify_progress(state, events, now_ns, budget_ns):
    # TODO: distinguish a completed run, failure and elapsed progress budget.
    return 'complete' if state.get('MainPID') == '0' else 'waiting'


if __name__ == '__main__':
    from studio_observer import main
    raise SystemExit(main(classify_progress, 'progress'))
