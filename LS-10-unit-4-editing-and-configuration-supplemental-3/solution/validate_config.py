#!/usr/bin/env python3
"""Validate this lab's literal key/value format without executing its text."""

import argparse
import json
import re
import sys
from pathlib import Path


def load(path):
    values = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        text = line.split("#", 1)[0].strip()
        if not text:
            continue
        if "=" not in text:
            raise ValueError(f"line {number}: expected key = value")
        key, value = (item.strip() for item in text.split("=", 1))
        if key not in {"name", "note", "timeout"} or key in values:
            raise ValueError(f"line {number}: unknown or duplicate key {key}")
        values[key] = value
    if set(values) != {"name", "note", "timeout"}:
        raise ValueError("exactly one name, note and timeout setting is required")
    if re.fullmatch(r"(?:[1-9]|[1-5][0-9]|60)", values["timeout"]) is None:
        raise ValueError(
            "timeout must be an integer from 1 through 60 without leading zeros"
        )
    if any(not 1 <= len(values[key]) <= 80 for key in ("name", "note")):
        raise ValueError("name and note require 1 through 80 characters")
    values["timeout"] = int(values["timeout"])
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("configuration", type=Path)
    parser.add_argument("--expect-timeout", type=int)
    args = parser.parse_args()
    try:
        value = load(args.configuration)
        if args.expect_timeout is not None and value["timeout"] != args.expect_timeout:
            raise ValueError("prepared timeout does not match the requested value")
    except (OSError, ValueError) as error:
        print("invalid configuration: " + str(error), file=sys.stderr)
        return 2
    print(json.dumps(value))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
