# Optional transfer: environment files and actual child processes

Complete the required configuration-edit core first. This optional transfer
asks a different question: which settings does a new process actually inherit,
and what happens when its assignment file changes after launch? Keep a separate
attempt and environment-notes.md. The core troubleshooting notebook continues
the core attempt rather than becoming another copy of this task.

## Setup, format and supplied equipment

Use an owned Linux terminal with Bash, Python 3.9 or later and GNU realpath.
No service manager, root access or package install is needed when these tools
already exist. Begin in `starter`; compare `solution` after completing an
attempt. This pack contains task.sh, settings.env, environment_app.py and the
evidence worksheet in each role.

The settings file is specifically a trusted **Bash assignment file**. It is
loaded by Bash's source builtin, so it can execute shell code. Use only the
owned demonstration assignments supplied and edited for this lab. This is not
a generic dotenv parser or systemd EnvironmentFile reader; those formats have
their own rules. There is no automatic variable substitution specification
shared by every file with an .env suffix.

The supplied file assigns `MESSAGE='Environment baseline'` and `REPEAT=2` but
does not export them. Single quotes keep the space inside MESSAGE and are
removed by the shell when it creates the value. Shell variable assignment and
environment export are separate operations. An exported variable is included
when a shell starts a child; an ordinary shell variable need not be.

The supplied application reads only MESSAGE and REPEAT from its own
os.environ. Message must contain 1 through 80 characters on one line. Repeat
must be one digit from 1 through 5. The application reports the actual PID, UID,
settings and rendered repetition. Use demonstration text in MESSAGE because
that value is printed. The application code is supplied; the learner task is
the named export section in task.sh.

## 1. Predict and make a disposable copy

~~~sh
cat settings.env
bash -n settings.env
lab=$(mktemp -d "${TMPDIR:-/tmp}/unit4-env.XXXXXX")
cp -- settings.env "$lab/settings.env"
printf 'LAB=%s\n' "$lab"
bash task.sh "$lab/settings.env"
echo "$?"
~~~

Bash -n checks shell syntax without running assignments. The untouched starter
reports `unfinished: export MESSAGE and REPEAT before launching the child`,
exits 78 and starts no application. That named unfinished outcome is not a
completed transfer. The launcher accepts an owned regular settings file and
refuses symbolic links. It resolves the filename before starting the child.

## 2. Complete the export section

Edit task.sh with nano or vim. Replace only the block between EXPORT_BEGIN and
EXPORT_END. After the supplied `source "$1"` line, export exactly MESSAGE and
REPEAT before launching Python. `export NAME OTHER_NAME` marks current shell
variables for inheritance. Leave the provided clean-environment launch, option
handling and exec statements intact. Check the script with `bash -n task.sh`.

The launcher uses `env -i PATH="$PATH"` to start a deliberately clean shell,
retaining only the command-search path. That makes the test independent of
MESSAGE or REPEAT already exported in the terminal. It does not erase the
parent terminal's environment. `bash --noprofile --norc` skips user startup
files. The child sources this lab's file, exports the named settings, applies
any explicit message override, then execs Python. Exec replaces that child
process rather than adding another long-running launcher.

`set -euo pipefail` handles failed commands, unset-variable use and pipeline
failures. It does not make Bash -n an application value validator. Python checks
the two values only after receiving the child environment.

~~~sh
bash task.sh "$lab/settings.env"
MESSAGE='Parent-only value' REPEAT=5 bash task.sh "$lab/settings.env"
bash task.sh "$lab/settings.env" --message 'Explicit override'
~~~

Predict each result. The first two calls both report Environment baseline and
repeat 2 because the child is deliberately cleaned before sourcing the file.
The third reports Explicit override and repeat 2: the explicit launcher option
overrides MESSAGE after sourcing, without changing the file. The rendered
string contains the chosen message twice. These are actual process environment
values, not text extracted from the file by the verifier.

To distinguish parent and child state, record the terminal's
`printf '%s\n' "${MESSAGE-unset}" "${REPEAT-unset}"` before and after a call.
Starting this child does not export its variables back into the parent.

## 3. Observe file edits versus a running environment

In terminal A, leave a watched child running:

~~~sh
bash task.sh "$lab/settings.env" --watch
~~~

It prints a started record with its actual PID. In terminal B, change to the
same role directory, set lab to the exact printed LAB path and pid to this
child's reported PID. Use only the process just started for this lab. Edit the
owned settings file to `MESSAGE='Changed disk value'` and `REPEAT=3`, then run:

~~~sh
bash -n "$lab/settings.env"
kill -USR1 "$pid"
~~~

The application implements USR1 as a snapshot request. It still reports
Environment baseline and repeat 2. Editing a file does not retroactively alter
the environment of an already running process. No reload feature is claimed
for this application. Press Ctrl+C in terminal A; it reports stopped. Start
the same launcher again and observe Changed disk value with repeat 3 and a new
PID. Record the actual two process identities and outputs.

## 4. Separate syntax failure from value failure

After stopping the watched child, retain a copy of the valid settings file.
Try these changes one at a time in the disposable copy:

- An unmatched quote: Bash -n fails, and the launcher stops before application
  launch. Repair the quote before the next case.
- `REPEAT=9`: Bash -n succeeds, but the launched application reports
  `invalid environment` and exits 2. Syntax validity is not value validity.
- Remove MESSAGE: the fresh child cannot obtain that setting from the caller;
  the application exits 2. Restore the assignment afterward.
- `MESSAGE='A different quoted choice'` with REPEAT=3: predict the three-copy
  rendered output, run it and compare. Verify that the quote characters are not
  part of the inherited value.
- An empty explicit `--message ''` override: the application rejects its value
  rather than treating it as no override.

The settings file remains unchanged when an explicit launcher override is
used. Keep the complete error text and immediate exit status for each changed
case. Do not interpret an application validation failure as a Bash parser
failure, or infer a file reload from a new process launch.

## Evidence and cleanup

Complete environment-notes.md with predictions, actual child values, PIDs/UIDs,
parent-state observations, file changes, restart results, overrides and both
types of failure. Explain source versus export, file versus environment, and
why a restart changes this program's settings. For instructor pacing, pause
after each numbered section and explain the observation before continuing.

Stop each watched child with Ctrl+C and observe stopped. Preserve the evidence
before removing only the exact disposable directory with `rm -rf -- "$lab"`.
The native source gate checks the unfinished starter, working reference and an
independent completion. Site consent, saved attempts and exact exports are
separate acceptance requirements.
