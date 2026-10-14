# Unit 7: Logging and Observability

## Core project: reconstruct and repair an owned service incident

The operating question is why one named service failed, which evidence supports
that cause, and whether a later invocation completed after the correction. This
is a journal investigation, separate from shell file enumeration. The optional
transfer investigates application records; the optional extension measures file
retention. The notebook uses this same core attempt and records its reasoning.

The source includes a deliberately broken incident fixture, a service unit,
redacted journal records and an analyzer. The learner task is `in_scope` inside
`task.sh`: select the requested user unit, boot ID and inclusive microsecond
window. The supplied parsing and report code then orders records, counts error
priorities and distinguishes a later ready event in a new invocation from a
repeated or unrelated message. The reference completes the same task.

## Concepts and limits

`systemctl --user status UNIT` describes the current invocation; `journalctl`
retains events from older invocations. A failed start followed by an active
oneshot fixture does not mean the earlier failure never happened. A boot ID and
time window prevent an old incident from being mistaken for the current one.
`__REALTIME_TIMESTAMP` uses epoch microseconds. `PRIORITY` uses syslog numbers:
0 through 3 are emergency through error; 4 is warning and 6 is information.
The word ERROR in an informational message does not change its priority.

User-unit journal records may identify the unit with `_SYSTEMD_USER_UNIT` or
`USER_UNIT`; application records and service-manager explanations have different
responsibilities. First identify the application diagnostic, then corroborate
it with the service exit status. `config_missing` means the declared file is
absent; `config_invalid` means the file exists but its content is unsupported.
A later `ready` event is evidence of a completed fixture invocation. Current
service state must still be checked independently.

The analyzer accepts JSON-per-line records with scalar journal fields. Missing
files, invalid JSON, unsupported field shapes and invalid windows fail with
status 2. An empty valid selection produces an empty evidence report, which is
not proof of health. The untouched starter diagnoses its unfinished task with
status 78. No private machine logs are supplied or required for the fixture.

## Read, predict and complete

From the selected role directory, read `sample.log` and predict the records
included by this query before completing `in_scope`:

~~~sh
bash task.sh sample.log linux-observe-demo.service aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa 100 500
~~~

The four case events and the informational ERROR-word message belong to this
window. The other boot, other unit and timestamp 50 do not. The application
cause is `case: event=config_missing` at 200, and a different invocation records
`case: event=ready` at 400. Count priorities rather than substrings. Change the
window to end at 300: recovery should disappear. Change the unit or boot: the
selection should be empty. Remove the input file or damage a copy of its JSON:
that must fail visibly rather than print a successful zero summary. Preserve
the supplied source when making changed fixtures.

## Real Linux investigation

Use an owned Linux/WSL environment with Bash, Python 3, a working user systemd
manager and readable user journal. `systemctl --user show-environment` and
`journalctl --user -n 1 --no-pager` are readiness checks. If the user journal is
unavailable, complete the redacted route and arrange a supported lab; do not
change a shared machine's journal policy or claim live acceptance. macOS is not
a systemd host. The site workspace can edit/save/download these files, while
these operating commands run in the Linux terminal.

Create a private disposable lab and install a uniquely named fixture unit. The
configuration is initially absent, so the first start has a known failure. Run
from the selected role directory:

~~~sh
lab=$(mktemp -d "${TMPDIR:-/tmp}/linux-observe.XXXXXX")
unit="linux-observe-$(basename "$lab").service"
unit_path="$HOME/.config/systemd/user/$unit"
mkdir -p "$HOME/.config/systemd/user"
cp incident_app.sh "$lab/incident_app.sh"
python3 - linux-logging-case.service "$lab" "$unit_path" <<'PYTHON'
from pathlib import Path
import sys
source, lab, destination = sys.argv[1:]
if any(character in lab for character in '\n\r"\\'):
    raise SystemExit("Use a lab path without quotes, backslashes or line breaks.")
with Path(destination).open('x') as target:
    target.write(Path(source).read_text().replace('__LAB__', lab))
PYTHON
start_us=$(date +%s%6N)
boot=$(cat /proc/sys/kernel/random/boot_id | tr -d -)
systemctl --user daemon-reload
systemctl --user start "$unit" || test "$(systemctl --user show "$unit" -p ExecMainStatus --value)" = 2
systemctl --user status "$unit" --no-pager || true
journalctl --user -u "$unit" -b --no-pager -o json >"$lab/failed.log"
~~~

The first relevant application event says `config_missing`; the manager's
`ExecMainStatus=2` corroborates the exit. Record both before changing anything.
Repair only the fixture's declared file, then start a new invocation:

~~~sh
printf 'enabled=yes\n' >"$lab/case.conf"
systemctl --user reset-failed "$unit"
systemctl --user start "$unit"
systemctl --user show "$unit" -p ActiveState -p SubState -p ExecMainStatus
journalctl --user -u "$unit" -b --no-pager -o json >"$lab/incident.log"
end_us=$(date +%s%6N)
bash task.sh "$lab/incident.log" "$unit" "$boot" "$start_us" "$end_us"
~~~

Expect active/exited and status 0 for this oneshot fixture. Check that the ready
row has a later timestamp and a new `_SYSTEMD_INVOCATION_ID`; retain minimal
redacted excerpts in `incident-notes.md`. Do not infer a continuously running
process from an exited oneshot. Try `enabled=no`, observe `config_invalid` and
status 2, then restore `enabled=yes` and retest. Never delete broad journal
history to reset an exercise. Only the fixture unit and private lab are cleaned:

~~~sh
systemctl --user stop "$unit"
rm -- "$unit_path"
systemctl --user daemon-reload
systemctl --user reset-failed "$unit" 2>/dev/null || true
case "$lab" in */linux-observe.*) rm -r -- "$lab" ;; esac
~~~

## Review and completion evidence

Explain the selected scope, first trustworthy diagnostic, why the word ERROR
and unrelated records were rejected, the specific correction, fresh retest,
current state and cleanup. Independent reading and instructor discussion use
the same sequence: predict, select, explain, change one case, retest. Reference
review follows an attempted draft and must not replace the learner's saved
attempt. Full native acceptance exercises the actual user manager and journal,
all three source roles, missing/invalid configuration, new invocations and
cleanup; the redacted route alone does not establish that operating result.

References: [journalctl](https://www.freedesktop.org/software/systemd/man/latest/journalctl.html)
and [journal fields](https://www.freedesktop.org/software/systemd/man/latest/systemd.journal-fields.html).
