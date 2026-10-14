# Backups, cron and a user timer

This Linux lab archives an explicit source directory into a separate owned
backup directory. Both scheduler examples use the same unprivileged account
and explicit paths. The systemd files are user units, not system units: installing
them with a system-wide manager would select the wrong identity and home.

## Archive and retention contract

Run Bash with GNU find, sort, tar, mktemp, realpath and the util-linux flock command.
Source and destination may contain spaces. The destination must be outside the
source tree. RETENTION_COUNT is a canonical integer from 1 through 1000; zero
and malformed values are rejected before an archive is created. The default is
five. Managed archive names begin with linux-systems-backup- and end in .tar.gz;
reserve that naming convention for this lab. Other files and symlinks are not
selected for retention.

Each successful run creates a new timestamped name with a unique suffix. A lock
serializes runs sharing a destination. tar writes a temporary archive and only
then publishes it without replacing any existing archive. A failed creation
removes temporary files and leaves earlier backups intact. The reference keeps
the archive just created plus the newest remaining managed archives, up to the
retention count. Retention failure is an error, not a success report. Archive
members are relative to the source, so restoration can target a separate tree.

## First run and independent restoration

Use a disposable Linux workspace containing fabricated course files:

~~~sh
lab_root=$(mktemp -d)
mkdir -p "$lab_root/source notes" "$lab_root/backup copies" "$lab_root/restored"
printf 'first observation\n' > "$lab_root/source notes/session.txt"
bash backup_home.sh "$lab_root/source notes" "$lab_root/backup copies"
find "$lab_root/backup copies" -name 'linux-systems-backup-*.tar.gz' -print
~~~

Select the archive path printed by the program. List its members with tar -tzf,
then extract this known lab archive with tar -xzf into the separate restored
directory. Compare session.txt against the original with cmp. Record the archive
name, input, restored bytes, status and any diagnostics. Archive creation alone
does not prove restoration.

The starter creates correct, unique archives but its named retention TODO is
unfinished. Complete that one operation without replacing the input contract,
lock or publication sequence. Make seven backups with changed content and
RETENTION_COUNT=2, then verify two managed archives remain and the newest
restores the newest input. Repeat with retention one, an unrelated file, a
missing source, zero retention and paths containing spaces. Earlier backups
remain unchanged when creation fails. Compare the reference after an attempted
repair and independent restore.

## Install the selected role for a user scheduler

In the owned Linux lab, create the source and backup directories and install
the selected completed script. These commands do not configure a system service:

~~~sh
mkdir -p "$HOME/.local/bin" "$HOME/linux-systems-lab" "$HOME/backups"
install -m 0755 backup_home.sh "$HOME/.local/bin/backup_home.sh"
mkdir -p "$HOME/.config/systemd/user"
install -m 0644 linux-backup.service linux-backup.timer "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user start linux-backup.service
systemctl --user status linux-backup.service
journalctl --user -u linux-backup.service --no-pager
systemctl --user enable --now linux-backup.timer
systemctl --user list-timers
~~~

The %h specifier expands to the user manager's home. No root HOME default is
used. A user manager may require an active login session; record actual manager
availability and behavior rather than assuming it exists in every VM or WSL
session. If unavailable, use the manual run and supplied unit reasoning route.
For cron, inspect the existing user crontab first and add only the one example
entry. Do not replace an existing crontab wholesale. The example sets a known
shell and PATH and uses explicit source and destination arguments. Test one
scheduler at a time; the destination lock also prevents overlapping archive
publication. Verify actual scheduled output and restoration.

## Undo and completion evidence

Disable and stop the named user timer, then remove only the two installed lab
unit files and run user daemon-reload. Remove only the added cron line if it was
used. Retain earlier backups until the independent restore has been verified.
Completion includes the retention TODO, changed cases, an actual restoration,
the scheduler identity/path record and a tested undo. A program run does not
prove worksheet completion or that a timer executed.
