# Transfer a working HTTP process to an owned user service

This optional Services and systemd exercise transfers the core service habits
to a different, supplied working process. The named task is in the user unit:
repair its WorkingDirectory and ExecStart app argument. The program is reused
from the accepted reverse-proxy app, with only its description changed. No
Nginx configuration or new HTTP handler implementation is required here.
The separate web-server project studies proxy behavior.

## Prerequisites and predictions

Complete the core toy-service project first. Use an owned Debian/Ubuntu Linux
VM or systemd-enabled WSL lab with Python 3, curl, ss and a working user manager.
Check uname -s, id, ps -p 1 -o comm=, systemctl --version,
systemctl --user show --property=Version --value and journalctl --user.
An unavailable manager or inaccessible journal is an unmet lab prerequisite.
A direct app run establishes a different contract from service operation.

The app accepts APP_PORT as an ASCII integer from 1024 through 65535, binds only
127.0.0.1 and exposes GET/HEAD /health. Its exact UTF-8 GET body is:

~~~text
{"service": "linux-toy-app", "status": "ok"}
~~~

The body ends with a newline; HEAD returns the same headers and no body.
/inspect reports parsed query values and the selected headers, unknown paths
return JSON 404, and POST returns 405 with Allow: GET, HEAD. Predict a repeated
query and a Unicode value before testing. Invalid APP_PORT exits 2 before
binding; an occupied port exits 1. Do not take over another process's port.

The untouched starter unit points at a missing working-directory child and a
missing Python script argument. These are two distinct tasks. After installation,
the first causes 200/CHDIR before Python. Repairing only WorkingDirectory exposes
the second failure: Python exits 2 and reports the missing script. Fix both
paths to the installed root and transfer_app.py. The unit's prevent list stops
these configuration failures from becoming a restart loop. Type=simple start
status is not the eventual service or HTTP-readiness result.

## Install a unique unit and its app

Extract one role and this reading, enter the selected role directory and keep
this shell open. The commands use the actual HOME and refuse an existing name.
Select a free owned loopback port; a later binding race still fails explicitly.

~~~bash
role_dir=$(pwd -P)
lab_name="linux-service-transfer-$(id -u)-$$"
lab_unit="$lab_name.service"
install_root="$HOME/.local/share/$lab_name"
unit_root="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
lab_port=$(python3 - <<'PY'
import socket
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
)
if test ! -e "$install_root" &&\
   test ! -e "$unit_root/$lab_unit"; then
mkdir -p "$install_root" "$unit_root"
cp "$role_dir/transfer_app.py" "$install_root/transfer_app.py"
printf 'APP_PORT=%s\n' "$lab_port" >"$install_root/transfer.env"
python3 - "$role_dir/linux-service-transfer.service" "$unit_root/$lab_unit" "$lab_name" <<'PY'
from pathlib import Path
import sys
source, target, name = sys.argv[1:]
text = Path(source).read_text()
prefix = "%h/.local/share/linux-service-transfer"
assert text.count(prefix) == 3
Path(target).write_text(text.replace(prefix, "%h/.local/share/" + name))
PY
systemd-analyze --user verify "$unit_root/$lab_unit"
systemctl --user daemon-reload
systemctl --user start "$lab_unit"
systemctl --user show "$lab_unit" --property=LoadState,ActiveState,SubState,MainPID,ExecMainStatus,Result,NRestarts
journalctl --user -u "$lab_unit" --no-pager -n 30
else
  printf 'The lab name is already in use. Stop here and choose a new name.\n' >&2
fi
~~~

%h is the real user's home; this is a user unit inheriting that user's identity.
Do not add a system User directive or substitute a different HOME. Explain each
installed path, the required environment file, Python binary and restart choice.
The syntax check can pass while runtime paths fail. Record each distinct failure
before correcting the named lines in the role unit, repeating the installation
substitution, daemon-reload, reset-failed and start sequence.

## Prove process and HTTP readiness

For the completed unit, inspect the owned PID and its actual listener, then
compare GET/HEAD with the predicted body and headers.

~~~bash
main_pid=$(systemctl --user show "$lab_unit" --property=MainPID --value)
test "$main_pid" -gt 0
ps -p "$main_pid" -o pid,ppid,uid,args
ss -ltnp "sport = :$lab_port"
curl --fail-with-body "http://127.0.0.1:$lab_port/health"
curl --head "http://127.0.0.1:$lab_port/health"
curl --get --data-urlencode 'word=café' --data-urlencode 'word=two' "http://127.0.0.1:$lab_port/inspect"
~~~

Confirm active/running state, the installed app in the recorded process command,
the actual user UID, a 127.0.0.1 socket owned by that PID, the exact response and
journal rows from that process. Another server's successful response is not
this unit's readiness. Record both command status and observed state.

## Restart, failed-directory diagnosis and restoration

Restart the unit, observe a new PID and repeat readiness. For an unexpected
failure, first reset-failed, re-read MainPID, verify its command/UID, then send
SIGKILL only to that recorded process. Wait for a different running PID and an
increased NRestarts count; repeat the HTTP and journal checks. An explicit stop
requests termination and has a different meaning.

Keep the working fragment unchanged during the next controlled fault. Add only
this owned drop-in, replacing the path with the unique install path above:

~~~bash
mkdir "$unit_root/$lab_unit.d"
printf '[Service]\nWorkingDirectory=%s/missing-directory\n' "$install_root" >"$unit_root/$lab_unit.d/90-lab-fault.conf"
systemctl --user daemon-reload
systemctl --user restart "$lab_unit"
systemctl --user show "$lab_unit" --property=ActiveState,MainPID,ExecMainStatus,Result
journalctl --user -u "$lab_unit" --no-pager -n 30
rm "$unit_root/$lab_unit.d/90-lab-fault.conf"
rmdir "$unit_root/$lab_unit.d"
systemctl --user daemon-reload
systemctl --user reset-failed "$lab_unit"
systemctl --user start "$lab_unit"
~~~

Record the actual missing-directory diagnostic and 200/CHDIR, then a fresh
running process and healthy response after restoration. This fault occurs before
the app; an HTTP route or environment error is a different layer.

## Enablement, record and cleanup

Enable the unique unit, inspect its default.target.wants link, stop it and
confirm it remains enabled with MainPID=0. Complete service-transfer-notes.md
with predictions, observed failures, repairs, process/socket/journal evidence
and the enable-versus-run distinction. A walkthrough can pause at each prediction
and state transition; the same commands support independent work.

~~~bash
systemctl --user enable "$lab_unit"
systemctl --user is-enabled "$lab_unit"
systemctl --user stop "$lab_unit"
systemctl --user show "$lab_unit" --property=ActiveState,MainPID,UnitFileState
systemctl --user disable "$lab_unit"
systemctl --user reset-failed "$lab_unit"
rm "$unit_root/$lab_unit"
systemctl --user daemon-reload
systemctl --user show "$lab_unit" --property=LoadState,ActiveState,MainPID
~~~

Confirm the process, listener, unit and activation link are gone. Retain the small
owned install/evidence directory for review, then remove only that exact directory.
The reference supplies predictions and a completed unit; it does not supply
observations from the current lab.

References: [systemd execution environment](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html),
[service restart behavior](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html).
