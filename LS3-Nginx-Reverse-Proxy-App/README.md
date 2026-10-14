# Run an application behind Nginx

This lab distinguishes the application socket, the front-end proxy socket and
the source of an HTTP response. Use Python 3, Nginx, curl and ss in an owned Linux
lab. The app and proxy listen only on loopback high ports. The supplied unit is
an optional user service, with the same ordinary account as the manual route.
Neither source program installs software or changes a system-wide site.

## Request contract and prediction

Both roles implement GET and HEAD /health: status 200 with service linux-toy-app
and status ok. Unknown paths return JSON 404. POST returns JSON 405 with Allow:
GET, HEAD. The request target is limited to 4096 characters and at most 16 query
fields; excessive query fields return JSON 400. Content-Length counts UTF-8
bytes, including the response newline; HEAD has the same headers without a body.
APP_PORT is a canonical ASCII integer from 1024 through 65535. Invalid settings
exit 2 before binding; an occupied port exits 1. The default app port is 8081.

GET /inspect records the actual path, parsed query, transport peer and four
received headers. Repeated query keys remain lists and blank values remain
visible. For /inspect?mode=read&mode=write&blank=, predict a path of /inspect,
a two-element mode list and a one-element blank list containing an empty string.
The reference returns these observations. The starter deliberately returns
JSON 501 at the named TODO; health is not proof that inspection is complete.
Complete inspection_payload using its supplied arguments before comparing the
reference. Do not replace observations with fixed sample answers.

## Verify the application first

Extract one role and this guide. Confirm uname -s, id and the permitted host
scope. Check that ports 8081 and 8080 are free with ss -ltnp. If they are occupied,
choose two free high ports and change APP_PORT, proxy_pass and listen together.
From the selected role, keep this process running in its own terminal:

~~~sh
APP_PORT=8081 python3 app.py
~~~

In a second terminal, record status, headers and body for these direct requests:

~~~sh
curl -i http://127.0.0.1:8081/health
curl -i 'http://127.0.0.1:8081/inspect?mode=read&mode=write&blank='
curl -i http://127.0.0.1:8081/missing
curl -I http://127.0.0.1:8081/health
ss -ltnp 'sport = :8081'
~~~

The startup line is flushed immediately. Record the actual PID and socket
identity. A process listing alone does not establish healthy HTTP behavior.
The app reports header values as data; a client can supply forwarding headers
directly. They are not authenticated identity or privilege evidence.

## Run the selected Nginx block in a disposable prefix

From the selected role, use this separate owned prefix. Keep the printed
lab_root value for every later command. The heredoc expands only the selected
absolute include path; the supplied proxy block keeps its Nginx variables.

~~~sh
lab_root=$(mktemp -d)
mkdir -p "$lab_root/logs"
install -m 0644 linux-toy-app.conf "$lab_root/proxy.conf"
cat > "$lab_root/nginx.conf" <<EOF
pid logs/nginx.pid;
error_log logs/main-error.log info;
events {}
http {
    access_log logs/main-access.log;
    include "$lab_root/proxy.conf";
}
EOF
nginx -p "$lab_root/" -c "$lab_root/nginx.conf" -t
nginx -p "$lab_root/" -c "$lab_root/nginx.conf" -g 'daemon off;'
~~~

Keep that Nginx process running in its terminal. In the request terminal:

~~~sh
curl -i http://127.0.0.1:8080/health
curl -i 'http://127.0.0.1:8080/inspect?mode=read&mode=write&blank='
curl -i -H 'Host: lab.invalid' -H 'X-Forwarded-For: 203.0.113.9' -H 'X-Forwarded-Proto: https' 'http://127.0.0.1:8080/inspect?topic=ports'
curl -i http://127.0.0.1:8080/missing
ss -ltnp 'sport = :8080'
tail -n 10 "$lab_root/logs/proxy-access.log"
tail -n 10 "$lab_root/logs/proxy-error.log"
~~~

The two sockets are distinct. Without an added URI in proxy_pass, this block
forwards the request path and query. The app's unknown-path 404 and the starter's
unfinished 501 remain those statuses through the proxy. Nginx overwrites the
supplied forwarding headers with its observed loopback client and http scheme;
the supplied spoofed values do not become authentication evidence. Compare
Host and received forwarding headers against the direct request. The access
log records request, status and upstream attempt; a log field alone does not
prove that an app answered.

Stop the owned app with Ctrl-C while leaving the owned proxy running. A direct
health request now fails to connect and a proxied health request returns 502.
Read the proxy error log, restore the same app and verify recovery to 200.
This distinguishes an unavailable upstream from an app-produced 404 or 501.
A syntax test only validates configuration; it neither starts Nginx nor proves
that the intended socket or application is serving.

## Optional user-service route after foreground verification

Stop the foreground app before starting the same app port under a user manager.
The following route requires an available systemd user manager in the owned lab:

~~~sh
mkdir -p "$HOME/.local/share/linux-toy-app" "$HOME/.config/systemd/user"
install -m 0644 app.py "$HOME/.local/share/linux-toy-app/app.py"
install -m 0644 linux-toy-app.service "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user start linux-toy-app.service
systemctl --user status linux-toy-app.service
journalctl --user -u linux-toy-app.service --no-pager
curl -i http://127.0.0.1:8081/health
~~~

The unit uses the user manager's home and active account, not www-data or a root
HOME default. It needs no system-wide unit or /opt installation. Record actual
manager availability and inspect its working directory, environment and PID.
If the user bus is unavailable, retain the verified foreground route and record
that limitation; a parsed unit file is not an operating service. Restore any
pre-existing file before installing this lab under its name. The separate
Services and systemd project covers sustained service-operation evidence.

## Undo and completion record

Stop only the two foreground processes with Ctrl-C in their own terminals.
For the optional route, stop the named user service, restore or remove only its
lab unit and app file, and reload the user manager. Confirm the two lab sockets
are gone before removing the disposable prefix; preserve the logs until the
failure and recovery record is complete. No distribution default site is enabled,
replaced or claimed by this block.

Completion includes the inspection TODO repair, independent predictions and
observations, path/query and header comparisons, socket/PID evidence, the
upstream-down 502 and recovery, and a verified undo. A reference run does not
complete the record or establish public hosting or service-manager operation.

Primary references: [Python HTTP server](https://docs.python.org/3.12/library/http.server.html)
and [Nginx proxy directives](https://nginx.org/en/docs/http/ngx_http_proxy_module.html).
