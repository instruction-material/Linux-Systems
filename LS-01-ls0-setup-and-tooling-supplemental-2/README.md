# Command Lookup, Version Checks and Real Failures

This optional transfer follows the Linux identity and readiness project. It
investigates a tool marked available in a command inventory: which executable
is selected, and does its actual version request succeed? It does not install
software or repeat the shell unit's log-summary project. Complete
`lookup-notes.md` using the prediction, observation and explanation pauses.
The same sequence supports independent reading and a paced walkthrough.

## Equipment and the two observations

Use an ordinary account in an owned Linux lab with Bash and GNU coreutils.
Extract one role with its complete `tools` folder. Read all three tiny supplied
`lab-tool.sh` files before executing them. They are inspected course fixtures,
not downloads or substitutes for installed programs. The website IDE edits,
saves and exports the files; execute the commands in the external Linux lab.

The first tool prints `lab-tool first 1.0`; the second prints
`lab-tool second 2.0`. Both exit 0. The failing tool writes
`controlled version failure` to stderr and exits 23. Each accepts only
`--version`. These controlled outputs isolate lookup from actual execution.
They do not certify that any real course package is installed or trustworthy.

`PATH` is an ordered, colon-separated list of search directories. A slash-free
command name can select a different executable when that order changes. A
shell can also resolve functions, builtins and cached names. This lab uses a
fresh noninteractive Bash for each lookup and run, the fixed external name
`lab-tool.sh`, and only the explicit inspected tool directories. It does not
model every interactive shell's aliases, functions or command cache.

`task.sh` first runs `command -v lab-tool.sh` and retains its status and path.
It then actually runs `lab-tool.sh --version`, retaining the real stdout,
stderr and exit status. A found command can fail. The reference reports usable
only when both observations succeed. Here usable means this version request
succeeded; it does not prove every feature of a program works.

The script changes PATH only in its two child Bash environments. It retains
the absolute path of the running Bash before that change and disables optional
startup-file loading for those children. The calling shell's PATH is unchanged.
It writes no input files, installs nothing and changes no system configuration.

## Predict and observe both search orders

ZIP extraction can omit executable mode bits. From the extracted role folder,
inspect the files, then make only these supplied fixtures executable:

~~~bash
chmod u+x tools/first/lab-tool.sh tools/second/lab-tool.sh tools/failing/lab-tool.sh
role_root=$(pwd -P)
path_before=$PATH
bash task.sh "$role_root/tools/first:$role_root/tools/second" > first.txt 2> first.err
first_status=$?
printf 'report_status=%s\n' "$first_status"
cat first.txt
cat first.err
test "$PATH" = "$path_before"
~~~

Expect lookup status 0, the first tool's path and version, run status 0 and
`usable=yes`. Repeat with second before first, saving different report files.
Predict the changed version before running. Neither order changes the other
tool's contents or any installed program.

## A present command that fails

Put failing before first and save all three channels:

~~~bash
bash task.sh "$role_root/tools/failing:$role_root/tools/first" > failed.txt 2> failed.err
failed_status=$?
printf 'report_status=%s\n' "$failed_status"
cat failed.txt
cat failed.err
~~~

Lookup still succeeds, the failing path is selected, run status is 23, and the
controlled error reaches stderr. The named TODO in the starter checks only
lookup status and incorrectly reports usable with report status 0. Repair that
last condition to require both saved statuses to be 0. Preserve the real tool
calls, their separate statuses and stderr. After repair, expect `usable=no`
and report status 1. Compare the separate reference after saving an attempt.

## Missing command, recovery and transfer

Create a private empty search directory and retain its printed path:

~~~bash
empty_search=$(mktemp -d)
printf 'empty_search=%s\n' "$empty_search"
bash task.sh "$empty_search" > missing.txt 2> missing.err
missing_status=$?
printf 'report_status=%s\n' "$missing_status"
cat missing.txt
cat missing.err
rmdir -- "$empty_search"
~~~

Expect lookup status 1, an empty resolved value, Bash's actual command-not-found
diagnostic and run status 127. The report exits 1. Recover by using the first
tool directory and retain its successful output separately. Do not install a
package to manufacture recovery for this controlled case.

For a changed case, remove execute permission from the first fixture, search
first:second, then restore its original mode. Predict whether the second tool
is selected; record the actual resolved path. Restrict this change to the
inspected course fixture. The script rejects empty, relative, missing, symlink
or unowned directory entries and line breaks; it does not accept a colon as
part of one directory name. Argument errors return 2 before the tool checks.

Complete the five notes tasks with the actual paths, statuses, failure and
recovery. Reopen the saved attempt and verify the original tool bytes and
calling PATH remain intact. Remove only the private case and generated report
files after retaining the evidence. A successful reference run does not fill
in this record or prove the readiness of a real installed tool.

Primary references: [Bash command search](https://www.gnu.org/software/bash/manual/html_node/Command-Search-and-Execution.html),
[Bash command builtin](https://www.gnu.org/software/bash/manual/html_node/Bash-Builtins.html),
and [Bash exit status](https://www.gnu.org/software/bash/manual/html_node/Exit-Status.html).
