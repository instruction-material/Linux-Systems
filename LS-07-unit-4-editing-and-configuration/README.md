# Unit 4: A validated configuration edit and rollback

This is the required Editing and Configuration project. The troubleshooting
notebook belongs to the same attempt. Optional environment-file transfer and
controlled-replacement work have separate purposes and are not prerequisites
for completing this core project.

The outcome is an observed operating loop: inspect, back up, edit, validate,
compare, apply, reload, observe and roll back. A successful file write alone is
not evidence that a running program accepted the change. This pack provides a
small process so the distinction can be tested without changing a system
service, opening a network listener, using root or editing /etc.

## Environment and files

Use an owned Linux VM, WSL distribution or Linux terminal with Bash, Python 3.9 or later,
GNU coreutils, diff and a terminal editor. This workflow uses GNU realpath and
chmod --reference; the complete shell workflow is not a macOS compatibility
claim. On an owned Debian/Ubuntu lab, missing tools can be installed with
`sudo apt-get install bash python3 coreutils diffutils nano`. No package install
is needed when these commands already exist.

Begin in this pack's `starter` directory. The `solution` directory contains one
working reference for later comparison. Each role includes:

- `config.json`: the valid baseline, with message `Baseline ready` and repeat 1.
- `candidate.json`: the proposed edit. The starter's repeat 9 is deliberately
  invalid; the reference uses repeat 2.
- `config_app.py`: the complete validator and disposable process. This is
  supplied operating equipment, not an additional Python assignment.
- `task.sh`: initialization, the named unfinished apply step and working
  rollback. Only the starter's apply section requires implementation.
- `edit-notes.md`: predictions, observations, diagnosis and recovery evidence.

JSON uses double-quoted keys and strings, commas between entries, and no
comments or trailing comma. The application accepts exactly `message` and
`repeat`. Message must contain 1 through 80 characters on one line. Repeat must
be an integer from 1 through 5; a string, boolean, duplicate key or unknown key
is rejected. Syntax validation and these application value rules are different
checks. An editor can save a syntactically valid file whose repeat is still 9.

## 1. Inspect and predict

~~~sh
pwd
sed -n '1,120p' task.sh
cat config.json candidate.json
python3 config_app.py validate config.json
python3 config_app.py validate candidate.json
~~~

The baseline prints `configuration valid` and exits 0. The untouched starter
candidate is rejected with exit 2 because repeat is outside its allowed range.
Run `echo "$?"` immediately after the command when recording an exit status.
Predict the result before running it. A command's visible text and its exit
status are both evidence.

## 2. Create one disposable lab

~~~sh
lab=$(mktemp -d "${TMPDIR:-/tmp}/unit4-edit.XXXXXX")
bash task.sh init "$lab"
printf 'LAB=%s\n' "$lab"
ls -la "$lab"
cp -p "$lab/config.json" "$lab/baseline.evidence.json"
~~~

Initialization requires an empty directory owned by the current account and
creates an ownership marker plus the two working configuration files. It
refuses a symbolic-link lab directory and later refuses symbolic links or
non-owned files at its three managed configuration paths. Keep the printed
absolute lab path. Never substitute a real service directory. The evidence
copy is independent of the controller's rolling `config.before.json` backup.

## 3. Observe a real running process

In terminal A, from the same role directory, run:

~~~sh
python3 config_app.py run "$lab/config.json"
~~~

It prints one JSON record with event `started`, its actual process ID, message,
repeat and rendered output. The baseline renders `Baseline ready` once. Leave
this terminal running. In terminal B, change to that same role directory and
assign `lab` to the exact printed LAB path, and `pid` to the actual PID reported
by this one disposable process. Replace the example text before running:

~~~sh
lab='/exact/LAB/path/printed/in/terminal/A'
pid=12345  # replace with this lab process's reported PID
kill -USR1 "$pid"
~~~

Use only the PID of the process just started for this lab. A signal is a small
notification to a process. Here USR1 requests a snapshot, HUP requests reload,
and INT or TERM requests exit. These meanings are implemented by this supplied
program; they are not universal meanings for every application. Terminal A
prints a `snapshot` record. Its PID stays the same throughout reload and
rollback, demonstrating an operating process rather than repeated fresh runs.

The program parses its file at startup and caches the accepted settings. Its
signal handlers request work, and the main loop validates a replacement before
swapping the cached settings. A rejected reload reports its reason and keeps
the previous accepted settings. Reading `rendered` shows the settings' effect
on the program's actual output.

## 4. Edit the candidate and inspect the difference

Use `nano "$lab/candidate.json"` or `vim "$lab/candidate.json"`. Set message to
`Edited configuration` and repeat to 2. In nano, Ctrl+O saves, Enter confirms the
filename, and Ctrl+X exits. In vim, press i to insert, Escape to leave insertion,
then type `:wq` and Enter to save and exit. `:q!` exits without saving.

