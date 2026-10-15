# Dependency state and recovery: reference reasoning

Supply the current lab's actual output and statuses. This reference explains
relationships without pretending that a supplied run completes the record.

## 1. Predict and inspect package metadata

The app declares a base-version relationship. Building an archive does not
install it. The owned root has its own dpkg database, distinct from the host's
installed packages. All modification commands must identify that root.

## 2. Missing dependency

The initial app install unpacks files but cannot configure the package without
the base. Require the nonzero install status and observed unpacked state.
The actual runtime also fails because its needed file is missing. These are
separate observations; one diagnostic must not be replaced by empty success.

## 3. Wrong installed version

Base 1.0 can be fully installed while failing the app's `>= 2.0` relationship.
App configuration remains unsuccessful; the program separately rejects 1.0
with status 2. Merely finding a package by name cannot prove a versioned
dependency has been satisfied.

## 4. Upgrade, runtime and configuration

After installing base 2.0, observe the app state before explicitly configuring
it. Its runtime can now work while its database state remains unpacked.
Configure it, then require both installed states, an empty audit and another
behavioral run. Do not infer restart or reboot evidence for this stateless
demo. Actual applications may have those additional change requirements.

## 5. Removal, changed sequence and recovery limits

dpkg should refuse base removal while the configured app depends on it; the
pair should still work. Remove the app first, then the base. Require absent
payload files and no installed lab packages while preserving logs/archives.
Installing base 2.0 first should make the first app installation succeed in a
fresh lab. APT's repository dependency planning differs from dpkg installing
only supplied local archives. Neither a simulation nor package metadata alone
establishes a healthy real service after patching.
