# LS4 Apache Virtual Host Compare

Serve the same small site with Apache and Nginx, then explain how each server
selects a virtual host and document root. This required project follows the
static Nginx lab. The reverse-proxy app is a separate project: these servers
serve files directly.

## Environment and source roles

Use an unprivileged account in an owned Debian/Ubuntu Linux VM or WSL
distribution. Apache 2.4, Nginx, Python 3, curl and ss must already be available.
For Debian/Ubuntu, the Apache binary is `apache2` and its modules are under
`/usr/lib/apache2/modules`. Check `apache2 -v`, `apache2 -l`, `nginx -v`,
`uname -s` and `id` first. These commands use explicit owned configurations
and loopback ports; the lab needs no public hostname, certificate or system
service changes.

Both roles include an Apache configuration, a complete comparison Nginx
configuration and two UTF-8 pages. The reference Apache primary virtual host
points at `public`. The learner Apache primary host deliberately points at
the empty `unfinished` folder. Its one named `document_root` TODO is changing
that primary `DocumentRoot` to the supplied `public` folder. Preserve the
second host, access rules, listeners, logs and Nginx configuration.

The untouched learner's request for primary `/index.html` returns 404; the
Nginx comparison already returns the supplied page. The learner's second Apache
host works. Predict these differences before completing the task. Compare
`solution` after an independent attempt.

## Prepare a reproducible owned prefix

From the selected `starter` or `solution` folder, run commands individually.
Keep this shell open so its environment and owned process identities remain
available. If either chosen port is occupied, choose unused ports above 1023
and update both Nginx `listen` lines in the installed copy.

```bash
role_dir=$(pwd -P)
lab_root=$(mktemp -d)
mkdir -p "$lab_root"/{run,logs,public,second,unfinished}
cp "$role_dir/index.html" "$lab_root/public/index.html"
cp "$role_dir/second.html" "$lab_root/second/index.html"
cp "$role_dir/linux-systems-apache.conf" "$lab_root/apache.conf"
cp "$role_dir/linux-systems-nginx.conf" "$lab_root/nginx.conf"
export LAB_ROOT="$lab_root" APACHE_PORT=18080
export LAB_UID="$(id -u)" LAB_GID="$(id -g)"
ss -ltn '( sport = :18080 or sport = :18081 )'
apache2 -f "$lab_root/apache.conf" -t
apache2 -f "$lab_root/apache.conf" -S
nginx -p "$lab_root/" -c nginx.conf -t
nginx -p "$lab_root/" -c nginx.conf -T
```

The Apache configuration expands these explicit environment values. Its
`ServerRoot`, runtime directory, PID file and logs stay in this prefix.
Nginx resolves its relative roots, logs and PID file through `-p`. Apache
uses the current numeric user and group; Nginx inherits the invoking identity.
Record the actual versions, UID/GID, chosen ports, syntax results and two host
mappings. Syntax success is a separate checkpoint from serving.

## Start, request and inspect

Register cleanup before starting either process. The following function only
addresses the two recorded background processes and waits for each separately.
Keep the temporary prefix for inspecting evidence after stopping.

```bash
apache_pid=""
nginx_pid=""
cleanup_lab() {
    if [ -n "$apache_pid" ]; then
        kill -TERM "$apache_pid" 2>/dev/null
        wait "$apache_pid"
        apache_pid=""
    fi
    if [ -n "$nginx_pid" ]; then
        kill -TERM "$nginx_pid" 2>/dev/null
        wait "$nginx_pid"
        nginx_pid=""
    fi
}
trap cleanup_lab EXIT INT TERM
apache2 -f "$lab_root/apache.conf" -DFOREGROUND >"$lab_root/apache-stdout.log" 2>&1 &
apache_pid=$!
nginx -p "$lab_root/" -c nginx.conf -g 'daemon off;' >"$lab_root/nginx-stdout.log" 2>&1 &
nginx_pid=$!
```

Use a new request after the listeners appear. For chosen alternative ports,
replace the URLs below. Save the response body and status independently.

