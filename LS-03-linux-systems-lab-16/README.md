# Optional studio: Coherent Snapshots Under a Cooperating Writer


## Environment and scope

Use an owned Linux VM, WSL distribution or Linux terminal with Python 3.9 or
later, Bash, a readable /proc filesystem and an ordinary account. Check
`uname -s`, `id`, `python3 --version` and `bash --version`. No root account,
service manager, installed package, public host or network connection is used.
The selected role contains task.sh, task.py, backup_studio.py, backup.py,
app.py, config.json, data.json and backup-notes.md. Keep all eight files with
the root README when saving and exporting the project.

The supplied equipment performs actual local backup and restore operations.
Edit only the named policy in task.py. The unfinished starter deliberately
makes a wrong policy decision; a real emitted observation with exit 1 is its
expected initial result. A traceback, missing output or setup refusal is not
that expected result. The complete reference exits 0. Exit 2 means a refused
input or failed experiment. An observed interruption exits 130 after cleanup.
Running equipment does not complete the independent worksheet.

## Run, observe and retain evidence

Begin in the selected role directory and run commands individually:

~~~sh
lab=$(mktemp -d "${TMPDIR:-/tmp}/backup-studio.XXXXXX")
evidence=$(mktemp "${TMPDIR:-/tmp}/backup-evidence.XXXXXX")
bash task.sh "$lab" >"$evidence"
status=$?
printf 'STATUS=%s EVIDENCE=%s\n' "$status" "$evidence"
python3 -m json.tool "$evidence"
~~~

Keep the evidence file outside the empty lab parent: shell redirection opens
its output before the program starts, so redirecting inside the parent would
make that parent nonempty and correctly refuse the experiment. The JSON keeps
actual commands, PID/UID, statuses, file bytes encoded as Base64, digests,
observations and cleanup results. These are observations, not fabricated sample
identities. Source files remain unchanged. Every successful cleanup removes
only the exact private case and leaves the supplied parent empty.

After the first attempt, explain its mismatch in backup-notes.md, implement
the named policy, save it, and repeat with a new evidence file. Read the
reference after retaining an attempted explanation. Repeat with
`bash task.sh "$lab" --reverse --generation 7`, separating the option and its
value as `--generation 7`. Compare the changed observations with a prediction.
Each numbered investigation also supplies natural pauses for a guided reading.

For the interruption drill run `bash task.sh "$lab" --hold` in the foreground.
The private backup-studio-ready.json appears only after the documented real
phase has been reached. Press Ctrl-C during that pause. Keep the emitted JSON,
verify status 130 and the empty parent, then rerun without --hold to demonstrate
recovery. The pause is bounded to eight seconds if no signal arrives. Missing,
nonempty and symlink parents and generations outside 1..9999 are refused before
creating a private case. Preserve an independent file outside the parent and
compare it afterward. Finish with `rmdir -- "$lab"`; retain the evidence and
completed worksheet. Never substitute a production directory for the lab.

This optional studio does not add a required course milestone. The operations
capstone separately covers actual service identities, scheduling, a proxy and
its incident runbook. Its recovery companions separately select a recovery
point and compare restored content against an independently expected target.
This studio's evidence target is stated below.

## 1. Distinguish integrity from one coherent application state

The fictional application has a generation in both config.json and data.json.
Both must describe the same generation. A cooperating writer holds an actual
exclusive flock on one stable lock file while changing the two files. It
publishes its first-write observation and pauses before the second change.
The controller records the actual WRITE lock from /proc/locks and independently
tries a nonblocking shared lock, which must fail while that writer holds it.

An archive can contain a valid digest for every byte and still combine a new
configuration with older data. The unchanged capstone backup equipment checks
its archive contents against its manifest; it does not invent an application
transaction spanning independently changing files. Predict the two generation
values before reading the untouched starter's archive observation.

## 2. Complete capture_under_lock

The callback capture creates and validates the actual archive. Hold a shared
flock on the same existing lock file around the entire callback and return its
result. Use fcntl.LOCK_SH and release with LOCK_UN in a finally block. Keep the
file descriptor open while waiting and capturing. Opening and immediately
closing the lock, locking a different file, or unlocking before capture leaves
the multi-file read unprotected. Shared readers may coexist; the writer uses
LOCK_EX. These locks coordinate participating processes and do not prevent an
uncooperative program from writing files. This is not a filesystem snapshot or
a guarantee of consistency for an arbitrary database.

The equipment starts a real policy process. In the reference it observes a
pending READ lock for that PID while the writer still holds WRITE. In the
starter, capture finishes before the writer is released and the archive
contains mismatched generations. After the actual writer release, the
reference captures both new generations. Compare the actual lock rows,
attempt/start/release/completion times, archive payloads and manifest digests.

## 3. Restore and test the actual application

The archive is restored to a new separate path using the checked backup CLI.
The restored application actually reads both JSON files. A coherent restored
pair prints RECOVERED= followed by the requested generation and exits 0. A
mixed pair reports an application-state mismatch and exits2 even though the
archive's digest checks passed. Explain these two different contracts.

## 4. Change order, interrupt and recover

--reverse changes which file the writer updates first. --generation 7, written
as `--generation 7`, changes the requested state. Both orders must become
coherent after the repair. --hold pauses with the real writer holding its lock
and with either the starter capture completed or the repaired reader blocked.
After Ctrl-C the controller stops and reaps only its exact child groups and
independently acquires an exclusive lock again. Record the cleared kernel lock
rows, removed PIDs, unchanged source and a clean successful rerun.

The required evidence is the actual timing of the protected multi-file read.
It is different from choosing the newest archive or checking the desired
recovery point. Refer to [Python flock](https://docs.python.org/3/library/fcntl.html#fcntl.flock)
for the shared, exclusive and nonblocking operations.
