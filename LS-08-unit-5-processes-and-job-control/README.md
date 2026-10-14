# Core project: observe processes, signals and interactive shell jobs

Operate one disposable program, predict each transition, and retain the actual
process and terminal evidence. This is the required Unit 5 process-control
project. Its troubleshooting notebook continues this same attempt.

## Equipment and the learner task

Use an owned Linux VM, WSL distribution or Linux terminal with Python 3.9 or
later, Bash with job control, procps `ps`, grep and coreutils (including mktemp, sleep and tee). Check `uname -s`, `id`,
`python3 --version` and `bash --version`. The interactive part requires a real
terminal or pseudoterminal; a web editor, redirected script or CI command
without a controlling terminal cannot demonstrate `fg` and `bg`.

Both roles supply the same working process_worker.py. It is lab equipment,
not an additional Python implementation assignment. The required unfinished
starter work is the named `process-evidence` task in process-notes.md: record
predictions, actual identities, observed states, raw output, exit statuses,
changed cases and cleanup, then explain the transitions. Reference notes give
the reasoning, not invented machine-specific IDs. Running working equipment
does not complete the observation record.

The program reports real PID, parent PID, numeric UID, process group and
session. It accepts --lifetime from 0.2 through 1800 seconds, default 600.
USR1 requests a snapshot; TERM normally records a graceful stop and exits 0;
INT records a stop and exits 130. HUP with an open output stream exits 129.
--ignore-term records TERM but keeps running for the controlled escalation
case. KILL cannot be caught and produces no final program record. An autonomous
deadline bounds a forgotten running process; it does not run while a process
is stopped. After continuation, elapsed wall time still counts toward it.

## 1. Launch and inspect a child

Begin in the selected role directory. Run commands individually in the same
Bash shell and keep it open so it can wait for its own child.

~~~bash
role_dir=$(pwd -P)
lab=$(mktemp -d "${TMPDIR:-/tmp}/unit5-process.XXXXXX")
printf 'EVIDENCE=%s\nSHELL_PID=%s\n' "$lab" "$$"
python3 -u "$role_dir/process_worker.py" --lifetime 600 >"$lab/cooperative.jsonl" 2>&1 &
pid=$!
printf 'CHILD_PID=%s\n' "$pid"
~~~

`&` starts an asynchronous command. `$!` captures that command's PID, not a
job number or the shell's `$$`. `-u` and the program's flush keep output
observable after redirection. `>` writes the file and `2>&1` directs errors
to the same destination. A launch is not proof that initialization succeeded.
Wait for the started record, with a bounded readiness check:

~~~bash
ready=0
for attempt in {1..50}; do
    if grep -q '"event":"started"' "$lab/cooperative.jsonl"; then
        ready=1
        break
    fi
    sleep 0.1
done
printf 'READY=%s\n' "$ready"
cat "$lab/cooperative.jsonl"
ps -p "$pid" -o pid,ppid,uid,pgid,sid,stat,args | tee "$lab/ps-running.txt"
jobs -l
~~~

Continue only with READY=1 and matching live PID, UID and command. The direct
child's PPID matches this Bash shell. A sleeping S state is ordinary while the
worker waits; state alone does not prove correctness. Optional `top -b -n 1 -p
"$pid"` gives a resource snapshot when procps top is installed. PID, process
group, session and job number describe different relationships. The shell's
jobs table contains its own jobs rather than every process on the machine.

## 2. Signal, observe and reap

~~~bash
kill -USR1 "$pid"
sleep 0.2
cat "$lab/cooperative.jsonl"
kill -TERM "$pid"
if wait "$pid"; then status=0; else status=$?; fi
printf 'WAIT_STATUS=%s\n' "$status" | tee "$lab/wait-status.txt"
cat "$lab/cooperative.jsonl"
ps -p "$pid" -o pid,ppid,uid,stat,args
~~~

Predict a snapshot from the same PID, followed by a TERM stopped record and
WAIT_STATUS=0. `wait` retrieves this child result and reaps its status; it is
not a timer. The `if` keeps a nonzero result observable even in a shell using
errexit. The final ps has no row for this ended child and returns 1. That is
the expected absence result. If the deadline already ended the worker, retain
that evidence and repeat in a fresh lab instead of signaling an old PID.

