#!/usr/bin/env python3
import json, subprocess, base64, os, sys

HEAD = 'repos/1248331222/flash-tool/git/refs/heads/master'
TREE_API = 'repos/1248331222/flash-tool/git/trees'
COMMIT_API = 'repos/1248331222/flash-tool/git/commits'
PROJ = '/home/ubuntu/flash_tool'

def gh(m, p, d=None):
    c = ['gh', 'api', p, '--method', m]
    if d: c += ['--input', '-']
    r = subprocess.run(c, input=json.dumps(d) if d else None, capture_output=True, text=True, timeout=120)
    if r.returncode: print('ERR:', r.stderr); exit(1)
    return json.loads(r.stdout)

base = gh('GET', HEAD)['object']['sha']
print(f'Base: {base[:7]}')

# Collect all files
skip_dirs = {'.git', 'venv', '__pycache__', 'docs'}
skip_files = {'app.log', 'flash_tool.log', 'sync_v385.py', 'sync_full.py', 'clear_repo.py', 'deploy_single.py', 'deploy_frontend.py', 'git_push.py', 'sync_repo.py'}
skip_ext = {'.pyc', '.pyo'}

# Include docs/index.html for GitHub Pages
items = []
for root, dirs, fnames in os.walk(PROJ):
    dirs[:] = [d for d in dirs if d not in skip_dirs]
    rel = os.path.relpath(root, PROJ)
    if rel == '.': rel = ''
    for f in fnames:
        if f in skip_files or os.path.splitext(f)[1] in skip_ext:
            continue
        rp = os.path.join(rel, f) if rel else f
        with open(os.path.join(root, f), 'rb') as fh:
            items.append({'path': rp, 'mode': '100644', 'type': 'blob',
                          'content': fh.read().decode('utf-8', errors='replace')})

print(f'Files: {len(items)}')

tree = gh('POST', TREE_API, {'tree': items})
c = gh('POST', COMMIT_API, {
    'message': 'v3.8.6: sync project update',
    'tree': tree['sha'], 'parents': [base]
})
gh('PATCH', HEAD, {'sha': c['sha'], 'force': True})
print(f'✅ v3.8.6 synced ({c["sha"][:7]})')
