# Linux lab identity and readiness

The report observes an existing Linux guest, WSL instance or owned remote lab.
It does not provision a VM, install packages, create users or change privilege
policy. A non-Linux host shell returns status 2 before reporting readiness.
The active identity comes from id, not a replaceable USER environment value.
The script interpreter and configured login shell are labeled separately.

## Provision one owned environment before reporting readiness

For a VM, use an already approved hypervisor and a dedicated new virtual disk.
A lab allocation of two virtual CPUs, 4 GB RAM and 32 GB disk leaves room for the
course. Download the Ubuntu Server installer matching the guest architecture
from Ubuntu, attach the ISO, select NAT networking and boot the new guest. Choose
language, keyboard and DHCP networking, then use only the new virtual disk for
the guided storage layout. Create an ordinary login account and a lab hostname,
complete installation, detach the ISO and reboot. Log in, record /etc/os-release
and uname -m, and take a named hypervisor snapshot before later changes. Shut
down, reopen the VM and confirm the same account and workspace are available.
These lab allocations are course choices, not claims about platform minimums.
The [Ubuntu installation guide](https://ubuntu.com/server/docs/tutorial/basic-installation/)
supports the installer sequence.

For Windows 11 or a supported Windows 10 build, open an administrator PowerShell
and run wsl --list --online. Choose the listed Ubuntu distribution intended for
the lab, then run wsl --install -d NAME, substituting that exact listed name.
Restart if requested, launch the distribution, and create its Linux account.
In PowerShell, wsl --list --verbose must show version 2; if it shows version 1,
use wsl --set-version NAME 2. Open the Linux distribution shell and record its
actual release before running course commands. The
[Microsoft WSL guide](https://learn.microsoft.com/en-us/windows/wsl/install)
supports these commands. Linux paths and Windows paths remain different.

An owned remote lab is another route: connect with its assigned SSH account,
record that host's identity and permitted scope, and obtain its snapshot/reset
method. A shared or production host is not a disposable course VM. The report
below verifies observations after provisioning; it cannot prove that the VM,
WSL distribution or reset route was created successfully.

## Run and interpret the observations

Extract one role and this guide. In the Linux lab, run:

~~~sh
bash lab_bootstrap_report.sh > readiness.txt 2> diagnostics.txt
report_status=$?
printf 'status=%s\n' "$report_status"
cat readiness.txt
cat /etc/os-release
ps -p 1 -o comm=
id
~~~

A successful report identifies the active account, kernel, working directory,
available commands and major filesystem locations. In the reference, WSL is
identified from the Linux proc version; systemd-detect-virt can identify another
virtualized context. The generic linux label states only that the kernel check
passed and a more specific context was not detected. Missing commands are
observations, not permission to install them on the host.

The starter's four TODO observations remain required: Linux context, course
workspace, package manager and privilege availability. Record distribution,
release, architecture, PID 1, identity, group membership, network boundary,
workspace and the VM's actual snapshot/reset route. An available sudo command
does not itself prove authorization for a later state change. Explain how the
workspace can be reopened and which later labs depend on missing tools.

## Walkthrough and independent evidence

Trace the early kernel guard before command inventory. Compare active identity
with configured shell information. Record a missing-tool case and the host-shell
failure separately from a healthy Linux report. The supplied course readiness
transcript is a clearly fictional reasoning route when a compatible Linux lab
is unavailable; it is not an observed VM. A successful script does not establish
that a VM was provisioned or complete the readiness record.
