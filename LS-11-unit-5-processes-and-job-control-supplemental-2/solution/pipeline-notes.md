# Reference reasoning for pipeline-evidence

The actual PIDs, UID, process-state samples, raw files and terminal transcript
come from the run. These explanations do not replace that evidence.

- Producer stdout is the consumer's stdin; diagnostics are on separate stderr
  streams. Received records link the two actual identities and sequence numbers.
- One job contains two distinct PIDs in a common process group. With this
  interactive Bash setup the producer leads the group. $! is the last process,
  while jobs -p reports the group leader. A jobspec is local to that shell.
- A group STOP leaves both identities in T state. bg resumes both, snapshots
  preserve their identity, and data sequence numbers advance. fg gives the
  group the terminal; Ctrl+C reaches it and this equipment exits 130.
- Producer count completion with requested 7 and consumer EOF with 0 produce
  component statuses 7 0. Default Bash reports 0; pipefail reports 7. EOF alone
  cannot establish upstream success. Capture the statuses immediately.
- A consumer that intentionally takes one item returns 0. The producer's next
  write encounters its closed reader and the restored SIGPIPE disposition
  terminates it. Bash reports 141 0, with overall 0 or 141 according to pipefail.
- Signaling only $! targets the consumer rather than every group member.
  Group-wide control and pipeline result aggregation are different concepts.
- A complete record retains raw output, changed cases, a diagnosed mismatch,
  every status and confirmation that both owned processes and temporary files
  were cleaned. Reference reasoning alone is not observation completion.
