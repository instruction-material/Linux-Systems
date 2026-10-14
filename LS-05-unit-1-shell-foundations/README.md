# Shell foundations: trustworthy log summary

This project composes enumeration, quoting, structured filtering, aggregation,
diagnostics and exit status. It reads an immediate directory of regular .log
files. It does not rewrite the inputs or search subdirectories. A symbolic link
is not a regular input in this exercise. The timestamp is field one, the level
is field two, and the remaining text is the message. Only the exact levels ERROR
and WARNING contribute to their respective totals.

## Concepts and worked prediction

The directory contains three log files, including an empty file and a filename
with a space. app 1.log contains two errors and one warning; app-2.log contains
one error and one warning. An INFO message containing the word ERROR contributes
no error. notes.txt is excluded. The reference result is therefore:

~~~text
files=3 errors=3 warnings=2
~~~

find emits NUL-separated paths because a line is not a safe filename boundary.
The read loop uses the same separator and quotes each path. The manifest is
written before aggregation so an enumeration failure retains its failure
status. awk counts the level field and returns two numeric values even when a
file is empty. The totals are printed only after all selected inputs are read.
Diagnostics remain on standard error. Successful empty input is different from
an unreadable or missing directory.

## Open and run

Use a Linux lab with Bash, find, awk and mktemp. Extract the selected role folder
with its reports subdirectory, retaining this guide. From that folder:

~~~sh
bash task.sh
bash task.sh reports > summary.txt 2> diagnostics.txt
task_status=$?
printf 'status=%s\n' "$task_status"
cat summary.txt
cat diagnostics.txt
~~~

The relative default is anchored to the script location, so running the script
from another working directory selects the same supplied reports. An explicit
directory argument selects a changed case. A missing directory returns status
1 and no successful summary. An extra argument returns status 2.

## Learner work and independent checks

The starter already reads and counts the inputs, but deliberately discards the
warning count at the named TODO. Remove that defect without changing the error
count, input format or output format. Record the prediction before running it.
Create a separate empty directory, a directory with one matching line, and a
directory with multiple matching lines. Add an INFO message containing ERROR,
a non-log text file and a filename containing spaces. Record summary, diagnostic
output and status for each case. Test a missing directory as a failure case.
Compare the reference only after recording a working attempt.

## Instructor walkthrough and completion evidence

Walk the supplied paths through find, the NUL read loop and awk before running
the complete pipeline. Explain why grep with an unconditional 'or true' cannot
distinguish no matches from an input error. Completion requires the named TODO
repair, the changed-case record and an explanation of the status boundary;
running a supplied program does not complete that reasoning record.
