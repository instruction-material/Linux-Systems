#!/usr/bin/env python3
"""Report only the two settings received in this process's environment."""

import argparse
import json
import os
import re
import signal
import sys
import time


def settings():
    message, repeat = os.environ.get("MESSAGE"), os.environ.get("REPEAT")
    if (
        message is None
        or not 1 <= len(message) <= 80
        or "\n" in message
        or "\r" in message
    ):
        raise ValueError("MESSAGE must be one line with 1 through 80 characters")
    if repeat is None or re.fullmatch("[1-5]", repeat) is None:
        raise ValueError("REPEAT must be a single integer from 1 through 5")
    return {
        "message": message,
        "repeat": int(repeat),
        "rendered": " ".join([message] * int(repeat)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", action="store_true")
    args = parser.parse_args()
    try:
        settings()
    except ValueError as error:
        print("invalid environment: " + str(error), file=sys.stderr)
        return 2
    flags = {"snapshot": False, "stop": False}

    def snapshot(_number, _frame):
        flags["snapshot"] = True

    def stop(_number, _frame):
        flags["stop"] = True

    def report(event):
        print(
            json.dumps(
                {"event": event, "pid": os.getpid(), "uid": os.getuid(), **settings()}
            ),
            flush=True,
        )

    if not args.watch:
        report("environment")
        return 0
    signal.signal(signal.SIGUSR1, snapshot)
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    report("started")
    while not flags["stop"]:
        if flags["snapshot"]:
            flags["snapshot"] = False
            report("snapshot")
        time.sleep(0.02)
    report("stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
