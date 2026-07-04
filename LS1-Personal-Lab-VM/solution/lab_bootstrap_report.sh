#!/usr/bin/env bash
set -euo pipefail

#################
#   CONSTANTS   #
#################
readonly -a PACKAGE_MANAGER_CANDIDATES=(apt dnf yum zypper pacman apk)
readonly -a COMMAND_CHECKS=(bash ls pwd grep find awk sed ssh systemctl journalctl crontab curl ip ss)
readonly -a PATH_CHECKS=(/ /home /etc /var /usr /tmp /srv)

#################
#   FUNCTIONS   #
#################
# Detect the first common package manager available on this system
detect_package_manager() {
	# Check each package manager candidate in the preferred reporting order
	for candidate in "${PACKAGE_MANAGER_CANDIDATES[@]}"; do
		# Report the first available package manager and stop searching
		if command -v "$candidate" >/dev/null 2>&1; then
			printf '%s' "$candidate"
			return 0
		fi
	done

	# Fall back when no known package manager is available
	printf 'unknown'
}

# Detect whether the lab is running under WSL, virtualization, or plain Linux
detect_linux_context() {
	# Prefer WSL detection because it also appears as Linux
	if grep -qi microsoft /proc/version 2>/dev/null; then
		printf 'wsl'
	# Report virtualized Linux when systemd exposes that information
	elif systemd-detect-virt --quiet 2>/dev/null; then
		printf 'virtualized-linux'
	# Use the generic Linux label for bare-metal or unknown environments
	else
		printf 'linux'
	fi
}

#################
#   MAIN CODE   #
#################
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
for command_name in "${COMMAND_CHECKS[@]}"; do
	# Report whether each course command is available on PATH
	if command -v "$command_name" >/dev/null 2>&1; then
		echo "[ok] $command_name -> $(command -v "$command_name")"
	else
		echo "[missing] $command_name"
	fi
done
echo

echo "== Filesystem Orientation =="
for path_name in "${PATH_CHECKS[@]}"; do
	# Report whether each major filesystem location exists
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
