# LS5 Systemd Toy Service

Manage a small long-lived process with a real systemd user manager. This required
project belongs to Services and systemd. The preceding shell exercises establish
command, output and exit-status habits; this project adds manager state, process
identity, journaling, restart policy and persistent enablement.

## Environment and learner contract

Use an owned Debian/Ubuntu Linux VM or systemd-enabled WSL distribution with
Python 3 and a working user manager. Check `uname -s`, `id`,
`ps -p 1 -o comm=`, `systemctl --version` and
`systemctl --user show --property=Version --value`.
Check that `journalctl --user` can read this user's service journal. A manager
connection or journal-access failure is an unmet prerequisite to resolve in
the lab before claiming service completion. A parsed unit file or direct
Python run covers different evidence.

Both roles use the same driver and user unit. Complete only the learner
`render_heartbeat(message, number)` function: return
`<message>: heartbeat <number>`. The untouched function returns None, emits
a diagnostic and exits 78 before any heartbeat. The unit prevents automatic
restart for that unfinished-task status. Compare the reference after an
independent completion.

HEARTBEAT_INTERVAL is a decimal from 0.1 through 60 seconds, without signs,
exponents or padded integer parts. HEARTBEAT_MESSAGE is one nonempty UTF-8
line of at most 128 bytes. HEARTBEAT_LIMIT is 0 for continuous operation or
a canonical integer from 1 through 9999. Invalid settings exit 2 before
producing a heartbeat. Each valid row is flushed immediately. A finite run
stops after its requested row count; a service uses continuous operation.

## Direct prediction and controlled input

From the selected role folder, run:

```bash
HEARTBEAT_INTERVAL=0.1 HEARTBEAT_MESSAGE=sample HEARTBEAT_LIMIT=2 python3 heartbeat_app.py
HEARTBEAT_INTERVAL=0 python3 heartbeat_app.py
HEARTBEAT_INTERVAL=nan python3 heartbeat_app.py
```

The reference and independently completed learner print exactly:

```text
sample: heartbeat 1
sample: heartbeat 2
```

The valid untouched learner exits 78 with its named unfinished diagnostic.
The two invalid settings exit 2 in both roles. Record stdout, stderr, status,
elapsed time and the different reasons. Add a valid boundary and a Unicode
message case. These checks establish the app contract before manager operation.

## Install a unique owned user unit

Keep this shell open. The guarded setup refuses to replace an
existing install or unit. It reads HOME without changing its value.

```bash
role_dir=$(pwd -P)
lab_name="linux-heartbeat-$(id -u)-$$"
lab_unit="$lab_name.service"
install_root="$HOME/.local/share/$lab_name"
unit_root="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
if test ! -e "$install_root" &&\
   test ! -e "$unit_root/$lab_unit"; then
mkdir -p "$install_root" "$unit_root"
cp "$role_dir/heartbeat_app.py" "$install_root/heartbeat_app.py"
cp "$role_dir/heartbeat.env.example" "$install_root/heartbeat.env"
python3 - "$role_dir/linux-heartbeat.service" "$unit_root/$lab_unit" "$lab_name" <<'PY'
from pathlib import Path
import sys
source, target, name = sys.argv[1:]
text = Path(source).read_text()
prefix = "%h/.local/share/linux-heartbeat"
assert text.count(prefix) == 3
Path(target).write_text(text.replace(prefix, "%h/.local/share/" + name))
PY
systemd-analyze --user verify "$unit_root/$lab_unit"
systemctl --user daemon-reload
systemctl --user cat "$lab_unit"
else
  printf 'The lab name is already in use. Stop here and choose a new name.\n' >&2
fi
```

The unit is a user unit: %h identifies the user's home; the process inherits
the user manager's identity. It needs no www-data account or /opt installation.
WorkingDirectory, the required environment file and ExecStart point into the
unique installed directory. The supplied Python binary is /usr/bin/python3;
verify that path in this Debian/Ubuntu lab.

The environment file sets the interval to 0.25 seconds and a distinct message.
EnvironmentFile values override the defaults supplied by Environment. Changing
its contents requires an app restart; changing unit directives also requires
daemon-reload before restart. Neither operation is a substitute for observed
running state and output.

## Start, inspect, enable and stop

```bash
systemctl --user start "$lab_unit"
systemctl --user status "$lab_unit" --no-pager
systemctl --user show "$lab_unit" --property=ActiveState,SubState,MainPID,ExecMainStatus,Result,NRestarts,InvocationID
journalctl --user -u "$lab_unit" --no-pager -n 20
```

