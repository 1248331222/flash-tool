# flash_tool/routes/api_upload.py
# 脚本上传模块 - WebDAV 上传到 OpenList / Hydra 预解析
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


def _hydra_preview(content: str, filename: str) -> dict:
    """调用 Hydra 引擎预解析脚本"""
    try:
        # 判断脚本类型
        ext = os.path.splitext(filename)[1].lower()
        script_type = 'sh' if ext in ('.sh',) else 'bat'

        engine = HydraEngine()
        result = engine.parse(content, script_type=script_type, script_path=filename)
        if result is None:
            return {"is_simple": False, "step_count": 0, "parse_errors": ["解析返回空"], "script_type": "unknown"}

        return {
            "is_simple": result.is_simple,
            "step_count": result.total_steps or len(result.steps),
            "parse_errors": result.warnings,
            "script_type": result.script_type,
        }
    except Exception as e:
        logger.warning(f"Hydra 预解析失败: {e}")
        return {
            "is_simple": False,
            "step_count": 0,
            "parse_errors": [str(e)],
            "script_type": "unknown",
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

    # 7. Hydra 预解析
    hydra_result = _hydra_preview(content, original_name) if do_preview else {}

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
    
    hydra_result = _hydra_preview(content, filename)
    
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
        files.append({
            "file_id": file_id,
            "original_name": info.get("original_name", ""),
            "upload_time": info.get("upload_time", ""),
            "script_type": info.get("script_type", ""),
            "brand": info.get("brand", ""),
            "device_model": info.get("device_model", ""),
            "step_count": info.get("hydra_result", {}).get("step_count", 0),
        })
    
    files.sort(key=lambda x: x.get("upload_time", ""), reverse=True)
    return jsonify({"success": True, "files": files})