#!/usr/bin/env bash
set -euo pipefail

detect_package_manager() {
	for candidate in apt dnf yum zypper pacman apk; do
		if command -v "$candidate" >/dev/null 2>&1; then
			printf '%s' "$candidate"
			return 0
		fi
	done

	printf 'unknown'
}

detect_linux_context() {
	if grep -qi microsoft /proc/version 2>/dev/null; then
		printf 'wsl'
	elif systemd-detect-virt --quiet 2>/dev/null; then
		printf 'virtualized-linux'
	else
		printf 'linux'
	fi
}

echo "== Linux Systems Lab Bootstrap Report =="
echo "Timestamp: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "Context: $(detect_linux_context)"
echo "User: ${USER:-unknown}"
echo "Home: ${HOME:-unknown}"
echo "Shell: ${SHELL:-unknown}"
echo "Hostname: $(hostname)"
echo "Kernel: $(uname -sr)"
echo "Package manager: $(detect_package_manager)"
echo "Working directory: $(pwd)"
echo

echo "== Command Check =="
for command_name in bash ls pwd grep find awk sed ssh systemctl journalctl crontab curl ip ss; do
	if command -v "$command_name" >/dev/null 2>&1; then
		echo "[ok] $command_name -> $(command -v "$command_name")"
	else
		echo "[missing] $command_name"
	fi
done
echo

echo "== Filesystem Orientation =="
for path_name in / /home /etc /var /usr /tmp /srv; do
	if [[ -e "$path_name" ]]; then
		printf '[ok] %s exists\n' "$path_name"
	else
		printf '[missing] %s\n' "$path_name"
	fi
done
echo

echo "== Next Actions =="
echo "1. Create ~/linux-systems-lab if it does not exist."
echo "2. Save this report to your course notebook."
echo "3. Record whether sudo is available with: sudo -v"
