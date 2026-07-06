#!/usr/bin/env python3
import json, subprocess, base64, os

HEAD_REF = 'repos/1248331222/flash-tool/git/refs/heads/master'
GIT_TREE = 'repos/1248331222/flash-tool/git/trees'
GIT_COMMIT = 'repos/1248331222/flash-tool/git/commits'
PROJECT = '/home/ubuntu/flash_tool'

def gh(method, path, data=None):
    cmd = ['gh', 'api', path, '--method', method]
    if data:
        cmd += ['--input', '-']
    p = subprocess.run(cmd, input=json.dumps(data) if data else None,
                       capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        print(f'ERR: {p.stderr}'); exit(1)
    return json.loads(p.stdout)

base = gh('GET', HEAD_REF)['object']['sha']
print(f'Base: {base[:7]}')

# Collect all files
EXCLUDE = {'.git', 'venv', '__pycache__'}
EXCLUDE_F = {'app.log', 'flash_tool.log', 'sync_v385.py', 'sync_full.py', 'clear_repo.py', 'deploy_single.py', 'git_push.py', 'sync_repo.py'}
EXCLUDE_E = {'.pyc', '.pyo'}

items = []
for root, dirs, fnames in os.walk(PROJECT):
    dirs[:] = [d for d in dirs if d not in EXCLUDE]
    rel = os.path.relpath(root, PROJECT)
    if rel == '.': rel = ''
    for f in fnames:
        if f in EXCLUDE_F or os.path.splitext(f)[1] in EXCLUDE_E:
            continue
        fp = os.path.join(root, f)
        rp = os.path.join(rel, f) if rel else f
        with open(fp, 'rb') as fh:
            items.append({'path': rp, 'mode': '100644', 'type': 'blob',
                          'content': fh.read().decode('utf-8', errors='replace')})

print(f'Files: {len(items)}')

tree = gh('POST', GIT_TREE, {'tree': items})
c = gh('POST', GIT_COMMIT, {
    'message': 'v3.8.5: regenerate single-file frontend',
    'tree': tree['sha'], 'parents': [base]
})
gh('PATCH', HEAD_REF, {'sha': c['sha'], 'force': True})
print(f'✅ Sync {c["sha"][:7]}')

# Enable Pages
p = gh('POST', 'repos/1248331222/flash-tool/pages',
       {'source': {'branch': 'master', 'path': '/docs'}})
print(f'Pages: {p["status"]} - {p["html_url"]}')
