"""Render reviewed lab units into an empty, owned and explicitly scoped tree."""
import argparse
import json
import os
import platform
import re
import stat
import sys
from pathlib import Path

FILES = ('app.py', 'config.json', 'data.json')
TEMPLATES = ('signal-garden.service', 'signal-garden-backup.service', 'signal-garden-backup.timer', 'nginx.conf')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--id', required=True)
    parser.add_argument('--app-port', type=int, required=True)
    parser.add_argument('--proxy-port', type=int, required=True)
    parser.add_argument('--backup-delay', type=int, default=2)
    args = parser.parse_args()
    root = args.root.absolute()
    if platform.system() != 'Linux' or os.geteuid() == 0:
        raise ValueError('render as the ordinary operator inside the owned Linux VM')
    if not re.fullmatch(r'[0-9a-f]{32}', args.id) or str(root) != '/srv/classes-capstone-' + args.id:
        raise ValueError('the root must be /srv/classes-capstone- followed by this exact 32-digit lab id')
    if root.is_symlink() or not root.is_dir() or root.stat().st_uid != os.geteuid() or any(root.iterdir()):
        raise ValueError('provide a fresh empty ordinary directory owned by this operator')
    if root.resolve() != root or root.parent.is_symlink() or stat.S_IMODE(root.stat().st_mode) != 0o755:
        raise ValueError('use the nonsymlink /srv tree and the declared 0755 traversal mode')
    if args.app_port == args.proxy_port or any(not 1024 <= p <= 65535 for p in [args.app_port, args.proxy_port]):
        raise ValueError('select distinct unprivileged app and proxy ports')
    if not 1 <= args.backup_delay <= 300:
        raise ValueError('the bounded lab timer delay is between 1 and 300 seconds')
    role = Path(__file__).resolve().parent
    source = {name: (role / name).read_bytes() for name in FILES}
    unit = 'cls-cap-' + args.id[:12]
    values = {'@@ROOT@@': str(root), '@@UNIT@@': unit, '@@UID@@': str(os.geteuid()),
              '@@GID@@': str(os.getegid()), '@@APP_PORT@@': str(args.app_port),
              '@@PROXY_PORT@@': str(args.proxy_port), '@@BACKUP_DELAY@@': str(args.backup_delay)}
    rendered = {}
    for name in TEMPLATES:
        text = (role / name).read_text()
        for old, new in values.items():
            text = text.replace(old, new)
        if '@@' in text:
            raise ValueError('an unresolved template field remains')
        rendered[name] = text
    # Rendering performs no privileged action, enables no unit and opens no listener.
    # The operator inspects these exact staged files before installing the lab units.
    (root / 'releases').mkdir(mode=0o755)
    release = root / 'releases' / 'a'
    release.mkdir(mode=0o755)
    for name, content in source.items():
        (release / name).write_bytes(content)
        (release / name).chmod(0o444)
    (root / 'current').symlink_to('releases/a', target_is_directory=True)
    for directory in ['staging', 'operator', 'nginx']:
        (root / directory).mkdir(mode=0o750)
    for directory in ['backups', 'restore']:
        (root / directory).mkdir(mode=0o700)
    (root / 'operator' / 'backup.py').write_bytes((role / 'backup.py').read_bytes())
    (root / 'operator' / 'backup.py').chmod(0o444)
    for name, text in rendered.items():
        (root / 'staging' / name).write_text(text)
        (root / 'staging' / name).chmod(0o600)
    record = {'labId': args.id, 'root': str(root), 'unit': unit,
              'appPort': args.app_port, 'proxyPort': args.proxy_port,
              'operatorUid': os.geteuid(), 'operatorGid': os.getegid(),
              'backupDelaySeconds': args.backup_delay, 'renderedOnly': True}
    (root / 'lab.json').write_text(json.dumps(record, indent=2) + '\n')
    (root / 'lab.json').chmod(0o600)
    print(json.dumps(record), flush=True)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
