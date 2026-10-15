# Partial Input, Pipeline Statuses and Misleading Success

This optional extension follows the required log-summary project. It keeps a
small two-stage pipeline visible: cat reads explicit text files, and awk counts
exact level fields. The investigation is whether a printed summary proves that
all input was read. Complete `pipeline-notes.md` using predictions and actual
stdout, stderr and both stage statuses. The same pauses support independent
reading and a paced walkthrough.

## Equipment and contract

Use an ordinary account in an owned Linux lab with Bash, cat and awk. Extract
one role with `count.awk` and the complete `records` folder. The website IDE
supports editing, saving and ZIP export; execute the pipeline in that external
Linux lab. The program changes no inputs, permissions or system configuration.

`bash task.sh FILE...` accepts one or more ordinary nonsymlink text-file paths.
A standalone `-`, a directory, a symbolic link or a special file is rejected.
A missing or unreadable path reaches the actual cat command and yields an input
failure. Quote each path; each operand is resolved from the caller's working
directory. The supplied awk program is located beside `task.sh`, even when the
script is invoked through an absolute path from another directory.

The input format has a timestamp in field one, a level in field two and then a
message. `count.awk` counts only exact ERROR and WARNING level fields. An INFO
message containing ERROR contributes neither an error nor a warning. `ERROR[42]`
is also a different level. On all three supplied files the complete result is
`errors=2 warnings=2`. Empty successful input gives two zero counts.

Every run prints `producer=N consumer=N` to stderr after immediately saving
Bash's `PIPESTATUS`. In the reference, status 0 means both cat and awk exited 0;
status 2 means invalid arguments or either stage failed. A printed summary
on status 2 is partial or unavailable, not a complete count. It is retained
for diagnosis, not hidden or replaced with invented zeroes.

## Healthy prediction and the intentionally misleading starter

From the selected role folder:

~~~bash
bash task.sh records/alpha.txt 'records/with space.txt' records/-dash.txt > healthy.txt 2> healthy.err
pipeline_status=$?
printf 'status=%s\n' "$pipeline_status"
cat healthy.txt
cat healthy.err
~~~

The unmodified starter succeeds here because its named TODO checks only awk.
Its defect becomes visible when cat reads one valid file and then fails to read
another. Predict the partial counts before running this changed case:

~~~bash
bash task.sh records/alpha.txt records/absent.txt > partial.txt 2> partial.err
pipeline_status=$?
printf 'status=%s\n' "$pipeline_status"
cat partial.txt
cat partial.err
~~~

With `absent.txt` genuinely absent, cat exits nonzero after the valid first
file; awk still reaches its normal END block and prints `errors=1 warnings=1`.
The starter returns 0 because it ignores cat's saved status. Correct the named
condition to include both original array entries. The completed implementation
returns 2 for this run. Preserve the partial output and actual diagnostics, then
explain why neither a printed number nor a successful final stage proves that
all input was available. Compare the reference after completing that repair.

## Why the status capture is placed there

By default a pipeline's status is its last command's status. `set -o pipefail`
changes that aggregate to the rightmost nonzero status, but it does not identify
all stage outcomes. `PIPESTATUS` records the separate stage results. The next
foreground command replaces it, so the array assignment immediately follows
the pipeline. With `errexit` enabled a failing pipeline can stop the script
before evidence is collected. The program uses `set +e` only around this
observation and restores `set -e` after saving the array. It then makes an
explicit final decision. Do not move a print, assignment to another variable,
or `|| true` between the pipeline and the array capture.

## Independent cases, consumer failure and restoration

Create an empty ordinary text file, run it as the sole input, and observe status
0 with both zero counts after the repair. Copy `alpha.txt` to a filename with
spaces and confirm that quoting keeps it one argument. Record what happens
when a valid input follows a missing one; incomplete input remains a failure
regardless of order.

In a disposable copy of the extracted role, preserve `count.awk` before making
its syntax invalid. Append an unclosed BEGIN block, run one supplied input,
then restore the exact original awk file:

~~~bash
cp count.awk count.awk.original
printf '\nBEGIN {\n' >> count.awk
bash task.sh records/alpha.txt > consumer.txt 2> consumer.err
pipeline_status=$?
printf 'status=%s\n' "$pipeline_status"
cat consumer.err
mv -- count.awk.original count.awk
bash task.sh records/alpha.txt > restored.txt 2> restored.err
restored_status=$?
printf 'restored=%s\n' "$restored_status"
~~~

The actual awk syntax error makes the consumer nonzero. Cat can either finish
its small write before that failure or receive SIGPIPE; record the observed
producer status instead of assuming a particular ordering. The reference and
completed starter return 2 either way. Restoring the original awk program and
rerunning the same input demonstrates recovery. The valid one-file summary is
`errors=1 warnings=1`.

Retain five completed notes tasks, the changed-case outputs, the actual input
failure and consumer-failure diagnostics, and the restored result. Remove only
the disposable test files created in the selected role folder. Reopen the saved
workspace and explain the repair before comparing the reference. A successful
reference run does not complete the learner's evidence record.

Primary references: [Bash pipelines](https://www.gnu.org/software/bash/manual/html_node/Pipelines),
[Bash PIPESTATUS](https://www.gnu.org/software/bash/manual/html_node/Bash-Variables.html),
and [GNU awk records and fields](https://www.gnu.org/software/gawk/manual/html_node/Fields.html).
