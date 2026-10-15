# Controlled DNS Diagnosis and Explicit Address Bypass

This optional extension separates a DNS answer, an address selection and an
HTTP request. Complete `resolver-notes.md` after the core networking checkpoint.
The supplied DNS implementation is complete equipment, not a request to write
a recursive resolver or replace the host's resolver configuration.

## Preparation and processes

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

Use three terminals in the selected role folder. Terminal A runs HTTP:
`bash task.sh serve`. Terminal B runs the controlled DNS service:
`bash task.sh dns --answer ready`. Both print independently selected ports and
PIDs. In terminal C enter `read -r -p 'HTTP port: ' http_port` and
`read -r -p 'DNS port: ' dns_port` using those actual ready lines. The DNS
fixture listens only on 127.0.0.1 UDP at its unprivileged port, not public port
53. It answers a single ordinary IN/A question for `lab.invalid.` with TTL 0.
The supported diagnostic uses UDP with EDNS and recursion disabled. This small
fixture does not implement general recursion, caching, TCP fallback or DNSSEC.

## Predict and separate observations

1. Predict how a valid address, an incorrect address and NXDOMAIN should differ
   in the DNS record and the later HTTP request. Record the prediction first.
2. With ready DNS running, use
   `bash task.sh inspect --dns-port "$dns_port" --http-port "$http_port" --report ready.json`.
   Find DNS status NOERROR, one A answer 127.0.0.1, the actual UDP listener PID,
   the HTTP listener PID, and HTTP 200. Independently inspect the answer using
   `dig -r @127.0.0.1 -p "$dns_port" lab.invalid. A +noedns +norecurse +notcp +nosearch +time=1 +tries=1`.
   An explicit server/port and final dot make this a query of the owned fixture;
   it does not test the host's ordinary name-service search path.
3. Leave HTTP running. Stop only terminal B and restart DNS with
   `bash task.sh dns --answer wrong`. Enter its new DNS port in terminal C and
   collect `wrong-answer.json`. NOERROR now supplies 127.0.0.2. The request
   following that selected answer should fail to connect to the .1 HTTP
   listener, while `explicitBypassRequest` still returns 200 at .1. Cite both
   results. DNS query success alone does not prove that its answer is correct.
4. Stop only DNS, restart `bash task.sh dns --answer missing`, enter its actual
   port and collect `nxdomain.json`. The DNS response says NXDOMAIN. `dig` can
   exit 0 for this valid negative response. The collector does not attempt the
   selected-address HTTP request because no A answer exists; that field is null.
   It separately performs the explicit .1 bypass to test the unchanged app.
5. Restore DNS using `--answer ready`, enter the new DNS port and collect
   `restored.json`. Independently query that server again and verify the ready
   answer plus a successful selected-address HTTP request. Stop both foreground
   servers, and use `ss -H -lunp "sport = :$dns_port"` and
   `ss -H -ltnp "sport = :$http_port"` to confirm their owned sockets are gone.

## What the bypass does

For the HTTP experiment the collector supplies the observed fixture address
to curl's `--resolve lab.invalid:PORT:ADDRESS`, with proxies disabled. Curl
therefore uses the explicit address for that one host/port pair. This makes
the relationship between the captured DNS answer and connection test visible;
it does not route curl's DNS lookups through the fixture automatically.
The separate .1 override can demonstrate a healthy app despite bad/missing
DNS, but is not evidence that the system resolver was repaired. This exercise
does not edit `/etc/hosts`, `/etc/resolv.conf`, routes, firewall rules or global
DNS. The repair being demonstrated is the owned DNS fixture's restored answer.

## Complete and retain

Finish the five notes tasks with the original prediction, independent DNS
comparison, incorrect-answer case, negative-answer case and restored/cleaned
state. Identify both process PIDs and both ports from actual records. Keep
claims about global resolution, TCP service reachability and HTTP status
separate. Reopen the saved workspace and retain all four reports with the notes.

Primary references: [BIND dig](https://bind9.readthedocs.io/en/latest/manpages.html#dig-dns-lookup-utility),
[curl --resolve](https://curl.se/docs/manpage.html#--resolve), and
[RFC 1035](https://www.rfc-editor.org/rfc/rfc1035.html) for the restricted
DNS packet equipment.
