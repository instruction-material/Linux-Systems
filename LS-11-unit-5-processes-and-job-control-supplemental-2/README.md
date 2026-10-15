# Optional transfer: one pipeline job, two processes and several statuses

Complete the required process-control core first. This separate transfer asks
how a job containing two processes differs from the core's single command.
Observe actual data flow, group-wide signals and failure propagation. Keep a
separate pipeline-notes.md attempt; the core notebook remains with the core.

## Supplied equipment and unfinished observation work

Use an owned Linux terminal, Python 3.9 or later, Bash, procps ps, grep and GNU
coreutils. Job control requires a controlling terminal. Both roles supply the
same complete pipeline_worker.py. The required unfinished work is the named
pipeline-evidence record in pipeline-notes.md. Reference notes explain the
relationships but do not supply fabricated local PIDs or observations.

The program has produce and consume modes. Produce writes JSON items to stdout;
consume reads those items from its stdin pipe and writes received records to
stdout. Both write diagnostic JSON to stderr, including real PID/PPID/UID,
PGID and SID. Redirecting diagnostic stderr separately keeps it out of the data
protocol. The at field is Unix wall-clock seconds for correlating records; it
is not CPU time. Consume refuses terminal input rather than silently reading
commands from the interactive shell.

--lifetime accepts 0.2 through 1800 seconds, default 600. Producer --count N
ends after N items; 0 means run until a signal or deadline. --exit-code chooses
its normal count-completion status from 0 through 125. Consumer --take N ends
after N items; 0 reads until EOF, a signal or deadline. Counts are 0 through
1000. Mode-inappropriate options and invalid values are rejected with status 2.

USR1 requests a diagnostic snapshot and CONT records a continuation. TERM
exits 0; INT exits 130. Produce restores the usual Unix SIGPIPE disposition:
writing after the pipe loses its reader can terminate it with SIGPIPE. That
signal cannot produce a final record from this program. A finite deadline is
a fallback, not evidence that a requested signal worked.

## 1. Start a fresh interactive job

From the selected role directory, start a fresh shell and confirm an empty
jobs table and monitor on. Unset prompt commands so status inspection has no
extra commands between the experiment and its diagnostic.

~~~bash
bash --noprofile --norc -i
unset PROMPT_COMMAND
jobs -l
set -o | grep monitor
lab=$(mktemp -d "${TMPDIR:-/tmp}/unit5-pipeline.XXXXXX")
printf 'PIPELINE_EVIDENCE=%s\n' "$lab"
python3 -u pipeline_worker.py produce --lifetime 600 2>"$lab/producer.jsonl" |
    python3 -u pipeline_worker.py consume --lifetime 600 >"$lab/received.jsonl" 2>"$lab/consumer.jsonl" &
last_pid=$!
printf 'LAST_PID=%s\n' "$last_pid"
~~~

The pipe connects producer stdout to consumer stdin. The final & backgrounds
the whole pipeline. In this fresh shell it is job %1. `$!` identifies its last
process, the consumer; it does not identify every process in the job. Confirm
both started records before interpreting a launch as readiness:

~~~bash
ready=0
for attempt in {1..50}; do
    if grep -q '"event":"started"' "$lab/producer.jsonl" &&
       grep -q '"event":"started"' "$lab/consumer.jsonl"; then
        ready=1
        break
    fi
    sleep 0.1
done
printf 'READY=%s\n' "$ready"
cat "$lab/producer.jsonl" "$lab/consumer.jsonl"
producer_pid=$(python3 -c 'import json,sys; print(json.loads(open(sys.argv[1]).readline())["pid"])' "$lab/producer.jsonl")
ps -p "$producer_pid,$last_pid" -o pid,ppid,uid,pgid,sid,stat,args
jobs -l
jobs -p
head -n 3 "$lab/received.jsonl"
~~~

Continue only with READY=1 and matching live identities/commands. The two PIDs
differ, share a process group, and belong to this shell's job. In this Bash
setup the producer leads that group, so jobs -p and the shared PGID differ
from the consumer's `$!`. The received records identify the actual producer and
consumer rather than a canned message. A job number is local to this shell;
a process group is the kernel grouping used for group signal delivery.

## 2. Stop and resume both members

~~~bash
kill -STOP %1
jobs -l
ps -p "$producer_pid,$last_pid" -o pid,ppid,uid,pgid,sid,stat,args
bg %1
kill -USR1 %1
sleep 0.2
cat "$lab/producer.jsonl" "$lab/consumer.jsonl"
tail -n 3 "$lab/received.jsonl"
~~~

