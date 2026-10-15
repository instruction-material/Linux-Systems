# Package and layout investigation

## 1. Prediction before running

TODO: Predict the command, configuration, documentation and support-file
locations for Bash. Predict whether shell resolution and database ownership
will use identical paths. Give a reason for each prediction.

## 2. Actual package and filesystem evidence

TODO: Record lab/distribution, date, package version, installed state,
architecture and dependency text. Name the saved report. Inspect one command
and one documentation path, plus configuration/service paths if present.
Record actual existence and link targets. Explain absent categories honestly.
Compare each prediction with these observations.

## 3. Changed package and command ownership

TODO: Collect a different installed package and compare its layout and
metadata. Record the requested command, resolved file, each ownership query
and whether an owner was found. Explain a merged-/usr alias if encountered.

## 4. Failure and retained evidence

TODO: Predict and observe an absent-package failure. Record the nonzero
status and absence of a completed report. Retry an existing report path and
verify that its prior bytes remain unchanged. Explain why hiding the error
would invalidate an inventory claim.

## 5. Proposed change and post-change check

TODO: Name current/desired version, source and reason, dependency impact,
configuration preservation, service/reboot effects, recovery evidence and a
specific behavioral check. Record any APT metadata or simulation limitations.
Separate proposed changes, actual installation, installed state and runtime
verification. Do not claim a simulated change was installed.
