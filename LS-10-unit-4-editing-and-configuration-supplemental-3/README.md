# Optional extension: previewed replacements and complete file recovery

Complete the required configuration-edit core first. This separate optional
extension practices a bounded batch edit. It does not repeat the core's live
reload exercise or the environment-file transfer. Its outcome is a previewed
change to exactly two named files, complete retained backups, validation before
application and exact recovery after a partial application.

## Setup and the deliberately small configuration format

Use an owned Linux terminal with Bash, Python 3.9 or later, GNU coreutils, sed
with -E support and diff. No system configuration, listener, service manager or
root account is needed. Start in `starter`; review `solution` after completing
an attempt. Each role contains task.sh, validate_config.py, primary.conf,
secondary.conf and replacement-notes.md.

This lab's literal key/value format has exactly one name, note and timeout.
An equals sign separates key from value, surrounding whitespace is ignored,
and # starts a comment. Blank lines and comment lines are allowed. Name and
note contain 1 through 80 characters. Timeout is an integer from 1 through 60
without leading zeros. Unknown, missing or duplicate keys are rejected. The
format does not evaluate shell assignments, quoting or variable expansions;
the .conf files are never sourced. The supplied Python validator reads that
format and checks a prepared file's timeout against the requested value.

The fixtures deliberately include numbers in names, notes and comments. A
broad replacement such as replacing every 10 would corrupt unrelated text.
The assignment is one anchored timeout setting, preserving its indentation,
spacing, inline comment and every unrelated byte.

## 1. Inspect and initialize exactly two files

~~~sh
cat primary.conf secondary.conf
python3 validate_config.py primary.conf
python3 validate_config.py secondary.conf
lab=$(mktemp -d "${TMPDIR:-/tmp}/unit4-replace.XXXXXX")
bash task.sh init "$lab"
printf 'LAB=%s\n' "$lab"
cp -p -- "$lab/primary.conf" "$lab/primary.evidence.conf"
cp -p -- "$lab/secondary.conf" "$lab/secondary.evidence.conf"
~~~

Primary starts with timeout 10 and secondary with timeout 20. Initialization
requires an empty owned directory and writes a lab marker. The controller uses
an explicit two-file list; it does not search /etc, follow symbolic links or
edit every file matching a glob. Quoted arguments keep paths with spaces intact.
The evidence copies are independent of the controller's later backups.

## 2. Complete the named replacement

Run `bash task.sh preview "$lab" 25` before editing the script. The untouched
starter reports `unfinished: implement the anchored timeout replacement`, exits
78 and leaves both current files unchanged. It cleans its temporary staging
directory and creates no backup. This is the named incomplete learner task.

Use nano or vim to replace only the block between REPLACE_BEGIN and REPLACE_END
in prepare_one. Its arguments are source, destination and new_value. Write a
sed -E substitution that matches a whole timeout setting line, captures the
prefix including whitespace, replaces only the digit sequence and retains the
suffix containing whitespace and an optional comment. Redirect to the supplied
destination, never to the source path. Redirection is opened before sed reads
input, so using the same filename on both sides can truncate the original.

Useful pattern parts are `^` and `$` for line boundaries,
`[[:blank:]]*` for spaces or tabs, `[0-9]+` for one or more digits, parentheses
for captured groups, and `(#.*)?` for an optional comment. In the replacement,
`\1` and `\2` reuse the captured prefix and suffix. The controller restricts
new_value to decimal integers in the allowed range before constructing the
expression. `--` ends command options before a filename. Run `bash -n task.sh`
after editing to check shell syntax.

The shell interprets the expression before sed receives it. A delimiter such
as | avoids combining the end-of-line $ anchor with @ into Bash's $@ argument
expansion; another delimiter requires appropriate shell quoting.

The supplied validator rejects missing or duplicate timeout keys before
preparation and then verifies the requested value in the staged result. A
replacement that silently changes no setting is not accepted as success.

## 3. Preview before applying

