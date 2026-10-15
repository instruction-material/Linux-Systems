# Optional extension: zombies, waiting and an observed adopter

Complete the process-control core first. This separate extension observes what
happens after exit or loss of a parent. It does not repeat the core's signal
exercise or the pipeline transfer. Keep a separate adoption-notes.md attempt.

## Equipment, boundaries and unfinished observation work

Use an owned Linux VM, WSL distribution or Linux terminal with /proc, Python
3.9 or later, the standard C library and procps ps. No root, service-manager
change, new namespace or system-wide setting is needed. The supplied program
enables and reads back the child-subreaper attribute on **its own new process**.
Its descendants remain inside this disposable experiment.

Both roles supply the same complete adoption_lab.py. The required unfinished
work is the named adoption-evidence record in adoption-notes.md. Reference
notes explain the relationships without pretending to contain this machine's
PIDs or raw observations. Equipment success does not complete the record.

The at field is Unix wall-clock seconds. A child startTicks value is its Linux
start time in clock ticks since boot; compare it with PID to recognize the same
birth identity, rather than confusing it with a wall-clock timestamp or status.

PID names a process, PPID names its current parent, and UID is its account
identity. A zombie has exited but its parent has not yet collected the result.
It cannot do more work or handle signals. An orphan has lost its original
parent. On Linux it can be adopted by the nearest living ancestor marked as a
subreaper; otherwise namespace/init policy determines the adopter. Do not assume
that every new PPID is 1. These are different state and relationship questions.

This experiment explicitly makes its observer a subreaper, confirms that flag,
and later verifies the actual adopter through /proc. Child processes do not
inherit that flag. The demonstration changes this one process's role rather
than silently changing how the whole machine supervises processes.

## 1. Read and predict the two stages

The first child exits 7 immediately. The observer deliberately leaves it
unreaped during an observation window, confirms real Z state and its actual
parent/UID, then waits for that exact child and records 7.

The second stage creates an original parent and its child. Pipes keep the
original parent alive until its child's initial identity has been observed.
Only then does the observer release that parent and wait for its exit 0. The
grandchild remains alive, loses its original parent, and is adopted by the
explicit subreaper. Its PID, birth time and UID remain unchanged while PPID
changes to the observer. After a second observation window, another pipe release
lets the adopted child exit 9. The observer can now wait for that adopted child.

--hold-seconds accepts 0.1 through 120, default 5, for each observation window.
The children have separate bounded lifetimes and close unused pipe ends. Normal
completion and a handled interruption clean up and reap the owned descendants.
SIGKILL cannot run a process's cleanup code; use ordinary Ctrl+C/TERM when
examining this program's interruption path.

## 2. Start in terminal A and retain the actual identities

From the selected role folder:

~~~bash
uname -s
id
python3 --version
lab=$(mktemp -d "${TMPDIR:-/tmp}/unit5-adoption.XXXXXX")
printf 'ADOPTION_EVIDENCE=%s\n' "$lab"
python3 -u adoption_lab.py --hold-seconds 60 --record "$lab/observations.jsonl"
~~~

Keep terminal A running. The first started record identifies the observer,
its actual UID and the observed subreaper flag. The spawned and zombie_observed
records give the first child PID and actual Z state. In terminal B, use Bash
and enter the exact evidence directory printed by terminal A. The following
assignments read the observer and first child from that run's saved JSON lines:

~~~bash
read -r -p 'Evidence directory printed by terminal A: ' lab
observer=$(python3 -c 'import json,sys; print(next(r["pid"] for r in map(json.loads,open(sys.argv[1])) if r["event"]=="started"))' "$lab/observations.jsonl")
child=$(python3 -c 'import json,sys; print(next(r["child"]["pid"] for r in map(json.loads,open(sys.argv[1])) if r["event"]=="zombie_observed"))' "$lab/observations.jsonl")
ps -p "$observer,$child" -o pid,ppid,uid,pgid,sid,stat,args
~~~

