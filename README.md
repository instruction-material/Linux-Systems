# Linux Systems

This repository holds starter and solution material for the Linux Systems
course. The labs are terminal-first and assume students are working on a Linux
VM, WSL instance, or remote Linux machine.

## Labs

- `LS1-Personal-Lab-VM`: environment validation and safe workstation setup
- `LS2-Static-Site-from-srv`: serve a static site from `/srv` with Nginx
- `LS3-Nginx-Reverse-Proxy-App`: run a toy app behind Nginx
- `LS4-Apache-Virtual-Host-Compare`: compare Apache virtual host setup to Nginx
- `LS5-Systemd-Toy-Service`: operate a persistent service with `systemd`
- `LS6-Backup-Cron-and-Timer`: schedule backups with `cron` and `systemd`

Each lab includes a `starter/` directory for learners and a `solution/`
directory for instructors or advanced review.

## Owned workflow repairs and native acceptance

The Shell Foundations and Permissions packs now have distinct operating tasks:
log enumeration with trustworthy status, and an observed ancestor-traversal
failure with a narrow correction. The lab-readiness, static-site and backup
packs include complete readings, explicit operating boundaries and changed-case
instructions. Backup examples use the same user identity for cron and a user
timer, and restoration is checked independently of archive creation.

Run the Linux acceptance with an ordinary account, GNU command-line tools and
Nginx available:

~~~sh
python3 test/verify_owned_labs.py --proof output/linux-owned-labs.json
~~~

The suite covers working references, deliberately unfinished starters, four
independent learner completions, real access observations, archive restoration
and isolated serving. It does not infer worksheet completion, VM provisioning
or scheduled execution. The remaining generated reference scripts are still
outside this repaired source track; their differing lesson purposes need the
continuing course audit. The site import integration is a separate gate.

## Logging and observability source track

Unit 7 now separates a scoped user-journal incident, optional structured application-log transfer, and optional disposable-file retention. Each pack includes its input fixture or complete setup, named learner task, working reference, operating predictions, changed cases and evidence record. The troubleshooting notebook belongs to the core incident attempt.

Run `python3 test/verify_logging_labs.py --proof output/linux-logging-labs.json` on the owned Linux user-manager environment with logrotate. The native gate verifies real journal UID/PID/boot/priority and invocation recovery, structured response timelines, compressed retention, no-op empty input, debug preview, path boundaries and cleanup. `--offline-only` checks the two analysis packs without claiming journal or logrotate acceptance.

## Editing and configuration core source track

The required Unit 4 core now exercises a validated configuration edit against an actual disposable process. It preserves exact backup bytes, separates disk edits from cached process state, observes explicit reload and rejected reload, and verifies rollback, file modes and cleanup. Its notebook continues the same attempt. The two optional Unit 4 packs remain outside this repair and require their distinct environment-file and controlled-replacement tasks.

Run `python3 test/verify_editing_core.py --proof output/linux-editing-core.json` as an ordinary Linux account with GNU coreutils. The native gate covers the named unfinished starter, working reference and an independent learner completion, using actual process signals and observed output. `--offline-only` checks syntax and configuration value cases; `--local-process-preflight` can exercise an existing POSIX/GNU tool setup on another host. Neither alternate mode is Linux acceptance. Site import, save, review and export acceptance is a separate gate.
