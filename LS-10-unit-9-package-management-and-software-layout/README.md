# Installed Packages, Command Ownership and File Layout

This is the required Unit 9 Linux Systems project. Investigate an installed
package and connect its database records to actual files. Complete the core
before choosing the optional manual-install comparison or dependency-recovery
lab. The troubleshooting notebook continues this investigation; it is not a
second copy of the project.

## Environment and saved work

Use an ordinary account in a Debian or Ubuntu Linux lab, including a suitable
WSL distribution. Python 3, Bash, `dpkg-query` and an installed `bash` package
are needed. The collector only reads installed metadata and file information;
it writes the report path supplied on the command line. It rejects root,
unsupported platforms, missing packages, invalid query names and existing
report files. It neither installs nor upgrades packages. Keep the original
reports alongside the notes so a later run cannot erase the first observation.

The site's IDE edits and saves these sources and notes. After confirming the
course import, open `package-notes.md` first, download the ZIP and extract it.
Run the commands in that extracted role folder in the Linux terminal. Saving
in the browser does not execute Linux commands. Save observations back into
the same attempt; the reference is a comparison after an independent attempt.

## What a package manager tracks

An installed package is a versioned collection of files plus metadata. Its
database can identify the package version, architecture, dependencies, state
and recorded paths. One package can place commands, documentation, support
files and configuration in different directories. A directory name alone does
not establish who installed a file. Query the database and inspect the actual
path together.

Debian-family systems commonly use APT to select repository versions and
resolve dependency changes; dpkg maintains installed-package state. RPM-family
systems commonly use DNF and an RPM database. Older systems can expose `yum`;
the distribution's version and documentation determine its behavior. These
families share questions but not interchangeable commands or databases. This
project's executable collector is explicitly for the Debian family.

Dependencies describe relationships between packages, not a complete runtime
trace. A `Depends` entry can contain version constraints or alternatives. Do
not split it into a list of commands to install. An installed database record
also does not prove the original download's authenticity or repository.

## Prediction and first observation

In `package-notes.md`, predict whether Bash's command, manual, startup
configuration and support files will all occupy one folder. Predict whether
the package database will name the same command path that the shell resolves.
Then run:

```sh
uname -s
id -u
python3 --version
dpkg-query --version
bash task.sh --package bash --command bash --report bash-first.json
python3 -m json.tool bash-first.json
```

Expect a successful collection with an installed package version and a list
of paths. Exact versions and counts depend on the lab; the notes must record
actual values. Exit status zero confirms collection, not completion of the
learning tasks. `learnerWorksheetCompletionInferred` remains false.

`package_report.py` runs the queries with an explicit argument list, records
their actual status and timing, and requires an `ok` error flag and current
state `installed`. The full status also includes a separate requested action:
`hold ok installed` and `deinstall ok installed` can still describe installed
files. Read the report's `state` fields separately; a requested removal is not
proof of completed removal. No missing-input error is converted into an empty
successful count. A report is created only after the queries complete. Its
mode is private to the current account and an existing report is not replaced.

## Connect the records to files

Identify at least one recorded command and one documentation path. Inspect
both with `ls -ld`, quoting each path. Explain whether each is a file,
directory or symbolic link and whether it exists. Find a configuration or
service path if this package records one; record "not supplied by this
package" when it does not. Do not invent a service just to fill a category.

Conventional locations provide clues: `/etc` holds system configuration;
`/usr/bin` and related command directories hold executables; `/usr/lib` holds
libraries and other support data; systemd unit directories contain service
definitions; `/usr/share/doc` and `/usr/share/man` contain documentation.
These categories are investigative aids, not a guarantee that every entry is
an executable or that every distribution uses exactly the same layout.

Read the report's `executable` section separately from its `package` section.
The shell searches `PATH`; the resulting command can belong to a different
package or to a manual install. Merged-/usr systems can expose `/bin` as a
link to `/usr/bin`, while the package database retains the older spelling.
The collector checks a legacy alias only when it names the same actual file.
Record each ownership query's status and result. An untracked command does
not become package-managed simply because it runs successfully.

## Changed cases and failure evidence

Collect a second installed package, for example:

```sh
bash task.sh --package coreutils --command ls --report coreutils-first.json
```

Compare the package version, dependency text and layout. The executable's
owner is reported independently. Predict and then try an intentionally absent
package, using a fresh report name. Confirm a nonzero status and no completed
report. Retry the first successful command with `--report bash-first.json`;
it must reject replacement and preserve the original bytes. These are normal
diagnostic cases, not reasons to hide an error with `|| true`.

## Plan a package change without performing it

Write a change plan before any actual package modification. Name the current
version, desired version, reason, source, dependency changes, service/reboot
effects, preservation of local configuration, rollback evidence, and a
post-change command that demonstrates the required behavior. Consult local
APT metadata with `apt-cache policy bash`. A candidate version is a current
selection from configured metadata, not proof of where an already installed
copy originally came from. With an instructor, inspect the read-only
simulation `apt-get --simulate install bash` and explain its proposed changes.
Package lists may be stale or absent; record that limitation. A successful
simulation is not an installation and does not establish runtime health.

If an approved disposable lab later performs a real change, capture before
and after versions, actual install status, service restart results and the
behavioral check. Package installation can leave a package unpacked but
unconfigured when a dependency is missing. Keep that state distinct from an
installed and healthy application. The optional dependency lab examines this
with a separate owned database rather than the host's installed packages.

## Completion and instructor walkthrough

Finish the five named tasks in the notes: prediction, package/file comparison,
changed package, failure/record preservation, and proposed change plan. At
least one prediction must be compared with actual evidence. Explain one
surprise rather than silently rewriting the prediction. Walk through the same
record with an instructor, including the exact path and version that support
each claim. The reference notes explain a valid method and interpretation;
they do not supply fabricated observations for this lab.

For an RPM-family lab, use the distribution's documented `rpm -qi`, `rpm -ql`
and `rpm -qf` queries and DNF's installed-package/version information to answer
the same questions. Save that as a separate observation, clearly naming the
platform. Do not run this Debian collector and label its failure an RPM
package investigation.

Primary references: [dpkg-query](https://manpages.debian.org/trixie/dpkg/dpkg-query.1.en.html),
[dpkg](https://manpages.debian.org/trixie/dpkg/dpkg.1.en.html) and
[Debian package metadata](https://www.debian.org/doc/manuals/debian-handbook/sect.package-meta-information.en.html).
