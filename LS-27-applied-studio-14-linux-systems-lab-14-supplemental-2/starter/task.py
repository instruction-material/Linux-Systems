import base64
import hashlib
import json
import os
import shutil
from nginx_lab import quote, run_lab

FIXTURES = ['release-a-health.txt', 'release-a-index.txt', 'release-b-health.txt', 'release-b-index.txt']

def activate(lab, target):
    assert target in ['release-a', 'release-b', 'wrong', 'missing']
    temporary = lab.root / '.pending-current'
    os.symlink(target, temporary)
    os.replace(temporary, lab.root / 'current')

def prepare(lab):
    for release in ['a', 'b']:
        directory = lab.root / ('release-' + release)
        directory.mkdir()
        for name in ['health', 'index']:
            shutil.copyfile(lab.root / ('release-' + release + '-' + name + '.txt'), directory / (name + '.txt'))

def server(lab):
    return ('server { listen 127.0.0.1:%s; server_name lab.test; root %s; '
            'open_file_cache off; etag off; location / { try_files $uri =404; } }') % (lab.port, quote(lab.root / 'current'))

def verify_release(directory, manifest):
    # TODO: compare every actual payload digest with the supplied manifest.
    return all((directory / name).is_file() for name in manifest)

def make_servers(lab):
    prepare(lab)
    manifest = json.loads((lab.root / 'release-manifest.json').read_text())
    assert set(manifest) == {'health.txt', 'index.txt'}
    assert all(isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value) for value in manifest.values())
    lab.data.update(manifest=manifest, integritySteps=[])
    os.symlink('release-a', lab.root / 'current')
    return server(lab)

def observe(lab):
    lab.request('initial health', '/health.txt')
    lab.request('initial page', '/index.txt')
    altered = 'health.txt' if lab.reverse else 'index.txt'
    lab.data['alteredMember'] = altered
    directory = lab.root / 'release-b'
    for label in ['intact', 'tampered', 'missing', 'restored']:
        for name in ['health', 'index']:
            shutil.copyfile(lab.root / ('release-b-' + name + '.txt'), directory / (name + '.txt'))
        if label == 'tampered':
            path = directory / altered
            path.write_bytes(path.read_bytes() + b'altered payload\n')
        if label == 'missing':
            (directory / 'index.txt').unlink()
        inspected = {}
        for name, expected in lab.data['manifest'].items():
            path = directory / name
            content = path.read_bytes() if path.is_file() else None
            inspected[name] = dict(exists=content is not None, expected=expected,
                contentBase64=base64.b64encode(content).decode() if content is not None else None,
                sha256=hashlib.sha256(content).hexdigest() if content is not None else None)
        activate(lab, 'release-a')
        accepted = verify_release(directory, lab.data['manifest'])
        if accepted:
            activate(lab, 'release-b')
        health = lab.request(label + ' health', '/health.txt')
        page = lab.request(label + ' page', '/index.txt')
        lab.data['integritySteps'].append(dict(label=label, inspectedFiles=inspected,
            integrityAccepted=accepted, afterTarget=os.readlink(lab.root / 'current'),
            healthStatus=health['status'], pageStatus=page['status']))
    return [step['integrityAccepted'] for step in lab.data['integritySteps']] == [True, False, False, True]

if __name__ == '__main__':
    raise SystemExit(run_lab(make_servers, observe, FIXTURES + ['release-manifest.json']))
