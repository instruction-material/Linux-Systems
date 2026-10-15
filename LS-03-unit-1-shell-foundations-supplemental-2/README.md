# Literal Search, Filename Boundaries and Three Outcomes

This optional transfer follows the required structured log-summary project.
It returns the names of text files containing a literal string. It does not
count severity fields, recursively discover files or edit input data. The
new work is a filename pipeline and the distinction between matches, no
matches and a failed search. Complete `search-notes.md` with actual evidence.
The prediction, inspection and explanation pauses support independent study
and a paced walkthrough.

## Equipment and stream contract

Use an ordinary account in an owned Linux lab with Bash, GNU grep and GNU sort.
Extract one role with its `records` folder. The site IDE edits, saves and exports
the workspace; run these commands in the external Linux lab after extraction.
No installation, system configuration or privileged access is part of the task.

`task.sh` accepts a nonempty literal string and one or more explicit ordinary
nonsymlink text-file paths. Each shell argument remains one filename. Quote
spaces, wildcard characters and newlines. The script rejects a standalone `-`
operand, directories, symbolic links and special files. A nonexistent or
unreadable file reaches grep and produces an actual tool error.

The pipeline is `grep -F -l -Z -e TEXT -- FILE... | sort -z -u`. `-F` interprets
text literally; `-e` protects a pattern beginning with a dash, and `--` ends
option parsing for the file operands. `-l` selects filenames rather than lines.
`-Z` terminates each filename with NUL; `sort -z -u` preserves that separator,
sorts the byte strings under the script's C locale, and removes repeated
identical path arguments. NUL cannot occur inside a Unix filename, while a
newline can. This does not merge different paths that happen to name the same
underlying file. Do not store a NUL stream in shell command substitution.

The reference returns 0 when at least one file matches and both tools succeed,
1 when no file matches and sorting succeeds, and 2 for invalid arguments or a
tool failure. stderr separately reports `grep=N sort=N`. stdout can contain
some valid names before an input fails. Status 2 makes that list incomplete;
discard it as a complete result. `grep -q` is deliberately absent because its
early success can conceal an error after a match.

## Predict, run and inspect the filename stream

From the selected role folder, predict the literal matches for `ERROR[42]`.
The supplied `alpha.txt` and `-dash.txt` contain that exact byte string;
`with space.txt` contains `ERROR4`, which is different literal text.

~~~bash
bash task.sh 'ERROR[42]' records/alpha.txt 'records/with space.txt' records/-dash.txt > first.bin 2> first.err
search_status=$?
printf 'status=%s\n' "$search_status"
cat first.err
while IFS= read -r -d '' file; do printf '%q\n' "$file"; done < first.bin
~~~

In the unfinished starter, the search and sort already run, but the final
status interpretation is the named TODO and always returns 2. Complete the
last decision using both saved array entries. A grep status of 1 is a valid
no-match outcome, while any nonzero sort status and a grep status greater
than 1 are failures. Keep the NUL separator, literal matching and input guards.
Compare the reference after recording a working attempt.

`PIPESTATUS` belongs to Bash and is replaced by the next foreground command,
even a diagnostic print. The assignment immediately after the pipeline saves
both original entries. `set +e` prevents an ordinary no-match status from
ending the script before that assignment; `set -e` is restored afterward.
`pipefail` alone supplies one aggregate status and cannot explain which tool
failed. Never add `|| true` and then report the search as successful.

## Changed cases and a filename containing a newline

Keep each run's output and diagnostic files separate. Use literal `ABSENT`
against all three supplied files: expect an empty NUL stream and status 1 in
the completed implementation. Repeat the matching call with `records/alpha.txt`
twice: its identical path appears once after `sort -u`. Compare a literal
`ERROR4` search against `ERROR[42]` and explain why a regular expression would
answer a different question.

Create the following disposable text file in the extracted role folder:

~~~bash
odd_file=$'records/two\nlines.txt'
printf '00:09 INFO ERROR[42]\n' > "$odd_file"
bash task.sh 'ERROR[42]' "$odd_file" records/alpha.txt > newline.bin 2> newline.err
search_status=$?
printf 'status=%s\n' "$search_status"
while IFS= read -r -d '' file; do printf '%q\n' "$file"; done < newline.bin
rm -- "$odd_file"
~~~

A line-based filename loop would split this one name. Retain the shell-quoted
observation and explain how the NUL boundary avoids that ambiguity.

Finally pass `records/alpha.txt` followed by a nonexistent path. Expect grep's
error, status 2 from the completed script and possibly a partial filename list.
An unreadable ordinary file is another failure case when available in the
owned lab; restore its original mode afterward. An empty list does not by
itself distinguish no matches from a failed search. Reopen the saved workspace
and retain the five completed notes tasks; a reference run does not complete
the evidence record.

Primary references: [GNU grep outcomes](https://www.gnu.org/s/grep/manual/html_node/Exit-Status.html),
[GNU grep filename separators](https://www.gnu.org/s/grep/manual/grep.html),
[GNU sort](https://www.gnu.org/s/coreutils/manual/html_node/sort-invocation.html),
and [Bash pipelines](https://www.gnu.org/software/bash/manual/html_node/Pipelines).
