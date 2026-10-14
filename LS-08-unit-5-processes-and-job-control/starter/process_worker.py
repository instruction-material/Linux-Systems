"""Disposable process equipment for observing real signals and shell jobs."""
import argparse
import json
import math
import os
import signal
import time


def lifetime(value):
    try:
        seconds = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("lifetime must be a number") from error
    if not math.isfinite(seconds) or not 0.2 <= seconds <= 1800:
        raise argparse.ArgumentTypeError("lifetime must be from 0.2 through 1800 seconds")
    return seconds


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--lifetime", type=lifetime, default=600)
parser.add_argument("--ignore-term", action="store_true")
args = parser.parse_args()
pending = []


def receive(number, _frame):
    # Do output in the main loop, not inside a possibly interrupted print call.
    pending.append(number)


for number in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP,
               signal.SIGUSR1, signal.SIGCONT):
    signal.signal(number, receive)
signal.signal(signal.SIGTSTP, signal.SIG_DFL)
started = time.monotonic()


def emit(event, **extra):
    row = {"event": event, "pid": os.getpid(), "ppid": os.getppid(),
           "uid": os.getuid(), "pgid": os.getpgrp(), "sid": os.getsid(0),
           "elapsed": round(time.monotonic() - started, 4)}
    row.update(extra)
    print(json.dumps(row, separators=(",", ":")), flush=True)


emit("started", ignoreTerm=args.ignore_term, lifetime=args.lifetime)
finished = False
status = 0
while not finished:
    while pending:
        number = pending.pop(0)
        name = signal.Signals(number).name
        if number == signal.SIGUSR1:
            emit("snapshot", signal=name)
        elif number == signal.SIGCONT:
            emit("continued", signal=name)
        elif number == signal.SIGTERM and args.ignore_term:
            emit("ignored", signal=name)
        else:
            status = 0 if number == signal.SIGTERM else 128 + number
            emit("stopped", signal=name, status=status)
            finished = True
            break
    if not finished and time.monotonic() - started >= args.lifetime:
        emit("stopped", signal="deadline", status=0)
        finished = True
    if not finished:
        time.sleep(0.05)
raise SystemExit(status)
