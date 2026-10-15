"""The named policy; studio_observer supplies the operating equipment."""
import sys

sys.dont_write_bytecode = True


def classify_progress(state, events, now_ns, budget_ns):
    if state.get('ActiveState') == 'failed' or state.get('Result') == 'exit-code':
        return 'failed'
    if (state.get('SubState') == 'exited' and state.get('ExecMainStatus') == '0'
            and any(row['event'] == 'end' for row in events)):
        return 'complete'
    starts = [row for row in events if row['event'] == 'start']
    if starts and now_ns - starts[0]['monotonicNs'] >= budget_ns:
        return 'overdue'
    return 'waiting'


if __name__ == '__main__':
    from studio_observer import main
    raise SystemExit(main(classify_progress, 'progress'))
