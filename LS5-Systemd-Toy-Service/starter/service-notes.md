# User service observation record

## Prediction and direct app checks

Record the named render_heartbeat task, expected rows, unfinished status,
valid and invalid settings, boundary/Unicode case and elapsed time.

## Environment and installed identity

Record Linux/Python/systemd versions, UID/GID, real user-manager connection,
source role, unique unit/install paths and the installed unit directives.

## Actual managed operation

Record active/substate/MainPID/exit status, the owned process command/UID,
selected journal rows, persistent activation link and the enabled/stopped
distinction. Keep process evidence separate from the start command's status.

## Changed cases and cleanup

Record manual restart PID/invocation changes, the owned SIGKILL case and actual
automatic restart count, invalid-interval failure, restoration and fresh
journal rows. Record the stopped process, disabled link and removed unit.
