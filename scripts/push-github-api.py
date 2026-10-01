"""Exact-object, fast-forward-only fallback when Git HTTPS transport fails."""
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / '本地语音输入' / 'scripts'))
import github_backup as github


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def identity(value):
    match = re.fullmatch(r'(.*) <([^>]+)> (\d+) ([+-])(\d{2})(\d{2})', value)
    if not match:
        raise RuntimeError('Unsupported commit identity')
    name, email, epoch, sign, hours, minutes = match.groups()
    offset = (int(hours)*60+int(minutes)) * (1 if sign == '+' else -1)
    return {'name':name, 'email':email, 'date':datetime.fromtimestamp(int(epoch), timezone(timedelta(minutes=offset))).isoformat()}


def commit_info(sha):
    headers, message = git('cat-file', 'commit', sha).decode('utf-8').split('\n\n', 1)
    values = {}
    parents = []
    for line in headers.splitlines():
        key, value = line.split(' ', 1)
        if key == 'parent':
            parents.append(value)
        elif key in ('tree','author','committer'):
            values[key] = value
        else:
            raise RuntimeError('Unsupported or signed commit header; refusing rewrite')
    return values, parents, message


def files_at(sha):
    result = {}
    for record in git('ls-tree', '-r', '-z', sha).split(b'\0'):
        if not record:
            continue
        metadata, path = record.split(b'\t', 1)
        mode, kind, blob = metadata.decode().split()
        if kind != 'blob':
            raise RuntimeError('Submodule not supported')
        result[path.decode('utf-8')] = (mode, blob)
    return result


def push():
    token = github.credentials()
    route = '/repos/' + github.OWNER + '/' + github.REPOSITORY
    repo = github.request(token, route)
    if not repo['private']:
        raise RuntimeError('Repository must remain private')
    initial = github.request(token, route + '/git/ref/heads/main')['object']['sha']
    subprocess.run(['git','-C',str(ROOT),'merge-base','--is-ancestor',initial,'HEAD'], check=True)
    commits = git('rev-list', '--reverse', initial+'..HEAD').decode().splitlines()
    current = initial
    for sha in commits:
        info, parents, message = commit_info(sha)
        if parents != [current]:
            raise RuntimeError('Only linear fast-forward history supported')
        base_info, _, _ = commit_info(current)
        files = files_at(sha)
        old_files = files_at(current)
        changed = [p.decode('utf-8') for p in git('diff','--name-only','-z',current,sha).split(b'\0') if p]
        entries = []
        binaries = []
        for path in changed:
            if path not in files:
                entries.append({'path':path,'mode':old_files[path][0],'type':'blob','sha':None})
                continue
            mode, blob_sha = files[path]
            data = git('cat-file', 'blob', blob_sha)
            try:
                text = data.decode('utf-8')
                if '\0' in text:
                    raise UnicodeError()
                entries.append({'path':path,'mode':mode,'type':'blob','content':text})
            except UnicodeError:
                binaries.append((path, mode, blob_sha, data))

        def upload_blob(item):
            path, mode, expected, data = item
            result = github.request(token, route+'/git/blobs', {'content':base64.b64encode(data).decode('ascii'),'encoding':'base64'})
            if result['sha'] != expected:
                raise RuntimeError('Binary Git blob checksum mismatch')
            print('Verified Git blob: '+path, flush=True)
            return {'path':path,'mode':mode,'type':'blob','sha':expected}

        with ThreadPoolExecutor(max_workers=3) as pool:
            entries.extend(pool.map(upload_blob, binaries))
        tree = github.request(token, route+'/git/trees', {'base_tree':base_info['tree'],'tree':entries})
        if tree['sha'] != info['tree']:
            raise RuntimeError('Git tree checksum mismatch; main was not changed')
        created = github.request(token, route+'/git/commits', {'message':message,'tree':info['tree'],
            'parents':parents,'author':identity(info['author']),'committer':identity(info['committer'])})
        if created['sha'] != sha:
            raise RuntimeError('Git commit checksum mismatch; main was not changed')
        current = sha
        print('Verified exact Git commit: '+sha, flush=True)
    if current != initial:
        github.request(token, route+'/git/refs/heads/main', {'sha':current,'force':False}, method='PATCH')
    actual = github.request(token, route+'/git/ref/heads/main')['object']['sha']
    if actual != current:
        raise RuntimeError('Remote ref verification failed')
    subprocess.run(['git','-C',str(ROOT),'update-ref','refs/remotes/origin/main',actual], check=True)
    print(json.dumps({'verified':True,'main':actual,'repository':repo['html_url']}), flush=True)


if __name__ == '__main__':
    try:
        push()
    except Exception as exc:
        print('API push failed: '+type(exc).__name__+((' HTTP '+str(exc.code)) if hasattr(exc,'code') else ''), flush=True)
        raise SystemExit(1)
