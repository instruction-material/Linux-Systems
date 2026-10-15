# Unknown Hosts and an Explicit Default

This optional transfer follows the required Apache/Nginx comparison. That core
observes two named sites and the ordinary first-site fallback. This investigation
asks how an explicit default changes unknown-host behavior and whether that
choice survives reversing the named blocks. It does not repeat page publishing
or proxy forwarding. The same prediction, trace, repair and comparison pauses
support independent reading and an instructor walkthrough.

## Equipment and observed contract

Use an ordinary account in an owned Debian/Ubuntu Linux lab with Bash, Python
3.8+ and Nginx already installed. Check `uname -s`, `id`, `python3 --version`
and `nginx -v`. Keep task.sh, task.py, nginx_lab.py and both text fixtures
together. The site IDE edits, saves and exports these files; execute the
exported role in the external Linux terminal.

Nginx first selects a listening address and port, then a named server for the
Host field. For this lab's two ordinary names, an unmatched name uses the
listener's default server. Without an explicit default_server parameter,
the first listed server supplies that fallback. The special-looking name `_`
does not itself make a server the default; the listen parameter does.

The equipment starts one owned foreground Nginx process with a private
configuration and a newly selected loopback port above 1023. It reads the
two supplied files, records the actual UID/PID, configuration test, wire
requests, response headers, statuses, body bytes and logs, then stops and
reaps that process. It never changes distribution sites, DNS or system units.
A syntax-test success is separate from a successful HTTP response.

## Predict, observe and repair

From the extracted starter or solution folder:

~~~bash
lab_root=$(mktemp -d)
bash task.sh "$lab_root" > first.json 2> first.err
first_status=$?
printf 'status=%s\n' "$first_status"
cat first.err
cat first.json
~~~

The untouched starter sets explicit_default=False. Predict 200 with alpha's
exact file for alpha.test, 200 with beta's file for beta.test, and alpha's
file for an unmatched name or IP Host. HTTP/1.0 without Host also reaches
that fallback. The report completes these observations but exits 1 because
the requested explicit-404 behavior is still absent.

Repair only the named explicit_default decision to True. The additional
server listens with default_server and returns 404. Named requests continue
to select their respective files; unknown names, IP Host and HTTP/1.0 without
Host now return 404. A missing Host in HTTP/1.1 is a separate malformed-request
400. A known host requesting /missing.txt returns 404 regardless of the repair.
HEAD for /index.txt has the file's byte Content-Length and an empty body.
Observation status 0 does not complete the independent notes.

The observer leaves the parent empty. Reuse it with
`bash task.sh "$lab_root" --reverse` and retain the second report. In the starter, unknown
requests now receive beta's file. After repair, both named mappings and the
explicit 404 fallback remain stable. Record actual responses before comparing
the reference; do not infer them only from configuration text.

## Manual request, failure, recovery and undo

For manual requests, use a new empty parent and add --hold-seconds 8. While
it runs, read ready.json in that parent from another terminal. Its port and
PID are actual values. Use that port with `curl -i -H 'Host: unmatched.test'
http://127.0.0.1:PORT/index.txt` and a named Host, then compare the saved report
and access log. The eight-second hold is only an inspection window.

Use --broken-config once in another empty parent. The real `nginx -t` rejects
the added unknown directive; report status 2 retains stderr and starts no
server. Recover by rerunning without that flag. Nonempty, absent or symlink
parents are input rejections and preserve their existing contents. Interrupt
a held run with Ctrl-C: status 130 records partial observation and cleanup.
Only the created private prefix and its ready.json are removed. Confirm the
recorded PID and listener are gone and the parent is empty before `rmdir`.

Complete all five host-notes.md tasks with the named repair, both block orders,
known and unknown responses, protocol distinction, syntax rejection, recovery
and cleanup. Host selection supplies routing behavior, not authentication or
authorization, and this loopback observation does not establish public hosting.

Primary reference: [Nginx request processing and default servers](https://nginx.org/en/docs/http/request_processing.html).