Predict the first child's PPID and Z state, then compare with ps and the JSON
record. Retain the real ps output. The observation window is finite. If it
has ended before inspection, keep the record and rerun in a fresh evidence
directory rather than inspecting a possibly reused old PID.

## 3. Observe waiting and actual adoption

After the first window, a reaped record reports the first child's status 7.
The next spawned and grandchild_observed records identify the original parent
and its child before reparenting. The program uses a pipe handshake so the
original parent cannot exit before that initial relationship is observed.

An adopted record then reports the same grandchild birth identity and UID, its
actual new PPID, and the original parent's PID. During the second window,
read the adopted child's actual PID in terminal B, then inspect it:

~~~bash
child=$(python3 -c 'import json,sys; print(next(r["child"]["pid"] for r in map(json.loads,open(sys.argv[1])) if r["event"]=="adopted"))' "$lab/observations.jsonl")
ps -p "$observer,$child" -o pid,ppid,uid,pgid,sid,stat,args
~~~

Compare
the actual new PPID with the observer's PID. The original parent has already
been waited for with status 0. The grandchild is alive while waiting on its
release pipe; its ordinary sleeping state is different from the earlier Z.

After the second window, the observer releases and waits for the adopted child,
records status 9 and reports cleanup with no owned children and closed pipe
descriptors. Back in terminal A, immediately retain:

~~~bash
printf 'PROGRAM_STATUS=%s\n' "$?"
~~~

Normal program status is 0. The internal child statuses 7, 0 and 9 are
observations, not an automatic failure of the overall experiment. --record
writes the same events to a new evidence file and refuses an existing path
before spawning children, with diagnostic status 2. To check this protection,
repeat the same command with the same --record path after a completed run;
confirm that it refuses and leaves the saved bytes intact. Use a fresh path
for each further experiment. Keep the displayed output and recorded events.

## 4. Change a case and distinguish an interruption

Repeat with --hold-seconds 0.5 and fresh evidence. The shorter observation
windows do not change which child exits 7, which parent exits 0, or which
adopted child exits 9. Record the new actual IDs and timing instead of copying
the first run. Run `python3 adoption_lab.py --hold-seconds nan` and retain its
argument diagnostic/status 2; no started record is produced.

For a separate interrupted run, use a new evidence filename:

~~~bash
python3 -u adoption_lab.py --hold-seconds 60 --record "$lab/interrupted.jsonl"
~~~

After zombie_observed appears, press Ctrl+C. Immediately print the program's
status. The observer records interruption and cleanup, returns 130, and reaps
its exited child. This is not a completed two-stage adoption case; retain a
normal run separately. A display pipe can close before final output, so the
explicit record file retains evidence independently of that display stream.
The native gate also interrupts after adoption to check that remaining owned
descendants are cleaned in that phase.

If /proc or the subreaper operation is unavailable, retain the diagnostic and
use an owned supported Linux environment. Do not replace actual reparenting
with a predicted diagram or treat a different platform as Linux acceptance.

## 5. Explain, retain and clean up

Complete adoption-notes.md with predictions, raw event and ps records, UID/PID
and parent identities, the two Z/live observations, all wait results, the
subreaper flag, the actual new parent, the changed run and interruption. Explain
why KILL cannot remove an already exited zombie and why the parent/adopter must
collect its result. Identify the evidence that excludes a race where the
original parent disappeared before its child was first observed.

The same numbered sequence supports independent reading or pauses for paced
discussion. Compare the reference reasoning after an attempt. Confirm that the
observed processes are gone, retain the evidence, then remove only each exact
printed disposable directory. The program's owned child cleanup does not remove
the saved evidence directory. Record any failure and correction before treating
the experiment as complete.

References: [waiting and zombie state](https://man7.org/linux/man-pages/man2/waitpid.2.html),
[the child-subreaper attribute](https://man7.org/linux/man-pages/man2/PR_SET_CHILD_SUBREAPER.2const.html).
