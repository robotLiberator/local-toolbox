"""Back up this toolbox privately using the user's existing Git credentials.

No credentials are written to disk or printed. Release assets are streamed.
"""
import argparse
import hashlib
import http.client
import json
import re
from pathlib import Path
import subprocess
import urllib.error
import urllib.parse
import urllib.request

OWNER = 'robotLiberator'
REPOSITORY = 'local-toolbox'
API = 'https://api.github.com'


def credentials():
    result = subprocess.run(['git', 'credential', 'fill'], input='protocol=https\nhost=github.com\nusername=' + OWNER + '\n\n',
                            text=True, capture_output=True, check=True)
    values = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    return values['password']


def request(token, route, data=None, method=None):
    payload = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(API + route, data=payload, method=method,
        headers={'Authorization':'Bearer ' + token, 'Accept':'application/vnd.github+json',
                 'X-GitHub-Api-Version':'2022-11-28', 'User-Agent':'Local-Toolbox-Backup', 'Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=60) as response:
        if response.status == 204:
            return None
        return json.load(response)


def prepare(token):
    user = request(token, '/user')
    if user['login'].lower() != OWNER.lower():
        raise RuntimeError('Authenticated account differs from expected owner')
    route = '/repos/' + OWNER + '/' + REPOSITORY
    try:
        repo = request(token, route)
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
        repo = request(token, '/user/repos', {'name':REPOSITORY, 'private':True,
            'description':'个人工具箱：独立本地应用、源码和离线产品备份', 'auto_init':False})
    if not repo['private']:
        raise RuntimeError('Existing repository is not private; refusing backup')
    print(json.dumps({'repository':repo['html_url'], 'private':repo['private']}, ensure_ascii=False), flush=True)


def upload(token, upload_url, path):
    parsed = urllib.parse.urlsplit(upload_url.split('{', 1)[0] + '?name=' + urllib.parse.quote(asset_name(path)))
    if parsed.hostname != 'uploads.github.com':
        raise RuntimeError('Unexpected upload host')
    connection = http.client.HTTPSConnection(parsed.hostname, timeout=300)
    try:
        connection.putrequest('POST', parsed.path + '?' + parsed.query)
        for key, value in {'Authorization':'Bearer ' + token, 'User-Agent':'Local-Toolbox-Backup',
                'Content-Type':'application/zip', 'Content-Length':str(path.stat().st_size),
                'Accept':'application/vnd.github+json'}.items():
            connection.putheader(key, value)
        connection.endheaders()
        count = 0
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            while chunk := stream.read(8 * 1024 * 1024):
                connection.send(chunk)
                digest.update(chunk)
                count += len(chunk)
                if count // (64 * 1024 * 1024) != (count-len(chunk)) // (64 * 1024 * 1024):
                    print(f'Uploaded {count//1024//1024} MiB: {path.name}', flush=True)
        response = connection.getresponse()
        data = json.loads(response.read())
        if response.status != 201 or data.get('state') != 'uploaded' or data.get('size') != count:
            raise RuntimeError(f'Asset upload failed: HTTP {response.status}')
        if data.get('digest') and data['digest'] != 'sha256:' + digest.hexdigest():
            raise RuntimeError('Remote asset digest mismatch')
        print(json.dumps({'asset':data['name'], 'bytes':count, 'sha256':digest.hexdigest(),
                          'url':data['browser_download_url']}, ensure_ascii=False), flush=True)
    finally:
        connection.close()


def release(token, tag, files, title=None, body=None):
    route = '/repos/' + OWNER + '/' + REPOSITORY + '/releases'
    try:
        result = request(token, route + '/tags/' + tag)
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
        result = request(token, route, {'tag_name':tag, 'target_commitish':'main',
            'name':title or ('本地语音输入 ' + tag), 'body':body or '完整 Windows x64 离线包及源码备份。请解压整个应用目录，不要只复制 exe。',
            'draft':False, 'prerelease':False})
    assets = request(token, route + '/' + str(result['id']) + '/assets')
    for filename in files:
        path = Path(filename).resolve(strict=True)
        existing = next((a for a in assets if a['name'] == asset_name(path)), None)
        if existing:
            with path.open('rb') as stream:
                digest = 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()
            if existing.get('digest') != digest or existing['size'] != path.stat().st_size:
                raise RuntimeError('Existing asset differs; refusing overwrite')
            print('Verified existing asset: ' + path.name, flush=True)
        else:
            upload(token, result['upload_url'], path)
    print(json.dumps({'release':result['html_url']}, ensure_ascii=False), flush=True)


def asset_name(path):
    # GitHub sanitizes Unicode asset filenames; keep a predictable download name.
    version = re.search(r'-v(\d+\.\d+\.\d+)\.zip$', path.name)
    if 'Windows-x64' in path.name:
        if not version:
            raise RuntimeError('Missing version in release archive filename')
        return 'bubble-dictation-windows-x64-v' + version[1] + '.zip'
    if '源码' in path.name:
        if not version:
            raise RuntimeError('Missing version in source archive filename')
        return 'local-toolbox-source-v' + version[1] + '.zip'
    if not path.name.isascii():
        raise RuntimeError('Asset name must be ASCII')
    return path.name


def verify(token, tag, files):
    route = '/repos/' + OWNER + '/' + REPOSITORY + '/releases'
    result = request(token, route + '/tags/' + tag)
    assets = request(token, route + '/' + str(result['id']) + '/assets')
    for filename in files:
        path = Path(filename).resolve(strict=True)
        with path.open('rb') as stream:
            digest = 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()
        matches = [a for a in assets if a.get('digest') == digest and a['size'] == path.stat().st_size and a['state'] == 'uploaded']
        if len(matches) != 1:
            raise RuntimeError('Remote checksum or asset count mismatch')
        asset = matches[0]
        if asset['name'] != asset_name(path):
            asset = request(token, route + '/assets/' + str(asset['id']),
                            {'name':asset_name(path), 'label':path.name}, method='PATCH')
        print(json.dumps({'verified':True, 'name':asset['name'], 'bytes':asset['size'],
                          'digest':asset['digest'], 'url':asset['browser_download_url']}, ensure_ascii=False), flush=True)


def prune_previous_voice_releases(token, tag, files):
    """Explicit maintenance command: keep verified 1.0.2; remove only 1.0.0/1.0.1."""
    if tag != 'bubble-dictation-v1.0.2' or len(files) != 2:
        raise RuntimeError('Cleanup requires the two current 1.0.2 archives')
    names = {asset_name(Path(filename)) for filename in files}
    if names != {'bubble-dictation-windows-x64-v1.0.2.zip', 'local-toolbox-source-v1.0.2.zip'}:
        raise RuntimeError('Unexpected current archive names')
    prepare(token)
    verify(token, tag, files)
    route = '/repos/' + OWNER + '/' + REPOSITORY
    for old_tag in ('bubble-dictation-v1.0.0', 'bubble-dictation-v1.0.1'):
        try:
            old = request(token, route + '/releases/tags/' + old_tag)
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
        else:
            if old['tag_name'] != old_tag:
                raise RuntimeError('Release identity mismatch')
            request(token, route + '/releases/' + str(old['id']), method='DELETE')
            print('Deleted previous voice release and assets: ' + old_tag, flush=True)
        try:
            request(token, route + '/git/ref/tags/' + old_tag)
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
        else:
            request(token, route + '/git/refs/tags/' + old_tag, method='DELETE')
            print('Deleted previous voice tag: ' + old_tag, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare','release','verify','prune-previous-voice'])
    parser.add_argument('--tag', default='bubble-dictation-v1.0.2')
    parser.add_argument('--title')
    parser.add_argument('--body')
    parser.add_argument('files', nargs='*')
    args = parser.parse_args()
    try:
        token = credentials()
        if args.action == 'prepare':
            prepare(token)
        elif args.action == 'release':
            release(token, args.tag, args.files, args.title, args.body)
        elif args.action == 'verify':
            verify(token, args.tag, args.files)
        else:
            prune_previous_voice_releases(token, args.tag, args.files)
    except Exception as exc:
        # Do not print response bodies, credentials, request objects or tracebacks.
        print('Backup failed: ' + type(exc).__name__ + (' HTTP ' + str(exc.code) if isinstance(exc, urllib.error.HTTPError) else ''), flush=True)
        raise SystemExit(1)
