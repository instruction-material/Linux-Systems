"""Record an actual timer activation in the private course workspace."""
import json
import os
import sys
import time
from pathlib import Path

path = Path(sys.argv[1])
duration = float(sys.argv[2])
pid = os.getpid()
with path.open('a', encoding='utf-8') as out:
    out.write(json.dumps({'event': 'start', 'pid': pid, 'uid': os.getuid(), 'monotonic': time.monotonic()})+'\n')
time.sleep(duration)
with path.open('a', encoding='utf-8') as out:
    out.write(json.dumps({'event': 'end', 'pid': pid, 'uid': os.getuid(), 'monotonic': time.monotonic()})+'\n')
