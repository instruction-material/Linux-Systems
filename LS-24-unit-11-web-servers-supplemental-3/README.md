# Entity Validators, Conditional Responses and Changed Bytes

This optional extension follows static serving and the host-routing transfer.
It asks when a conditional request receives 304 instead of the representation,
and why a server's metadata-based entity tag is not a content hash. It does
not repeat proxy recovery or the Apache/Nginx configuration comparison.
Complete validator-notes.md at each prediction and changed-file pause; the
same sequence supports independent reading and a paced walkthrough.

## Equipment and HTTP vocabulary

Use an ordinary account in an owned Linux lab with Bash, Python 3.8+ and Nginx
already installed. Keep task.sh, task.py, nginx_lab.py and resource.txt together
in the extracted role folder. The site IDE edits, saves and exports them;
run the equipment in that external Linux terminal.

A GET 200 carries representation bytes. HEAD requests the corresponding
headers without a response body. Last-Modified reports a timestamp; an
If-Modified-Since request can let the server compare that date with the file.
ETag is an entity validator; If-None-Match sends a saved tag. A matching
conditional GET can return 304 with no representation body, telling a client
to reuse its saved representation. This equipment sends actual requests and
does not simulate a browser cache or create an imaginary downloaded body.

The supplied Nginx configuration uses if_modified_since exact and the header
`Cache-Control: max-age=0, must-revalidate`. That policy requires a stored
response to be revalidated when stale; it does not disable storing the response.
The exercise records the real headers and bodies independently of that policy.
No TLS, public hostname or system service is configured.

## Repair the entity-tag decision

From the extracted role folder:

~~~bash
lab_root=$(mktemp -d)
bash task.sh "$lab_root" > validators.json 2> validators.err
validator_status=$?
printf 'status=%s\n' "$validator_status"
cat validators.err
cat validators.json
~~~

The starter's named decision is etag_setting='off'. Its initial GET has a
Last-Modified header but no ETag. The equipment uses a deliberately nonmatching
placeholder in If-None-Match when no tag exists, so that request returns 200.
The date-based request can still return 304. Report status 1 distinguishes
finished observations from the requested entity-tag behavior.

Repair only etag_setting to 'on'. Preserve the real server, date behavior,
request trace and cleanup. A fresh GET returns the exact resource.txt bytes
and an ETag. Sending that actual tag in If-None-Match returns 304 and no body;
a different tag returns 200. HEAD returns 200 with the file's byte length
and no body. Record these as separate observations before comparing the reference.

## Two different private file changes

The equipment changes only its private copy, never the supplied resource.txt.
First it appends bytes and advances that file's modification timestamp by
two seconds. A request with the earlier entity tag now returns 200, changed
bytes and a new tag. Sending the new tag returns 304. File mtime is changed;
the machine clock is untouched.

Next it changes one byte while preserving both size and the new timestamp.
A plain GET proves the body bytes changed again, but Nginx's automatically
generated static-file tag remains based on metadata. The old tag can still
produce 304. Compare actual SHA-256 values with ETag values: this demonstration
shows why equal validators alone do not prove cryptographically identical
bytes. It is an observed limitation of this supplied static-serving setup,
not a claim about every application-generated ETag.

A missing representation returns 404. The explicit `always` header rule also
places Cache-Control on that response; recording the header does not change
the status. Keep every response's status, body length and validators separate.

## Failure, recovery and completion record

Add --broken-config once with another fresh empty parent. The actual syntax
check fails, status 2 retains stderr, and no server is started. Rerun without
that flag to record recovery. For a manual window, use --hold-seconds 8, read
the real port from ready.json, then request /resource.txt with curl from another
terminal. Ctrl-C during the hold returns 130 and stops the owned process.
Nonempty, missing and symlink parents are rejected without clearing them.

The report retains the actual configuration, command results, responses,
three body digests, private-file sizes/timestamps, logs and cleanup fields.
Confirm the owned PID and socket are gone and the parent is empty, then remove
only that empty parent. Complete all five validator-notes.md tasks with the
named repair, independent predictions, both validator types, both file-change
experiments, failure, recovery and cleanup. Running the reference does not
complete this record or establish that a browser cache was exercised.

Primary references: [Nginx ETag and modification-date directives](https://nginx.org/en/docs/http/ngx_http_core_module.html#etag),
[Nginx response headers](https://nginx.org/en/docs/http/ngx_http_headers_module.html),
and [HTTP conditional requests](https://www.rfc-editor.org/rfc/rfc9110.html#name-conditional-requests),
[static-file ETag implementation](https://github.com/nginx/nginx/blob/release-1.24.0/src/http/ngx_http_core_module.c#L1577-L1580),
and [HTTP cache freshness](https://www.rfc-editor.org/rfc/rfc9111.html#name-max-age-2).
