# Optional studio: Restoring Operating Attributes Alongside Payload Bytes


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

## 1. Define the operating attributes independently

The controlled source has an executable app.py with mode0750, private config
with mode0600 and group-readable data with mode0640. An octal permission digit
adds read4, write2 and execute1 for owner, group and others respectively. These
are ordinary permission bits without set-ID bits. The equipment sets distinct
past modification times and then records the actual stat values read back from
the source filesystem. The independent target is that observed record.

The checked archive/restore equipment intentionally restores ordinary private
files with mode0600. Its manifest proves exact payload bytes, not preserved
original modes or nanosecond modification times. Inspect the actual before
record and real permission-denied attempt to execute the restored application.
No child PID is invented for an operating-system refusal to start a file.

## 2. Complete restore_attributes

For each of the three declared names, apply the recorded ordinary mode using
os.chmod and recorded mtime using os.utime with the ns argument. Preserve the
current access time when supplying the two-value nanosecond tuple. Use the
integer st_mtime_ns observation, not floating-point seconds. The equipment
has already checked these ordinary owned restore files; the metadata comes
from this controlled source record rather than an untrusted archive request.
Do not restore ownership, set-ID bits or attributes taken from arbitrary input.

Inspect mode and mtime again after the policy, and compare the actual payload
hashes independently. Correct bytes alone cannot satisfy this project's
attribute requirement. This bounded exercise covers ordinary mode bits and
modification time. It does not preserve ACLs, extended attributes, owners,
groups, hard-link relationships or creation times.

## 3. Execute the restored program

The reference's actual direct execution succeeds and prints the selected
generation. The starter leaves mode0600, so its direct execution is refused.
Record both the permission result and exact before/after stat fields; do not
replace this check with only an os.access prediction. Changing a file's mode
does not itself change its content digest.

## 4. Change enumeration and interrupt the drill

--reverse presents the independent attribute record in the opposite order;
--generation 7 is passed as `--generation 7` to change the fictional data.
The repaired result must preserve the same attribute contract in either
order. --hold pauses after the actual separate restore and before the policy.
That interruption tests bounded filesystem cleanup, not a live service or
writer. Preserve the full record, confirm the parent is empty and rerun.

This project's target is operating metadata, separate from the capstone
companion's expected-content comparison. See [os.chmod](https://docs.python.org/3/library/os.html#os.chmod),
[os.stat](https://docs.python.org/3/library/os.html#os.stat) and
[os.utime](https://docs.python.org/3/library/os.html#os.utime).
