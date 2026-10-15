# Readiness Gates and Reversible Release Activation

This central project belongs to the optional Service Deployment Studio in
the Linux Integration Studio Archive. It combines earlier static serving and
process-operation habits into a controlled deployment sequence. Completing
this studio is optional; Operations Capstone remains the required integration
project.
The question is whether an activated candidate is the intended ready release,
and what becomes visible after a rejected candidate is rolled back. The
manifest transfer separately checks payload integrity; the concurrency
extension separately coordinates competing publishers.

## Equipment, state and the named task

Use an ordinary account in an owned Linux lab with Bash, Python 3.8+ and Nginx
installed. Check `uname -s`, `id`, `python3 --version` and `nginx -v`. Keep
task.sh, task.py, nginx_lab.py and all four release text fixtures together
in the extracted role folder. The site IDE edits, saves and exports them;
execute the exported role in that external Linux terminal.

The equipment creates a private prefix inside an explicit empty owned
nonsymlink parent. It starts one foreground Nginx process on a new loopback
port and records the actual UID/PID, syntax check, requests, responses and
logs. The private current symlink selects release-a or release-b. Replacing
that symlink with os.replace is one atomic namespace change on this filesystem.
It does not make several HTTP requests a single transaction or establish
power-loss durability. Each probe is retained as its own observation.

Nginx serves current/health.txt and current/index.txt with its open-file cache
disabled. A health response identifies the selected release. A 200 status
alone does not prove that the intended identity answered. The named starter
readiness_ok function checks only status. Repair it to require both status 200
and the exact expected response bytes. The response stores bodyBase64;
base64.b64decode(reply["bodyBase64"]) recovers its bytes. expected_health
already holds bytes, and boolean and combines the two conditions. Preserve
the real server and rollback
machinery; compare the reference after saving an independent attempt.

## Predict and run the activation sequence

From the extracted role folder:

~~~bash
lab_root=$(mktemp -d)
bash task.sh "$lab_root" > deployment.json 2> deployment.err
deployment_status=$?
printf 'status=%s\n' "$deployment_status"
cat deployment.err
cat deployment.json
~~~

Predict these checkpoints before reading the report:

1. The initial release-a health and page return 200 with their supplied bytes.
2. A good release-b candidate returns the expected health and stays selected.
3. A candidate whose health still says release=a returns 200 but has the wrong
   identity. The completed policy rejects it and restores release-b; the
   untouched starter accepts it and exposes its wrong page.
4. A candidate with no health file returns 404. Both policies reject it, but
   rollback restores the actual preceding target. A bad earlier decision can
   therefore influence the state restored by a later rollback.

The report records beforeTarget, candidate, actual health response,
readinessAccepted, rolledBack and the actual afterTarget. Request the page
after each decision rather than assuming the link operation proves serving.
Observation status 0 means this sequence met its target behavior; the untouched
starter exits 1 after retaining the wrong-identity evidence. Neither status
completes the independent deployment-notes.md record.

The observer leaves the parent empty. Run again with --reverse to start at
release-b and deploy release-a as the good candidate. Predict which bytes and
target names change and which readiness/rollback decisions stay invariant.
The wrong-identity candidate deliberately retains release=a: its expected
identity is release=wrong, so it is still a distinct failed candidate.

## Inspect, reject, recover and undo

Use `--hold-seconds 8` to inspect the running owned prefix before the sequence.
Read the actual port, PID and prefix from ready.json in another terminal and
use curl against /health.txt and /index.txt at that loopback port. The hold
creates an inspection window; it does not install a persistent service.

Use --broken-config in a separate empty parent. The actual nginx syntax test
rejects an unknown directive, status 2 retains stderr, and no server starts.
Rerun without that flag for recovery. Missing/nonempty/symlink parents and an
invalid hold are rejected without clearing their contents. Ctrl-C during
the hold returns 130 and retains partial observation with owned-process cleanup.

After every run, inspect serverPidGone, listenerClosed, ownedCaseRemoved and
workspaceEmpty, and confirm the named PID/socket are gone before removing
only the empty parent with rmdir. Preserve the report and logs first. The
source fixtures and any outside files stay unchanged. Complete all five notes
tasks with predictions, exact responses, the repair, changed order, rejection,
rollback, recovery and undo. This is an owned deployment-mechanism observation;
data migrations, persistent service installation and public hosting require
their own operating plans and evidence.

Primary references: [Python atomic replacement](https://docs.python.org/3/library/os.html#os.replace)
and [Nginx file-cache configuration](https://nginx.org/en/docs/http/ngx_http_core_module.html#open_file_cache).
