#!/usr/bin/env python3
"""Sync full project + single-file frontend to GitHub"""
import json, subprocess, base64, os, sys

GIT_API = 'repos/1248331222/flash-tool/git'
HEAD_REF = f'{GIT_API}/refs/heads/master'
PROJECT = '/home/ubuntu/flash_tool'

def gh(method, path, data=None):
    cmd = ['gh', 'api', path, '--method', method]
    if data:
        cmd += ['--input', '-']
    p = subprocess.run(cmd, input=json.dumps(data) if data else None,
                       capture_output=True, text=True, timeout=60)
    if p.returncode != 0:
        print(f'ERROR: {p.stderr}', file=sys.stderr); sys.exit(1)
    return json.loads(p.stdout)

base_sha = gh('GET', HEAD_REF)['object']['sha']
print(f'Base: {base_sha[:7]}')

# Collect all files (exclude junk)
EXCLUDE_DIRS = {'.git', 'venv', '__pycache__', 'node_modules'}
EXCLUDE_FILES = {'app.log', 'flash_tool.log', 'sync_repo.py', 'clear_repo.py', 'deploy_single.py', 'git_push.py'}
EXCLUDE_EXTS = {'.pyc', '.pyo'}

files = []
for root, dirs, fnames in os.walk(PROJECT):
    dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
    rel_root = os.path.relpath(root, PROJECT)
    if rel_root == '.':
        rel_root = ''
    for fname in fnames:
        ext = os.path.splitext(fname)[1]
        if fname in EXCLUDE_FILES or ext in EXCLUDE_EXTS:
            continue
        fpath = os.path.join(root, fname)
        relpath = os.path.join(rel_root, fname) if rel_root else fname
        files.append((relpath, fpath))

files.sort()
print(f'Total: {len(files)} files')

# Create blobs
tree_items = []
for i, (relpath, fpath) in enumerate(files):
    with open(fpath, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode()
    blob = gh('POST', f'{GIT_API}/blobs', {'content': b64, 'encoding': 'base64'})
    tree_items.append({'path': relpath, 'mode': '100644', 'type': 'blob', 'sha': blob['sha']})
    if (i + 1) % 30 == 0:
        print(f'  {i+1}/{len(files)}...')

print(f'  All {len(files)} blobs created')

# Create tree
tree = gh('POST', f'{GIT_API}/trees', {'tree': tree_items})
print(f'Tree: {tree["sha"][:7]}')

# Commit
commit = gh('POST', f'{GIT_API}/commits', {
    'message': 'sync: full project + single-file frontend',
    'tree': tree['sha'], 'parents': [base_sha]
})
print(f'Commit: {commit["sha"][:7]}')

# Update ref
gh('PATCH', HEAD_REF, {'sha': commit['sha'], 'force': True})
print('Ref updated ✅ 同步完成')
