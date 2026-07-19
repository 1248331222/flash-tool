# Skytree Flasher / routes/api_upload.py
# 脚本上传模块 - WebDAV 上传到 OpenList
# 纯标准库实现，无额外依赖

import os, re, json, time, hashlib, random, base64
from urllib import request as urllib_request
from urllib.error import URLError, HTTPError
from flask import Blueprint, request, jsonify, current_app

from config import (
    WEBDAV_URL, WEBDAV_USER, WEBDAV_PASS, UPLOAD_DIR,
    WEBDAV_PUBLIC_BASE_URL,
    UPLOAD_WEBDAV_TIMEOUT_SHORT, UPLOAD_WEBDAV_TIMEOUT_LONG,
    UPLOAD_PREVIEW_MAX_CHARS, logger
)

upload_bp = Blueprint('upload', __name__, url_prefix='/api/script')

# ============================================================
# 管理鉴权装饰器 — 标注/重标/列出OpenList 等管理操作需管理员 token
# ============================================================
import functools

def _admin_required(f):
    """验证请求头 X-Admin-Token 是否匹配管理员凭证"""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        token = request.headers.get('X-Admin-Token', '')
        # 管理员凭证不硬编码在代码中。检查环境变量，若无则使用校验值
        from config import WEBDAV_USER as _wu
        admin_token = os.environ.get('ADMIN_TOKEN', '')
        if not admin_token:
            # 无环境变量时回退：必须传入的 token 等于 base64(WEBDAV_USER:WEBDAV_PASS)
            expected = base64.b64encode(f"{_wu}:{os.environ.get('WEBDAV_PASS', '')}".encode()).decode()
            if token == expected:
                return f(*args, **kwargs)
        elif token == admin_token:
            return f(*args, **kwargs)
        return jsonify({"success": False, "error": "管理员鉴权失败"}), 403
    return wrapper


ALLOWED_EXTENSIONS = {'.bat', '.cmd', '.sh', '.txt'}
MAX_FILE_SIZE = 1 * 1024 * 1024  # 1MB

DANGEROUS_PATTERNS = [
    r'rm\s+(-[rf]+\s+)+/',
    r'dd\s+if=/dev/zero',
    r':\(\)\s*\{\s*:\|:\s*&\s*\}\s*;',
]


def _sanitize_filename(original_name):
    """文件名脱敏：时间戳_随机6位_原文件名"""
    ts = time.strftime('%Y%m%d_%H%M%S')
    rand = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=6))
    return f"{ts}_{rand}_{original_name}"


def _detect_encoding(content: bytes) -> str:
    """检测文件编码，优先 UTF-8 回退 GBK"""
    for enc in ['utf-8', 'gbk', 'gb2312']:
        try:
            content.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return 'utf-8'


def _security_scan(content: str) -> list:
    """基础安全扫描，返回发现的危险模式列表"""
    findings = []
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            findings.append(pattern)
    return findings


def _upload_via_webdav(file_path: str, remote_name: str) -> bool:
    """通过 WebDAV PUT 上传文件到 OpenList（纯标准库实现）"""
    url = WEBDAV_URL.rstrip('/') + '/' + remote_name
    try:
        with open(file_path, 'rb') as f:
            content = f.read()

        # Basic Auth
        auth_str = base64.b64encode(f"{WEBDAV_USER}:{WEBDAV_PASS}".encode()).decode()
        req = urllib_request.Request(
            url,
            data=content,
            method='PUT',
            headers={
                'Content-Type': 'application/octet-stream',
                'Authorization': f'Basic {auth_str}',
            }
        )
        with urllib_request.urlopen(req, timeout=UPLOAD_WEBDAV_TIMEOUT_LONG) as resp:
            code = resp.status
            if code in (201, 204):
                logger.info(f"WebDAV 上传成功: {remote_name}")
                return True
            else:
                logger.error(f"WebDAV 上传失败: HTTP {code}")
                return False
    except URLError as e:
        logger.error(f"WebDAV 上传异常: {e}")
        return False
    except Exception as e:
        logger.error(f"WebDAV 上传异常: {e}")
        return False


