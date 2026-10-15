# Manual release and ownership: reference reasoning

This is a method and interpretation, not a record of the current lab. Supply
actual commands, hashes, paths, statuses and output from an independent run.

## 1. Predict and identify the objects

The C file is source; the compiled executable is a build product; the tar file
is a distribution object; a release directory contains installed files. The
active link selects an installed release. Successful compilation alone does
not register a package or establish an installed runtime.

## 2. Installed layout and real ownership

Compare the recorded manifest hash with the actual installed binary and run
that binary. Ask dpkg about the exact path. A fresh manual prefix should be
untracked even though the program works. A matching local hash relates two
objects; it does not prove an authentic supplier or enroll files in dpkg.
Record unexpected ownership results rather than copying the expected answer.

## 3. Changed version and rollback

Require runtime observations of 1.0, then 2.0, then 1.0 after switching back.
Each active-link target must agree with its version and recorded binary.
Other releases remain available. This rollback covers this stateless demo;
it does not establish recovery of configuration, migrated data or services.

## 4. Failure and bounded removal

A duplicate archive must fail without replacing it. Removing inactive 2.0
should leave active 1.0 and the outside sentinel unchanged. The source,
archives and logs have different lifetimes from installed payloads. Retain
the actual failure status, removal evidence and later working check.

## 5. Explain and preserve the record

An operator of a manual install must track source, compiler/options, release
bytes, layout, update responsibility and recovery. Contrast that record with
the package core's installed database evidence. Keep earlier observations,
then remove only the exact owned experiment after retaining its evidence.
Reference equipment success does not complete a learner observation record.
