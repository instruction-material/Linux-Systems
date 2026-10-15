"""The named policy; studio_observer supplies the operating equipment."""
import sys

sys.dont_write_bytecode = True


def select_completed(rows, invocation):
    import json
    # TODO: scope completion events to the actual requested invocation.
    selected = []
    for row in rows:
        try:
            message = json.loads(row.get('MESSAGE', ''))
        except (ValueError, TypeError):
            continue
        if isinstance(message, dict) and message.get('event') == 'end':
            selected.append(row)
    return selected


if __name__ == '__main__':
    from studio_observer import main
    raise SystemExit(main(select_completed, 'correlation'))
