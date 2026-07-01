# flash_tool/routes/api_upload.py
# 脚本上传模块 - WebDAV 上传到 OpenList / 天树引擎预解析
# 纯标准库实现，无额外依赖

import os, re, json, time, hashlib, random, base64
from urllib import request as urllib_request
from urllib.error import URLError
from flask import Blueprint, request, jsonify, current_app

from config import WEBDAV_URL, WEBDAV_USER, WEBDAV_PASS, UPLOAD_DIR, logger
from core.hydra import HydraEngine

upload_bp = Blueprint('upload', __name__, url_prefix='/api/script')

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


def _preview_script(content: str, filename: str) -> dict:
    """调用天树引擎预解析脚本"""
    try:
        # 判断脚本类型
        ext = os.path.splitext(filename)[1].lower()
        script_type = 'sh' if ext in ('.sh',) else 'bat'

        engine = HydraEngine()
        result = engine.parse(content, script_type=script_type, script_path=filename)
        if result is None:
            return {"is_simple": False, "step_count": 0, "parse_errors": ["解析返回空"],
                    "script_type": "unknown", "engine_status": "unsupported"}

        # engine_status: "supported" / "unsupported" / "partial"
        if result.total_steps > 0 and not result.warnings:
            engine_status = "supported"
        elif result.total_steps > 0 and result.warnings:
            engine_status = "partial"
        else:
            engine_status = "unsupported"

        return {
            "is_simple": result.is_simple,
            "step_count": result.total_steps or len(result.steps),
            "parse_errors": result.warnings,
            "script_type": result.script_type,
            "engine_status": engine_status,
        }
    except Exception as e:
        logger.warning(f"天树引擎预解析失败: {e}")
        return {
            "is_simple": False,
            "step_count": 0,
            "parse_errors": [str(e)],
            "script_type": "unknown",
            "engine_status": "unsupported",
        }


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
        with urllib_request.urlopen(req, timeout=30) as resp:
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
    do_preview = request.form.get('hydra_preview', 'true').lower() == 'true'

    # 7. 天树引擎预解析
    hydra_result = _preview_script(content, original_name) if do_preview else {}

    # 8. 保存本地 + 上传 OpenList
    safe_name = _sanitize_filename(original_name)
    local_path = os.path.join(UPLOAD_DIR, safe_name)
    
    # 确保本地目录存在
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    # 写本地文件
    with open(local_path, 'w', encoding='utf-8') as f:
        f.write(content)

    # 上传到 OpenList
    upload_ok = _upload_via_webdav(local_path, safe_name)

    # 9. 更新元数据
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
        "hydra_result": hydra_result,
        "uploaded_to_openlist": upload_ok,
        "expire_time": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() + 86400 * 10)),
    }
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    return jsonify({
        "success": True,
        "file_id": safe_name,
        "message": "上传成功" + ("，已同步到样本库" if upload_ok else "（本地保存）"),
        "hydra_result": hydra_result,
        "uploaded_to_openlist": upload_ok,
    })


