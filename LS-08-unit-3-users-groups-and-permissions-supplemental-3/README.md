# Creation Masks, Existing Files and Executable Bits

This optional extension follows the permissions core and name-removal
transfer. It investigates initial creation modes rather than ancestor access
or deleting existing entries. Complete `umask-notes.md` with predictions,
actual modes and explanations. The pauses support independent study and a
paced walkthrough.

## What a creation mask changes

Use an ordinary account in an owned Linux lab with Bash, Python 3.8 or later
and GNU stat. Preserve `task.sh` beside `creation_observer.py`. The website IDE
edits, saves and exports these files; run them in the external Linux terminal.

Without a default ACL, a requested mode is filtered by `requested & ~mask`.
This is bit clearing, not decimal or octal subtraction. A regular file created
with requested 0666 does not gain executable bits when mask is 0000. A
directory requested as 0777 can retain search bits. Programs can request other
modes or change them later, so a mask alone does not establish every file's
final mode. Changing a mask does not retroactively change existing files.

The observer creates only fresh temporary examples under an explicit empty
owned workspace. It first creates an existing 0640 document, changes its own
process mask, requests a new 0666 file and 0777 directory, records actual modes
and the existing file's bytes, then restores its inherited mask and removes
its generated tree. It rejects root, symlink/nonempty workspaces and inherited
default ACLs. These observations concern this account and filesystem, not a
service identity or a system-wide policy change.

## Predict and compare actual creation

From the extracted role folder, retain the printed path and caller mask:

~~~bash
lab_root=$(mktemp -d)
printf 'lab_root=%s\n' "$lab_root"
caller_mask=$(umask)
bash task.sh "$lab_root" 0022 > mask-0022.json 2> mask-0022.err
mask_status=$?
printf 'status=%s caller_before=%s caller_after=%s\n' "$mask_status" "$caller_mask" "$(umask)"
cat mask-0022.err
cat mask-0022.json
~~~

Predict 0644 for the new regular file and 0755 for the new directory. The
existing document should retain 0640 and its original checksum. The absolute
workspace, inherited mask and observed values must come from this run.

The starter's named TODO incorrectly uses a requested 0777 for a regular
file. Repair that requested mode to match the actual file creation call.
Keep the real mask, actual stat results and restoration unchanged. Compare
the reference after recording a working attempt. Status 0 means completed
observations and a matching model; status 1 can carry a complete result with
a deliberately incorrect starter prediction. Status 2 means invalid input,
an unsupported lab or incomplete operation; inspect stderr. Interruption
returns 130. A matching model does not complete the evidence notes.

## Independently check with Bash and stat

Use a child shell so the experiment does not change the caller's mask:

~~~bash
manual_root=$(mktemp -d)
printf 'manual_root=%s\n' "$manual_root"
printf 'existing data\n' > "$manual_root/existing.txt"
chmod 0640 -- "$manual_root/existing.txt"
(
    umask 0022
    : > "$manual_root/new.txt"
    mkdir -- "$manual_root/new-directory"
    stat -c 'mode=%a path=%n' -- "$manual_root/new.txt" "$manual_root/new-directory" "$manual_root/existing.txt"
)
printf 'caller_after=%s\n' "$(umask)"
cat -- "$manual_root/existing.txt"
~~~

Before changing the input, predict masks 0077, 0002, 0000 and 0137. Retain
their actual reports separately:

~~~bash
for mask in 0077 0002 0000 0137; do
    bash task.sh "$lab_root" "$mask" > "mask-$mask.json" 2> "mask-$mask.err"
    run_status=$?
    printf 'mask=%s status=%s\n' "$mask" "$run_status"
done
~~~

Explain why 0137 demonstrates bit clearing better than subtraction, why no
successful regular-file observation has execute bits, and why the existing
0640 document stays unchanged. Repeat the independent Bash comparison under a
different mask in a fresh private directory; do not overwrite the first
evidence. A restrictive directory mode can prevent entry, so restore only its
owner permissions before removing that generated example.

## Failed input, recovery and cleanup

Retain an invalid octal mask and correct the same command:

~~~bash
bash task.sh "$lab_root" 0088 > invalid.json 2> invalid.err
invalid_status=$?
cat invalid.err
bash task.sh "$lab_root" 0077 > recovered.json 2> recovered.err
recovered_status=$?
printf 'invalid=%s recovered=%s\n' "$invalid_status" "$recovered_status"
ls -la -- "$lab_root"
printf 'caller_before=%s caller_after=%s\n' "$caller_mask" "$(umask)"
chmod 0700 -- "$manual_root/new-directory"
printf 'Review before removal: %q\n' "$lab_root" "$manual_root"
rm -r -- "$lab_root" "$manual_root"
~~~

The workspace should be empty after every completed observation. Complete five
notes tasks: the mode prediction table, the starter repair, an independent
Bash/stat comparison, changed/failed/recovered inputs, and verified mask and
filesystem restoration. The reference supplies a method rather than a saved
answer for the learner's actual observations.

Primary references: [Linux umask](https://man7.org/linux/man-pages/man2/umask.2.html)
and [GNU file permissions](https://www.gnu.org/software/coreutils/manual/html_node/File-permissions.html).