Type=simple may report a successful start command before the app later fails.
The untouched starter program must settle in failed state with ExecMainStatus=78,
MainPID=0 and no restart loop. Complete the named function in the learner source
then copy the changed app to the installed path:

```bash
cp "$role_dir/heartbeat_app.py" "$install_root/heartbeat_app.py"
systemctl --user reset-failed "$lab_unit"
systemctl --user start "$lab_unit"
```

For a completed app, require active/running state, a nonzero MainPID and actual
journal rows from that process. Inspect only the recorded owned PID:

```bash
main_pid=$(systemctl --user show "$lab_unit" --property=MainPID --value)
ps -p "$main_pid" -o pid,ppid,uid,args
systemctl --user enable "$lab_unit"
systemctl --user is-enabled "$lab_unit"
systemctl --user stop "$lab_unit"
systemctl --user show "$lab_unit" --property=ActiveState,SubState,MainPID
```

Enable creates the persistent user-target activation link; it does not itself
start the app. A stopped unit is inactive with MainPID=0 even while enabled.
Record the actual target link and explain this distinction. Start the unit
again for the following experiments with `systemctl --user start "$lab_unit"`.

## Manual restart and unexpected failure

Record the current MainPID and invocation, restart with
`systemctl --user restart "$lab_unit"`, and observe a new PID and new journal
rows. Each app process restarts its heartbeat numbering at 1.

For an automatic-restart case, first verify the current PID belongs to the
installed heartbeat app and matches the unit's MainPID. Send SIGKILL only to
that recorded process:

```bash
systemctl --user reset-failed "$lab_unit"
main_pid=$(systemctl --user show "$lab_unit" --property=MainPID --value)
test "$main_pid" -gt 0
ps -p "$main_pid" -o pid,ppid,uid,args
kill -KILL "$main_pid"
systemctl --user show "$lab_unit" --property=ActiveState,MainPID,NRestarts,Result
journalctl --user -u "$lab_unit" --no-pager -n 30
```

Resetting the failed state before this isolated case also resets its start-limit
counters. Record a fresh restart-count baseline after that reset.

Wait for the restart delay, then require a new running PID, NRestarts greater
than its earlier value and new heartbeat rows. An explicit stop is different:
it requests termination and does not trigger on-failure restart.

## Configuration failure, recovery and undo

Save the working environment file, then replace it with an invalid interval:

```bash
cp "$install_root/heartbeat.env" "$install_root/heartbeat-good.env"
printf 'HEARTBEAT_INTERVAL=0\nHEARTBEAT_MESSAGE=broken-lab\nHEARTBEAT_LIMIT=0\n' >"$install_root/heartbeat.env"
systemctl --user restart "$lab_unit"
journalctl --user -u "$lab_unit" --no-pager -n 30
systemctl --user show "$lab_unit" --property=ActiveState,SubState,ExecMainStatus,Result,NRestarts
```

The app exits 2. The bounded restart policy eventually produces a failed unit
after the start limit. Record the actual diagnostic, restart count and manager
result; do not infer success from the restart command's return alone.

Restore the good environment, use `systemctl --user reset-failed "$lab_unit"`
and start it again. Confirm active/running state, a new process with the owned
identity and fresh journal rows bearing the restored message.

Complete service-notes.md with the environment, versions, source role, direct
app cases, installed paths, real manager states, PID/UID evidence, journal
rows, enable/stop distinction, manual and automatic restarts, failure,
recovery and cleanup. The reference explains predicted behavior; the record
requires actual observations. A walkthrough can pause at each prediction,
state transition and repair; the same sequence supports independent reading.

```bash
systemctl --user stop "$lab_unit"
systemctl --user disable "$lab_unit"
systemctl --user reset-failed "$lab_unit"
rm "$unit_root/$lab_unit"
systemctl --user daemon-reload
systemctl --user show "$lab_unit" --property=LoadState,ActiveState,MainPID
```

Record the disappearance of the owned process and activation link. Keep the
small installed source/evidence directory for the completion record. Remove it
later only after confirming it is the unique directory created above.

References: [systemd.service](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html),
[systemctl](https://www.freedesktop.org/software/systemd/man/latest/systemctl.html),
[systemd.unit](https://www.freedesktop.org/software/systemd/man/latest/systemd.unit.html).
