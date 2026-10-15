# Interface, Route, Listener and Application Evidence

This required Unit 10 project replaces networking guesses with observations at
separate layers. Complete `network-notes.md` while retaining each raw JSON
record. The same prediction, observation and explanation pauses work for
independent reading and a paced walkthrough.

## Preparation and roles

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

## Read the layers

An interface is a local network device; an address is assigned to an interface.
The `lo` loopback device carries traffic within this host. `ip -j address show
dev lo` records its flags and address/prefix entries. A loopback operstate of
UNKNOWN does not by itself mean that it is down. Read the flags and the actual
test too. The main route table and `ip -j route get 127.0.0.1` answer different
questions: configured main-table routes versus the kernel's selected local
path. A selected route describes a proposed path, not successful delivery.

A listening TCP socket has an address, port and owning process. `ss -H -ltnp`
lists listeners without name resolution and includes visible process ownership.
The supplied collector filters by the exact observed port. A healthy interface
and a successful ICMP echo do not prove that a particular TCP service is alive.
HTTP adds another layer: connecting to a server can still return a missing
path or an application failure.

## Predict, run and compare

1. Before starting a server, predict which layer names the address, route,
   listening process and application result. Record that prediction as task 1.
2. In terminal A run `bash task.sh serve`. Keep it running. Note the actual
   address, port and PID from its ready line.
3. In terminal B enter `read -r -p 'Port from the ready line: ' port`, then type
   that number. Run `bash task.sh inspect --port "$port" --report first.json`.
   Open `first.json`. Find the `lo` address, selected route, exact listener,
   ICMP observation, and HTTP status/body. `/health` returns 200 and a body
   containing `ready` and the server PID. Compare that PID with the ready line
   and `ss`; do not confuse the collector PID with the serving process.
4. Independently run `ip -j address show dev lo`, `ip -j route get 127.0.0.1`,
   `ss -H -ltnp "sport = :$port"`, and
   `curl --noproxy '*' --fail-with-body "http://127.0.0.1:$port/health"`.
   Compare these actual outputs with the corresponding saved observations.
5. Predict a request to an absent path, then run
   `bash task.sh inspect --port "$port" --path /missing --report missing.json`.
   Expect HTTP 404, curl status 22, and `missing` with the same server PID.
   This is an HTTP response from a listening server, not evidence of a dead port.
6. Stop terminal A with Ctrl-C. Confirm the exact listener is gone using `ss`.
   Run `bash task.sh inspect --port "$port" --report stopped.json`. In this
   controlled lab, expect curl status 7, HTTP status 000 (stored as integer 0),
   and no HTTP body. The interface/route may remain healthy. If another process
   has since acquired that port, record that actual observation instead of
   forcing the expected answer. Start a fresh owned server for another trial.
7. Start a fresh server, enter its new actual port and collect `restored.json`.
   Demonstrate HTTP 200 and the new listener PID. Preserve all earlier records.

The equipment disables curl proxies and uses literal 127.0.0.1/127.0.0.2 targets.
No public listener, route edit, firewall edit or internet request is needed.
An ICMP permission error in a restricted environment is an observation about
the available test, not proof that the HTTP service is down.

## Complete and retain

Finish all five notes tasks with an initial prediction, actual record/field
citations, your independent comparison, the stopped-service changed case, and
recovery/cleanup evidence. State the narrowest conclusion each tool supports.
Download/reopen the saved workspace and keep the reports with the final notes.
Running the reference does not complete the learner's investigation.

## Optional transfer

The listener continuation isolates wrong bind addresses, absent paths and
application readiness. The DNS continuation deliberately separates a DNS answer
from an explicit HTTP address override. These are distinct optional experiments
after this core checkpoint, not three copies of one log-summary script.

Primary references: [ip](https://man7.org/linux/man-pages/man8/ip.8.html),
[ss](https://man7.org/linux/man-pages/man8/ss.8.html),
[ping](https://man7.org/linux/man-pages/man8/ping.8.html), and
[curl options and exit codes](https://curl.se/docs/manpage.html).
