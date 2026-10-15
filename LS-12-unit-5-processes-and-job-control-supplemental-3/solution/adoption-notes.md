# Reference reasoning for adoption-evidence

Use the run's actual PIDs, UID, ps output, raw records and timing. These are
relationships to explain, not invented local observations to copy.

- The observer explicitly enables and reads its own child-subreaper flag. That
  per-process setting does not change the host's init process or global policy.
- The first child exits 7 and remains a real Z until its parent waits. It has
  already stopped executing. The later wait retrieves 7 and releases its state;
  an additional kill cannot perform the parent's reaping operation.
- A readiness pipe keeps the original parent alive until its child's initial
  identity and parent have been observed. Releasing that parent and waiting for
  its 0 establishes a real transition rather than an assumed chronology.
- The grandchild keeps its PID, birth time and UID but acquires the observer's
  PPID because that living ancestor is explicitly a subreaper. The new parent
  is measured; it is not assumed to be 1. This is a live adopted process,
  distinct from the earlier already-exited zombie.
- A second release lets the adopted child exit 9. The observer can now wait for
  it. Internal 7/0/9 results are successful observations of the experiment;
  normal overall program status is 0, with no remaining owned children.
- Ctrl+C during the first window is a separate interrupted case. The observer
  records interruption and cleans/reaps its children. That does not prove the
  second adoption stage occurred. Retain the explicit record file and program
  status, and keep a complete normal run separately.
- Complete evidence includes changed timing, rejected arguments, interruption,
  final process/descriptor cleanup, an actual mismatch and its correction.
  Neither the reference notes nor program success alone completes that record.
