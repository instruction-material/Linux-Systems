# Deleting Names and Writing File Contents

This optional transfer follows the core ancestor-traversal diagnosis. It asks
a different question: can an account change file bytes, list a directory, or
remove a known filename? Complete `unlink-notes.md` with predictions and actual
results. The same pauses support independent reading and a paced walkthrough.

## Permission model and equipment

Use an ordinary account in an owned Linux lab with Bash, Python 3.8 or later,
and GNU coreutils. Root is rejected because it can bypass these access checks.
The website IDE edits, saves and exports the files. Preserve `task.sh` beside
`permission_observer.py`; execute them in the external Linux terminal.

For this lab the account owns every generated file and directory. Owner bits
therefore apply. File write permits changing bytes. Directory read permits
listing names; directory search (execute) permits reaching a known child name.
Removing an entry ordinarily requires write and search on its containing
directory, even if the file is read-only. File write alone does not permit
removing its directory entry. This lab uses no sticky directories, ACLs,
read-only mounts, immutable attributes, other accounts or security modules;
those can impose additional rules. Its observations do not establish another
account's access or authorize changes to a service tree.

The program creates only fresh temporary examples under an explicitly supplied
empty owned directory, performs real append/list/unlink operations, records
success or EACCES, and removes its generated examples. It rejects a symlink,
nonempty workspace, unsupported environment or inherited default ACL.

## Predict before running the supplied observation

Predict append, directory listing and unlink for these owner-mode combinations:

| Parent | File | Question |
| --- | --- | --- |
| 0700 | 0400 | Can a read-only document's name be removed? |
| 0500 | 0600 | Can bytes change while its name cannot be removed? |
| 0300 | 0400 | Does removing a known name require listing the directory? |

From the extracted role folder, keep the printed workspace path:

~~~bash
lab_root=$(mktemp -d)
printf 'lab_root=%s\n' "$lab_root"
bash task.sh "$lab_root" > access.json 2> access.err
access_status=$?
printf 'status=%s\n' "$access_status"
cat access.err
cat access.json
ls -la -- "$lab_root"
~~~

Verify that the parent is empty again after the run. In the complete result,
observationsCompleted describes actual operations; allPredictionsMatch checks
only the program's model. The starter's named TODO incorrectly predicts unlink
from the file's write bit. Repair it using owner write AND owner search on the
containing directory. Keep the real observations and cleanup unchanged.
Compare the reference only after recording the attempted repair.

Status 0 means the observations completed and the model matched. Status 1 can
still include complete observations when the starter model disagrees. Status 2
means invalid input, an unsupported lab or an incomplete operation; inspect
stderr and do not claim a complete result. Interruption returns 130. None of
these statuses completes the evidence notes automatically.

## Independently observe the actual commands

Create a separate private tree so the program's removed examples are not
mistaken for files available for later inspection:

~~~bash
manual_root=$(mktemp -d)
printf 'manual_root=%s\n' "$manual_root"
mkdir -- "$manual_root/box"
printf 'owned example\n' > "$manual_root/box/document.txt"
chmod 0400 -- "$manual_root/box/document.txt"
chmod 0700 -- "$manual_root/box"
stat -c 'mode=%a uid=%u gid=%g path=%n' -- "$manual_root/box" "$manual_root/box/document.txt"
printf 'probe\n' >> "$manual_root/box/document.txt"
append_status=$?
rm -- "$manual_root/box/document.txt"
unlink_status=$?
printf 'append=%s unlink=%s\n' "$append_status" "$unlink_status"
~~~

The expected append failure is evidence, so use these commands in an ordinary
interactive shell without errexit. Predict and retain each actual status.
Restore the generated document, change just the containing directory and
observe the opposite combination:

~~~bash
printf 'owned example\n' > "$manual_root/box/document.txt"
chmod 0600 -- "$manual_root/box/document.txt"
chmod 0500 -- "$manual_root/box"
printf 'probe\n' >> "$manual_root/box/document.txt"
append_status=$?
rm -- "$manual_root/box/document.txt"
unlink_status=$?
printf 'append=%s unlink=%s\n' "$append_status" "$unlink_status"
cat -- "$manual_root/box/document.txt"
chmod u+w -- "$manual_root/box"
rm -- "$manual_root/box/document.txt"
recovered_status=$?
printf 'recovered unlink=%s\n' "$recovered_status"
~~~

For the third case recreate the file with 0400, set box to 0300, then retain
the actual `ls`, append and `rm` statuses separately. Use the known full
filename. Restore box to 0700 before inspecting or cleaning it. Explain why a
failed listing does not prevent unlink of that known name.

## Changed input, failure and cleanup

Use a second empty path containing a space and compare the same model and
operations. Put a marker file in that workspace, run again and retain the
rejection without deleting the marker. Remove only that owned marker and
repeat to verify recovery:

~~~bash
mkdir -- "$lab_root/with space"
bash task.sh "$lab_root/with space" > changed.json 2> changed.err
printf 'keep\n' > "$lab_root/with space/marker.txt"
bash task.sh "$lab_root/with space" > rejected.json 2> rejected.err
rejected_status=$?
cat -- "$lab_root/with space/marker.txt"
rm -- "$lab_root/with space/marker.txt"
bash task.sh "$lab_root/with space" > recovered.json 2> recovered.err
recovered_status=$?
printf 'rejected=%s recovered=%s\n' "$rejected_status" "$recovered_status"
chmod 0700 -- "$manual_root/box"
printf 'Review before removal: %q\n' "$lab_root" "$manual_root"
rm -r -- "$lab_root" "$manual_root"
~~~

Retain five notes tasks: predictions, the model repair, actual independent
commands, changed/rejected/recovered evidence, and verified cleanup. A supplied
reference method contains no prefilled observations for this run.

Primary reference: [GNU mode structure](https://www.gnu.org/software/coreutils/manual/html_node/Mode-Structure.html)
and [Linux unlink rules](https://man7.org/linux/man-pages/man2/unlink.2.html).
