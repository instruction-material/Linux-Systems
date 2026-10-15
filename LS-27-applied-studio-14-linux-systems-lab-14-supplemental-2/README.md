# Release Manifests and Actual Payload Integrity

This optional transfer follows readiness and rollback. It asks whether the
candidate files match a supplied expected manifest before activation. The
core's HTTP readiness probe establishes a different fact: a small health
endpoint can answer correctly while another page has been altered.

## Equipment and the supplied integrity contract

Use an ordinary owned Linux lab with Bash, Python 3.8+ and Nginx installed.
Keep task.sh, task.py, nginx_lab.py, release-manifest.json and all four text
fixtures together in the exported role. The site IDE edits, saves and exports
them; run the commands in that external Linux terminal.

The manifest maps exactly health.txt and index.txt to expected SHA-256 digests
for release-b. A digest is calculated from actual bytes. File existence alone
does not establish that those bytes match. This is a locally supplied class
manifest, not proof of an authenticated external builder or publisher. Its
source and trust boundary must be known separately.

The equipment starts an owned loopback Nginx process and copies both releases
into its private prefix. Every case first restores release-a as the current
target. The named verify_release starter checks only that each expected file
exists. Repair it to require every file and its actual SHA-256 to match the
corresponding manifest value. Path.read_bytes reads the actual file bytes;
hashlib.sha256(content).hexdigest() returns their lowercase hexadecimal digest.
manifest.items() supplies each member name and expected digest. Preserve the
exact two-member boundary, real
file reads, server responses and cleanup. Review the reference after an attempt.

## Predict four separate preflight decisions

From the extracted role folder:

~~~bash
lab_root=$(mktemp -d)
bash task.sh "$lab_root" > integrity.json 2> integrity.err
integrity_status=$?
printf 'status=%s\n' "$integrity_status"
cat integrity.err
cat integrity.json
~~~

The intact case matches both files and permits release-b. The tampered case
appends bytes only to the private index.txt while retaining its name. The
reference rejects it and leaves release-a selected. The untouched starter
accepts it, so release-b's health still returns 200 with release=b while its
page contains the altered payload. Record both actual responses.

The missing case removes private index.txt; both policies reject it. The
restored case copies the original private inputs back and permits release-b
again. The report retains each inspected file's existence, bytes, actual
digest and expected digest, the policy decision, target and HTTP responses.
The reference decision sequence is true,false,false,true. An incorrect
tampered-file acceptance yields observation status 1; meeting this sequence
yields0. Neither result completes artifact-notes.md.

Run --reverse using the now-empty parent. It changes the tampered member from
index.txt to health.txt. Predict which HTTP bytes change if the incomplete
policy permits it; the completed integrity decision stays a rejection. This
comparison distinguishes a changed payload member from a missing one.

## Failure, recovery and completion

Use `--hold-seconds 8` for an independent curl inspection of the actual port and
prefix recorded in ready.json. Use --broken-config once to retain the real
syntax rejection and status 2, then rerun normally for recovery. Ctrl-C during
the hold yields130 and stops the owned process. Input guards preserve missing,
nonempty and symlink parents; only an empty owned parent is accepted.

The copies, current link and temporary server belong to the private case.
No source fixture, global Nginx configuration or public service is changed.
Verify the recorded PID and listener are gone and the parent is empty before
rmdir. Complete all five notes tasks with independent predictions, the named
repair, manifest trust boundary, actual bytes/digests, health/page distinction,
changed member, rejection, recovery and cleanup. A successful reference is
equipment for the investigation, not a completed learner record.

Primary references: [Python SHA-256 interface](https://docs.python.org/3/library/hashlib.html)
and [Python atomic replacement](https://docs.python.org/3/library/os.html#os.replace).
