# Environment and drop-in evidence

Record actual Linux/user-manager identity and the owned unit/install/drop-in
paths. Hash the original base unit and keep that fragment unchanged. Predict
which source supplies each environment value: unit defaults, the base file,
Environment in the drop-in and the replacement file.

Record the baseline journal message/PID, merged unit and EnvironmentFiles,
untouched drop-in behavior, the named completion, actual process environment,
new PID and journal rows, an environment-file edit without a restart, behavior
after restart, invalid configuration and repair. Finally remove only the owned
drop-in and observe restoration of the base message before complete cleanup.
Code/configuration success does not complete this observation record.

## Reference predictions

EnvironmentFile values take precedence over Environment. The untouched drop-in
therefore keeps base-heartbeat despite its Environment assignment. The empty
EnvironmentFile directive clears the inherited file list; the following path
selects override.env. Editing that file affects the next process, not the
already running process. Removing the drop-in, reloading and restarting restores
the unchanged base fragment and base-heartbeat. Confirm these predictions with
actual environment and journal observations.
