# Operations Capstone: A Service That Can Be Diagnosed and Restored

This is the required Linux Systems operations capstone. It integrates the
earlier environment, permissions, configuration, process, service, journal,
networking and backup units. The three integration studios in the optional
archive are additional practice; completing them all is not a prerequisite.
Plan 8–12 paced sessions, retaining the same evidence for independent study or
a guided walkthrough. The outcome is an operated system and a reproducible
runbook, not a successful log-counting command.

## Equipment, boundaries and files

Use an owned disposable Debian/Ubuntu VM with systemd as PID 1, an ordinary
operator account with approved sudo access, Bash, Python 3.8+, Nginx,
systemd-analyze, journalctl, curl, ss and GNU coreutils. WSL2 needs its actual
system manager enabled; otherwise use the VM. Arrange missing tools before
the session. Take a VM snapshot before installing the lab units. Keep every
listener on loopback and all content fictional. No production server, public
DNS, TLS, firewall change, cloud credential or external database is involved.

The website IDE edits, saves and exports this complete role folder and README.
Execute in the Linux lab. Keep all eleven role files together. `app.py`
validates its configuration and serves process identity and a fictional message.
`backup.py` creates checked archives and restores into new paths. The service,
backup service, timer and Nginx files are templates with explicit `@@...@@`
fields. `render_lab.py` copies the role into a fresh scoped tree and fills these
fields; it neither invokes sudo nor installs/starts anything. Inspect the
rendered files before each privileged operation. `operations-notes.md` remains
an independent record in both roles.

## Sessions 1–2: establish the environment and complete the starter

Record actual `id`, `uname -a`, `ps -p 1 -o comm=`, `systemd --version`,
`python3 --version`, `nginx -v`, `findmnt -T /srv` and `df -h /srv`. Record the
working directory and the VM snapshot. Check which earlier units supply any
missing concept before continuing.

Make and explain four focused corrections in the starter: choose 127.0.0.1
instead of a public bind address; replace the TODO release id with release-a;
make WorkingDirectory select `@@ROOT@@/current`; and include every declared
project member in `selected_members()`. Preserve the original and predict
each failure before comparing the reference. The application rejects an
unsafe bind or unspecified release before opening a listener. The system
manager, rather than this configuration check, observes a missing working
directory. The backup refuses an incomplete member selection before publication.

~~~bash
bash task.sh check > configuration.json 2> configuration.err
check_status=$?
printf 'configuration status=%s\n' "$check_status"
cat configuration.err
cat configuration.json
~~~

Run expected failures without errexit so their statuses can be recorded. A
reference configuration check must return 0; malformed input returns 2 with
stderr. A configuration check does not establish that a service is running.

## Sessions 3–4: render, inspect and operate the actual service

Keep this shell open so its scoped variables remain available. Retain the
printed values. If either selected port is already in use, choose fresh ports
and render a new lab; do not stop an existing listener.

~~~bash
role_root=$(pwd -P)
lab_id=$(python3 -c 'import uuid; print(uuid.uuid4().hex)')
unit_id="cls-cap-${lab_id:0:12}"
lab_root="/srv/classes-capstone-$lab_id"
operator_uid=$(id -u)
operator_gid=$(id -g)
read -r app_port proxy_port < <(python3 -c 'import socket; a=socket.socket(); b=socket.socket(); a.bind(("127.0.0.1",0)); b.bind(("127.0.0.1",0)); print(a.getsockname()[1],b.getsockname()[1]); a.close(); b.close()')
printf 'root=%s unit=%s app=%s proxy=%s\n' "$lab_root" "$unit_id" "$app_port" "$proxy_port"
ss -ltn
sudo -v
sudo mkdir -- "$lab_root"
sudo chown "$operator_uid:$operator_gid" -- "$lab_root"
chmod 0755 -- "$lab_root"
bash task.sh render --root "$lab_root" --id "$lab_id" --app-port "$app_port" --proxy-port "$proxy_port" > rendered.json
cat rendered.json
cat "$lab_root/staging/signal-garden.service"
cat "$lab_root/staging/signal-garden-backup.service"
cat "$lab_root/staging/signal-garden-backup.timer"
python3 "$lab_root/current/app.py" --check --config "$lab_root/current/config.json" --port "$app_port"
~~~

The operator owns the release tree. Directories permit traversal, code/data
are 0444 and private backups/restores are 0700. The service uses a separately
allocated DynamicUser identity and a read-only filesystem view. Its UID can
change between starts; record the actual value each time. The backup service
runs as the operator and has write access only to its declared backup path.
DynamicUser is a system-manager feature here, not a second name for the
operator's user service.

