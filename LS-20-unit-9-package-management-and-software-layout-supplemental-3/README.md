# Dependency Failure, Installed State and Recovery

This optional Unit 9 extension follows the installed-package investigation.
Use actual dpkg operations to distinguish an unpacked application, a satisfied
dependency, a configured package and a working program. It has its own attempt
and evidence record, separate from the manual-release comparison.

## Scope, equipment and prerequisites

Use an ordinary account in an owned disposable Debian/Ubuntu Linux lab with
Python 3, Bash, `dpkg`, `dpkg-deb` and `dpkg-query`. The driver constructs three
tiny local packages from the supplied source: base 1.0, base 2.0 and app 1.0.
The app declares `Depends: linux-layout-base (>= 2.0)`. No repository download,
maintainer script, trigger, root-owned payload or privileged operation is part
of these packages. The host's installed package database is not the experiment.

The installation root and its database live below one newly created owned
lab. Every dpkg change supplies that root explicitly and records its command
and status. `--force-not-root` permits this ordinary-account demonstration;
it does not waive dependency checks. Never drop the root option, copy these
operations onto the host database, add sudo, or add `--force-depends`. Use the
supplied driver to keep the operation scoped. If the environment cannot run
this lab, retain the diagnostic and resolve its prerequisite rather than
pretending that an installation occurred.

Both roles provide working equipment. Complete the named observation tasks in
`dependency-notes.md`; reference reasoning is not this machine's evidence.
After confirming the IDE import, open those notes first, save/download the
ZIP, extract the role and use its Linux terminal. Browser saves do not execute
dpkg operations. Return observations to the same saved attempt.

## Package dependencies and state

Package metadata describes a version requirement. Here app 1.0 requires base
2.0 or later. Installing an archive can unpack its files before configuration
fails. File presence and even a successful direct program run therefore do not
by themselves establish `install ok installed` state. Read the actual database
state separately. dpkg installs supplied archives and checks relationships;
it does not fetch a missing dependency. APT can plan a repository transaction
and resolve related changes, using its configured metadata and policy.

## 1. Predict and construct the local packages

Predict the first app install's status, whether its file will exist afterward,
its database state, and what will be needed for recovery. Then run:

```bash
uname -s
id -u
dpkg --version
python3 --version
lab_parent=$(mktemp -d)
lab="$lab_parent/dependencies"
bash task.sh init --lab "$lab"
bash task.sh build --lab "$lab"
dpkg-deb --field "$lab/packages/linux-layout-app-1.0.deb" Package Version Depends
dpkg-deb --contents "$lab/packages/linux-layout-app-1.0.deb"
```

Keep the shell open and save the exact `OWNED_LAB` path. The package build
retains this lab account's file ownership and writes a manifest of archive
hashes. It refuses an existing workspace/build; each changed experiment uses
a new lab. Package structure and installed state are different observations.

## 2. Observe the missing dependency without hiding failure

```bash
bash task.sh install-app --lab "$lab"
printf 'INSTALL_STATUS=%s\n' "$?"
bash task.sh query --lab "$lab"
bash task.sh audit --lab "$lab"
bash task.sh run --lab "$lab"
printf 'RUNTIME_STATUS=%s\n' "$?"
```

Expect a nonzero install status and an app that is unpacked but not configured.
`query` asks the separate database for both packages; its own status can be
nonzero while the base is absent. Retain stdout, stderr and status separately.
`audit` identifies the incomplete package. The unpacked program should report
a missing dependency file and exit 1. This failure is an intended observation,
not a reason to continue as though installation succeeded.

## 3. Distinguish an installed wrong version from a sufficient one

```bash
bash task.sh install-base --lab "$lab" --version 1.0
bash task.sh configure-app --lab "$lab"
printf 'CONFIGURE_STATUS=%s\n' "$?"
bash task.sh query --lab "$lab"
bash task.sh run --lab "$lab"
printf 'RUNTIME_STATUS=%s\n' "$?"
```

Base 1.0 can be installed successfully, while app configuration still fails
its `>= 2.0` requirement. The app remains unpacked. Its direct runtime check
separately rejects base 1.0 with status 2. Record those distinct statuses and
reasons. A dependency's name being present is not enough to satisfy a version
constraint. Do not edit the installed status database to make it look healthy.

## 4. Upgrade, check runtime, then configure and audit

```bash
bash task.sh install-base --lab "$lab" --version 2.0
bash task.sh query --lab "$lab"
bash task.sh run --lab "$lab"
bash task.sh configure-app --lab "$lab"
bash task.sh query --lab "$lab"
bash task.sh audit --lab "$lab"
bash task.sh run --lab "$lab"
```

Observe the app's actual database state before and after explicit
configuration. With base 2.0 the supplied program prints
`dependency-demo ready base=2.0` and exits 0, including before the app's
configuration step. That pre-configuration run deliberately demonstrates
that runtime success and fully installed metadata are different claims.
After configuration, require both packages to show `install ok installed`,
an empty consistency audit and another successful behavioral run.

These packages have no service unit or persistent service process. No service
restart or reboot is established by this experiment. A real patch plan must
identify such effects for the real application, preserve configuration/data,
retain recovery evidence and run its actual post-change acceptance check.

## 5. Observe dependent removal and cleanly undo the lab

Predict what should happen if the installed base is removed while the app
still depends on it. Then run and immediately retain the status:

```bash
bash task.sh remove-base --lab "$lab"
printf 'REMOVE_BASE_STATUS=%s\n' "$?"
bash task.sh query --lab "$lab"
bash task.sh run --lab "$lab"
bash task.sh remove-app --lab "$lab"
bash task.sh remove-base --lab "$lab"
bash task.sh audit --lab "$lab"
```

Require the first removal to fail without breaking the working installed
pair. Remove the dependent first, then the base. Verify the app and base
payload paths are gone and the separate database has no installed lab
packages. Record archive, dpkg-log and operation-log retention separately
from removal of installed payloads. Keep an outside sentinel unchanged.

Complete all five note sections with predictions and real query/audit/runtime
records. Preserve `dpkg.log` and `operations.jsonl`; the latter contains paired
command lifecycles, outputs and actual statuses. Repeat a changed sequence in
a fresh lab, such as installing base 2.0 before the app, and explain why its
first app install succeeds. Failed commands never become a success flag for
the whole investigation. After saving evidence, delete only the exact printed
disposable workspace and its own parent. Use the same numbered sequence for
independent study or pauses in an instructor walkthrough.

Primary references: [dpkg states and scoped installation options](https://manpages.debian.org/trixie/dpkg/dpkg.1.en.html)
and [Debian dependency metadata](https://www.debian.org/doc/manuals/debian-handbook/sect.package-meta-information.en.html).
