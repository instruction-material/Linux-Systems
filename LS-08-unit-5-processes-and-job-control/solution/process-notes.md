# Reference reasoning for the process-evidence record

This explains the expected relationships. Machine-specific PIDs, UID, paths,
timestamps, process-state samples and raw terminal records come from the actual
run. These explanations are not a substitute for those observations.

- A direct asynchronous Python child has the invoking Bash as PPID. `$!` is its
  PID; `$$` identifies that shell. The started record and ps must agree on the
  actual PID/owner/command. A job number is a shell-local handle, not a PID.
- A ready worker spends most of its time sleeping. USR1 creates a snapshot from
  the same live identity. Normal TERM creates a stopped record, exits 0 and lets
  wait retrieve 0. The ended child has no remaining ps row after reaping.
- --ignore-term records the request but does not exit. Confirming that same
  identity before KILL keeps the deliberate escalation tied to the owned task.
  KILL creates no program shutdown record. Bash wait reports 137; Python's
  subprocess returncode for the same signal termination is -9.
- A 0.5-second lifetime creates a deadline result and returns 0. Invalid nan
  fails argument validation with status 2 before any started event. Neither
  outcome proves handling of a requested signal.
- In a real interactive Bash, Ctrl+Z stops the foreground group. The worker
  remains the same process in T state. bg continues it and returns the terminal
  to the shell. Its continued/snapshot records retain the identity. fg gives
  its group the terminal; Ctrl+C reaches that foreground group. This worker's
  INT handler returns 130, so fg also returns 130 and the job is removed.
- A zombie has already exited but awaits parent bookkeeping. Stopping is a
  live state transition and reaping does not resume a stopped process. An
  orphan has a new parent determined by the actual environment. A Bash job
  table, a process table and a service manager answer different questions.
- A complete record includes a changed case, a diagnosed mismatch, the actual
  logs and terminal transcript, all statuses and confirmation that every owned
  process and disposable directory was cleaned. Opening these reference notes
  or running the supplied equipment alone does not complete that record.