A terminated child can remain Z until its parent reaps it. Bash can reap jobs
asynchronously, so a fleeting or absent Z row does not disprove that mechanism.
An orphan has lost its original parent; its new PPID depends on namespace and
subreaper policy and is not invariably 1. Neither state means a program is
still doing useful work. Service supervision is a later unit.

## 3. A deliberate refusal and a changed case

Launch another worker into a new log in this owned directory:

~~~bash
python3 -u "$role_dir/process_worker.py" --ignore-term --lifetime 600 >"$lab/stubborn.jsonl" 2>&1 &
pid=$!
~~~

Repeat the bounded readiness check with stubborn.jsonl. Confirm this new PID,
owner and command with ps, then send TERM. Wait 0.2 seconds and inspect the log:
an ignored record and the same live PID demonstrate the refusal. Confirm that
identity again immediately before `kill -KILL "$pid"`. Use the same conditional
wait pattern and retain WAIT_STATUS=137. The operating system killed it; there
is no stopped record from the program. A zero result from `kill -0` would only
show existence/permission, not useful progress or graceful shutdown.

For a changed case, run `python3 process_worker.py --lifetime 0.5` in the
foreground. Record its actual identity, a deadline stop and status 0. Run
`python3 process_worker.py --lifetime nan` and record the distinct argument
diagnostic/status 2 with no started record. Do not turn either failure or
deadline text into a claim that a requested signal was handled.

## 4. Use actual terminal job control

Open a fresh interactive Bash inside the role directory:

~~~bash
bash --noprofile --norc -i
jobs -l
set -o | grep monitor
lab=$(mktemp -d "${TMPDIR:-/tmp}/unit5-terminal.XXXXXX")
printf 'TERMINAL_EVIDENCE=%s\nSHELL_PID=%s\n' "$lab" "$$"
python3 -u process_worker.py --lifetime 600 >"$lab/interactive.jsonl" 2>&1
~~~

The jobs table starts empty and monitor is on. The last command now owns the
foreground. Press **Ctrl+Z**, then run `jobs -l`. It reports a stopped job and
its actual PID. In this fresh shell that job is %1; use the displayed jobspec
if a different number appears. Assign pid to the exact displayed PID and use
ps to record its T state, PGID and session. A stop retains the process and its
identity; it is different from exit and cannot be reaped as completed work.

~~~bash
bg %1
jobs -l
kill -USR1 %1
sleep 0.2
cat "$lab/interactive.jsonl"
fg %1
~~~

`bg` continues the job without giving it the terminal foreground. The continued
and snapshot records have the same PID as before the stop. The Bash builtin
kill understands its own jobspec; an external command does not share that jobs
table. The worker does not read from the terminal, so it can continue safely
in the background. A background terminal reader can instead stop with TTIN.

After fg, press **Ctrl+C**, then immediately run:

~~~bash
printf 'FOREGROUND_STATUS=%s\n' "$?"
jobs -l
cat "$lab/interactive.jsonl"
~~~

The terminal sends INT to the foreground process group. This worker catches
it and exits 130; fg returns that result. The shell regains the foreground and
the job disappears. INT is catchable; KILL and STOP are not. Ctrl+Z uses TSTP,
which programs can handle, while this worker leaves its default stop behavior.
A script started without a terminal cannot demonstrate these terminal transitions. Record the actual terminal sequence and results, not a printed
prediction of it.

## 5. Explain, retain and clean up

Complete every process-notes.md item with actual observations. Explain the
difference between `$!`, `$$` and %1; PID/PPID/UID; S, T and Z; graceful exit,
ignored TERM, KILL, waiting, and foreground process groups. Compare the
reference reasoning after producing an attempt. Pause after each numbered
section for paced discussion, or follow the same sequence independently.

In each shell, inspect jobs and ps for the exact recorded identities, stop and
wait for any remaining owned worker, and confirm it is gone. Resume a stopped
job before requesting a graceful stop. Never target process names or PIDs that
the lab did not create. Preserve logs and notes, then remove only the exact
printed disposable evidence directory. `exit` leaves the fresh inner Bash;
retain and clean the outer shell's separate evidence directory as well.

References: [Bash job control](https://www.gnu.org/software/bash/manual/html_node/Job-Control-Basics.html),
[job-control builtins](https://www.gnu.org/software/bash/manual/html_node/Job-Control-Builtins.html),
[Linux process state](https://man7.org/linux/man-pages/man5/proc_pid_stat.5.html).