```bash
ss -ltnp '( sport = :18080 or sport = :18081 )'
ps -p "$apache_pid,$nginx_pid" -o pid,ppid,uid,args
cat "$lab_root/run/apache.pid" "$lab_root/run/nginx.pid"
curl -sS -H 'Host: linux-systems.test' -o "$lab_root/apache-primary.body" -w '%{http_code}\n' http://127.0.0.1:18080/index.html
curl -sS -H 'Host: linux-systems.test' -o "$lab_root/nginx-primary.body" -w '%{http_code}\n' http://127.0.0.1:18081/index.html
curl -i -H 'Host: second.test' http://127.0.0.1:18080/index.html
curl -i -H 'Host: second.test' http://127.0.0.1:18081/index.html
curl -I -H 'Host: linux-systems.test' http://127.0.0.1:18080/index.html
curl -i -H 'Host: other.test' http://127.0.0.1:18080/index.html
curl -i -H 'Host: other.test' http://127.0.0.1:18081/index.html
curl -i -H 'Host: linux-systems.test' http://127.0.0.1:18080/missing.txt
curl -i -H 'Host: linux-systems.test' http://127.0.0.1:18081/missing.txt
```

The two fictional hostnames need no hosts-file or DNS edits because curl sends
the Host header. Both listeners remain 127.0.0.1. The PID files must identify
the recorded parent processes. The secondary page is distinct. Unknown hosts
fall back to the first configured host in these configurations; that routing
choice supplies no authentication. Missing files return 404. A successful
HEAD has the UTF-8 file's byte Content-Length and no response body.

For the learner, edit only the installed Apache primary `DocumentRoot` TODO,
then save the same correction to the learner source. Validate with `-t`,
reload with `kill -USR1 "$apache_pid"`, and repeat the primary request until
the new configuration is observed. Successful primary bodies must match the
supplied `index.html` exactly:

```bash
cmp "$role_dir/index.html" "$lab_root/apache-primary.body"
cmp "$role_dir/index.html" "$lab_root/nginx-primary.body"
tail -n 10 "$lab_root/logs/apache-access.log" "$lab_root/logs/nginx-access.log"
```

## Change configuration, observe reload and undo

Save the working installed configurations first:

```bash
cp "$lab_root/apache.conf" "$lab_root/apache-good.conf"
cp "$lab_root/nginx.conf" "$lab_root/nginx-good.conf"
python3 - "$lab_root" <<'PY'
from pathlib import Path
import sys
root = Path(sys.argv[1])
changes = [
    ("apache.conf", 'DocumentRoot "${LAB_ROOT}/public"', 'DocumentRoot "${LAB_ROOT}/second"'),
    ("nginx.conf", "root public;", "root second;"),
]
for name, before, after in changes:
    path = root / name
    text = path.read_text()
    assert text.count(before) == 1
    path.write_text(text.replace(before, after, 1))
PY
apache2 -f "$lab_root/apache.conf" -t
nginx -p "$lab_root/" -c nginx.conf -t
kill -USR1 "$apache_pid"
kill -HUP "$nginx_pid"
```

Repeat fresh primary requests for up to five seconds until both return the
second page. Record the changed configuration, status and exact body. The
secondary host remains unchanged. Graceful reload keeps the recorded parent
PID; stop/start creates a new identity.

Restore the two good copies, validate both again, reload with the same signals
and verify the primary page returns. For a failure case, append
`InvalidOwnedLabDirective` to the installed Apache configuration. Its syntax
check must fail. Keep that rejected configuration out of a reload; a request
still uses the existing working server. Restore the good copy and verify syntax.
Repeat with `invalid_owned_lab_directive;` in the installed Nginx configuration.
Record each actual failure status and diagnostic.

## Completion and cleanup

Complete `compare-notes.md` with the two host/root mappings, explicit activation
boundary, reload signals, UID/GID, PID/socket identities, status/body/HEAD
observations, rejected configuration diagnostics and restoration evidence.
Explain why an unknown hostname follows the first host, why a copied file needs
a separate serving observation, and why a failed syntax check must not be
followed by reload.

In a distribution-managed Apache site, `sites-available` stores configurations
and `sites-enabled` selects them, commonly through `a2ensite`. Here, the explicit
`-f` configuration is the lab's activation route. A separate supervised
throwaway-VM exercise can compare the managed-service layout after this owned
configuration exercise is complete.

```bash
cleanup_lab
trap - EXIT INT TERM
ss -ltn '( sport = :18080 or sport = :18081 )'
```

Both owned listeners must disappear. Preserve the small temporary prefix and
source edits with the completion record. A walkthrough can pause at prediction,
the learner's 404, correction, comparison, rejected syntax, reload and undo; the
same commands and record support independent reading.

References: [Apache startup](https://httpd.apache.org/docs/2.4/invoking.html),
[Apache directives](https://httpd.apache.org/docs/2.4/mod/core.html),
[Apache graceful restart](https://httpd.apache.org/docs/2.4/stopping.html),
[Nginx process control](https://nginx.org/en/docs/control.html).