@upload_bp.route('/upload', methods=['POST'])
def upload_script():
    """接收前端上传的刷机脚本，保存本地并上传到 OpenList"""
    # 1. 检查文件
    if 'file' not in request.files:
        return jsonify({"success": False, "error_code": "NO_FILE", "message": "未选择文件"})

    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error_code": "NO_FILE", "message": "文件名为空"})

    original_name = file.filename
    ext = os.path.splitext(original_name)[1].lower()

    # 2. 检查扩展名
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({
            "success": False, "error_code": "INVALID_FORMAT",
            "message": f"仅支持 {', '.join(ALLOWED_EXTENSIONS)} 格式"
        })

    # 3. 读取文件内容
    raw_bytes = file.read()
    if len(raw_bytes) > MAX_FILE_SIZE:
        return jsonify({
            "success": False, "error_code": "FILE_TOO_LARGE",
            "message": "文件大小超过 1MB 限制"
        })

    # 4. 检测编码，转为 UTF-8
    encoding = _detect_encoding(raw_bytes)
    try:
        content = raw_bytes.decode(encoding)
    except UnicodeDecodeError:
        content = raw_bytes.decode('utf-8', errors='replace')

    # 5. 安全检查
    dangerous = _security_scan(content)
    if dangerous:
        return jsonify({
            "success": False, "error_code": "DANGEROUS_CONTENT",
            "message": "脚本包含危险命令，已被拦截",
            "details": dangerous
        })

    # 6. 获取可选参数
    brand = request.form.get('brand', '').strip()
    device_model = request.form.get('device_model', '').strip()

    # 7. 保存本地 + 上传 OpenList
    safe_name = _sanitize_filename(original_name)
    local_path = os.path.join(UPLOAD_DIR, safe_name)

    # 确保本地目录存在
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # 写本地文件
    with open(local_path, 'w', encoding='utf-8') as f:
        f.write(content)

    # 上传到 OpenList
    upload_ok = _upload_via_webdav(local_path, safe_name)

    # 8. 更新元数据
    meta_path = os.path.join(UPLOAD_DIR, 'metadata.json')
    metadata = {}
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        except:
            metadata = {}

    metadata[safe_name] = {
        "original_name": original_name,
        "upload_time": time.strftime('%Y-%m-%d %H:%M:%S'),
        "file_size": len(raw_bytes),
        "script_type": ext.lstrip('.'),
        "brand": brand,
        "device_model": device_model,
        "encoding": encoding,
        "uploaded_to_openlist": upload_ok,
        "expire_time": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() + 86400 * 10)),
    }
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    return jsonify({
        "success": True,
        "file_id": safe_name,
        "message": "上传成功" + ("，已同步到样本库" if upload_ok else "（本地保存）"),
        "uploaded_to_openlist": upload_ok,
    })


@upload_bp.route('/list', methods=['GET'])
def list_uploads():
    """列出已上传的脚本"""
    meta_path = os.path.join(UPLOAD_DIR, 'metadata.json')
    if not os.path.exists(meta_path):
        return jsonify({"success": True, "files": []})

    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
    except:
        return jsonify({"success": True, "files": []})

    files = []
    for file_id, info in metadata.items():
        original_name = info.get("original_name", file_id)
        files.append({
            "file_id": file_id,
            "original_name": original_name,
            "upload_time": info.get("upload_time", ""),
            "script_type": info.get("script_type", ""),
            "brand": info.get("brand", ""),
            "device_model": info.get("device_model", ""),
        })

    files.sort(key=lambda x: x.get("upload_time", ""), reverse=True)
    return jsonify({"success": True, "files": files})


@upload_bp.route('/delete/<file_id>', methods=['DELETE'])
def delete_upload(file_id):
    """删除已上传的脚本（本地 + WebDAV）"""
    # 安全检查
    if '..' in file_id or '/' in file_id or '\\' in file_id:
        return jsonify({"success": False, "error": "无效的文件名"})

    local_path = os.path.join(UPLOAD_DIR, file_id)
    local_deleted = False
    remote_deleted = False

    # 删除本地文件
    if os.path.exists(local_path):
        try:
            os.remove(local_path)
            local_deleted = True
        except Exception as e:
            logger.error(f"删除本地文件失败: {e}")

    # 删除 WebDAV 远端文件
    remote_deleted = _openlist_delete(file_id)

    # 更新 metadata.json
    meta_path = os.path.join(UPLOAD_DIR, 'metadata.json')
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            metadata.pop(file_id, None)
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
        except:
            pass

    return jsonify({
        "success": True,
        "message": "已删除",
        "file_id": file_id,
        "local_deleted": local_deleted,
        "remote_deleted": remote_deleted,
    })


