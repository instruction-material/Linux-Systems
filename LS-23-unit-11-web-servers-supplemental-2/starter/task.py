"""Investigate explicit defaults with actual loopback Nginx requests."""
import base64
from nginx_lab import quote, run_lab

# TODO: select an explicit fallback independently of the named-site order.
explicit_default = False

def make_servers(lab):
    sites = [('alpha.test', 'alpha.txt'), ('beta.test', 'beta.txt')]
    if lab.reverse:
        sites.reverse()
    blocks = []
    if explicit_default:
        blocks.append('server { listen 127.0.0.1:%s default_server; server_name _; return 404; }' % lab.port)
    for name, filename in sites:
        blocks.append('server { listen 127.0.0.1:%s; server_name %s; location = /index.txt { alias %s; } location / { return 404; } }' % (lab.port, name, quote(lab.root / filename)))
    lab.data.update(explicitDefault=explicit_default, namedSiteOrder=[x[0] for x in sites])
    return '\n'.join(blocks)

def observe(lab):
    alpha = lab.request('named alpha', '/index.txt', 'alpha.test')
    beta = lab.request('named beta', '/index.txt', 'beta.test')
    lab.request('uppercase name and explicit port', '/index.txt', 'ALPHA.TEST:' + str(lab.port))
    unknown = lab.request('unmatched name', '/index.txt', 'unmatched.test')
    ip = lab.request('IP host', '/index.txt', '127.0.0.1')
    no_host = lab.request('HTTP1.0 without Host', '/index.txt', None, version='HTTP/1.0')
    malformed = lab.request('HTTP1.1 without Host', '/index.txt', None)
    missing = lab.request('known name missing file', '/missing.txt', 'alpha.test')
    head = lab.request('HEAD known file', '/index.txt', 'alpha.test', method='HEAD')
    return (alpha['status'] == beta['status'] == head['status'] == 200
            and base64.b64decode(alpha['bodyBase64']) == (lab.source / 'alpha.txt').read_bytes()
            and base64.b64decode(beta['bodyBase64']) == (lab.source / 'beta.txt').read_bytes()
            and unknown['status'] == ip['status'] == no_host['status'] == missing['status'] == 404
            and malformed['status'] == 400 and not base64.b64decode(head['bodyBase64']))

if __name__ == '__main__':
    raise SystemExit(run_lab(make_servers, observe, ['alpha.txt', 'beta.txt']))
