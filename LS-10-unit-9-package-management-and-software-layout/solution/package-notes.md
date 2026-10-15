# Package and layout investigation: reference reasoning

This reference describes how to complete the same investigation. Actual
versions, paths, statuses and observations must come from the current lab's
saved reports. Reading or running the reference does not complete a learner's
record.

## 1. Prediction before running

A reasonable initial prediction places executable commands under a command
directory, configuration under `/etc`, and manuals under `/usr/share/man`.
The package is not necessarily a single directory. A prior prediction can be
wrong: record it, then explain the observed layout. The presence of merged-/usr
links means two path spellings can name the same underlying file.

## 2. Actual package and filesystem evidence

Use the report's installed metadata for the exact version, architecture,
state and dependency expression. Select real entries from `files` and inspect
them. Do not assume Bash installs a systemd service. If no service path is
listed, report that absence; the project does not require inventing one.
Classifications describe conventional locations, while existence and link
targets describe the current filesystem. Neither is a package authenticity
check. Record any missing listed file as a discrepancy to investigate.

## 3. Changed package and command ownership

Compare a new coreutils/ls report with Bash's report. They should describe
distinct packages and sets of files, but exact counts and versions vary. The
resolved executable is found through PATH independently of the selected
package. Check the ownership-query records rather than inferring ownership
from the file's name. On a merged-/usr lab an equivalent `/bin` alias can
explain a successful database match after the resolved `/usr/bin` spelling
has no match. An untracked executable is also a possible real observation.

## 4. Failure and retained evidence

An absent literal package should produce a nonzero collector status and no
completed report. Existing output must be rejected without replacing it.
Preserve and compare its bytes. Empty successful inventory output after a
failed query would hide the difference between "no relevant paths" and
"collection failed". Save the actual failure status and diagnostic.

## 5. Proposed change and post-change check

Use actual current metadata and a reasoned target. Inspect available APT
policy/simulation information, identifying stale or unavailable metadata.
Document dependency/configuration/service effects and recoverable state.
After an authorized real change, installed-version evidence and a separate
runtime check are both needed. A simulation predicts a transaction; it does
not perform it. Likewise, dependency metadata does not prove that a service
has restarted or an application works. The manual-install and dependency
supplements extend these questions with different experiments.