~~~sh
bash task.sh preview "$lab" 25
cmp "$lab/primary.conf" "$lab/primary.evidence.conf"
cmp "$lab/secondary.conf" "$lab/secondary.evidence.conf"
~~~

Predict both diff hunks before running preview. Only the timeout digits should
change to 25; names, notes and comments must stay byte-for-byte unchanged. Both
cmp commands exit 0 because preview leaves current files unchanged. Diff exits
1 when differences exist, so the controller distinguishes that ordinary result
from a diff error. A successful preview exits 0 after validating both prepared
files. Its private staging files are removed on exit.

Read the supplied orchestration around the learner function. It uses a private
mktemp staging directory, validates all current and prepared files before
application, preserves current modes with chmod --reference and registers an
EXIT trap to remove only that staging directory. `set -euo pipefail` handles
command failures; it is not a substitute for the format/value validator.

## 4. Apply and retain the complete backup identity

~~~sh
bash task.sh apply "$lab" 25
~~~

Record the exact `backup=...` path printed by this command. Set backup to that
path before the comparison and rollback commands; do not leave example text:

~~~sh
backup='/exact/backup/path/printed/by/the/apply/command'
cmp "$backup/primary.conf" "$lab/primary.evidence.conf"
cmp "$backup/secondary.conf" "$lab/secondary.evidence.conf"
python3 validate_config.py "$lab/primary.conf" --expect-timeout 25
python3 validate_config.py "$lab/secondary.conf" --expect-timeout 25
~~~

The controller copies both original files and their modes into a new backup
directory, writes its complete marker only after both copies succeed, then
prints the backup identity before replacement. Each rename replaces one file
atomically. The pair is not an atomic multi-file transaction: interruption or
a failed second rename can leave the first file changed and the second old.
That is why the complete backup is retained separately from temporary staging.
Do not infer an all-or-nothing batch from two successful validation commands.

## 5. Reject a faulty batch and restore both files

Copy the current files as fresh evidence. In only the disposable secondary
file, remove timeout or add a second timeout line. Predict the validation error
and run `bash task.sh apply "$lab" 30`. It must fail before replacing either
current file or creating a new complete backup. Compare the valid primary to
its fresh evidence and the deliberately edited secondary to its own faulty
evidence. Repair the fault or restore it from the complete backup before the
next successful batch. A failed preview also must leave current bytes unchanged.

To recover the retained original pair, including after a partially applied
batch, run:

~~~sh
bash task.sh rollback "$lab" "$backup"
cmp "$lab/primary.conf" "$lab/primary.evidence.conf"
cmp "$lab/secondary.conf" "$lab/secondary.evidence.conf"
~~~

Both comparisons must exit 0. Rollback accepts only a complete owned backup
directly inside this lab with the expected marker and two regular owned files.
It validates both backup files before replacing either current file. An invalid
backup must not silently overwrite a working configuration. The native gate
also forces the second rename to fail, observes the partial pair, and verifies
explicit rollback of both retained originals. It does not claim resilience to
arbitrary machine failure during a multi-file operation.

## 6. Changed cases and evidence

Repeat preview/apply/rollback with requested timeout 60, then 1. Try 0, 61 or
`2x`; the controller must reject them before editing. Change indentation and
an inline comment in an owned file and predict which bytes the anchored edit
preserves. Confirm that a commented example, a name containing 10 and the note
containing 10 and 20 stay unchanged. Replace one owned file with a symbolic
link to another disposable evidence file and confirm refusal without changing
that target. Restore a regular owned file afterward.

Record predictions, exact diffs, exit statuses, modes, complete backup paths,
unchanged-source comparisons, any observed partial state and exact recovery in
replacement-notes.md. Explain how an anchor differs from a broad text search
and why validation precedes application. For instructor pacing, pause after
each numbered section; the same sequence supports independent work.

Preserve the evidence and then remove only the exact disposable lab directory
created above with `rm -rf -- "$lab"`. This task starts no persistent process.
Native source acceptance covers the unfinished starter, reference, independent
completion, actual replacement failure and cleanup. Site import/save/review and
exact ZIP exports remain a separate acceptance gate.
