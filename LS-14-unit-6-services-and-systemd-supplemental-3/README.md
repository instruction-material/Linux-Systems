# Extend an owned service with environment files and a drop-in

This optional Services and systemd exercise studies configuration precedence
and restoration without rewriting the base unit. The heartbeat app is the
working reference from the core service project, used unchanged in both roles.
The named task is in 20-lab-settings.conf: clear the inherited environment-file
list and select override.env so actual process output uses extension-heartbeat.
This differs from transferring another app into a unit or implementing a heartbeat.

## Prerequisites and the precedence model

Complete the core toy-service project first. Use an owned Debian/Ubuntu Linux VM
or systemd-enabled WSL lab with Python 3, a real user manager and readable user
journal. Check uname -s, id, ps -p 1 -o comm=, systemctl --version,
systemctl --user show --property=Version --value and journalctl --user.
Resolve missing manager/journal access before claiming service completion.

The unit's Environment provides defaults. base.env replaces those defaults with
base-heartbeat and a 0.1-second interval. EnvironmentFile values take precedence
over Environment, including an Environment assignment in a later drop-in.
An empty EnvironmentFile directive clears the accumulated file list; the next
EnvironmentFile path selects override.env. Both files are required when selected.
A missing file is not silently ignored. HEARTBEAT_INTERVAL accepts an ASCII
decimal from 0.1 through 60 without signs, exponents or padded integer parts.
HEARTBEAT_MESSAGE is one nonempty UTF-8 line of at most 128 bytes; HEARTBEAT_LIMIT
is 0 for continuous operation or a canonical integer from 1 through 9999.
Invalid settings exit 2 before any heartbeat. From the role directory, a finite
direct check is:

~~~bash
HEARTBEAT_INTERVAL=0.1 HEARTBEAT_MESSAGE=sample HEARTBEAT_LIMIT=2 python3 heartbeat_app.py
~~~

The exact output is sample: heartbeat 1 followed by sample: heartbeat 2, each
on its own newline-terminated row. This covers the app, not manager operation.

The untouched drop-in is syntactically valid and the service can remain healthy,
yet actual output still uses base-heartbeat. This is the named unfinished
configuration result. Complete only the file-list reset and replacement path,
then compare the reference after an independent completion. Predict every state
and message before observing it. A healthy unit does not establish the intended
configuration, and systemctl show Environment alone does not reveal file-supplied
values in the running process.

## Unique base installation

Extract one role and this reading, enter the role directory and keep the shell
open. These commands read the actual HOME and refuse to replace an existing lab.

~~~bash
role_dir=$(pwd -P)
lab_name="linux-service-extension-$(id -u)-$$"
lab_unit="$lab_name.service"
install_root="$HOME/.local/share/$lab_name"
unit_root="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
if test ! -e "$install_root" &&\
   test ! -e "$unit_root/$lab_unit" &&\
   test ! -e "$unit_root/$lab_unit.d"; then
mkdir -p "$install_root" "$unit_root"
cp "$role_dir/heartbeat_app.py" "$install_root/heartbeat_app.py"
cp "$role_dir/base.env.example" "$install_root/base.env"
cp "$role_dir/override.env.example" "$install_root/override.env"
python3 - "$role_dir/linux-service-extension.service" "$unit_root/$lab_unit" "$lab_name" <<'PY'
from pathlib import Path
import sys
source, target, name = sys.argv[1:]
text = Path(source).read_text()
prefix = "%h/.local/share/linux-service-extension"
assert text.count(prefix) == 3
Path(target).write_text(text.replace(prefix, "%h/.local/share/" + name))
PY
sha256sum "$unit_root/$lab_unit" >"$install_root/base-unit.sha256"
systemd-analyze --user verify "$unit_root/$lab_unit"
systemctl --user daemon-reload
systemctl --user start "$lab_unit"
systemctl --user show "$lab_unit" --property=ActiveState,SubState,MainPID,EnvironmentFiles,FragmentPath,DropInPaths
journalctl --user -u "$lab_unit" --no-pager -n 20
else
  printf 'The lab name is already in use. Stop here and choose a new name.\n' >&2
fi
~~~