Proceed only after the configuration and unit verification both return 0.
Install only the rendered files for this id. The runtime enable links disappear
at reboot; this bounded lab is not a durable production installation.

~~~bash
sudo install -m 0644 "$lab_root/staging/signal-garden.service" "/run/systemd/system/$unit_id.service"
sudo install -m 0644 "$lab_root/staging/signal-garden-backup.service" "/run/systemd/system/$unit_id-backup.service"
sudo install -m 0644 "$lab_root/staging/signal-garden-backup.timer" "/run/systemd/system/$unit_id-backup.timer"
sudo systemd-analyze verify "/run/systemd/system/$unit_id.service" "/run/systemd/system/$unit_id-backup.service" "/run/systemd/system/$unit_id-backup.timer"
sudo systemctl daemon-reload
sudo systemctl enable --runtime --now "$unit_id.service"
sudo systemctl show "$unit_id.service" -p ActiveState -p SubState -p MainPID -p User -p DynamicUser -p InvocationID -p WorkingDirectory
curl --silent --show-error --include "http://127.0.0.1:$app_port/health"
curl --silent --show-error --include "http://127.0.0.1:$app_port/missing"
sudo journalctl --no-pager -u "$unit_id.service" -n 30
sudo ss -ltnp
stat -c 'mode=%a uid=%u path=%n' "$lab_root/current/app.py" "$lab_root/backups"
~~~

Verify the actual health UID differs from root and the operator, its PID matches
MainPID, its invocation id matches the manager, and its code-write open was
denied with EACCES or EROFS. Compare the actual code SHA-256 with `sha256sum`.
A returned 200 alone does not establish release identity or least privilege.
Keep manager configuration, process identity, actual denied access, socket,
HTTP response and journal evidence separate.

## Session 5: validate the owned foreground proxy

In terminal B, set `lab_root` to the exact printed value. Run Nginx as the
ordinary operator. It reads only this configuration, writes only its scoped
logs/temp files, and keeps its process in this terminal.

~~~bash
nginx -t -p "$lab_root/nginx/" -c "$lab_root/staging/nginx.conf"
nginx -p "$lab_root/nginx/" -c "$lab_root/staging/nginx.conf"
~~~

In terminal A, retain `curl --include http://127.0.0.1:$proxy_port/health`
and the corresponding missing route. Compare status and JSON with direct
requests; record the proxy PID, listener and scoped access/error logs. The
proxy is not a second copy of the application and grants no authentication.

## Sessions 6–7: scheduled backup, checked restore and failed output

Inspect the timer and both units before starting the timer. Its two-second
OnActiveSec delay is a bounded classroom schedule. RemainAfterElapse keeps
the elapsed timer available for inspection until it is stopped. Stop it before
reactivating it for the changed-input drill. Do not manually start the
backup service and then describe that as a timer-triggered backup.

~~~bash
sudo systemctl enable --runtime --now "$unit_id-backup.timer"
sudo systemctl list-timers --all "$unit_id-backup.timer"
sudo systemctl show "$unit_id-backup.timer" -p ActiveState -p LastTriggerUSec -p TimersMonotonic
sudo journalctl --no-pager -u "$unit_id-backup.service" -n 20
~~~

Wait for the timer's actual trigger and a completed backup-unit journal result.
If there is no trigger, diagnose the timer before claiming an archive exists.
Retain the exact archive name, checksum, three-member manifest, source and
destination device ids, and permissions from the actual backup. The same
filesystem is sufficient for this recovery drill, but is not protection against
loss of that filesystem or host. The manifest checks local payload integrity;
it is not an externally authenticated builder signature.

~~~bash
sudo systemctl disable --runtime --now "$unit_id-backup.timer"
archive=$(python3 "$lab_root/operator/backup.py" latest "$lab_root/backups")
python3 "$lab_root/operator/backup.py" verify "$archive"
sha256sum -- "$archive" > trusted-archive.sha256
python3 "$lab_root/operator/backup.py" restore "$archive" "$lab_root/restore/drill-1"
for name in app.py config.json data.json; do
    cmp -- "$lab_root/current/$name" "$lab_root/restore/drill-1/$name"
    stat -c 'mode=%a uid=%u path=%n' "$lab_root/restore/drill-1/$name"
done
python3 "$lab_root/operator/backup.py" restore "$archive" "$lab_root/restore/drill-1"
existing_target_status=$?
python3 "$lab_root/operator/backup.py" build "$lab_root/current" "$lab_root/backups" --reject-after-write
rejected_candidate_status=$?
printf 'existing restore=%s rejected candidate=%s\n' "$existing_target_status" "$rejected_candidate_status"
sha256sum -c trusted-archive.sha256
find "$lab_root/backups" -maxdepth 1 -type f -printf '%f\n'
~~~

