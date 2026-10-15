# Choosing an Interpreter and Preserving Arguments

This optional extension follows the readiness project and command-lookup
transfer. It investigates how a script is launched after its interpreter has
been located. It does not create a VM, install Bash, or repeat a file-search
pipeline. Complete `launch-notes.md` at the prediction, comparison, repair and
explanation pauses. The same steps support independent reading and a paced
walkthrough.

## Equipment and the supplied program

Use an ordinary account in an owned Linux lab with Bash at `/bin/bash`, a
working `/bin/sh`, and GNU coreutils. Ubuntu's `/bin/sh` normally uses Dash;
record the actual lab interpreter rather than assuming every Linux host has
the same implementation. The website IDE edits, saves and exports the files.
Execute them in the external Linux lab after extraction.

Read `args-demo.sh`. It stores the supplied arguments in a Bash array, reports
their count and prints one indexed value for each original argument. The
array syntax and arithmetic loop require Bash. The `.sh` filename does not
select an interpreter. The first line names `/bin/bash` for direct execution,
but an explicit `sh args-demo.sh` asks sh to read the source and bypasses that
choice. Some sh implementations accept extensions; its actual result belongs
in the notes. Successful execution by one implementation does not establish
portable POSIX shell syntax.

`task.sh` accepts an owned ordinary nonsymlink script followed by zero or more
arguments. Its supplied target is the inspected `args-demo.sh`. The reference
launches it with the running Bash and forwards `"$@"`, preserving separate
arguments, spaces, empty strings, literal wildcards and leading dashes. It
turns a relative script path into an absolute path before launch. It does not
evaluate the argument text as another command. The final `exec` replaces the
wrapper process, so the interpreter's status and diagnostics remain visible.

## Predict, run and repair the named interpreter choice

From the extracted role folder, record the environment and first invocation:

~~~bash
printf 'running_bash=%s\n' "$BASH_VERSION"
ls -l /bin/sh /bin/bash
bash task.sh ./args-demo.sh 'two words' '' > first.txt 2> first.err
first_status=$?
printf 'status=%s\n' "$first_status"
cat first.txt
cat first.err
~~~

The unfinished starter explicitly launches `/bin/sh`, even though the program
requires Bash. In a Dash-based lab it produces a real syntax error and nonzero
status. Repair only the named launcher to use the already running Bash with
`--noprofile --norc`, retaining the script path and quoted `"$@"`. Keep the
guards and `exec`. `BASH_ENV=/dev/null` prevents an optional noninteractive
startup file from adding behavior to this controlled launch.

After repair, expect status 0 and:

~~~text
argument_count=2
argument[0]=<two words>
argument[1]=<>
~~~

The empty second argument is present. Removing the quotes from `"$@"` can lose
it and split words or expand wildcard characters. Save the attempt before
opening the separate reference, which supplies a method rather than completed
observations from this lab.

## Direct execution differs from explicitly reading source

Create a private copy; retain the path printed by mktemp. Keep the original
role files unchanged during these mode experiments:

~~~bash
probe_root=$(mktemp -d)
printf 'probe_root=%s\n' "$probe_root"
cp -- args-demo.sh "$probe_root/demo.sh"
chmod 600 "$probe_root/demo.sh"
bash task.sh "$probe_root/demo.sh" 'two words' ''
wrapper_status=$?
"$probe_root/demo.sh" 'two words' ''
direct_status=$?
printf 'wrapper=%s direct=%s\n' "$wrapper_status" "$direct_status"
~~~

Explicit Bash reads the owned readable script even without its execute bit.
Direct execution needs execute permission and a usable shebang/interpreter;
the 0600 case gives a real permission diagnostic and Bash status 126. Record
that diagnostic separately from a syntax error. Then set only the private
copy to mode 0700 and repeat direct execution. On a filesystem that permits
execution, its correct shebang selects Bash and the argument report succeeds.
A noexec mount can still reject direct execution; record that environment
limit rather than claiming the mode bit alone guarantees success.

Compare `/bin/sh "$probe_root/demo.sh" 'two words' ''` against
`/bin/bash "$probe_root/demo.sh" 'two words' ''`. In a Dash-based lab the first
fails at Bash-only syntax and the second succeeds. Neither explicit call asks
the kernel to choose an interpreter from the file's first line.

## Changed arguments, failure, recovery and cleanup

Run the repaired wrapper with no demo arguments, then with `'*.txt'`,
`'-n'`, an empty argument and a value containing a newline. Predict the exact
count and retained boundaries before each call. A literal wildcard remains
literal; the wrapper does not search the directory. Invoke the wrapper by its
absolute path from another directory and pass the demo's absolute path to
separate the script location from the caller's working directory.

For an actual read failure, save the private copy's mode, remove its read and
execute permissions, run the wrapper as the ordinary account and retain its
nonzero status and diagnostic. Restore mode 0600 and verify explicit Bash
recovery. A directory, symlink, missing target or missing argument is instead
an input rejection with status 2; the wrapper does not silently follow it.

Retain all five notes tasks, including original and repaired commands, actual
interpreter observations, changed arguments, failure and recovery. Verify the
original demo bytes and caller's working directory are unchanged. Remove only
the private copy and its now-empty parent after preserving the evidence:

~~~bash
rm -- "$probe_root/demo.sh"
rmdir -- "$probe_root"
~~~

Primary references: [Bash shell scripts](https://www.gnu.org/software/bash/manual/html_node/Shell-Scripts.html),
[Bash invocation](https://www.gnu.org/software/bash/manual/html_node/Invoking-Bash.html),
[Bash special parameters](https://www.gnu.org/software/bash/manual/html_node/Special-Parameters.html),
and [Bash exit status](https://www.gnu.org/software/bash/manual/html_node/Exit-Status.html).
