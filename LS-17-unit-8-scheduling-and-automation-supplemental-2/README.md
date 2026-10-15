# Calendar Expressions and Explicit Clock Anchors

This optional transfer follows the backup and user-scheduler core. It asks
when a systemd calendar expression next elapses from a chosen point in time.
It does not create a backup, install a timer or repeat a log-summary exercise.
Complete `calendar-notes.md` at each prediction and comparison pause. The same
sequence supports independent reading and a paced walkthrough.

## Equipment and the forecast contract

Use an ordinary account in an owned Linux lab with Bash, Python 3.8 or later
and systemd-analyze supporting --base-time, available since systemd 244. A user
manager is unnecessary for this parser-only transfer. Keep `task.sh` beside
`calendar_observer.py`. The site IDE edits, saves and exports the files; run
them in that external Linux terminal.

A systemd calendar expression is not a five-field crontab entry. It can name
weekdays, a date pattern, a time and a timezone. In `*-*-* 12:00:00 UTC`, the
asterisks select every year, month and day; the time is noon UTC. In
`Mon..Fri *-*-* 09:00:00 UTC`, the weekday range excludes the weekend. Keep the
whole expression quoted as one shell argument.

The installed calendar parser calculates the next three elapses. --base-time
selects the starting timestamp; without it the parser uses the current time.
UTC makes the example's timezone explicit. The observer retains the exact
argv, PID, real return code, raw stdout and stderr. It uses a bounded child
process and changes neither the clock nor any scheduler. Relative phrases in
the tool's output can still reflect the live clock; compare the actual next
timestamps rather than treating that prose as a fixed fixture.

## Predict a daily sequence and repair the anchor

From the extracted role folder:

~~~bash
bash task.sh '2000-01-01 11:59:59 UTC' '*-*-* 12:00:00 UTC' > daily.json 2> daily.err
daily_status=$?
printf 'status=%s\n' "$daily_status"
cat daily.err
cat daily.json
~~~

From that base, the reference's next three dates are January 1, 2 and 3, 2000,
each at 12:00:00 UTC. The starter's named TODO omits the base from the actual
tool command even though it retains the requested value in the report. Its
forecast follows the live clock instead. Repair the one include_base decision
so the actual argv contains --base-time with the supplied timestamp. Preserve
the real parser, quoted arguments, diagnostics and deadline. Compare the
reference after saving an attempt.

Run the independent command and compare its timestamps to tool.stdout:

~~~bash
systemd-analyze calendar --iterations=3 --base-time='2000-01-01 11:59:59 UTC' -- '*-*-* 12:00:00 UTC'
~~~

## Changed weekdays and leap years

Use base `2000-01-07 09:00:01 UTC` with
`Mon..Fri *-*-* 09:00:00 UTC`. Predict January 10, 11 and 12 at 09:00 UTC; the
base is just after Friday's matching time. Then use base
`2000-02-28 13:00:00 UTC` and `*-02-29 12:00:00 UTC`. Predict leap-day
elapses in 2000, 2004 and 2008. Retain the actual normalized expressions and
timestamps, not only the written predictions. No machine clock is rewound.

Pass `not-a-calendar` as the expression, save the actual parser rejection and
nonzero status, then recover with the valid daily expression. An invalid base
also reaches the parser after repair; the incomplete starter can conceal that
error because it never passes the base. A missing argument is a separate input
rejection with status 2. Do not manufacture dates or convert parser failure to
a successful empty forecast.

Complete all five notes tasks. Explain why successful parsing cannot prove
that a timer is installed, enabled, triggered or that its service succeeded.
The live-service extension observes that separate behavior. Retain reports
before removing only the generated JSON/error files; the supplied source and
the system clock remain unchanged.

Primary references: [systemd calendar analysis](https://github.com/systemd/systemd/blob/main/man/systemd-analyze.xml)
and [calendar syntax](https://www.freedesktop.org/software/systemd/man/latest/systemd.time.html).
