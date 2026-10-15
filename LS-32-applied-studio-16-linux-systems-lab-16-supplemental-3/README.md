# Optional studio: Verified Retention with Preserved Recovery Anchors


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

## 1. Inspect the real backup history

The equipment actually publishes three distinct generations with the accepted
backup CLI. It records each checked manifest and payload, then adds a corrupt
archive, an unpublished partial candidate and a refused symlink to an
independent file outside the archive directory. File mtimes are deliberately
made older than the recorded cutoff, so they cannot establish publication
order or validity. The first and latest verified archives are protected
recovery anchors. The ordinary cutoff is the latest manifest's createdNs.

The intended ordinary retirement set contains exactly the middle verified
archive. The first stays protected, the latest is protected and not older than
the cutoff, and corrupt/partial/link evidence stays untouched. Predict the set
before reading the starter result. Verification of complete archive contents
and a recorded publication time are different from a filename or mtime hint.

## 2. Complete choose_retirements

Return the paths of records that are verified, published and ordinary, have
createdNs strictly less than cutoff_ns, and are absent from protected. Sorting
the returned paths makes the plan stable without treating enumeration order
as age. Do not compare None from an unverified record with an integer; first
check verification. The task asks for a plan, not deletion inside the policy.

The unchanged execution guard independently checks the entire proposed set
before removing any file. It rejects duplicates, unknown/unverified paths,
protected anchors and paths outside the allowed private history. An unsafe
starter plan is refused as a whole, leaving all files intact. A correct plan
causes actual unlink operations for exactly the selected old verified files.
Record the plan, acceptance decision, before bytes/inode, actual absence and
unchanged protected, corrupt, partial and symlink evidence.

## 3. Demonstrate recovery after actual retention

Both protected anchors are restored through the real backup CLI into two new
separate destinations after the deletion decision. Compare restored file
hashes and different fictional generations against the retained archive
payloads. A remaining directory entry alone is insufficient evidence that
the desired recovery anchors still work. The independent sentinel stays exact.

## 4. Test a changed cutoff and interruption

Run with --reverse and a changed `--generation 7` to reject order assumptions.
Run with --keep-all: its cutoff is the first verified publication time, so no
unprotected verified archive is old enough and the correct plan is empty.
Both anchors must still restore. --hold pauses after real history verification
and before planning; Ctrl-C tests exact filesystem cleanup before any
retirement. Then rerun and retain a successful recovery record.

This is a private retention drill with preserved anchors, not the capstone
companion's choice of an archive to restore. The locally observed manifest
time is not an independently signed timestamp. An arbitrary operator or
uncooperative concurrent writer is outside this controlled history's trust
boundary. See [os.unlink](https://docs.python.org/3/library/os.html#os.unlink)
and [Python file metadata](https://docs.python.org/3/library/os.html#os.stat).
