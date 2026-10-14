# Log Investigation Extension Practice

This optional extension measures a retention policy on disposable application
files with the real logrotate program. It follows investigation work but adds
an operating question: which batches remain after rotation, how are they read,
and can the application write to the newly created active file? It does not
vacuum a system journal, alter system logrotate jobs or schedule a new service.

## Source and task

`task.sh` is a supplied renderer and runner for exactly one owned application
log. `logrotate.conf` is the learner task: replace TODO with a policy retaining
two archives. The untouched starter produces logrotate's bad-count failure;
no valid rotation is claimed. The reference uses `rotate 2`. `size 1` provides
a small disposable trigger; `--force` makes these manual tests reproducible.
`compress` stores rotated batches in gzip files. `create 0600` creates a private
new active file, `notifempty` skips empty input and `missingok` tolerates an
absent file in the policy. The supplied runner deliberately requires app.log
for the lab so an unintended missing input remains visible.

The directory must belong to the active user, have mode 700 and contain the
exact lab marker. Its app.log, generated policy and state paths must be regular
files rather than symlinks. The runner confines its generated template path to
this directory. Spaces in a directory name are supported; quotes, backslashes
and line breaks are rejected explicitly. Bash, Python 3, GNU stat, gzip and
logrotate are required in the owned Linux environment. The site IDE edits and
exports this pack; operating commands run in that Linux terminal.

## Predict, preview and rotate

Run from the selected role directory. Create a new private lab and give it a
marker that distinguishes it from other folders:

~~~sh
lab=$(mktemp -d "${TMPDIR:-/tmp}/linux-log-retention.XXXXXX")
chmod 700 "$lab"
printf 'linux-log-retention-v1\n' >"$lab/.linux-log-lab"
printf 'batch-one\n' >"$lab/app.log"
logrotate --version
bash task.sh "$lab"
~~~

After completing the policy, one run creates app.log.1.gz containing batch-one
and a new empty app.log with mode 600 as reported by GNU stat. Inspect the
rendered policy and use logrotate's debug mode as a read-only preview of future
operations; debug mode does not rotate files or update the state file:

~~~sh
cat "$lab/rotation.conf"
logrotate --debug --state "$lab/rotation.state" "$lab/rotation.conf"
gzip -cd -- "$lab/app.log.1.gz"
stat -c '%a %U %n' -- "$lab/app.log"
printf 'batch-two\n' >>"$lab/app.log"
bash task.sh "$lab"
printf 'batch-three\n' >>"$lab/app.log"
bash task.sh "$lab"
gzip -cd -- "$lab/app.log.1.gz"
gzip -cd -- "$lab/app.log.2.gz"
~~~

Predict before each operation. After three nonempty rotations, the newest
archive contains batch-three, the second contains batch-two and batch-one has
expired under the count-two policy. Count archives and verify their contents;
a successful command alone does not prove retention. Run again with the empty
active file: notifempty should leave the archive identities and contents
unchanged. Write a new batch to the active file to show that creation and
ownership permit subsequent logging.

Place an unrelated sentinel outside the lab and verify its hash remains
unchanged. Try a missing marker or a symlinked app.log in a separate disposable
copy: the runner must reject those inputs before calling logrotate. Try a path
containing spaces. The lab state file is local to this exercise; never pass a
system state file or /etc/logrotate.conf to these commands.

## Cleanup and evidence

Record the policy, version, preview, actual archive contents, expiration,
active-file mode, empty-run result, sentinel hash and cleanup in
`retention-notes.md`. Remove only the directory created above:

~~~sh
case "$lab" in
    */linux-log-retention.*)
        test "$(cat -- "$lab/.linux-log-lab")" = linux-log-retention-v1 && rm -r -- "$lab"
        ;;
esac
~~~

The independent and instructor routes share the prediction/operation/inspection
sequence. Review the reference after completing the policy draft; retain a
separate saved learner attempt. Native acceptance must use actual logrotate,
not simulated archive names. This exercise observes manually invoked retention;
it does not claim that a scheduler or running application reopened a file.
Reference: [logrotate manual](https://github.com/logrotate/logrotate/blob/main/logrotate.8.in).
