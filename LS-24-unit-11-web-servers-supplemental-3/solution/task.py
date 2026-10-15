"""Compare real static validators with response bytes and metadata."""
import base64
import hashlib
import os
from nginx_lab import quote, run_lab

# Enable the server-generated entity validator and retain date checks.
etag_setting = 'on'

def headers(row):
    return {key.lower(): value for key, value in row['headers']}

def make_servers(lab):
    lab.data['etagSetting'] = etag_setting
    return ('server { listen 127.0.0.1:%s; server_name lab.test; root %s; '
            'etag %s; if_modified_since exact; add_header Cache-Control "max-age=0, must-revalidate" always; '
            'location / { try_files $uri =404; } }') % (lab.port, quote(lab.root), etag_setting)

def observe(lab):
    path = lab.root / 'resource.txt'
    before = path.read_bytes()
    first = lab.request('initial representation', '/resource.txt')
    initial = headers(first)
    old_tag = initial.get('etag', '"no-entity-tag-supplied"')
    same = lab.request('matching entity validator', '/resource.txt', headers={'If-None-Match': old_tag})
    lab.request('matching modification date', '/resource.txt', headers={'If-Modified-Since': initial['last-modified']})
    lab.request('different entity validator', '/resource.txt', headers={'If-None-Match': '"different-course-tag"'})
    lab.request('HEAD representation', '/resource.txt', method='HEAD')
    old_mtime = path.stat().st_mtime_ns
    changed = before + b'changed size and timestamp\n'
    path.write_bytes(changed)
    os.utime(path, ns=(old_mtime + 2000000000, old_mtime + 2000000000))
    updated = lab.request('old validator after changed file', '/resource.txt', headers={'If-None-Match': old_tag})
    new_tag = headers(updated).get('etag', '"no-entity-tag-supplied"')
    fresh = lab.request('current validator after changed file', '/resource.txt', headers={'If-None-Match': new_tag})
    stamp = path.stat().st_mtime_ns
    same_size = bytes([changed[0] ^ 1]) + changed[1:]
    path.write_bytes(same_size)
    os.utime(path, ns=(stamp, stamp))
    hidden = lab.request('same metadata different bytes', '/resource.txt')
    metadata = lab.request('validator after same metadata edit', '/resource.txt', headers={'If-None-Match': new_tag})
    lab.request('missing representation', '/missing.txt')
    lab.data['fileChanges'] = dict(initialSha256=hashlib.sha256(before).hexdigest(),
                                 updatedSha256=hashlib.sha256(changed).hexdigest(),
                                 sameMetadataSha256=hashlib.sha256(same_size).hexdigest(),
                                 initialSize=len(before), updatedSize=len(changed), sameMetadataSize=len(same_size),
                                 initialMtimeNs=old_mtime, updatedMtimeNs=stamp,
                                 sameMetadataMtimeNs=path.stat().st_mtime_ns)
    return ('etag' in initial and same['status'] == fresh['status'] == metadata['status'] == 304
            and updated['status'] == hidden['status'] == 200
            and base64.b64decode(updated['bodyBase64']) == changed
            and base64.b64decode(hidden['bodyBase64']) == same_size)

if __name__ == '__main__':
    raise SystemExit(run_lab(make_servers, observe, ['resource.txt']))
