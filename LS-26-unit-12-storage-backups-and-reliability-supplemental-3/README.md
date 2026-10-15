# Reviewed Retention and a Verified Recovery Window

This optional extension follows the core restore. Investigate an explicitly reviewed retention policy and the recovery points it preserves or removes in its own attempt.

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

## 1. Define the recovery window before deleting anything

Predict which versions a keep-two policy retains after three successful
backups. In this fresh lab, run:

```bash
bash task.sh backup --lab "$lab" --name v1
bash task.sh change --lab "$lab" --text 'version two'
bash task.sh backup --lab "$lab" --name v2
bash task.sh change --lab "$lab" --text 'version three'
bash task.sh backup --lab "$lab" --name v3
bash task.sh verify --lab "$lab" --name v1
bash task.sh verify --lab "$lab" --name v2
bash task.sh verify --lab "$lab" --name v3
sha256sum -- "$lab"/backups/*/archive.tar
```

Compare all three independent checksums with the manifests.
Read each manifest's sequence and source version. Ordering uses the explicit
creation sequence, not alphabetical filenames or a guess from display time.

## 2. Review a plan that deletes nothing

```bash
bash task.sh plan --lab "$lab" --keep 2 --report first-plan
cat "$lab/reports/first-plan.json"
```

The plan records every archive and manifest hash, sequence, exact proposed
removal and retained set. Confirm all three backup directories still exist.
Explain why `v1` is proposed for removal and what historical recovery point
would be lost. An existing report name is refused and keep-zero is rejected.
A plan is a recorded proposal, not proof that any deletion happened.

## 3. Make the plan stale and require a fresh decision

Run `bash task.sh change --lab "$lab" --text 'version four'` and
`bash task.sh backup --lab "$lab" --name a-fourth`.
Its filename sorts before `v1`, but its sequence is newer. Try
`bash task.sh apply --lab "$lab" --report first-plan`; capture status 2 and the
stale-plan refusal. Confirm all four archives remain unchanged. An added,
changed, corrupt or removed backup invalidates the captured state. A corrupt
archive fails integrity verification (1) before selection or deletion.

## 4. Apply only the freshly reviewed selection

Run `bash task.sh plan --lab "$lab" --keep 2 --report current-plan`.
Read and explain its proposed
removal of `v1` and `v2` and retention of `v3` and `a-fourth`. Then run:

```bash
bash task.sh apply --lab "$lab" --report current-plan
```

Confirm exactly the two selected old directories are gone and both retained
archive/manifest pairs are byte-identical to their planned hashes. Source data,
reports, earlier restored evidence and an outside sentinel remain unchanged.
Reapplying the old plan now fails because the current set differs; record the
refusal without hiding it. This lab intentionally removes only disposable
backup copies, and never selects the last verified archive for removal.

## 5. Prove what the retained window can restore

```bash
bash task.sh restore --lab "$lab" --name v3 --destination recovered-third
bash task.sh restore --lab "$lab" --name a-fourth --destination recovered-fourth
```

Compare
their real texts `version three` and `version four`, binary file, empty
directory, file modes and current ownership with each saved manifest. State
explicitly that a request for `version one` can no longer be satisfied from
these retained backups. A retention count cannot replace a restore test or an
independently protected copy. Complete the five notes with prediction, initial
proposal, stale-plan rejection, exact deletion evidence and the two restored
recovery points. Save evidence before removing only this disposable lab and
its exact private parent.

Primary references: [GNU df](https://man7.org/linux/man-pages/man1/df.1.html),
[GNU du](https://man7.org/linux/man-pages/man1/du.1.html),
[GNU tar](https://man7.org/linux/man-pages/man1/tar.1.html) and
[GNU sha256sum](https://man7.org/linux/man-pages/man1/sha256sum.1.html).