Confirm an owned running PID and base-heartbeat rows from that process. %h resolves
to the actual user's home, and the user unit inherits that user's identity.
Verify /usr/bin/python3 and the installed app path in this Debian/Ubuntu lab.
The app's interval/message/limit validation is described in the core reading;
these examples use continuous service operation with HEARTBEAT_LIMIT=0.

## Install the selected role's drop-in

~~~bash
mkdir "$unit_root/$lab_unit.d"
python3 - "$role_dir/20-lab-settings.conf" "$unit_root/$lab_unit.d/20-lab-settings.conf" "$lab_name" <<'PY'
from pathlib import Path
import sys
source, target, name = sys.argv[1:]
text = Path(source).read_text()
Path(target).write_text(text.replace("%h/.local/share/linux-service-extension", "%h/.local/share/" + name))
PY
systemctl --user daemon-reload
systemctl --user cat "$lab_unit"
systemctl --user show "$lab_unit" --property=EnvironmentFiles,DropInPaths,NeedDaemonReload
systemctl --user restart "$lab_unit"
journalctl --user -u "$lab_unit" --no-pager -n 30
sha256sum --check "$install_root/base-unit.sha256"
~~~

Re-read MainPID after restart and correlate only that PID's journal rows with
the predicted message. The untouched drop-in keeps base-heartbeat. The reference
and independent completion select only override.env and produce extension-heartbeat.
Inspect the owned process command/UID and, when readable, its actual environment:

~~~bash
main_pid=$(systemctl --user show "$lab_unit" --property=MainPID --value)
ps -p "$main_pid" -o pid,ppid,uid,args
tr '\0' '\n' <"/proc/$main_pid/environ" | grep '^HEARTBEAT_'
~~~

Explain why the merged unit's Environment assignment can differ from actual
process values. Record the effective file list and unchanged base-unit hash.

## File edits, restart, failure and rollback

Keep the working override file, then change its message to edited-heartbeat
without changing the unit or drop-in. Observe that the current PID and its rows
retain the previous message. Restart, then confirm a different PID and fresh
edited-heartbeat rows. File contents are read for the next process; a running
process does not acquire edits. Unit/drop-in directive edits additionally need
daemon-reload. A reload command is not an app restart.

For the completed configuration, back up override.env and set its interval to 0.
Restart and observe a failed unit, MainPID=0, exit 2 and an actual interval
diagnostic; the prevent list avoids a retry loop. Restore valid contents,
reset-failed, start and confirm recovery with a new PID and expected rows.
The untouched starter still selects base.env, so an ignored override-file edit
is evidence of its unfinished task, not successful extension.

Remove only the owned 20-lab-settings.conf, remove its now-empty directory,
daemon-reload, reset-failed and restart. Observe only base.env in EnvironmentFiles,
a new owned PID and base-heartbeat output. Confirm the base fragment hash remains
unchanged. Record both restoration and cleanup in service-extension-notes.md.

~~~bash
rm "$unit_root/$lab_unit.d/20-lab-settings.conf"
rmdir "$unit_root/$lab_unit.d"
systemctl --user daemon-reload
systemctl --user reset-failed "$lab_unit"
systemctl --user restart "$lab_unit"
sha256sum --check "$install_root/base-unit.sha256"
systemctl --user show "$lab_unit" --property=MainPID,EnvironmentFiles,DropInPaths
journalctl --user -u "$lab_unit" --no-pager -n 20
systemctl --user stop "$lab_unit"
systemctl --user disable "$lab_unit"
systemctl --user reset-failed "$lab_unit"
rm "$unit_root/$lab_unit"
systemctl --user daemon-reload
systemctl --user show "$lab_unit" --property=LoadState,MainPID
~~~

Confirm the owned unit, drop-in, activation link and process are gone. Retain
source/evidence for review, then remove only the unique installed directory.
An analysis record requires the actual observations above; completed source or a
printed prediction does not replace them. The same ordered predictions and
commands support an independent reading or a paced walkthrough.

References: [environment-file precedence](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html),
[unit drop-ins](https://www.freedesktop.org/software/systemd/man/latest/systemd.unit.html).
