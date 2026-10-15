# Recovery Point Selection from a Verified Archive History

This optional capstone transfer answers a selection question: which completed,
intact snapshot is the newest one at or before an explicit recovery target?
It follows the required service, scheduled backup and separate restore drill.
The extension project asks a different question about independently expected
restored state. Selection and restore acceptance are separate decisions.

## Policy model and the named repair

Repair choose_backup in task.py. It receives explicit candidate Paths and a
positive cutoffNs value. Consider only published .tar.gz files. Use
backup.validate(path) to reread the actual archive, reject incomplete or corrupt
candidates, and obtain its manifest. Keep only createdNs <= cutoffNs. Choose
the greatest (createdNs, filename) tuple among eligible candidates, or return
None when there is no eligible candidate. The filename breaks equal-time ties;
it does not establish the recovery time. No candidate is deleted or changed.

The starter chooses the newest filesystem mtime without checking integrity,
publication or cutoff. Predict its selected corrupt archive before running.
The supplied backup.validate returns (contents, manifest) only after checking
the exact four regular members and payload digests; it can raise OSError,
ValueError, KeyError, TypeError or tarfile.TarError for rejected inputs.
Catch those candidate rejections while preserving the other candidates.
max with a key over the stated tuple chooses the eligible maximum; test an
empty eligible list before taking that maximum.

## Four distinct recovery targets

For the expected target, the later complete archive lies after the cutoff.
The correct choice is expected, despite misleading mtimes and the corrupt
duplicate. The earlier target chooses first. The latest-complete target uses
a cutoff that also includes the .partial creation time: it still chooses
later, because the candidate was never published. A cutoff before the first
archive returns None. Retain all four actual selected paths and manifests.

An intact selected archive is restored by the real backup.py child into a new
separate directory. Its restored bytes are retained in the report. A policy
that selects the corrupt archive records the validation refusal and cannot
claim a successful restore. Compare the policy result with that concrete
outcome. A latest() operation without the target cutoff cannot answer the
recovery question defined here.

## Environment and exact source roles

Use an ordinary non-root account in the owned Linux lab with Bash and Python
3.8+ available. No sudo, persistent unit, service listener or external database
is used in this continuation. The required capstone establishes those manager,
timer, proxy and service observations separately. This project investigates
the recovery evidence needed for its runbook. It is optional practice.

Keep all eight role files together: task.sh, task.py, history_lab.py, backup.py,
app.py, config.json, data.json and recovery-notes.md. The app and its inputs are
copied as archive payloads here; this continuation does not execute the app or
claim a service deployment. backup.py, app.py, config.json and data.json retain
the required capstone reference bytes at revision
03a48030a2673e4a118668814d8187bbc7bfe8b1. history_lab.py supplies experiment
equipment; task.py contains the single named policy repair. The starter and
reference leave the independent evidence worksheet blank.

The site IDE edits, saves and exports the complete selected role. Execute the
exported commands in the external Linux terminal. Preserve a separate starter
attempt before consulting the reference. From that role directory:

~~~bash
lab_root=$(mktemp -d)
bash task.sh "$lab_root" > recovery.json 2> recovery.err
recovery_status=$?
printf 'status=%s\n' "$recovery_status"
cat recovery.err
python3 -m json.tool recovery.json
~~~

Status 0 means the policy met the observed cases; an untouched incomplete
starter returns 1 after retaining its incorrect decisions. Neither status
completes recovery-notes.md. Status 2 reports an input or equipment failure.

## Actual archive history and its limits

The equipment creates one private child under the explicit empty owned parent.
Three real backup.py child processes produce gzip archives for first, expected
and later fictional data. Each successful build validates its complete candidate
before atomic publication. Separate actual verify processes reread every
archive and compare app.py, config.json and data.json with its manifest.
The manifest records createdNs and the SHA-256 of each payload member.

Creation time is observed from the lab clock. The equipment requires strictly
increasing values and reports failure if the clock moves backward during this
small experiment. A real recovery plan must specify the clock and ordering
authority. This local manifest is not an authenticated external publisher, and
its creation time alone does not establish when a business transaction occurred.
The exercise defines its recovery targets from this explicit synthetic history.

The equipment then writes another actual readable gzip archive with altered
data but the old manifest. An actual verify command rejects its digest mismatch.
A separate actual build with --reject-after-write leaves a valid-looking
.partial candidate without publishing it. Existing trusted archives remain
unchanged. Filesystem modification dates are deliberately moved into a different
order; the corrupt archive receives the newest mtime. A filename, recent mtime,
readable gzip container or successful listing does not establish the required
recovery point or a completed publication.

The report retains the archive bytes, manifests, actual child PID/argv/cwd,
stdout, stderr, statuses, times and cleanup. It also retains separate restored
file bytes where a restore succeeds. Inspect those facts rather than accepting
only the final policy verdict. The use of a synthetic payload makes these
checks reproducible without customer data or a production database.

## Changed case, refusal, interruption and cleanup

Run again using the same now-empty parent with --reverse. The equipment reverses
the enumeration of complete archives; the policy answers must still follow the
recorded target and bytes. It creates a new private history for this run, so
compare labels and relationships rather than expecting identical timestamps,
archive names or archive digests between runs.

~~~bash
bash task.sh "$lab_root" --reverse > reversed.json 2> reversed.err
reversed_status=$?
printf 'status=%s\n' "$reversed_status"
~~~

Use --hold-seconds 8 to pause after the real history is prepared. ready.json
under lab_root identifies the actual owned process and its private case.
Ctrl-C yields status 130 with partial observations, removes its own case and
ready file, and reaps any owned subprocess. Repeat normally for recovery.
Holds outside 0–15, a missing or symlink parent, and a nonempty parent are
rejected without removing their existing contents. Try a parent containing
spaces. Keep an unrelated sentinel outside the lab and compare its hash before
and after the run. Only the owned temporary child and ready file are removed;
no archive retention policy or system journal is changed.

Before removing the parent, verify ownedCaseRemoved, workspaceEmpty and
sourceUnchanged, inspect that the recorded child PIDs are gone, and preserve
the JSON and worksheet elsewhere. Then use rmdir on the exact empty parent.
Do not remove another path merely because it has a similar name.

## Evidence and paced use

Record the environment and reset boundary, a prediction before each decision,
the named repair, exact commands and statuses, actual archive and restored-byte
evidence, changed order, refusal, interruption, recovery and cleanup. Explain
what the observations prove and what remains dependent on an independent
recovery target. A guided walkthrough uses the same predict, operate, inspect,
correct and repeat sequence; it does not replace the independent worksheet.

Primary references: [Python SHA-256](https://docs.python.org/3/library/hashlib.html),
[tar archive member inspection](https://docs.python.org/3/library/tarfile.html)
and [atomic file replacement](https://docs.python.org/3/library/os.html#os.replace).
