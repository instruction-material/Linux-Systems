# Progress Budgets, Worker Stalls and Explicit Failures

This optional extension investigates a time-bounded operating question. A PID
or active job is not evidence of useful progress, and a missing PID can mean
successful completion or failure. Classify the observed work against a declared
budget while retaining the actual clock, state and event evidence.

## Classification and the declared budget

Complete classify_progress in task.py. Return failed for a sampled failed unit
or exit-code result. Return complete only when the successful exited oneshot
also has its completion event. Otherwise compare now_ns with the current start
event's monotonicNs: return overdue at or beyond budget_ns, and waiting before
that deadline. The comparison concerns the recorded sample time; it is not a
claim about monitoring notification latency or an external uptime objective.

The good worker exits zero after producing its current output. The hanging
worker records its actual start and remains in a real live manager-owned
process until cleanup. Observe it before the budget and again after the
elapsed budget: waiting then overdue. The failed worker emits an error and
actually exits 7; the manager retains its failed/exit-code evidence. The
starter infers completion from MainPID=0, so it conflates that failure with
successful completion and cannot recognize an overdue live worker.

The default progress budget is 1.2 seconds. --budget-seconds accepts 0.8, 1.2
or 2.0. It changes the declared observation window, not the system clock.
The equipment reports failure if its early sample arrives too late to prove
the before-deadline case; it does not invent an earlier observation. Run with
--reverse to change the order of good, hanging and failed jobs, then compare
the same state and time relationships. An overdue sample proves no completion
by that declared deadline, not that all future recovery is impossible.

## Environment and exact role files

Use Bash and Python 3.8+ in an owned disposable Linux environment, as an ordinary
non-root account with an available own-user systemd manager and readable own-user
journal. systemctl, systemd-run and journalctl must already be installed. The
earlier readiness, service, logging and scheduling units establish those
prerequisites. Do not treat a host shell or a missing manager as a successful
substitute. The equipment reports the actual prerequisite failure with status 2.

Keep task.sh, task.py, studio_observer.py, studio_worker.py and
observability-notes.md together. The site IDE edits, saves and exports this
selected role; operating commands run in the external Linux terminal. Only the
named function in task.py is the learner repair. The observer and worker are
supplied equipment, and the worksheet remains independent in both roles.

The manager supplies one INVOCATION_ID per runtime cycle. RemainAfterExit=yes
keeps a successful oneshot active after its process exits. RemainAfterElapse=yes
keeps the elapsed timer queryable. These settings retain observation state;
they do not establish that the intended output was produced. The linked primary
references describe those settings separately from this project's policy.

## Predict, run and inspect

From the exported role folder, create one explicit empty private parent:

~~~bash
lab_root=$(mktemp -d)
bash task.sh "$lab_root" > observation.json 2> observation.err
observation_status=$?
printf 'status=%s\n' "$observation_status"
cat observation.err
python3 -m json.tool observation.json
~~~

The equipment uses only fresh classes-observe-<32-hex> names in the own-user
manager. Each actual timer starts its service after a short monotonic delay;
there is no persistent unit installation or repeating schedule here. The report
retains LastTriggerUSec, service state, invocation, worker events and real journal
records. Only the correlation transfer additionally restarts its primary service
for a manual retest. No other activation is claimed to have been scheduled.

Status 0 requires the policy to match every recorded case. An unchanged starter
returns 1 after preserving its differing decisions. Status 2 reports a setup or
equipment failure; status 130 reports an interrupted observation. A reference
run establishes equipment behavior, not a completed independent worksheet.

Keep the exact CLI argv, child PIDs, output, stderr, statuses and times with the
manager and application observations. The worker records its PID, ordinary UID,
manager invocation and both wall and monotonic timestamps. Hanging workers are
also observed through their real /proc command line and UID. Journal _PID/_UID,
boot and user-unit identities must agree with the selected worker observations.

## Changed case, interruption and recovery

~~~bash
bash task.sh "$lab_root" --reverse > changed.json 2> changed.err
changed_status=$?
printf 'status=%s\n' "$changed_status"
~~~

The now-empty parent is reused for a newly generated case; identifiers and
timestamps change. Compare the intended relationships rather than copying
earlier values. For an independent live inspection, run a held observation:

~~~bash
bash task.sh "$lab_root" --hold-seconds 15 > held.json 2> held.err
~~~

This creates a separate actual timer-triggered hanging worker before the ordinary
cases. ready.json under lab_root identifies the observer, exact owned service
and live worker PID. In another terminal inspect that named user unit, its timer
and journal. Ctrl-C in the observer terminal requests status 130 and owned cleanup.
Repeat normally after the interruption for a real recovery run. A killed terminal
cannot guarantee cleanup; retain the recorded names and stop only those exact
owned timer/service units before removing their private files. Never use broad
unit-stop or journal-vacuum commands for this exercise.

Missing, nonempty or symlink parents, root/non-Linux operation, unavailable
tools/manager and holds outside 0–15 are refusals. Existing input files must stay
unchanged. Try a parent containing spaces and keep an unrelated sentinel outside
it. Change no global manager, account, privilege or journal configuration.

## Cleanup, evidence and paced use

The equipment stops only the generated timers/services, resets only its own
failed unit if needed, verifies those transient units unloaded and their observed
workers exited, removes its private case and ready file, and preserves source
files. It leaves the real journal intact. Inspect statesAfterCleanup,
ownedWorkerPidsGone, ownedCaseRemoved, workspaceEmpty and sourceUnchanged. Preserve
the report and worksheet elsewhere, then use rmdir on the exact empty parent.

Complete observability-notes.md with environment, prediction, actual manager and
journal identities, output or progress evidence, the named repair, changed case,
refusal, interruption, recovery and verified cleanup. A paced walkthrough follows
the same predict, operate, inspect, correct and repeat sequence. Keep application
expectation and the limits of the captured observation explicit in the runbook.

Primary references: [runtime invocation environment](https://github.com/systemd/systemd/blob/main/man/systemd.exec.xml),
[oneshot and retained service state](https://github.com/systemd/systemd/blob/main/man/systemd.service.xml)
and [elapsed timer state](https://github.com/systemd/systemd/blob/main/man/systemd.timer.xml).
