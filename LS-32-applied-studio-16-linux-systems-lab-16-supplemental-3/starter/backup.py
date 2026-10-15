"""Validate a private snapshot before publication and restore to a fresh path."""
import argparse
import hashlib
import io
import json
import os
import shutil
import stat
import sys
import tarfile
import time
import uuid
from pathlib import Path

REQUIRED = ('app.py', 'config.json', 'data.json')
MAX_BYTES = 1048576


def selected_members():
    return REQUIRED


def digest(data):
    return hashlib.sha256(data).hexdigest()


def owned_directory(path):
    if path.is_symlink() or not path.is_dir() or path.stat().st_uid != os.geteuid():
        raise ValueError('expected an ordinary owned directory: ' + str(path))
    if path.resolve() == Path('/'):
        raise ValueError('the filesystem root is not a lab directory')
    return path.resolve()


def validate(archive):
    details = archive.lstat()
    if not stat.S_ISREG(details.st_mode) or details.st_size > 8 * MAX_BYTES:
        raise ValueError('expected a small ordinary archive')
    with tarfile.open(archive, 'r:gz') as bundle:
        members = bundle.getmembers()
        expected = set(REQUIRED) | {'manifest.json'}
        if len(members) != len(expected) or {m.name for m in members} != expected:
            raise ValueError('archive members must be exactly the declared project files and manifest')
        if any(not m.isfile() or not 0 <= m.size <= MAX_BYTES for m in members):
            raise ValueError('links, special files and oversized members are not restored')
        contents = {}
        for member in members:
            with bundle.extractfile(member) as stream:
                contents[member.name] = stream.read(MAX_BYTES + 1)
            if len(contents[member.name]) != member.size:
                raise ValueError('incomplete archive member')
        manifest = json.loads(contents.pop('manifest.json'))
        if set(manifest) != {'version', 'createdNs', 'files'} or manifest['version'] != 1:
            raise ValueError('unsupported manifest')
        if not isinstance(manifest['createdNs'], int) or manifest['createdNs'] <= 0:
            raise ValueError('manifest must record its creation time')
        if set(manifest['files']) != set(REQUIRED):
            raise ValueError('manifest omits a required project file')
        actual = {name: digest(content) for name, content in contents.items()}
        if manifest['files'] != actual:
            raise ValueError('actual payload digests do not match the manifest')
        return contents, manifest


def sync_directory(directory):
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def build(source, destination, reject_after_write=False):
    source = source.resolve()
    owned_directory(source)
    destination = owned_directory(destination)
    selected = selected_members()
    if len(selected) != len(REQUIRED) or set(selected) != set(REQUIRED):
        raise ValueError('select every declared project file before creating a snapshot')
    contents = {}
    for name in selected:
        path = source / name
        details = path.lstat()
        if not stat.S_ISREG(details.st_mode) or details.st_uid != os.geteuid() or details.st_size > MAX_BYTES:
            raise ValueError('snapshot inputs must be small ordinary owned files')
        contents[name] = path.read_bytes()
    if shutil.disk_usage(destination).free < sum(map(len, contents.values())) + 131072:
        raise ValueError('insufficient free space for the declared candidate policy')
    created = time.time_ns()
    stem = 'snapshot-' + str(created) + '-' + uuid.uuid4().hex
    candidate = destination / (stem + '.partial')
    final = destination / (stem + '.tar.gz')
    manifest = {'version': 1, 'createdNs': created,
                'files': {name: digest(data) for name, data in contents.items()}}
    archive_data = dict(contents, **{'manifest.json': (json.dumps(manifest, sort_keys=True) + '\n').encode()})
    with candidate.open('xb') as output:
        with tarfile.open(fileobj=output, mode='w:gz') as bundle:
            for name, data in archive_data.items():
                member = tarfile.TarInfo(name)
                member.size = len(data)
                member.mode = 0o600
                member.mtime = created // 1000000000
                bundle.addfile(member, io.BytesIO(data))
        output.flush()
        os.fsync(output.fileno())
    candidate.chmod(0o600)
    if reject_after_write:
        raise ValueError('controlled rejection left the untrusted partial candidate at ' + str(candidate))
    checked, checked_manifest = validate(candidate)
    if checked != contents or checked_manifest != manifest:
        raise ValueError('the independently read candidate differs from its source')
    os.replace(candidate, final)
    sync_directory(destination)
    return {'archive': str(final), 'sha256': digest(final.read_bytes()),
            'manifest': manifest, 'sourceDevice': source.stat().st_dev,
            'destinationDevice': destination.stat().st_dev, 'publishedAfterValidation': True}


def restore(archive, target):
    contents, manifest = validate(archive)
    target = target.absolute()
    parent = owned_directory(target.parent)
    if target.name in ('', '.', '..') or target.exists() or target.is_symlink():
        raise ValueError('restore requires a new separate destination, not an existing path')
    target = parent / target.name
    target.mkdir(mode=0o700)
    try:
        for name, content in contents.items():
            with (target / name).open('xb') as out:
                out.write(content)
            (target / name).chmod(0o600)
        actual = {name: digest((target / name).read_bytes()) for name in REQUIRED}
        if actual != manifest['files']:
            raise ValueError('restored bytes differ from the checked manifest')
    except BaseException:
        shutil.rmtree(target)
        raise
    return {'destination': str(target), 'files': actual, 'uid': target.stat().st_uid,
            'separateDestinationCreated': True}


def latest(directory):
    directory = owned_directory(directory)
    for path in sorted(directory.glob('snapshot-*.tar.gz'), reverse=True):
        try:
            validate(path)
        except (OSError, ValueError, KeyError, TypeError, tarfile.TarError):
            continue
        return path
    raise ValueError('no validated complete snapshot exists')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    create = sub.add_parser('build')
    create.add_argument('source', type=Path)
    create.add_argument('destination', type=Path)
    create.add_argument('--reject-after-write', action='store_true')
    check = sub.add_parser('verify')
    check.add_argument('archive', type=Path)
    recover = sub.add_parser('restore')
    recover.add_argument('archive', type=Path)
    recover.add_argument('destination', type=Path)
    last = sub.add_parser('latest')
    last.add_argument('directory', type=Path)
    args = parser.parse_args()
    if os.geteuid() == 0:
        raise ValueError('the project backup runs as the ordinary lab operator')
    if args.command == 'build':
        result = build(args.source, args.destination, args.reject_after_write)
    elif args.command == 'restore':
        result = restore(args.archive, args.destination)
    elif args.command == 'verify':
        _, manifest = validate(args.archive)
        result = {'archive': str(args.archive), 'actualSha256': digest(args.archive.read_bytes()), 'manifest': manifest, 'verified': True}
    else:
        print(latest(args.directory))
        return 0
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
