# Manual Release Layout and Package Ownership

This optional Unit 9 transfer project follows the installed-package core.
Build a supplied small program from source, make a release archive, install it
under an owned prefix, compare its ownership with the package database, and
observe a version switch and rollback. It is a separate attempt from the core
inventory. The dependency-recovery extension studies a different problem.

## Environment and learner task

Use an ordinary account in an owned Debian/Ubuntu Linux lab with Python 3,
Bash, `cc` and `dpkg-query`. Have the instructor provision missing tools before
the experiment. The C source is complete equipment; implementing C functions
is not the assignment. Both roles provide the same working driver and source.
The unfinished work is the five-part evidence record in `manual-notes.md`.
The reference supplies interpretation, not invented results from this machine.

After confirming the site IDE import, open `manual-notes.md`, save/download
the ZIP and extract the selected role. Run the following commands in that
role's Linux terminal. Browser editing does not compile or install Linux code.
Bring the observations back to the same saved attempt.

## Source, build, archive and install are different objects

Source is the human-readable C file. A compiler turns it into an executable
for this lab's platform. The archive bundles that executable and a manifest.
Installing the archive copies its two files into a release-specific directory;
an explicit link selects the active release. These steps leave different
evidence. A successful compilation does not show installation, and a recorded
hash does not establish who supplied trustworthy source.

Here the version is a compiler definition, so the same source produces 1.0
and 2.0 binaries. The flags request C17, normal diagnostics and rejection of
warnings. No system package is installed. No shell startup file or global PATH
is changed. The driver is deliberately restricted to the two supplied versions,
and it refuses existing builds, archives and installed release directories.
It writes only its fresh marker-protected lab; run it without sudo.

## 1. Predict, then build the first release

Predict whether `dpkg-query` will own a binary merely because it was compiled
successfully. Predict what will change when a version is selected and what
rollback will need. Keep the predictions in the notes before running:

```bash
uname -s
id -u
python3 --version
cc --version
lab_parent=$(mktemp -d)
lab="$lab_parent/manual"
bash task.sh init --lab "$lab"
bash task.sh build --lab "$lab" --version 1.0
bash task.sh archive --lab "$lab" --version 1.0
```

Keep this shell open and retain the exact `OWNED_LAB` path. `init` requires a
new path and creates a private marker and operation log. The build appears
under `builds/1.0`; the archive and its recorded SHA-256 appear under `archives`.
Read `layout_demo.c`: `--version` prints the selected version, `--status`
prints a status line, and an unsupported argument returns status 2.

Inspect the build and archive as different objects:

```bash
"$lab/builds/1.0/layout-demo" --version
tar -tzf "$lab/archives/1.0.tar.gz"
cat "$lab/archives/1.0.sha256"
```

Expect version `1.0` and two archive files: `bin/layout-demo` and
`share/layout-demo/manifest.json`. These lab-specific paths are chosen to make
the distinction visible; they are not a requirement for every upstream program.

## 2. Install, select and inspect real ownership

```bash
bash task.sh install --lab "$lab" --version 1.0
bash task.sh activate --lab "$lab" --version 1.0
bash task.sh check --lab "$lab"
readlink "$lab/current"
"$lab/current/bin/layout-demo" --status
```

The active link should name `releases/1.0`, and the runtime should report 1.0.
`check` compares installed binary bytes with the release manifest, runs that
binary's version query and asks the real installed dpkg database about its
exact path. In this fresh owned prefix, expect ownership status 1 and
`packageManaged: false`. That query result is an observed ownership answer,
not a failure to compile or run. A different dpkg query error is a failed
check and is retained as such.

The manual manifest relates this installed binary to the recorded build;
it does not enroll it in dpkg or prove authenticity. The person operating a
manual install must retain source/version information, build commands,
archive hashes, configuration placement, update responsibility and recovery
instructions. Compare this burden with the required core's package records.

## 3. Change the version and demonstrate rollback

```bash
bash task.sh build --lab "$lab" --version 2.0
bash task.sh archive --lab "$lab" --version 2.0
bash task.sh install --lab "$lab" --version 2.0
bash task.sh activate --lab "$lab" --version 2.0
bash task.sh check --lab "$lab"
bash task.sh activate --lab "$lab" --version 1.0
bash task.sh check --lab "$lab"
```

Require actual runtime versions 2.0 and then 1.0; the link's name alone is
insufficient. Record the binary hashes and the three runtime observations.
Activation changes the link atomically after validating the chosen release.
The other installed release remains present. Rollback here does not restore
a database, migrate user data, undo external effects or restart a service;
this supplied program has none of those responsibilities. A real change plan
must address them when the application has them.

## 4. Preserve a failure and an outside sentinel

Retry `archive` for the already recorded version 1.0. Require a nonzero status
and unchanged archive bytes. Do not turn this diagnostic into success with
`|| true`. Before testing removal, create a small sentinel file in the parent
directory, outside the lab, and record its bytes. Remove release 2.0 while 1.0
is active, then check 1.0 again:

```bash
printf 'outside sentinel\n' >"$lab_parent/sentinel.txt"
bash task.sh remove --lab "$lab" --version 2.0
bash task.sh check --lab "$lab"
cat "$lab_parent/sentinel.txt"
```

Require that the inactive release is gone, the active version still runs,
archives/evidence remain, and the outside sentinel is unchanged. The driver
rejects unexpected release files, altered binary/manifest pairs, symlinks in
owned directory paths and unrecognized active links. If a diagnostic occurs,
keep its exact output and status and resolve it before claiming success.

## 5. Explain, retain and clean up

Complete all five named note sections with predictions, raw commands/output,
exit statuses, hashes, link targets, actual ownership results, changed version,
rollback and cleanup observations. Read `operations.jsonl` for paired command
lifecycles and their actual output. Compare a different run in a fresh lab
instead of replacing the first evidence.

Remove release 1.0 only after saving the record. This removes the active link
and that release, while leaving archives and the command log for inspection.
A subsequent `check` should fail because no release is active. Retain the
notes and evidence before deleting only this exact printed disposable lab and
its own parent/sentinel. The collector does not claim worksheet completion.
The numbered observations support independent reading or a paced walkthrough
with an instructor.

Primary reference: [dpkg-query path ownership](https://manpages.debian.org/trixie/dpkg/dpkg-query.1.en.html).
