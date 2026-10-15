# Listener Failure versus an HTTP Error

This optional transfer follows the required interface/route investigation.
Keep the same local path while changing one service property at a time.
Complete `listener-notes.md`; do not replace evidence with a generic list of
networking commands or change the host's networking configuration.

## Equipment and recording

Use an ordinary account in a Debian/Ubuntu Linux lab or WSL distribution.
The lab needs Python 3, Bash, iproute2 (`ip`, `ss`), iputils `ping`, and curl
7.76 or later. The DNS continuation also needs BIND `dig`. Arrange for these
tools to be available before the experiment. No Python packages are installed.
The website IDE edits, saves and exports these files; run the commands in the
external Linux lab after extracting the ZIP. The equipment rejects a non-Linux
host, root, non-loopback destinations and invalid port numbers.

Keep two terminals in the same selected role folder. `serve` occupies terminal A
and prints a ready record containing its actual address, port and PID. The
kernel selects an available port; never assume the example from another run.
Ctrl-C in that terminal closes the owned listener. `inspect` in terminal B
records actual commands, statuses, output, timestamps and process identities.
Use a new report name for each case. An existing report, including a symlink,
is preserved. A completed private report has mode 0600 and appears only after
all observations have been collected.

The collector returns 0 when the record was saved, including a recorded failed
request. That status is not a claim that the network is healthy or the worksheet
is complete. Read the request's `curlStatus`, `httpStatus`, body and error text.
Input or platform rejection returns 2; an equipment/report failure returns 1.
The starter and reference contain identical working equipment. Normal work is
the five named tasks in the notes, not rewriting the supplied Python services.
The reference explains a method; it cannot supply the current lab's live PIDs,
ports, paths, packet results or your initial prediction.

## Distinguish the cases before running them

The bind address belongs to the listening socket. A connection aimed at
127.0.0.1 does not reach a socket bound only to 127.0.0.2, even when the numeric
port is equal. Linux normally routes both through loopback. Compare the exact
local address in `ss`, the selected destination, and the owning PID before
guessing a missing route or firewall rule. `ping` tests ICMP, not that TCP port.

The supplied HTTP service has two modes. Ready mode returns 200 at `/health`;
unavailable mode returns 503 there. Both return 404 for `/missing`. Every body
includes the actual serving PID. With `--fail-with-body`, curl retains 4xx/5xx
bodies but returns 22. A refused TCP connection instead has curl status 7 and
no HTTP response. The collector saves these distinct outcomes without turning
them into a fabricated all-pass summary.

## Controlled sequence

1. In notes task 1, predict the first failing layer and expected `ss`, curl
   status and HTTP status for each case below. Keep your initial prediction.
2. Terminal A: `bash task.sh serve --bind 127.0.0.2`. In terminal B enter
   `read -r -p 'Port from the ready line: ' port`. Then run
   `bash task.sh inspect --port "$port" --address 127.0.0.1 --report wrong-bind.json`.
   The listener exists at .2, while this request targets .1. Identify that
   mismatch using actual addresses rather than calling every failed request DNS.
3. With that same server still running, use
   `bash task.sh inspect --port "$port" --address 127.0.0.2 --report changed-target.json`.
   Expect HTTP 200. Explain why this diagnostic client change proves a reachable
   endpoint but does not move the server's bind address.
4. Stop the .2 server. Start `bash task.sh serve --bind 127.0.0.1` and enter its
   actual new port. Save `ready.json`, then run
   `bash task.sh inspect --port "$port" --path /missing --report missing-path.json`.
   Compare HTTP 200 at `/health` with 404 at `/missing`, the retained body and
   the same listening process. A missing URL is not a missing TCP listener.
5. Stop the server. Start `bash task.sh serve --mode unavailable`, enter its
   port and save `unavailable.json`. The expected result is HTTP 503 with curl
   status 22 and an `unavailable` body. The process and socket still exist.
   State what this controlled fixture proves and what a real 503 would still
   require examining, such as application dependencies and its own logs.
6. Stop that server, start ready mode again and save `recovered.json` using the
   new port. Independently verify the exact listener/PID with
   `ss -H -ltnp "sport = :$port"` and request `/health` using curl. Finally stop
   it and verify the owned listener disappears. Keep all case records.

## Explain the repair

Complete the five notes tasks: predictions, bind mismatch evidence and changed
target, path comparison, application readiness, and recovery/cleanup. State
which correction belongs to the client destination, listening configuration,
URL path or application behavior. The reference describes these relationships
without inventing a server PID or treating every HTTP error as a network outage.
Normal completion requires the actual changed cases and a corrected local
request. No proxy, system service, firewall or public exposure is introduced.

Primary references: [ss socket filters](https://man7.org/linux/man-pages/man8/ss.8.html)
and [curl error/body behavior](https://curl.se/docs/manpage.html).
