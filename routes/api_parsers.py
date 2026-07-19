# Skytree Flasher / routes/api_parsers.py
"""解析器管理 API — 安装/卸载/列出外挂 JS 解析器"""

import os, json, time, base64, shutil
from urllib import request as urllib_request
from urllib.error import URLError, HTTPError
from flask import Blueprint, request, jsonify

from config import logger, PARSERS_DIR

parsers_bp = Blueprint('parsers', __name__, url_prefix='/api/parsers')

def _ensure_dir():
    os.makedirs(PARSERS_DIR, exist_ok=True)

def _registry_path():
    return os.path.join(PARSERS_DIR, 'registry.json')

def _load_registry() -> dict:
    """加载解析器注册表"""
    rp = _registry_path()
    if os.path.exists(rp):
        try:
            with open(rp, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"parsers": []}

def _save_registry(reg: dict):
    _ensure_dir()
    with open(_registry_path(), 'w', encoding='utf-8') as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)

def _parser_file_path(filename: str) -> str:
    return os.path.join(PARSERS_DIR, filename)

def _refresh_registry():
    """扫描 parsers 目录，自动同步 registry.json（处理手动放入/删除的文件）"""
    _ensure_dir()
    reg = _load_registry()
    known = {p['filename'] for p in reg['parsers']}

    # 扫描目录中所有 .js 文件
    actual = set()
    for f in os.listdir(PARSERS_DIR):
        if f.endswith('.js') and f != 'registry.json':
            actual.add(f)

    # 新文件自动注册
    for f in actual - known:
        fp = _parser_file_path(f)
        stat = os.stat(fp)
        reg['parsers'].append({
            "filename": f,
            "name": f.replace('.js', ''),
            "installed_at": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime)),
            "size": stat.st_size,
            "source": "local",
        })

    # 已删除文件移除注册
    reg['parsers'] = [p for p in reg['parsers'] if p['filename'] in actual]

    _save_registry(reg)
    return reg

@parsers_bp.route('/list', methods=['GET'])
def list_parsers():
    """列出已安装的解析器"""
    reg = _refresh_registry()
    return jsonify({"success": True, "parsers": reg['parsers'], "parsers_dir": PARSERS_DIR})

