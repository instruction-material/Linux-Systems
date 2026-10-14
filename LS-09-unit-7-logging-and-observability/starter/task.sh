#!/usr/bin/env bash
set -euo pipefail
exec python3 - "$@" <<'PYTHON'
import json
import re
import sys
from pathlib import Path


def in_scope(row, unit, boot, begin, end):
    # SCOPE_TASK
    # TODO: require the requested unit, boot and inclusive time window.
    return None


def main():
    if len(sys.argv) != 6:
        raise ValueError("usage: bash task.sh INPUT.log UNIT BOOT_ID START_US END_US")
    path, unit, boot = sys.argv[1:4]
    begin, end = map(int, sys.argv[4:])
    if not re.fullmatch(r"[A-Za-z0-9_.@-]+\.service", unit):
        raise ValueError("a named user service is required")
    if not re.fullmatch(r"[0-9a-f]{32}", boot) or begin < 0 or end < begin:
        raise ValueError("use a boot ID and an ordered microsecond time window")
    probe = {"_SYSTEMD_USER_UNIT": unit, "_BOOT_ID": boot, "__REALTIME_TIMESTAMP": str(begin)}
    if in_scope(probe, unit, boot, begin, end) is None:
        print("Complete in_scope: unit, boot and inclusive time-window selection.", file=sys.stderr)
        return 78
    rows = []
    with Path(path).open(encoding="utf-8") as source:
        for number, line in enumerate(source, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"record {number} is not an object")
            stamp = row.get("__REALTIME_TIMESTAMP")
            if not isinstance(stamp, str) or not stamp.isdecimal():
                raise ValueError(f"record {number} needs a scalar journal timestamp")
            if in_scope(row, unit, boot, begin, end):
                message, priority = row.get("MESSAGE"), row.get("PRIORITY")
                if not isinstance(message, str) or not isinstance(priority, str) or priority not in "01234567" or len(priority) != 1:
                    raise ValueError(f"record {number} needs scalar MESSAGE and PRIORITY fields")
                rows.append(row)
    rows.sort(key=lambda row: int(row["__REALTIME_TIMESTAMP"]))
    errors = [row for row in rows if int(row["PRIORITY"]) <= 3]
    causes = [row for row in errors if row["MESSAGE"].startswith("case: event=config_")]
    first = causes[0] if causes else None
    latest = causes[-1] if causes else None
    recovery = next((row for row in rows if latest and row["MESSAGE"] == "case: event=ready" and int(row["__REALTIME_TIMESTAMP"]) > int(latest["__REALTIME_TIMESTAMP"]) and row.get("_SYSTEMD_INVOCATION_ID") and row.get("_SYSTEMD_INVOCATION_ID") != latest.get("_SYSTEMD_INVOCATION_ID")), None)
    print(json.dumps({"unit": unit, "boot": boot, "window": [begin, end], "eventCount": len(rows), "errors": len(errors), "firstError": first["MESSAGE"] if first else None, "firstErrorTime": first["__REALTIME_TIMESTAMP"] if first else None, "latestError": latest["MESSAGE"] if latest else None, "latestErrorTime": latest["__REALTIME_TIMESTAMP"] if latest else None, "recovered": recovery is not None, "recoveryTime": recovery["__REALTIME_TIMESTAMP"] if recovery else None}, sort_keys=True))
    return 0


try:
    sys.exit(main())
except (OSError, ValueError, KeyError) as error:
    print(f"Journal investigation failed: {error}", file=sys.stderr)
    sys.exit(2)
PYTHON
