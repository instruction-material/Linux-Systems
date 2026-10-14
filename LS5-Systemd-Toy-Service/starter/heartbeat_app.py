"""Print a validated heartbeat for direct or systemd user-service execution."""
import os
import re
import sys
import time
from decimal import Decimal, InvalidOperation


def settings():
    raw_interval = os.environ.get("HEARTBEAT_INTERVAL", "5")
    if not re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", raw_interval):
        raise ValueError("HEARTBEAT_INTERVAL must be a decimal from 0.1 through 60")
    try:
        interval = Decimal(raw_interval)
    except InvalidOperation as error:
        raise ValueError("HEARTBEAT_INTERVAL is invalid") from error
    if not interval.is_finite() or not Decimal("0.1") <= interval <= Decimal(60):
        raise ValueError("HEARTBEAT_INTERVAL must be a decimal from 0.1 through 60")
    message = os.environ.get("HEARTBEAT_MESSAGE", "linux-heartbeat")
    if not message or len(message.encode("utf-8")) > 128 or any(c in message for c in "\r\n\0"):
        raise ValueError("HEARTBEAT_MESSAGE must be one nonempty UTF-8 line of at most 128 bytes")
    raw_limit = os.environ.get("HEARTBEAT_LIMIT", "0")
    if not re.fullmatch(r"0|[1-9][0-9]{0,3}", raw_limit):
        raise ValueError("HEARTBEAT_LIMIT must be 0 for continuous operation or 1 through 9999")
    return float(interval), message, int(raw_limit)


def render_heartbeat(message, number):
    # TODO render_heartbeat: return the named message, colon, heartbeat and number.
    return None


def main():
    try:
        interval, message, limit = settings()
    except ValueError as error:
        print(str(error), file=sys.stderr, flush=True)
        return 2
    number = 1
    while True:
        line = render_heartbeat(message, number)
        if line is None:
            print("unfinished render_heartbeat task", file=sys.stderr, flush=True)
            return 78
        print(line, flush=True)
        if limit and number >= limit:
            return 0
        number += 1
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