@upload_bp.route('/view/<file_id>', methods=['GET'])
def view_script(file_id):
    """查看已上传脚本的内容"""
    # 安全检查：防止路径遍历
    if '..' in file_id or '/' in file_id or '\\' in file_id:
        return jsonify({"success": False, "error": "无效的文件名"})

    local_path = os.path.join(UPLOAD_DIR, file_id)

    # 文件内容
    content = None

    # 先读本地
    if os.path.exists(local_path):
        try:
            with open(local_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(local_path, 'rb') as f:
                content = f.read().decode('utf-8', errors='replace')

    # 本地没有 → 从 WebDAV 多路径尝试拉取
    if content is None:
        import urllib.request, base64
        candidates = [
            WEBDAV_URL.rstrip('/') + '/' + file_id,
            WEBDAV_URL.rstrip('/') + '/BD/' + file_id,
            WEBDAV_PUBLIC_BASE_URL.rstrip('/') + '/' + file_id,
        ]
        last_err = ''
        for wd_url in candidates:
            try:
                req = urllib_request.Request(wd_url)
                if '/sd/' not in wd_url:
                    auth = base64.b64encode(f"{WEBDAV_USER}:{WEBDAV_PASS}".encode()).decode()
                    req.add_header('Authorization', f'Basic {auth}')
                with urllib_request.urlopen(req, timeout=UPLOAD_WEBDAV_TIMEOUT_SHORT) as resp:
                    raw = resp.read()
                    if raw:
                        try:
                            content = raw.decode('utf-8')
                        except:
                            content = raw.decode('utf-8', errors='replace')
                        break
            except Exception as e:
                last_err = str(e)
        if content is None:
            return jsonify({"success": False, "error": f"文件加载失败 (tried {len(candidates)} paths): {last_err}"})

    if content is None:
        return jsonify({"success": False, "error": "文件不存在"})

    # 限制返回大小
    max_chars = UPLOAD_PREVIEW_MAX_CHARS
    if len(content) > max_chars:
        content = content[:max_chars] + f"\n\n...（文件过大，仅显示前 {max_chars} 字符）"

    return jsonify({
        "success": True,
        "file_id": file_id,
        "content": content,
    })


# ============================================================
# WebDAV 工具函数
# ============================================================

def _webdav_auth_header():
    """生成 Basic Auth header"""
    auth = base64.b64encode(f"{WEBDAV_USER}:{WEBDAV_PASS}".encode()).decode()
    return f"Basic {auth}"


def _openlist_list_files():
    """
    WebDAV PROPFIND 列出 OpenList 目录中的文件名。
    返回 list[str]
    """
    url = WEBDAV_URL.rstrip('/') + '/'
    propfind_body = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<d:propfind xmlns:d="DAV:"><d:prop><d:displayname/></d:prop></d:propfind>'
    )
    req = urllib_request.Request(
        url, data=propfind_body.encode('utf-8'),
        method='PROPFIND',
        headers={
            'Authorization': _webdav_auth_header(),
            'Content-Type': 'application/xml; charset=utf-8',
            'Depth': '1',
        }
    )
    try:
        with urllib_request.urlopen(req, timeout=UPLOAD_WEBDAV_TIMEOUT_LONG) as resp:
            body = resp.read().decode('utf-8', errors='ignore')
        names = []
        for m in re.finditer(r'<d:href>(.*?)</d:href>', body):
            href = m.group(1).strip().rstrip('/')
            name = href.rsplit('/', 1)[-1] if '/' in href else href
            if name and name != '':
                names.append(name)
        return names
    except Exception as e:
        logger.error(f"PROPFIND 失败: {e}")
        return []


def _openlist_download(remote_name, local_path):
    """WebDAV GET 下载文件。返回 bool"""
    url = WEBDAV_URL.rstrip('/') + '/' + remote_name
    req = urllib_request.Request(
        url, method='GET',
        headers={'Authorization': _webdav_auth_header()}
    )
    try:
        with urllib_request.urlopen(req, timeout=UPLOAD_WEBDAV_TIMEOUT_LONG) as resp:
            content = resp.read()
        with open(local_path, 'wb') as f:
            f.write(content)
        return True
    except Exception as e:
        logger.error(f"下载 {remote_name} 失败: {e}")
        return False


def _openlist_rename(old_name, new_name):
    """WebDAV MOVE 重命名。返回 bool"""
    old_url = WEBDAV_URL.rstrip('/') + '/' + old_name
    new_url = WEBDAV_URL.rstrip('/') + '/' + new_name
    req = urllib_request.Request(
        old_url, method='MOVE',
        headers={
            'Authorization': _webdav_auth_header(),
            'Destination': new_url,
        }
    )
    try:
        with urllib_request.urlopen(req, timeout=UPLOAD_WEBDAV_TIMEOUT_LONG) as resp:
            return resp.status in (201, 204)
    except Exception as e:
        logger.error(f"MOVE {old_name} -> {new_name} 失败: {e}")
        return False


def _openlist_delete(remote_name):
    """WebDAV DELETE 删除文件。返回 bool"""
    url = WEBDAV_URL.rstrip('/') + '/' + remote_name
    req = urllib_request.Request(
        url, method='DELETE',
        headers={'Authorization': _webdav_auth_header()}
    )
    try:
        with urllib_request.urlopen(req, timeout=UPLOAD_WEBDAV_TIMEOUT_LONG) as resp:
            return resp.status in (200, 201, 204)
    except HTTPError as e:
        if e.code == 404:
            return True  # 文件已不存在也算成功
        logger.error(f"DELETE {remote_name} 失败: HTTP {e.code}")
        return False
    except Exception as e:
        logger.error(f"DELETE {remote_name} 异常: {e}")
        return False