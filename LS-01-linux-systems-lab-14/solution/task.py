import base64
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

def readiness_ok(reply, expected_health):
    # Confirm actual status and expected release identity.
    return reply['status'] == 200 and base64.b64decode(reply['bodyBase64']) == expected_health

def make_servers(lab):
    prepare(lab)
    (lab.root / 'wrong').mkdir()
    shutil.copyfile(lab.root / 'release-a-health.txt', lab.root / 'wrong/health.txt')
    (lab.root / 'wrong/index.txt').write_text('Wrong release page.\n')
    (lab.root / 'missing').mkdir()
    (lab.root / 'missing/index.txt').write_text('No health representation.\n')
    initial, good = ('release-b', 'release-a') if lab.reverse else ('release-a', 'release-b')
    os.symlink(initial, lab.root / 'current')
    lab.data.update(initialTarget=initial, goodTarget=good, deploymentSteps=[])
    return server(lab)

def observe(lab):
    lab.request('initial health', '/health.txt')
    lab.request('initial page', '/index.txt')
    good = lab.data['goodTarget']
    expected_good = (lab.root / good / 'health.txt').read_bytes()
    for label, target, expected in [('good', good, expected_good), ('wrong identity', 'wrong', b'release=wrong\n'), ('missing health', 'missing', b'release=missing\n')]:
        before = os.readlink(lab.root / 'current')
        activate(lab, target)
        reply = lab.request(label + ' health', '/health.txt')
        accepted = readiness_ok(reply, expected)
        if not accepted:
            activate(lab, before)
        page = lab.request(label + ' page after decision', '/index.txt')
        lab.data['deploymentSteps'].append(dict(label=label, beforeTarget=before, candidate=target,
            expectedHealthBase64=base64.b64encode(expected).decode(), readinessAccepted=accepted,
            rolledBack=not accepted, afterTarget=os.readlink(lab.root / 'current'), pageStatus=page['status']))
    steps = lab.data['deploymentSteps']
    return (steps[0]['readinessAccepted'] and not steps[1]['readinessAccepted']
            and not steps[2]['readinessAccepted'] and os.readlink(lab.root / 'current') == good)

if __name__ == '__main__':
    raise SystemExit(run_lab(make_servers, observe, FIXTURES))
