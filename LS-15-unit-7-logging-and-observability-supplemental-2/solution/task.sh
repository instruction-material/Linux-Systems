#!/usr/bin/env bash
set -euo pipefail
exec python3 - "$@" <<'PYTHON'
import datetime
import json
import sys
from pathlib import Path


def is_server_failure(row):
    # RESPONSE_TASK
    return row["event"] == "complete" and 500 <= row["status"] <= 599


def main():
    if len(sys.argv) != 3 or not sys.argv[2]:
        raise ValueError("usage: bash task.sh APPLICATION.log REQUEST_ID")
    if is_server_failure({"event": "complete", "status": 503}) is None:
        print("Complete is_server_failure: use the completion event and numeric HTTP status.", file=sys.stderr)
        return 78
    entries = []
    with Path(sys.argv[1]).open(encoding="utf-8") as source:
        for number, line in enumerate(source, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict) or not all(isinstance(row.get(key), str) for key in ["time", "request", "event", "message"]):
                raise ValueError(f"record {number} needs time, request, event and message text")
            stamp = datetime.datetime.fromisoformat(row["time"].replace("Z", "+00:00"))
            if stamp.tzinfo is None or stamp.utcoffset() is None:
                raise ValueError(f"record {number} needs an explicit timezone")
            if row["event"] == "complete" and (type(row.get("status")) is not int or not 100 <= row["status"] <= 599):
                raise ValueError(f"record {number} needs a numeric HTTP status")
            if row["request"] == sys.argv[2]:
                entries.append((stamp, row))
    entries.sort(key=lambda item: item[0])
    failures = [(stamp, row) for stamp, row in entries if is_server_failure(row)]
    responses = [(stamp, row) for stamp, row in entries if row["event"] == "complete"]
    first = failures[0][0] if failures else None
    recovered = any(first is not None and stamp > first and row["status"] == 200 for stamp, row in responses)
    print(json.dumps({"request": sys.argv[2], "events": len(entries), "serverFailures": len(failures), "statuses": [row["status"] for _, row in responses], "lastStatus": responses[-1][1]["status"] if responses else None, "recovered": recovered}, sort_keys=True))
    return 0


try:
    sys.exit(main())
except (OSError, ValueError, KeyError) as error:
    print(f"Application investigation failed: {error}", file=sys.stderr)
    sys.exit(2)
PYTHON
