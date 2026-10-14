# Apache and Nginx comparison reference

Apache selects these named hosts through VirtualHost and ServerName. Nginx uses
server and server_name. Each first host serves public; each second host serves
second. Unknown Host values use the first configured host in this lab.

Apache DocumentRoot expands the explicitly exported LAB_ROOT. Nginx root is
relative to the owned prefix supplied with -p. Apache Directory rules allow
the owned page directories; Nginx location resolves existing files or 404.
The two implementations have different configuration mechanisms even when their
successful response bodies match.

The installed Apache file is selected by -f, with explicit environment values,
module paths, current numeric user/group and owned runtime/log paths. The
installed Nginx file is selected relative to -p. Both bind loopback high ports.
Apache -t and Nginx -t validate before the lab starts or reloads. Apache USR1
and Nginx HUP perform graceful reload; the recorded parent identity stays stable.
Stop/start changes that identity. A rejected syntax test leaves the already
running configuration available until a valid reload is requested.

Primary and secondary /index.html requests return the corresponding exact
UTF-8 page after learner completion. Missing files return 404. HEAD returns
the file's byte length without a body. Changing only the primary root to second
makes both primary bodies equal the secondary page; restoring the good copies
returns the original primary page.

Complete the environment and actual-observation record in a separate saved
attempt: versions, UID/GID, source identity, sockets/PIDs, response statuses and
bodies, log lines, rejected diagnostics, restored bytes and cleanup. Use an
independent changed case before comparing this explanation.
