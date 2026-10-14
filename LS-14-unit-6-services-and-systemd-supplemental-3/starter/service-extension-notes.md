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
