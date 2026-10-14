# Apache and Nginx comparison record

## Independent prediction

- Primary learner Apache /index.html: TODO status and reason.
- Primary Nginx /index.html: TODO status and expected bytes.
- Second Host header: TODO document roots in both servers.
- Unknown Host header: TODO selected host and explanation.

## Observed environment

Record Linux version, Apache/Nginx versions, UID/GID, source role, owned prefix,
ports, syntax statuses, actual socket addresses and PID-file/parent identities.

## Trace, correction and comparison

Record the named document_root correction, primary and secondary statuses,
exact byte comparisons, HEAD length/body observation, unknown Host behavior,
missing-path responses and selected access-log lines.

Map VirtualHost/server, DocumentRoot/root, Directory access rules/location,
explicit -f/-p activation, syntax commands, logs and graceful reload signals.

## Changed case and undo

Record the primary-root change, both new bodies, unchanged secondary mapping,
stable parent PIDs, each deliberately rejected configuration and actual
diagnostic, then the restored primary bytes and disappeared owned listeners.
