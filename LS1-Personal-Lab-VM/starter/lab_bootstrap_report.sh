#!/usr/bin/env bash
set -u

echo "== Linux Systems Lab Bootstrap Report =="
echo "User: ${USER:-unknown}"
echo "Home: ${HOME:-unknown}"
echo "Shell: ${SHELL:-unknown}"
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
