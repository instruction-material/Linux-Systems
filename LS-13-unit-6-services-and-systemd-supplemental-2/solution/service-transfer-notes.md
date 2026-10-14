# Service transfer evidence

Record the Linux release, user-manager version, actual UID, selected role,
owned unit/install paths and chosen loopback port. Predict the effect of each
named path task before changing the unit. Record command status separately from
LoadState, ActiveState, MainPID, ExecMainStatus and actual journal diagnostics.

Include missing working-directory and missing app-argument cases, the completed
unit, matching process UID/command path, actual loopback socket/PID, GET and HEAD
health responses, manual and automatic restarts, enabled versus stopped state,
repair, source-file changes and final cleanup. A syntax check or active state
alone does not establish HTTP readiness. The HTTP code is supplied and working;
the task concerns service paths and operation rather than another handler build.

## Reference predictions

The working directory is the installed root and ExecStart names transfer_app.py.
A missing working directory fails before Python with 200/CHDIR. A missing Python
script argument exits 2 and reports that missing file. The bounded prevent list
avoids retrying these task/configuration failures. A healthy unit has an owned
MainPID and an actual 127.0.0.1 listener returning the documented health body.
These predictions do not replace the observed evidence above.