@upload_bp.route('/preview', methods=['POST'])
def preview_script():
    """预览脚本内容（不保存）"""
    data = request.get_json(silent=True) or {}
    content = data.get('content', '')
    filename = data.get('filename', 'script.bat')
    
    if not content:
        return jsonify({"success": False, "error": "内容为空"})
    
    hydra_result = _preview_script(content, filename)
    
    return jsonify({
        "success": True,
        "preview_lines": content.split('\n')[:20],
        "total_lines": len(content.split('\n')),
        "hydra_result": hydra_result,
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
        hydra_result = info.get("hydra_result", {})
        original_name = info.get("original_name", file_id)
        # 优先按文件名前缀判定，其次取元数据
        prefix_status = _filename_engine_status(file_id)
        if prefix_status != 'unknown':
            engine_status = prefix_status
        else:
            engine_status = hydra_result.get("engine_status", "unknown")
        files.append({
            "file_id": file_id,
            "original_name": original_name,
            "upload_time": info.get("upload_time", ""),
            "script_type": info.get("script_type", ""),
            "brand": info.get("brand", ""),
            "device_model": info.get("device_model", ""),
            "step_count": hydra_result.get("step_count", 0),
            "engine_status": engine_status,
        })
    
    files.sort(key=lambda x: x.get("upload_time", ""), reverse=True)
    return jsonify({"success": True, "files": files})


@upload_bp.route('/view/<file_id>', methods=['GET'])
def view_script(file_id):
    """查看已上传脚本的内容"""
    # 安全检查：防止路径遍历
    if '..' in file_id or '/' in file_id or '\\' in file_id:
        return jsonify({"success": False, "error": "无效的文件名"})
    
    local_path = os.path.join(UPLOAD_DIR, file_id)
    if not os.path.exists(local_path):
        return jsonify({"success": False, "error": "文件不存在"})
    
    # 读取元数据
    meta_path = os.path.join(UPLOAD_DIR, 'metadata.json')
    meta_info = {}
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                all_meta = json.load(f)
                meta_info = all_meta.get(file_id, {})
        except:
            pass
    
    # 读取文件内容（限制 1MB）
    try:
        with open(local_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(local_path, 'rb') as f:
            raw = f.read()
        content = raw.decode('utf-8', errors='replace')
    
    # 限制返回大小
    max_chars = 100 * 1024  # 100KB
    if len(content) > max_chars:
        content = content[:max_chars] + f"\n\n...（文件过大，仅显示前 {max_chars} 字符）"
    
    return jsonify({
        "success": True,
        "file_id": file_id,
        "original_name": meta_info.get("original_name", ""),
        "upload_time": meta_info.get("upload_time", ""),
        "brand": meta_info.get("brand", ""),
        "device_model": meta_info.get("device_model", ""),
        "step_count": meta_info.get("hydra_result", {}).get("step_count", 0),
        "content": content,
    })


# ============================================================
# WebDAV 工具函数（标注闭环用）
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
        with urllib_request.urlopen(req, timeout=30) as resp:
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
        with urllib_request.urlopen(req, timeout=30) as resp:
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
        with urllib_request.urlopen(req, timeout=30) as resp:
            return resp.status in (201, 204)
    except Exception as e:
        logger.error(f"MOVE {old_name} -> {new_name} 失败: {e}")
        return False


def _label_log_path():
    return os.path.join(UPLOAD_DIR, 'label_log.json')


def _append_label_log(entry: dict):
    log_path = _label_log_path()
    logs = []
    if os.path.exists(log_path):
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        except:
            logs = []
    logs.append(entry)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


def _filename_engine_status(name: str) -> str:
    """从文件名前缀判定引擎状态：supported / unsupported / unknown"""
    if name.startswith('yes_'):
        return 'supported'
    elif name.startswith('no_'):
        return 'unsupported'
    return 'unknown'


def _add_prefix(name: str, prefix: str) -> str:
    """加前缀，避免重复。prefix: yes_ 或 no_"""
    if name.startswith('yes_') or name.startswith('no_'):
        return name
    return prefix + name


# ============================================================
# 标注路由
# ============================================================

@upload_bp.route('/label', methods=['POST'])
def label_samples():
    """
    触发全量标注：
    1. 从 OpenList PROPFIND 列出所有无 yes_/no_ 前缀的脚本
    2. 逐文件下载 → 天树引擎解析 → 判定 → MOVE 重命名
    """
    temp_dir = os.path.join(UPLOAD_DIR, '_label_tmp')
    os.makedirs(temp_dir, exist_ok=True)

    # 1. 拉取列表
    all_names = _openlist_list_files()
    logger.info(f"PROPFIND 返回 {len(all_names)} 个文件")

    # 2. 筛选待判定（无 yes_/no_ 前缀、扩展名符合）
    TARGET_EXTS = {'.bat', '.cmd', '.sh', '.txt'}
    pending = []
    for name in all_names:
        ext = os.path.splitext(name)[1].lower()
        if ext not in TARGET_EXTS:
            continue
        if name.startswith('yes_') or name.startswith('no_'):
            continue
        pending.append(name)

    logger.info(f"待判定: {len(pending)} 个文件")

    # 3. 逐文件下载 → 解析 → 改名
    results = []
    for remote_name in pending:
        local_path = os.path.join(temp_dir, remote_name)
        if not _openlist_download(remote_name, local_path):
            results.append({"name": remote_name, "status": "download_failed"})
            continue

        # 读取内容
        try:
            with open(local_path, 'rb') as f:
                raw = f.read()
            content = raw.decode('utf-8', errors='ignore')
        except Exception as e:
            results.append({"name": remote_name, "status": "read_failed", "error": str(e)})
            continue

        # 天树引擎解析
        hydra = _preview_script(content, remote_name)
        total_steps = hydra.get("step_count", 0)
        prefix = "yes_" if total_steps > 0 else "no_"
        new_name = _add_prefix(remote_name, prefix)

        # MOVE 重命名
        if _openlist_rename(remote_name, new_name):
            _append_label_log({
                "time": time.strftime('%Y-%m-%d %H:%M:%S'),
                "old_name": remote_name,
                "new_name": new_name,
                "step_count": total_steps,
                "result": prefix.replace('_', ''),
            })
            results.append({
                "name": remote_name, "new_name": new_name,
                "step_count": total_steps, "status": "ok",
            })
        else:
            results.append({"name": remote_name, "status": "rename_failed"})

        # 清理临时文件
        try:
            os.remove(local_path)
        except:
            pass

    # 统计
    ok = sum(1 for r in results if r.get("status") == "ok")
    fail = len(results) - ok

    return jsonify({
        "success": True,
        "message": f"标注完成：{ok} 成功, {fail} 失败 (共 {len(results)} 个)",
        "total": len(results),
        "ok": ok,
        "fail": fail,
        "details": results,
    })


@upload_bp.route('/relabel', methods=['POST'])
def relabel_samples():
    """
    重新判定所有 no_ 前缀的文件（引擎升级后可能翻转）。
    流程同 label，但只处理 no_ 前缀。
    """
    temp_dir = os.path.join(UPLOAD_DIR, '_label_tmp')
    os.makedirs(temp_dir, exist_ok=True)

    all_names = _openlist_list_files()
    TARGET_EXTS = {'.bat', '.cmd', '.sh', '.txt'}

    pending = []
    for name in all_names:
        ext = os.path.splitext(name)[1].lower()
        if ext not in TARGET_EXTS:
            continue
        if not name.startswith('no_'):
            continue
        pending.append(name)

    logger.info(f"重新判定: {len(pending)} 个 no_ 文件")

    results = []
    flipped = 0
    for remote_name in pending:
        local_path = os.path.join(temp_dir, remote_name)
        if not _openlist_download(remote_name, local_path):
            results.append({"name": remote_name, "status": "download_failed"})
            continue

        try:
            with open(local_path, 'rb') as f:
                raw = f.read()
            content = raw.decode('utf-8', errors='ignore')
        except Exception as e:
            results.append({"name": remote_name, "status": "read_failed", "error": str(e)})
            continue

        hydra = _preview_script(content, remote_name)
        total_steps = hydra.get("step_count", 0)

        if total_steps > 0:
            # 翻转 no_ → yes_
            new_name = 'yes_' + remote_name[3:]  # 去掉 no_ 前缀
            if _openlist_rename(remote_name, new_name):
                flipped += 1
                _append_label_log({
                    "time": time.strftime('%Y-%m-%d %H:%M:%S'),
                    "old_name": remote_name,
                    "new_name": new_name,
                    "step_count": total_steps,
                    "result": "flipped",
                })
                results.append({
                    "name": remote_name, "new_name": new_name,
                    "step_count": total_steps, "status": "flipped",
                })
            else:
                results.append({"name": remote_name, "status": "rename_failed"})
        else:
            # 仍不支持，保持 no_
            results.append({
                "name": remote_name, "step_count": total_steps,
                "status": "unchanged",
            })

        try:
            os.remove(local_path)
        except:
            pass

    unchanged = sum(1 for r in results if r.get("status") == "unchanged")
    fail = sum(1 for r in results if r.get("status") in ("download_failed", "read_failed", "rename_failed"))

    return jsonify({
        "success": True,
        "message": f"重新判定完成：{flipped} 翻转, {unchanged} 保持, {fail} 失败",
        "total": len(results),
        "flipped": flipped,
        "unchanged": unchanged,
        "fail": fail,
        "details": results,
    })