~~~sh
python3 config_app.py validate "$lab/candidate.json"
diff -u "$lab/config.json" "$lab/candidate.json"
kill -USR1 "$pid"
~~~

Validation passes with these values. Diff exits 1 when the two files differ; that is not
a failed comparison command. Inspect the changed keys before continuing. The
running process still reports the baseline because editing the candidate does
not apply it. Quoting every path keeps a path containing spaces one argument.

## 5. Complete the starter's named apply step

First run `bash task.sh apply "$lab"`. The untouched starter reports
`unfinished: implement the validated apply step`, exits 78 and changes no
configuration or backup. This deliberate result is not a completed exercise.

Replace only the block between APPLY_BEGIN and APPLY_END in the starter's
`task.sh`. Implement these operations in order:

1. Run this role's Python validator on both the current file and candidate.
   Do not replace a known-good backup with an already invalid current file.
2. Copy current config to `config.before.json`, preserving its mode with cp -p.
3. Create a temporary file inside the lab with mktemp. Register an EXIT trap
   that removes that exact temporary path if any later step fails.
4. Copy the candidate to the temporary file and use chmod --reference with the
   current config to retain its mode.
5. Move the prepared file over `config.json`. Keeping the temporary file in the
   same directory allows the rename to replace that one directory entry
   atomically. It does not turn a whole multi-file deployment into a transaction.

The supplied variables are `$lab`, `$app` and `$here`. Invoke validation as
`python3 "$app" validate "$lab/candidate.json"`, with the corresponding current
path for the first check. Use `cp -p -- SOURCE DESTINATION`,
`staged=$(mktemp "$lab/.config.XXXXXX")`,
`trap 'rm -f -- "$staged"' EXIT`,
`chmod --reference="$lab/config.json" "$staged"` and
`mv -f -- "$staged" "$lab/config.json"` as the relevant shell building blocks.
The variables inside the single-quoted trap are expanded when the trap runs.

`set -euo pipefail` stops on an unhandled failed command, rejects an unset
variable and propagates a failed pipeline component. It does not validate
configuration semantics for the program. `umask 077` restricts newly created
files. `$BASH_SOURCE` locates the controller's supplied validator independently
of the current working directory. The guards and rollback are provided so the
assignment focuses on the validated apply ordering.

## 6. Apply, then explicitly reload

~~~sh
bash -n task.sh
bash task.sh apply "$lab"
cmp "$lab/config.before.json" "$lab/baseline.evidence.json"
cmp "$lab/config.json" "$lab/candidate.json"
kill -USR1 "$pid"
kill -HUP "$pid"
kill -USR1 "$pid"
~~~

Bash -n checks shell syntax without executing the script. Both cmp commands
exit 0, proving exact backup and applied bytes. The snapshot before HUP
still shows the baseline. Terminal A then reports `reloaded`, followed by a
snapshot rendering `Edited configuration Edited configuration`. Copying a file
and asking an application to reload it are separate operations.

## 7. Reject a changed case and prove rollback

Save exact copies of the active file and backup as evidence. Change the
candidate's repeat to 0, or add a second repeat key, and run apply again. It
must exit nonzero. Compare active and backup to the evidence copies; both must
remain byte-for-byte unchanged. Request a snapshot and confirm the process
still renders the accepted edited message twice.

~~~sh
cp -p "$lab/config.json" "$lab/active.evidence.json"
cp -p "$lab/config.before.json" "$lab/backup.evidence.json"
# Edit candidate.json to an invalid changed case before running the next line.
bash task.sh apply "$lab"
cmp "$lab/config.json" "$lab/active.evidence.json"
cmp "$lab/config.before.json" "$lab/backup.evidence.json"
kill -USR1 "$pid"
bash task.sh rollback "$lab"
cmp "$lab/config.json" "$lab/baseline.evidence.json"
kill -HUP "$pid"
kill -USR1 "$pid"
~~~

The final running output must again render `Baseline ready` once with the same
PID. Repeat with a different valid message containing spaces and repeat 3.
Predict the resulting rendered text. For an additional recovery investigation,
retain valid evidence, deliberately make only this disposable active file
invalid, and request HUP. Observe `reload-rejected` and the previous accepted
running output, then use the validated rollback and reload to restore it.

## Evidence, comparison and cleanup

Complete edit-notes.md with commands, predicted and observed results, exit
statuses, exact comparisons, the real PID, rejected change and final recovery.
Pause after each numbered section for discussion, or work through
the same sequence independently. Explain why validation precedes replacement
and why editing disk did not itself update the running output. Compare the
reference only after producing a working attempt and explain any differences.

Press Ctrl+C in terminal A and observe `stopped`. Confirm the lab process has
exited before removing only the exact disposable directory created above:
`rm -rf -- "$lab"`. Preserve the worksheet and any required evidence first.
Do not use an unrelated PID or a real configuration directory for cleanup.

The source verifier runs the starter, reference and an independent completion
against actual owned processes. Its Linux acceptance is retained separately
from site import/export acceptance. A local syntax check alone proves neither.
