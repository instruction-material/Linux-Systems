# Static content under /srv: publish and verify exact state

The page installer accepts an explicit document root inside the owned Linux lab.
It anchors source index.html to the script's directory, not the working directory.
No system Nginx configuration is changed by the script. The starter's named TODO
is deliberately unfinished; the reference installs the neighboring page with
0644 mode, applies requested ownership, then publishes it. Ownership errors are
fatal and retain an earlier page. Ownership changes target only the document
root and staged page, never a recursive tree of unrelated files.

## Independent filesystem run

Extract one role with index.html and the configuration. In Linux:

~~~sh
lab_root=$(mktemp -d)
bash deploy_static_site.sh "$lab_root/public"
stat -c '%a %U:%G %n' "$lab_root/public" "$lab_root/public/index.html"
cmp index.html "$lab_root/public/index.html"
~~~

The root is 0755 and the page is 0644. Omitting owner preserves the active
account's ownership; an explicit OWNER:GROUP must be applied successfully.
Repeat from another working directory, with spaces in the target path, and with
an invalid owner. For the failure case, create an earlier known page and verify
its bytes remain unchanged. Record output, diagnostics and status. Complete the
starter TODO without replacing its ownership/error boundary.

## Owned VM Nginx route

The supplied server block listens only on 127.0.0.1:8080 and has no default_server
claim. This avoids conflict with the distribution's ordinary default site and
does not create a public listener. In the disposable VM, publish to
/srv/linux-systems-site, using its intended serving owner when administrative
permission is available. Inspect the exact source and target paths before a
privileged command. Copy the reviewed block into the VM's sites-available folder
and enable only its named symlink in sites-enabled. Validate with nginx -t before
reloading the VM's Nginx service. Request http://127.0.0.1:8080/ from that VM,
compare the served page, and request an unknown path to verify status 404.

For a temporary document root, replace only the root directive with the exact
published absolute path before enabling that block. Each parent directory must
allow the Nginx worker identity to traverse it; a default private mktemp parent
does not grant that traversal. Use the owned /srv route or an explicitly planned
lab layout rather than opening unrelated home directories recursively.

Record the account, directory modes, syntax-test result, reload result, served
bytes and unknown-path status independently. A successful copy does not prove
that Nginx is serving that path. Preserve the prior VM configuration and disable
only the named lab site to undo it; validate before the restoration reload.
Completion includes the TODO, changed cases, serving observations and an undo.
