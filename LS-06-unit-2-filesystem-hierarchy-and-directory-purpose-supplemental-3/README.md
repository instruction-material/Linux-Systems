# Reported Size, Read Bytes and Live Kernel Files

This optional extension distinguishes a file's metadata, its mounted
filesystem and bytes returned by a real read. Linux kernel views such as
`/proc/uptime` are generated information, not ordinary stored documents.
Complete `filesystem-notes.md` with actual observations. The prediction,
inspection and explanation pauses support independent study and a paced
walkthrough. This is separate from the core static-site deployment and from
later disk-capacity, archive and restore investigations.

## Equipment and what the program measures

Use an ordinary account in an owned Linux lab with Python 3.8 or later, Bash, GNU stat,
GNU head and util-linux findmnt. Preserve `filesystem_observer.py` beside
`task.sh` when extracting the role. The website IDE edits, saves and exports
these files; it does not provide the Linux kernel observations.

The program accepts one or more explicit paths. It resolves symbolic links,
rejects directories, FIFOs, devices and a standalone `-`, and reads only
regular files or readable regular-looking kernel pseudo-files. It never
writes to the selected inputs, changes mount configuration or invokes sudo.
Each path is inspected by actual `stat`, `findmnt` and `head` commands, with
separate arguments, bounded subprocess time and retained statuses/output.

`stat` reports metadata size, device and inode. `findmnt --target` identifies
the path's actual mounted filesystem; the program explicitly requests JSON
TARGET, FSTYPE and SOURCE columns. A directory name is not enough to identify
that filesystem. `head` reads at most 4097 bytes. The report retains a maximum
4096-byte base64 capture plus its SHA-256, records the actual bytes returned,
and marks truncated captures. A large file's size can exceed that bounded
read without being a kernel view. Metadata and content are observed by
separate commands, so a changing input is not one atomic snapshot.

## Predict ordinary, empty and kernel-backed observations

Create two ordinary inputs under a private disposable directory. Keep the
printed parent path for this shell:

~~~bash
lab_root=$(mktemp -d)
printf 'lab_root=%s\n' "$lab_root"
printf 'alpha\n' > "$lab_root/ordinary.txt"
: > "$lab_root/empty.txt"
bash task.sh "$lab_root/ordinary.txt" "$lab_root/empty.txt" /proc/uptime > first.json 2> first.err
observer_status=$?
printf 'status=%s\n' "$observer_status"
cat first.err
cat first.json
~~~

Predict size 6 and six read bytes for the supplied ordinary file, and zero
size/zero read bytes for the supplied empty file. Read `/proc/uptime` rather
than supplying sample numbers. On the target Linux environment it reports
metadata size 0 while returning a nonempty live record with two uptime/idle
time quantities. Identify its actual filesystem type from findmnt rather than
from its size alone. Record the observed values and explain why reported size
0 cannot establish that this generated file is empty.

The starter's named content_is_empty TODO uses only reported metadata size.
Repair it using the count from the successful bounded read. The supplied
reference gives a method, not prefilled observations. Status 0 means every
requested observation completed; it does not establish worksheet completion
or repair of the starter's decision. A native command failure returns 1,
invalid/unreadable path selection or unsupported environment can return 2,
and an interruption returns 130. On failure stdout contains no successful
complete report; stderr retains the error, actual tool records and any earlier
completed observations. Do not treat a partly completed error record as the
normal all-path result.

## Independently compare actual tools and decode a capture

~~~bash
stat -L --printf='reported bytes=%s device=%d inode=%i\n' -- /proc/uptime
findmnt --json --target /proc/uptime --output TARGET,FSTYPE,SOURCE
head --bytes=4097 -- /proc/uptime > independent-uptime.txt
read_status=$?
printf 'read_status=%s\n' "$read_status"
wc -c < independent-uptime.txt
python3 - <<'CHECK'
import base64, json
with open('first.json', encoding='utf-8') as source:
    result = json.load(source)
for entry in result['observations']:
    print(entry['inputPath'], repr(base64.b64decode(entry['capturedBase64'])))
CHECK
~~~

Independent uptime reads occur at different times. Compare meaning, the
nonempty read and filesystem context; do not require identical live numbers.
The bytes stored inside one report and their stored checksum do remain exact
and can be checked independently. The program does not identify a particular
person's usage or infer persistent storage from a live kernel record.

## Changed cases, failure and recovery

Use a long ordinary input and a quoted path, then retain a later live read:

~~~bash
python3 -c "print('x' * 5000, end='')" > "$lab_root/long.txt"
cp -- "$lab_root/ordinary.txt" "$lab_root/with space.txt"
bash task.sh "$lab_root/long.txt" "$lab_root/with space.txt" /proc/uptime > changed.json 2> changed.err
changed_status=$?
printf 'changed=%s\n' "$changed_status"
bash task.sh "$lab_root/ordinary.txt" "$lab_root/absent.txt" > failed.json 2> failed.err
failed_status=$?
printf 'failed=%s\n' "$failed_status"
cat failed.err
~~~

The long input has metadata size 5000, returns 4097 bytes and retains 4096;
truncated is true. Compare these fields before interpreting a mismatch.
Preserve the missing-path error record and verify no complete stdout result
was claimed. To observe an actual native read denial on a disposable copy:

~~~bash
cp -- "$lab_root/ordinary.txt" "$lab_root/private.txt"
saved_mode=$(stat -c '%a' -- "$lab_root/private.txt")
chmod 000 -- "$lab_root/private.txt"
bash task.sh "$lab_root/private.txt" > denied.json 2> denied.err
denied_status=$?
printf 'denied=%s\n' "$denied_status"
chmod "$saved_mode" -- "$lab_root/private.txt"
cat denied.err
~~~

Correct the missing path and repeat the same comparison to verify recovery.
Retain five completed notes tasks, actual tool outputs, the changed input and
failed/restored records. Reopen the saved workspace before comparing the
reference. Remove only the exact disposable input directory after reviewing
its printed value; retain result records separately.

~~~bash
printf 'Review before removal: %q\n' "$lab_root"
rm -r -- "$lab_root"
~~~

Primary references: [GNU stat](https://www.gnu.org/s/coreutils/manual/html_node/stat-invocation.html),
[GNU head](https://www.gnu.org/s/coreutils/manual/html_node/head-invocation.html),
[findmnt](https://man7.org/linux/man-pages/man8/findmnt.8.html), and
[Linux procfs](https://man7.org/linux/man-pages/man5/proc.5.html).