Both intentional refusals return 2. The new .partial file is untrusted and is
never selected by latest. The earlier validated archive and restored bytes
remain unchanged. Inspect/retain the partial evidence before removing only
that owned candidate. Restore never extracts archive paths directly: it
accepts only the exact three ordinary members, checks every digest and creates
a new destination. Existing paths, links, extra members and altered bytes do
not become a successful restore.

## Sessions 8–9: inject, diagnose, correct and clean-start

Create a drop-in for only this run's service. Predict manager status, journal
messages, direct connection and proxy status before restarting. Retain actual
restarts and the first failing layer. In particular, a valid unit syntax check
does not prove its working directory exists.

~~~bash
printf '[Service]\nWorkingDirectory=%s/missing-release\n' "$lab_root" > failed-workdir.conf
sudo mkdir -- "/run/systemd/system/$unit_id.service.d"
sudo install -m 0644 failed-workdir.conf "/run/systemd/system/$unit_id.service.d/failed-workdir.conf"
sudo systemctl daemon-reload
sudo systemctl restart "$unit_id.service"
restart_status=$?
printf 'restart request=%s\n' "$restart_status"
sudo systemctl show "$unit_id.service" -p ActiveState -p SubState -p Result -p NRestarts -p ExecMainStatus
sudo journalctl --no-pager -u "$unit_id.service" -n 40
curl --max-time 3 --silent --show-error --include "http://127.0.0.1:$app_port/health"
curl --max-time 3 --silent --show-error --include "http://127.0.0.1:$proxy_port/health"
sudo rm -- "/run/systemd/system/$unit_id.service.d/failed-workdir.conf"
sudo rmdir -- "/run/systemd/system/$unit_id.service.d"
sudo systemctl daemon-reload
sudo systemctl reset-failed "$unit_id.service"
sudo systemctl restart "$unit_id.service"
curl --max-time 3 --silent --show-error --include "http://127.0.0.1:$proxy_port/health"
sha256sum -c trusted-archive.sha256
sudo systemctl stop "$unit_id.service"
sudo systemctl start "$unit_id.service"
curl --max-time 3 --silent --show-error --include "http://127.0.0.1:$app_port/health"
~~~

Allow the manager to finish its bounded restart attempts before retaining its
final failed state. While the app is stopped, the direct listener refuses
connections and the proxy returns 502. After restoring the original working
directory, require a new actual healthy process/invocation and retained data.
The final stop/start is a separate clean-start check. Record service UID/PID
again rather than assuming they remain the same.

## Sessions 10–12: changed input, runbook and disable/remove rollback

Change only the fictional message in an owned release copy, retaining the
original and its checksums. Predict why this application, which loads data at
startup, needs a restart before health reports that change. Repeat an actual
timer activation and a restore to a second new path. Keep the first trusted
archive. Explain code/config/data ownership, failure diagnosis, schedule,
restore procedure and limitations in a versioned runbook. The reference does
not fill any observation or explanation in operations-notes.md.

Finish by pressing Ctrl-C in terminal B and verifying its Nginx PID/listener
are gone. In terminal A stop the timer and both services, remove only this
id's runtime enable links and unit files, reload, and verify inactive/absent
units and closed app/proxy listeners before removing the scoped tree.

~~~bash
sudo systemctl disable --runtime --now "$unit_id-backup.timer" "$unit_id.service"
sudo systemctl stop "$unit_id-backup.service"
sudo rm -- "/run/systemd/system/$unit_id.service" "/run/systemd/system/$unit_id-backup.service" "/run/systemd/system/$unit_id-backup.timer"
sudo systemctl daemon-reload
sudo systemctl reset-failed "$unit_id.service" "$unit_id-backup.service"
sudo systemctl show "$unit_id.service" -p LoadState -p ActiveState -p MainPID
ss -ltn
printf 'Review this exact owned tree before removal: %s\n' "$lab_root"
sudo rm -r -- "$lab_root"
~~~

Copy out the runbook, checksums and selected evidence before removing the tree.
Do not erase the system journal; this id's historical records are part of the
diagnosis. If cleanup fails, retain the exact root/id/unit state and correct
that gate before declaring rollback. No command here alters global Nginx
configuration, other services, accounts, DNS, firewall or production data.

Primary references: [systemd execution and DynamicUser](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html),
[timer semantics](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html),
[systemctl enable/disable](https://www.freedesktop.org/software/systemd/man/latest/systemctl.html),
[Nginx beginner guide](https://nginx.org/en/docs/beginners_guide.html), and
[Python tar archives](https://docs.python.org/3/library/tarfile.html).