Predict T for both members after STOP. The Bash builtin understands %1 and
signals the job's process group; a generic external command has no access to
this shell's job table. After bg, the same two identities continue, both record
CONT/snapshot events, and new data arrives. Compare sequence numbers before
and after, not just existence. Neither worker reads the terminal in this job.

Run `fg %1`, wait until it owns the foreground, and press Ctrl+C. Immediately
print `printf 'FOREGROUND_STATUS=%s\n' "$?"`. The foreground group receives
INT, the workers record their stops, and fg returns 130. Confirm jobs is empty
and neither recorded process remains. Record actual outcomes if a deadline or
another event happened first; repeat with fresh evidence rather than signaling
old PIDs.

## 3. Preserve component status before another command overwrites it

The next pipelines are bounded and run in the foreground. Before each, predict
the producer status, consumer status and overall pipeline status.

~~~bash
set +o pipefail
python3 -u pipeline_worker.py produce --count 3 --exit-code 7 2>"$lab/fail-default-producer.jsonl" |
    python3 -u pipeline_worker.py consume >"$lab/fail-default-received.jsonl" 2>"$lab/fail-default-consumer.jsonl"
printf 'PIPELINE_STATUS=%s COMPONENTS=%s\n' "$?" "${PIPESTATUS[*]}"
set -o pipefail
python3 -u pipeline_worker.py produce --count 3 --exit-code 7 2>"$lab/fail-checked-producer.jsonl" |
    python3 -u pipeline_worker.py consume >"$lab/fail-checked-received.jsonl" 2>"$lab/fail-checked-consumer.jsonl"
printf 'PIPELINE_STATUS=%s COMPONENTS=%s\n' "$?" "${PIPESTATUS[*]}"
~~~

Both component lists are 7 0. The producer completed three items and returned
the requested 7; the consumer received them, observed EOF and returned 0. By
default Bash reports the last command's 0. With pipefail it reports the
rightmost nonzero component, here 7. EOF is a pipe condition, not a guarantee
that upstream succeeded. Both parameter expansions happen before printf runs;
running cat or another command first would replace the status information.
Retain the printed diagnostics and actual JSON files.

## 4. A reader that deliberately ends early

~~~bash
set +o pipefail
python3 -u pipeline_worker.py produce --lifetime 5 2>"$lab/early-producer.jsonl" |
    python3 -u pipeline_worker.py consume --take 1 --lifetime 5 >"$lab/early-received.jsonl" 2>"$lab/early-consumer.jsonl"
printf 'PIPELINE_STATUS=%s COMPONENTS=%s\n' "$?" "${PIPESTATUS[*]}"
set -o pipefail
python3 -u pipeline_worker.py produce --lifetime 5 2>"$lab/early-checked-producer.jsonl" |
    python3 -u pipeline_worker.py consume --take 1 --lifetime 5 >"$lab/early-checked-received.jsonl" 2>"$lab/early-checked-consumer.jsonl"
printf 'PIPELINE_STATUS=%s COMPONENTS=%s\n' "$?" "${PIPESTATUS[*]}"
~~~

The consumer intentionally accepts one item and exits 0. The next write reaches
a closed pipe and terminates this producer with SIGPIPE. Bash reports its
component as 141 (128 + 13). Expect overall 0 without pipefail and 141 with it,
while both component lists remain 141 0. Inspect the actual early-reader and
producer records. Pipefail changes reporting, not the reason the consumer
stopped, and a nonzero upstream result does not by itself explain intent.

## 5. Explain and clean up

Complete pipeline-notes.md with predictions, both identities and group/session
relationships, stopped/continued states, data sequences, all four component
status comparisons and the actual signal/EOF records. Explain how a group-wide
action differs from signaling only the PID in `$!`. Diagnose one mismatch and
retain its correction. The reference supplies reasoning after an attempt.
Pause after each section for paced discussion or use the same sequence alone.

Inspect jobs and ps for the exact owned identities. Stop/reap any remaining
owned job before cleanup; resume a stopped job before graceful termination.
Preserve the evidence, remove only this printed temporary directory, then exit
the fresh inner shell. Restore the original shell's pipefail preference when
using an existing shell instead. This transfer does not change system services.

References: [Bash pipelines](https://www.gnu.org/software/bash/manual/html_node/Pipelines.html),
[job-control builtins](https://www.gnu.org/software/bash/manual/html_node/Job-Control-Builtins.html).
