# Dependency state and recovery evidence

## 1. Predict and inspect package metadata

TODO: Record the separate lab root/database, UID and versions. Predict the
first app install's status, file presence, installed state and needed recovery.
Inspect the real local archive's declared dependency and payload.

## 2. Missing dependency

TODO: Retain actual install status, query stdout/stderr/status, audit output,
app file presence and runtime failure. Distinguish unpacked from configured.

## 3. Wrong installed version

TODO: Record base 1.0 installation, failed app configuration, both actual
database states and runtime status 2. Explain the version requirement.

## 4. Upgrade, runtime and configuration

TODO: Record base 2.0 installation, app state before configuration, its actual
runtime output, explicit configuration, both final states and an empty audit.
Explain why a working program alone does not prove configured metadata.

## 5. Removal, changed sequence and recovery limits

TODO: Predict and observe blocked base removal and the still-working pair.
Remove app before base; verify payload removal, database state, retained logs,
and unchanged outside sentinel. Try base-2.0-first in a new lab. Explain
package versus runtime checks and the extra needs of a real patch plan.
