#!/usr/bin/env python3
"""A disposable process that retains configuration until an explicit reload."""

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key: " + key)
        result[key] = value
    return result


def load_config(path):
    value = json.loads(
        Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique_object
    )
    if not isinstance(value, dict) or set(value) != {"message", "repeat"}:
        raise ValueError("use exactly the message and repeat keys")
    message, repeat = value["message"], value["repeat"]
    if (
        not isinstance(message, str)
        or not 1 <= len(message) <= 80
        or "\n" in message
        or "\r" in message
    ):
        raise ValueError("message must be one line with 1 through 80 characters")
    if type(repeat) is not int or not 1 <= repeat <= 5:
        raise ValueError("repeat must be an integer from 1 through 5")
    return value


def run(path):
    current = load_config(path)
    flags = {"reload": False, "snapshot": False, "stop": False}

    def request_reload(_number, _frame):
        flags["reload"] = True

    def request_snapshot(_number, _frame):
        flags["snapshot"] = True

    def request_stop(_number, _frame):
        flags["stop"] = True

    signal.signal(signal.SIGHUP, request_reload)
    signal.signal(signal.SIGUSR1, request_snapshot)
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    def report(event, **extra):
        print(
            json.dumps(
                {
                    "event": event,
                    "pid": os.getpid(),
                    **current,
                    "rendered": " ".join([current["message"]] * current["repeat"]),
                    **extra,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    report("started")
    while not flags["stop"]:
        if flags["reload"]:
            flags["reload"] = False
            try:
                replacement = load_config(path)
            except (OSError, ValueError) as error:
                report("reload-rejected", reason=str(error))
            else:
                current = replacement
                report("reloaded")
        if flags["snapshot"]:
            flags["snapshot"] = False
            report("snapshot")
        time.sleep(0.02)
    report("stopped")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("validate", "run"))
    parser.add_argument("configuration", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "validate":
            load_config(args.configuration)
            print("configuration valid")
        else:
            run(args.configuration)
    except (OSError, ValueError) as error:
        print("invalid configuration: " + str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
