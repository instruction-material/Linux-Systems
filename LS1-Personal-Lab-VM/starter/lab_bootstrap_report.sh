#!/usr/bin/env bash
set -u
[[ "$(uname -s)" == Linux ]] || { printf "Use the Linux guest or WSL shell; host identity is not Linux readiness.\n" >&2; exit 2; }

echo "== Linux Systems Lab Bootstrap Report =="
echo "Active identity: $(id -un) uid=$(id -u) groups=$(id -G)"
echo "Configured home environment: ${HOME:-unknown}"
echo "Script interpreter: Bash $BASH_VERSION"
echo "Configured login shell: ${SHELL:-unknown}"
echo "Hostname: $(hostname)"
echo "Kernel: $(uname -sr)"
echo "Working directory: $(pwd)"
echo

echo "== Command Check =="
for command_name in bash ls pwd grep find awk sed ssh systemctl journalctl crontab; do
	if command -v "$command_name" >/dev/null 2>&1; then
		echo "[ok] $command_name -> $(command -v "$command_name")"
	else
		echo "[missing] $command_name"
	fi
done
echo

echo "== TODO =="
echo "1. Confirm you are inside Linux, not a host shell."
echo "2. Create a course workspace under your home directory."
echo "3. Record which package manager this machine uses."
echo "4. Note whether you have sudo access."
