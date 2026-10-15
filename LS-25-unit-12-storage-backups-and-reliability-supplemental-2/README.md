# Archive Listing versus Content Integrity

This optional transfer follows a successful separate restore. Isolate archive readability, content integrity, refusal and recovery in its own attempt.

## Environment and saved work

Use an ordinary account in a Debian/Ubuntu Linux lab or WSL distribution with
Python 3, Bash, GNU tar and GNU coreutils (`df`, `du`, `sha256sum`). Arrange for
missing tools before starting. No package installation is part of this lab.
The site IDE edits, saves and exports these sources and notes. Confirm the
selected role's import, download its ZIP, extract it and run commands from the
role folder in the external Linux terminal. Browser saving does not run tar.

The starter and reference have identical working equipment. Complete the five
named tasks in the notes using predictions and actual evidence; the reference
explains a method without fabricating this lab's paths, sizes, timings or hashes.
Use the same numbered pauses for independent reading and a paced walkthrough.
An equipment exit of 0 does not complete the notes. Errors are separate: invalid
arguments, root, the wrong platform, an existing name or a stale policy return
2; missing tools, failed native commands or corrupt backup evidence return 1.
An ordinary handled interruption returns 130.

Start with a fresh private parent and keep this shell open:

```bash
uname -s
id -u
python3 --version
tar --version
df --version
lab_parent=$(mktemp -d)
lab="$lab_parent/storage"
bash task.sh init --lab "$lab"
```

Record the exact printed absolute `lab` path. Initialization refuses an existing
path. All commands require this account's matching lab marker and regular files
or directories. Keep this directory private; do not substitute real home,
shared, system or production data. The small supplied dataset has a text
version, a binary file, a filename containing a space, an empty directory, a
1 MiB sparse file and an explicitly excluded transient `cache` directory.

The archive contains `data` contents except `cache`. Its manifest records file
names, types, content hashes, sizes, account ownership and permission modes,
plus archive SHA-256, sequence, source path and the capacity observation.
`backup` first checks currently available bytes against apparent input size,
archive overhead and a configurable reserve (16 MiB by default). Space can
change after that check. The actual tar status and complete inventory check
remain necessary. A partial staging directory is discarded after a handled
command failure or interruption; earlier published backups remain in place.
A power loss or SIGKILL can leave staging evidence, which requires inspection.
It never counts as a valid backup.

Archive checks reject unsupported paths, links, special files, extra/missing
members, content mismatches and special permission bits. Restore uses actual
GNU tar only after validation, into a new directory under `restores`. It
refuses an existing destination and compares restored bytes, paths, ownership
and modes with the saved inventory. The original source is checked separately.
Failures do not become empty successful summaries.

Commands, PIDs, start/end times, statuses, stdout, stderr and child cleanup are
retained in private `operations.jsonl`. Keep that record with the notes, source
observations, manifests, trusted checksum record and restored comparison.

## Scope of the evidence

`df` observes the containing mounted filesystem. `du` observes the selected tree;
its apparent-size mode counts logical lengths rather than allocated blocks.
The sparse file can therefore have a large logical length and few allocated
bytes. Read actual results instead of assuming the two totals match. Inode
availability is another resource, separate from available bytes. The plain tar
archive need not preserve the original sparse allocation, even when restored
content and length match.

These owned archives use the same filesystem as the source. They demonstrate
file recovery, not survival of that disk's failure. A real backup plan needs
an independently protected copy, explicit recovery point/time requirements,
access control and repeated restoration tests. RAID, replication and a copied
file alone do not establish that recovery requirement. The manifest here is
an integrity reference, not a signature: changing both archive and manifest
can defeat a self-contained checksum claim. Retain a trusted checksum record
separately. This regular-file lab does not establish database consistency or
preservation of ACLs, xattrs, links, device files or a bootable system.

## 1. Establish a trustworthy comparison

After the fresh initialization, predict what a successful archive listing
does and does not prove. Run:

```bash
bash task.sh backup --lab "$lab" --name baseline
bash task.sh list --lab "$lab" --name baseline
bash task.sh verify --lab "$lab" --name baseline
bash task.sh restore --lab "$lab" --name baseline --destination trusted-copy
sha256sum -- "$lab/backups/baseline/archive.tar"
```

Save the actual manifest/checksum outside
the archive and compare every restored entry. Keep this good backup untouched.

## 2. Change content without breaking the tar listing

```bash
bash task.sh backup --lab "$lab" --name damaged
bash task.sh damage --lab "$lab" --name damaged --mode flip
bash task.sh list --lab "$lab" --name damaged
bash task.sh verify --lab "$lab" --name damaged
verify_status=$?
printf 'VERIFY_STATUS=%s\n' "$verify_status"
```

The deliberate flip changes a byte in the archived text payload; its header
and names remain readable. Expect a successful listing but a nonzero integrity
check (1). Compare the changed archive SHA-256 with its retained manifest.
Do not rewrite the manifest to manufacture a pass. This controlled fault
explains why archive readability alone does not prove correct backup content.

## 3. Observe the restoration gate

Run `bash task.sh restore --lab "$lab" --name damaged --destination refused`.
Capture status 1 and the actual mismatch error. Confirm `restores/refused`
was never created, live data is unchanged and the trusted baseline and restore
remain byte-identical. Source availability and a valid earlier copy are separate
observations from this failed candidate.

## 4. Compare a truncated archive

Create and damage another fresh archive:

```bash
bash task.sh backup --lab "$lab" --name truncated
bash task.sh damage --lab "$lab" --name truncated --mode truncate
bash task.sh list --lab "$lab" --name truncated
bash task.sh verify --lab "$lab" --name truncated
bash task.sh restore --lab "$lab" --name truncated --destination truncated-refused
```

Capture each status immediately with `$?`. Compare its listing failure,
verification refusal and rejected restore to a new destination. Retain actual
statuses rather than treating a tar diagnostic as a completed investigation.
The truncated archive and the readable-but-changed archive are different cases.

## 5. Recover from a fresh verified artifact

```bash
bash task.sh change --lab "$lab" --text 'repaired version'
bash task.sh backup --lab "$lab" --name repaired
bash task.sh verify --lab "$lab" --name repaired
bash task.sh restore --lab "$lab" --name repaired --destination recovered
```

Compare real restored bytes,
mode and current account with the new manifest and source. The repaired backup
is a new artifact; it does not repair the damaged historical bytes. Preserve
both failed records and the original good baseline. Complete all five notes
with initial predictions, independent checksum/listing results, refusal before
destination creation, changed-case evidence and recovery/cleanup observations.
Save evidence before removing only this exact disposable lab and parent.

Primary references: [GNU df](https://man7.org/linux/man-pages/man1/df.1.html),
[GNU du](https://man7.org/linux/man-pages/man1/du.1.html),
[GNU tar](https://man7.org/linux/man-pages/man1/tar.1.html) and
[GNU sha256sum](https://man7.org/linux/man-pages/man1/sha256sum.1.html).
