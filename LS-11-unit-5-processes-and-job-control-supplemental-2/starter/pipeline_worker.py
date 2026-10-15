"""Two supplied workers for observing real Bash pipeline jobs."""
import argparse
import json
import math
import os
import select
import signal
import sys
import time


def seconds(value):
    try:
        result = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("lifetime must be a number") from error
    if not math.isfinite(result) or not 0.2 <= result <= 1800:
        raise argparse.ArgumentTypeError("lifetime must be from 0.2 through 1800")
    return result


def count(value):
    try:
        result = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("count must be an integer") from error
    if not 0 <= result <= 1000:
        raise argparse.ArgumentTypeError("count must be from 0 through 1000")
    return result


def exit_code(value):
    try:
        result = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("exit code must be an integer") from error
    if not 0 <= result <= 125:
        raise argparse.ArgumentTypeError("exit code must be from 0 through 125")
    return result


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("mode", choices=("produce", "consume"))
parser.add_argument("--lifetime", type=seconds, default=600)
parser.add_argument("--count", type=count, default=0)
parser.add_argument("--take", type=count, default=0)
parser.add_argument("--exit-code", type=exit_code, default=0)
args = parser.parse_args()
if args.mode == "produce" and args.take:
    parser.error("--take belongs to consume")
if args.mode == "consume" and (args.count or args.exit_code):
    parser.error("--count and --exit-code belong to produce")
if args.mode == "consume" and sys.stdin.isatty():
    parser.error("consume requires a pipe, not terminal input")
pending = []


def receive(number, _frame):
    pending.append(number)


for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP,
               signal.SIGUSR1, signal.SIGCONT):
    signal.signal(number, receive)
signal.signal(signal.SIGTSTP, signal.SIG_DFL)
if args.mode == "produce":
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
started = time.monotonic()


def row(event, **extra):
    return {"event": event, "mode": args.mode, "pid": os.getpid(),
            "ppid": os.getppid(), "uid": os.getuid(), "pgid": os.getpgrp(),
            "sid": os.getsid(0), "at": time.time(), **extra}


def diagnostic(event, **extra):
    print(json.dumps(row(event, **extra), separators=(",", ":")),
          file=sys.stderr, flush=True)


def signals():
    while pending:
        number = pending.pop(0)
        name = signal.Signals(number).name
        if number in (signal.SIGUSR1, signal.SIGCONT):
            diagnostic("snapshot" if number == signal.SIGUSR1 else "continued", signal=name)
        else:
            return (0 if number == signal.SIGTERM else 128 + number), name
    return None


diagnostic("started")
sequence = 0
buffer = b""
if args.mode == "consume":
    os.set_blocking(sys.stdin.fileno(), False)
status, reason = 0, "deadline"
while time.monotonic() - started < args.lifetime:
    requested = signals()
    if requested is not None:
        status, reason = requested
        break
    if args.mode == "produce":
        sequence += 1
        print(json.dumps(row("item", sequence=sequence), separators=(",", ":")), flush=True)
        if args.count and sequence >= args.count:
            status, reason = args.exit_code, "count"
            break
        time.sleep(0.1)
    else:
        ready, _, _ = select.select([sys.stdin.fileno()], [], [], 0.05)
        if not ready:
            continue
        chunk = os.read(sys.stdin.fileno(), 65536)
        if not chunk:
            requested = signals()
            if requested is not None:
                status, reason = requested
            elif buffer:
                status, reason = 2, "incomplete-record"
            else:
                reason = "eof"
            break
        buffer += chunk
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            try:
                item = json.loads(line)
                if (not isinstance(item, dict) or item.get("event") != "item"
                        or type(item.get("sequence")) is not int
                        or type(item.get("pid")) is not int):
                    raise ValueError("unexpected producer record")
            except (ValueError, UnicodeDecodeError):
                status, reason = 2, "invalid-record"
                break
            sequence += 1
            print(json.dumps(row("received", producerPid=item["pid"],
                                 sequence=item["sequence"]), separators=(",", ":")), flush=True)
            if args.take and sequence >= args.take:
                reason = "take"
                break
        if reason == "invalid-record" or (args.take and sequence >= args.take):
            break
diagnostic("stopped", signal=reason, status=status, records=sequence)
raise SystemExit(status)
