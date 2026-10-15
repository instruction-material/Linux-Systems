#!/usr/bin/env python3
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
config = json.loads((root / "config.json").read_text())
data = json.loads((root / "data.json").read_text())
if config["generation"] != data["generation"]:
    print("restored application-state mismatch", file=sys.stderr)
    raise SystemExit(2)
print("RECOVERED=" + str(data["generation"]))
