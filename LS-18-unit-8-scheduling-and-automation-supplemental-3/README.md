# Repeating User Timers and Completed Oneshot State

This optional extension follows the backup core and calendar forecast
transfer. It observes actual activations of a short owned user service. The
question is how a completed oneshot becomes eligible for another inactivity
trigger. It does not install a persistent schedule or repeat archive retention.
Complete `timer-notes.md` at the prediction, trace, repair and cleanup pauses.
The same sequence supports independent reading and a paced walkthrough.

## Equipment and ownership boundary

Use an ordinary account in a disposable owned Linux lab with Bash, Python 3.8+
and installed systemctl/systemd-run. The account needs an available systemd
user manager: `systemctl --user show --property=Version --value` must succeed. Use the core
service lab to establish that environment first. Do not apply this exercise
to a shared or production account. Keep task.sh, timer_observer.py and
timer_worker.py together. The site IDE edits, saves and exports them; execute
them in that external Linux lab.

The observer accepts an explicit empty owned nonsymlink workspace. It creates
only a fresh private case there and uniquely named classes-scheduling-* user
units. It uses transient units, never writes installed unit files, enables a
boot schedule, reloads the manager or changes another service. The actual
systemd-run and systemctl commands, results and worker events are retained in
the report. A missing manager is an actual prerequisite failure.

## Predict the service state before running

Type=oneshot waits for its short action to finish. With RemainAfterExit=yes,
successful completion leaves the service active even after the worker exits.
With no, it returns to inactive. OnUnitInactiveSec measures a delay from that
deactivation; an active completed service cannot supply the next deactivation.
The timer's initial OnActiveSec gives the first activation. These are monotonic
delays, distinct from the calendar dates in the transfer.

The tiny worker records its actual UID, PID and monotonic start/end timestamps
around a short sleep. A single timer/service pair does not start another copy
while that service is still active. Compare complete event pairs and service
states; a missing end after interruption is partial work, not a completed run.
The small AccuracySec value and zero random delay make the short observation
practical; they do not promise exact timestamps under load.

From the extracted role folder, retain the printed workspace path:

~~~bash
lab_root=$(mktemp -d)
printf 'lab_root=%s\n' "$lab_root"
bash task.sh "$lab_root" short > first.json 2> first.err
first_status=$?
printf 'status=%s\n' "$first_status"
cat first.err
cat first.json
~~~

The starter's named TODO uses RemainAfterExit=yes. Expect one completed
activation followed by active/exited state, report status 1 and no repeat.
Repair only that property to no. Preserve the actual user units, worker,
inactivity delay and cleanup. In the reference, three completions normally
finish the observation early; otherwise the bounded window is retained as
actual evidence. Status 0 requires at least two completed nonoverlapping
activations. A count below that threshold is not silently called success.

## Observe the changed duration and inspect actual states

Use a fresh empty workspace, run profile long and compare the event times.
The worker changes from 0.10 to 0.45 seconds; the inactivity delay remains 350ms.
Retain the longer gap between successive starts and verify the previous end
precedes the next start. The report retains statesBeforeCleanup for the actual
timer and service, then statesAfterCleanup proving their removal.

The observer stops only its two generated units in finally, waits for them to
unload and checks that every observed worker PID has exited. It removes only
its generated ready file and private case. The supplied workspace is empty
again. Preserve the actual unit name, command results, complete and partial
events and cleanup fields before removing the report files.

For an independent user-manager comparison, choose a new unique manual name:

~~~bash
manual_unit="classes-scheduling-manual-$UID-$$"
systemd-run --user --quiet --collect --unit="$manual_unit" --property=Type=oneshot --property=RemainAfterExit=no --on-active=1s --on-unit-inactive=2s --timer-property=AccuracySec=10ms /usr/bin/printf 'manual activation\n'
systemctl --user list-timers --all "$manual_unit.timer"
journalctl --user -u "$manual_unit.service" --no-pager
systemctl --user stop "$manual_unit.timer" "$manual_unit.service"
~~~

Allow actual time for repeated activations before inspecting the journal. If
the lab does not retain that user journal, record that limitation; the earlier
worker report is separate actual evidence. Verify the named manual units are
gone after stopping them. Do not use broad stop/reset patterns.

## Interruption, recovery and completion record

With another fresh empty workspace, use --seconds 8, wait for its ready.json
and worker events, then interrupt the foreground wrapper with Ctrl-C. The
observer handles the request, stops its own units and emits a report with
interrupted=true and status 130. A worker may have a start without an end;
verify cleanup rather than counting it as completed. A subsequent normal run
in the now-empty workspace provides recovery evidence.

A missing/nonempty/symlink workspace or invalid profile is an input rejection
with status 2. Preserve any existing sentinel instead of clearing the directory
to make the guard pass. Finish the five notes tasks with the named repair,
actual UIDs, PIDs, timing, states, changed case, interruption, recovery and undo.
A successful reference observation does not complete that independent record.

Remove only an empty lab parent after preserving the report:

~~~bash
rmdir -- "$lab_root"
~~~

Primary references: [systemd timer behavior](https://github.com/systemd/systemd/blob/main/man/systemd.timer.xml),
[oneshot service state](https://github.com/systemd/systemd/blob/main/man/systemd.service.xml),
and [transient user units](https://github.com/systemd/systemd/blob/main/man/systemd-run.xml).