@parsers_bp.route('/read/<filename>', methods=['GET'])
def read_parser(filename):
    """读取解析器文件内容"""
    if '/' in filename or '\\' in filename or '..' in filename:
        return jsonify({"success": False, "error": "文件名非法"}), 400

    target = _parser_file_path(filename)
    if not os.path.isfile(target):
        return jsonify({"success": False, "error": "文件不存在"}), 404

    try:
        with open(target, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({"success": True, "content": content, "size": os.path.getsize(target)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@parsers_bp.route('/install', methods=['POST'])
def install_parser():
    """上传安装解析器（.js 文件）"""
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "未选择文件"})

    file = request.files['file']
    filename = file.filename
    if not filename.endswith('.js'):
        return jsonify({"success": False, "error": "仅支持 .js 文件"})

    # 安全检查：文件名不含路径分隔符
    if '/' in filename or '\\' in filename or '..' in filename:
        return jsonify({"success": False, "error": "文件名非法"})

    # 覆盖安装检查
    _ensure_dir()
    target = _parser_file_path(filename)
    force = request.form.get('force', 'false').lower() == 'true'

    if os.path.exists(target) and not force:
        # 返回需要确认的信息
        stat = os.stat(target)
        return jsonify({
            "success": False,
            "error": "overwrite_confirm",
            "message": f"解析器 {filename} 已存在（{(stat.st_size/1024):.1f}KB），是否覆盖？",
            "existing": {"filename": filename, "size": stat.st_size},
        })

    file.save(target)

    # 更新注册表
    reg = _load_registry()
    # 移除旧的同名条目
    reg['parsers'] = [p for p in reg['parsers'] if p['filename'] != filename]
    reg['parsers'].append({
        "filename": filename,
        "name": request.form.get('name', filename.replace('.js', '')),
        "installed_at": time.strftime('%Y-%m-%d %H:%M:%S'),
        "size": os.path.getsize(target),
        "source": "local",
    })
    _save_registry(reg)

    return jsonify({"success": True, "message": f"已安装 {filename}"})

@parsers_bp.route('/uninstall/<filename>', methods=['DELETE'])
def uninstall_parser(filename):
    """卸载解析器"""
    if '/' in filename or '\\' in filename or '..' in filename:
        return jsonify({"success": False, "error": "文件名非法"})

    target = _parser_file_path(filename)
    if not os.path.exists(target):
        return jsonify({"success": False, "error": "解析器不存在"})

    os.remove(target)

    # 更新注册表
    reg = _load_registry()
    reg['parsers'] = [p for p in reg['parsers'] if p['filename'] != filename]
    _save_registry(reg)

    return jsonify({"success": True, "message": f"已卸载 {filename}"})

@parsers_bp.route('/install-url', methods=['POST'])
def install_from_url():
    """从 URL 下载安装解析器"""
    data = request.get_json(silent=True) or {}
    url = data.get('url', '').strip()
    filename = data.get('filename', '').strip()

    if not url:
        return jsonify({"success": False, "error": "URL 为空"})

    if not filename:
        # 从 URL 提取文件名
        filename = url.rsplit('/', 1)[-1].split('?')[0]
    if not filename.endswith('.js'):
        filename += '.js'
    if '/' in filename or '\\' in filename or '..' in filename:
        return jsonify({"success": False, "error": "文件名非法"})

    _ensure_dir()
    target = _parser_file_path(filename)

    try:
        req = urllib_request.Request(url)
        with urllib_request.urlopen(req, timeout=30) as resp:
            content = resp.read()

        # 简单校验：JS 文件不应超过 500KB
        if len(content) > 500 * 1024:
            return jsonify({"success": False, "error": "文件过大（>500KB）"})

        with open(target, 'wb') as f:
            f.write(content)
    except Exception as e:
        return jsonify({"success": False, "error": f"下载失败: {e}"})

    reg = _load_registry()
    reg['parsers'] = [p for p in reg['parsers'] if p['filename'] != filename]
    reg['parsers'].append({
        "filename": filename,
        "name": filename.replace('.js', ''),
        "installed_at": time.strftime('%Y-%m-%d %H:%M:%S'),
        "size": len(content),
        "source": "url:" + url,
    })
    _save_registry(reg)

    return jsonify({"success": True, "message": f"已从 URL 安装 {filename}"})

@parsers_bp.route('/install-webdav', methods=['POST'])
def install_from_webdav():
    """从 WebDAV 安装解析器"""
    from config import WEBDAV_URL, WEBDAV_USER, WEBDAV_PASS

    data = request.get_json(silent=True) or {}
    remote_name = data.get('filename', '').strip()
    # 允许覆盖 WebDAV 配置
    webdav_url = (data.get('webdav_url') or WEBDAV_URL).rstrip('/')
    webdav_user = data.get('webdav_user') or WEBDAV_USER
    webdav_pass = data.get('webdav_pass') or WEBDAV_PASS

    if not remote_name:
        return jsonify({"success": False, "error": "文件名为空"})
    if not remote_name.endswith('.js'):
        remote_name += '.js'

    _ensure_dir()
    target = _parser_file_path(remote_name)

    try:
        auth = base64.b64encode(f"{webdav_user}:{webdav_pass}".encode()).decode()
        url = webdav_url + '/' + remote_name
        req = urllib_request.Request(url, headers={'Authorization': f'Basic {auth}'})
        with urllib_request.urlopen(req, timeout=30) as resp:
            content = resp.read()

        with open(target, 'wb') as f:
            f.write(content)
    except Exception as e:
        return jsonify({"success": False, "error": f"WebDAV 下载失败: {e}"})

    reg = _load_registry()
    reg['parsers'] = [p for p in reg['parsers'] if p['filename'] != remote_name]
    reg['parsers'].append({
        "filename": remote_name,
        "name": remote_name.replace('.js', ''),
        "installed_at": time.strftime('%Y-%m-%d %H:%M:%S'),
        "size": len(content),
        "source": "webdav",
    })
    _save_registry(reg)

    return jsonify({"success": True, "message": f"已从 WebDAV 安装 {remote_name}"})

@parsers_bp.route('/webdav-list', methods=['POST'])
def webdav_list_parsers():
    """列出 WebDAV 上可用的解析器"""
    from config import WEBDAV_URL, WEBDAV_USER, WEBDAV_PASS

    data = request.get_json(silent=True) or {}
    webdav_url = (data.get('webdav_url') or WEBDAV_URL).rstrip('/')
    webdav_user = data.get('webdav_user') or WEBDAV_USER
    webdav_pass = data.get('webdav_pass') or WEBDAV_PASS

    auth = base64.b64encode(f"{webdav_user}:{webdav_pass}".encode()).decode()
    propfind = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<d:propfind xmlns:d="DAV:"><d:prop>'
        '<d:displayname/><d:getcontentlength/><d:getlastmodified/>'
        '</d:prop></d:propfind>'
    )
    try:
        req = urllib_request.Request(
            webdav_url + '/',
            data=propfind.encode('utf-8'),
            method='PROPFIND',
            headers={
                'Authorization': f'Basic {auth}',
                'Content-Type': 'application/xml; charset=utf-8',
                'Depth': '1',
            }
        )
        with urllib_request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode('utf-8', errors='ignore')

        import re
        files = []
        # 解析 PROPFIND 响应中的 href + 内容长度
        for m in re.finditer(r'<d:href>(.*?)</d:href>', body):
            href = m.group(1).strip().rstrip('/')
            name = href.rsplit('/', 1)[-1] if '/' in href else href
            if name.endswith('.js') and name != 'registry.json':
                files.append({"name": name})

        return jsonify({"success": True, "files": files})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})