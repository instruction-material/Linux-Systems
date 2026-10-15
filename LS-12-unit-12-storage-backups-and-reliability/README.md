# Capacity Evidence, Verified Backup and Separate Restore

This is the required Unit 12 project. Investigate actual capacity and a separate verified restoration before optional continuations. The notebook continues the same core attempt.

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

## 1. Predict and observe capacity

Predict which command describes a filesystem, a directory tree, logical file
length and inode availability. Run `bash task.sh observe --lab "$lab" --report
first` and open `reports/first.json`. The four recorded commands are actual df
and du queries. Independently repeat the displayed commands and compare their
scope, units and current output. Read `sparseFile.size` and `allocatedBytes`.
Record actual mount identity, available bytes and inodes; do not invent totals.
Reusing `--report first` refuses replacement and preserves its original bytes.

## 2. Create and independently inspect a backup

```bash
bash task.sh backup --lab "$lab" --name initial
bash task.sh list --lab "$lab" --name initial
bash task.sh verify --lab "$lab" --name initial
sha256sum -- "$lab/backups/initial/archive.tar"
```

Compare the independent checksum with `manifest.json`. Find every declared
file, the empty directory and its mode; confirm `cache` is absent from the
archive while its source file still exists. A listing proves readable archive
structure, while verification also checks content and the declared member set.
Keep this initial backup and manifest. An existing backup name is refused.

## 3. Change live data, then restore the earlier state separately

```bash
bash task.sh change --lab "$lab" --text 'version two'
bash task.sh restore --lab "$lab" --name initial --destination recovered-first
cat "$lab/data/report.txt"
cat "$lab/restores/recovered-first/report.txt"
```

Predict those two contents before reading them. The live source remains
`version two`; the separate restore contains `version one`. Compare the full
manifest, byte hashes, file modes and account ownership, including binary
content, the space in the filename and the empty directory. Restoring an older
version does not make the current source older or the backup current.

## 4. Observe a capacity rejection without filling the disk

The following requests a reserve larger than currently available space:

```bash
reserve=$(python3 -c 'import os,sys; v=os.statvfs(sys.argv[1]); print(v.f_bavail*v.f_frsize+1024*1024*1024)' "$lab")
bash task.sh backup --lab "$lab" --name no-space --reserve-bytes "$reserve"
capacity_status=$?
printf 'CAPACITY_STATUS=%s\n' "$capacity_status"
```

Read the actual available/needed byte message and status 1. Confirm no
`backups/no-space` or partial staging candidate exists and `initial` retains
its original bytes. This is an explicit reserve rejection based on a real
capacity observation, not a test that fills a filesystem to exhaustion.

## 5. Make and restore a changed backup

Create `--name changed`, restore it to `--destination recovered-second` and
confirm the second restore contains `version two`. Check the first restore
and original backup still retain their earlier state. Retry an existing
restore destination and retain its refusal plus unchanged restored bytes.
Record the source/exclusion list, two recovery points, trusted checksums and
actual restore evidence. The troubleshooting notebook continues this same
attempt rather than creating another program.

After saving evidence, remove only the exact disposable lab and private
parent created above. Never substitute a home directory or storage device.
The optional corruption and retention labs use separate fresh attempts.

Primary references: [GNU df](https://man7.org/linux/man-pages/man1/df.1.html),
[GNU du](https://man7.org/linux/man-pages/man1/du.1.html),
[GNU tar](https://man7.org/linux/man-pages/man1/tar.1.html) and
[GNU sha256sum](https://man7.org/linux/man-pages/man1/sha256sum.1.html).
