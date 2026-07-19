# Skytree Flasher / routes/api_fs.py
"""文件系统 API — 供前端文件管理器和解析器使用"""

import os, glob as globmod, shutil
from flask import Blueprint, request, jsonify

from config import PUBLIC_DIR, logger
from core.utils import sanitize_path

fs_bp = Blueprint('fs', __name__, url_prefix='/api/fs')

def _safe_path(user_path: str) -> str:
    """基于 PUBLIC_DIR 的安全路径"""
    return sanitize_path(PUBLIC_DIR, user_path)

def _is_safe_path(full_path: str) -> bool:
    """检查完整路径是否在 PUBLIC_DIR 内"""
    base = os.path.realpath(PUBLIC_DIR)
    full = os.path.realpath(full_path)
    return full == base or full.startswith(base + os.sep)

@fs_bp.route('/list', methods=['GET'])
def fs_list():
    """列出目录内容（PUBLIC_DIR 范围内），支持 pattern 过滤"""
    path = request.args.get('path', '') or ''
    pattern = request.args.get('pattern', '')
    try:
        safe = _safe_path(path)
        abs_dir = os.path.realpath(safe)
        if not os.path.isdir(safe):
            return jsonify({"success": False, "error": "不是目录"}), 400

        items = []
        if pattern:
            matched = globmod.glob(os.path.join(safe, pattern))
            for f in matched:
                if os.path.isfile(f):
                    items.append({
                        "name": os.path.basename(f),
                        "path": os.path.relpath(f, PUBLIC_DIR),
                        "abs_path": os.path.realpath(f),
                        "type": "file",
                        "size": os.path.getsize(f),
                    })
        else:
            for entry in sorted(os.scandir(safe), key=lambda e: (not e.is_dir(), e.name.lower())):
                items.append({
                    "name": entry.name,
                    "path": os.path.relpath(entry.path, PUBLIC_DIR),
                    "abs_path": os.path.realpath(entry.path),
                    "type": "dir" if entry.is_dir() else "file",
                    "size": entry.stat().st_size if entry.is_file() else 0,
                })
        return jsonify({"success": True, "path": os.path.relpath(safe, PUBLIC_DIR), "abs_path": abs_dir, "items": items})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 403


@fs_bp.route('/browse', methods=['GET'])
def fs_browse():
    """浏览整个文件系统（文件管理器专用，使用绝对路径）"""
    raw_path = request.args.get('path', '/')
    try:
        # 规范化路径
        decoded = raw_path
        if '%' in raw_path:
            from urllib.parse import unquote
            decoded = unquote(raw_path)

        if not decoded or decoded == '/':
            # 根目录：返回常见挂载点
            roots = []
            for r in ['/', '/sdcard', '/storage', '/data']:
                if os.path.isdir(r):
                    roots.append({
                        "name": r,
                        "abs_path": r,
                        "type": "dir",
                        "size": 0,
                    })
            return jsonify({"success": True, "abs_path": "/", "items": roots})

        # 规范化
        target = os.path.normpath(decoded)
        if not os.path.isabs(target):
            target = '/' + target

        if not os.path.isdir(target):
            return jsonify({"success": False, "error": "不是目录: " + target}), 400

        items = []
        try:
            for entry in sorted(os.scandir(target), key=lambda e: (not e.is_dir(), e.name.lower())):
                try:
                    items.append({
                        "name": entry.name,
                        "abs_path": os.path.realpath(entry.path),
                        "type": "dir" if entry.is_dir() else "file",
                        "size": entry.stat().st_size if entry.is_file() else 0,
                    })
                except (PermissionError, OSError):
                    continue
        except PermissionError:
            return jsonify({"success": False, "error": "权限不足: " + target}), 403

        return jsonify({"success": True, "abs_path": target, "items": items})
    except Exception as e:
        logger.error(f"fs_browse 失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@fs_bp.route('/exists', methods=['GET'])
def fs_exists():
    path = request.args.get('path', '')
    try:
        safe = _safe_path(path)
        exists = os.path.exists(safe)
        is_dir = os.path.isdir(safe) if exists else False
        return jsonify({"success": True, "exists": exists, "is_dir": is_dir})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 403

@fs_bp.route('/glob', methods=['POST'])
def fs_glob():
    """展开通配符，返回匹配的文件绝对路径列表"""
    data = request.get_json(silent=True) or {}
    pattern = data.get('pattern', '')
    base_path = data.get('base_path', '/')
    try:
        safe_base = _safe_path(base_path)
        # 确保 pattern 不会逃逸
        safe_pattern = os.path.join(safe_base, pattern)
        matched = globmod.glob(safe_pattern)
        # 过滤掉不在安全范围内的
        result = [os.path.realpath(f) for f in matched if os.path.isfile(f) and _is_safe_path(f)]
        return jsonify({"success": True, "files": result, "count": len(result)})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 403
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@fs_bp.route('/read', methods=['GET'])
def fs_read():
    """读取文件内容（文本或二进制 base64）"""
    path = request.args.get('path', '')
    encoding = request.args.get('encoding', 'auto')
    try:
        safe = _safe_path(path)
        if not os.path.isfile(safe):
            return jsonify({"success": False, "error": "文件不存在"}), 404

        abs_path = os.path.realpath(safe)
        size = os.path.getsize(safe)
        if encoding == 'base64' or size > 2 * 1024 * 1024:
            import base64
            with open(safe, 'rb') as f:
                content = base64.b64encode(f.read()).decode('ascii')
            return jsonify({"success": True, "encoding": "base64", "size": size, "content": content, "abs_path": abs_path})

        # 自动检测编码
        raw = None
        for enc in ['utf-8', 'gbk', 'gb2312']:
            try:
                with open(safe, 'r', encoding=enc) as f:
                    raw = f.read()
                return jsonify({"success": True, "encoding": enc, "size": size, "content": raw, "abs_path": abs_path})
            except (UnicodeDecodeError, ValueError):
                continue
        # 都失败则返回 base64
        import base64
        with open(safe, 'rb') as f:
            content = base64.b64encode(f.read()).decode('ascii')
        return jsonify({"success": True, "encoding": "base64", "size": size, "content": content, "abs_path": abs_path})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 403
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@fs_bp.route('/read-abs', methods=['GET'])
def fs_read_abs():
    """通过绝对路径读取文件内容（文件管理器专用）"""
    raw_path = request.args.get('path', '')
    encoding = request.args.get('encoding', 'auto')
    try:
        from urllib.parse import unquote
        decoded = raw_path
        if '%' in raw_path:
            decoded = unquote(raw_path)

        if not decoded or not os.path.isabs(decoded):
            return jsonify({"success": False, "error": "需要绝对路径"}), 400

        target = os.path.normpath(decoded)
        if not os.path.isfile(target):
            return jsonify({"success": False, "error": "文件不存在: " + target}), 404

        abs_path = os.path.realpath(target)
        size = os.path.getsize(target)

        if encoding == 'base64' or size > 2 * 1024 * 1024:
            import base64
            with open(target, 'rb') as f:
                content = base64.b64encode(f.read()).decode('ascii')
            return jsonify({"success": True, "encoding": "base64", "size": size, "content": content, "abs_path": abs_path})

        for enc in ['utf-8', 'gbk', 'gb2312']:
            try:
                with open(target, 'r', encoding=enc) as f:
                    raw = f.read()
                return jsonify({"success": True, "encoding": enc, "size": size, "content": raw, "abs_path": abs_path})
            except (UnicodeDecodeError, ValueError):
                continue

        import base64
        with open(target, 'rb') as f:
            content = base64.b64encode(f.read()).decode('ascii')
        return jsonify({"success": True, "encoding": "base64", "size": size, "content": content, "abs_path": abs_path})
    except PermissionError:
        return jsonify({"success": False, "error": "权限不足"}), 403
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@fs_bp.route('/write-abs', methods=['POST'])
def fs_write_abs():
    """通过绝对路径写入文件内容（文件管理器专用，用于导出/另存为）"""
    from urllib.parse import unquote
    data = request.get_json(silent=True) or {}
    raw_path = data.get('path', '')
    content = data.get('content', '')
    encoding = data.get('encoding', 'utf-8')

    try:
        decoded = raw_path
        if '%' in raw_path:
            decoded = unquote(raw_path)
        if not decoded or not os.path.isabs(decoded):
            return jsonify({"success": False, "error": "需要绝对路径"}), 400

        target = os.path.normpath(decoded)
        target_dir = os.path.dirname(target)
        if target_dir and not os.path.isdir(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        if encoding == 'base64':
            import base64
            with open(target, 'wb') as f:
                f.write(base64.b64decode(content))
        else:
            with open(target, 'w', encoding='utf-8') as f:
                f.write(content)

        return jsonify({"success": True, "path": os.path.realpath(target)})
    except PermissionError:
        return jsonify({"success": False, "error": "权限不足"}), 403
    except Exception as e:
        logger.error(f"fs_write_abs 失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@fs_bp.route('/mkdir', methods=['POST'])
def fs_mkdir():
    data = request.get_json(silent=True) or {}
    path = data.get('path', '')
    try:
        safe = _safe_path(path)
        os.makedirs(safe, exist_ok=True)
        return jsonify({"success": True, "path": os.path.relpath(safe, PUBLIC_DIR)})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 403
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@fs_bp.route('/delete', methods=['POST'])
def fs_delete():
    data = request.get_json(silent=True) or {}
    path = data.get('path', '')
    try:
        safe = _safe_path(path)
        if not os.path.exists(safe):
            return jsonify({"success": False, "error": "不存在"}), 404
        if os.path.isdir(safe):
            shutil.rmtree(safe)
        else:
            os.remove(safe)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 403
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@fs_bp.route('/copy', methods=['POST'])
def fs_copy():
    data = request.get_json(silent=True) or {}
    src = data.get('src', '')
    dst = data.get('dst', '')
    try:
        safe_src = _safe_path(src)
        safe_dst = _safe_path(dst)
        if os.path.isdir(safe_src):
            shutil.copytree(safe_src, safe_dst)
        else:
            shutil.copy2(safe_src, safe_dst)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 403
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@fs_bp.route('/move', methods=['POST'])
def fs_move():
    data = request.get_json(silent=True) or {}
    src = data.get('src', '')
    dst = data.get('dst', '')
    try:
        safe_src = _safe_path(src)
        safe_dst = _safe_path(dst)
        shutil.move(safe_src, safe_dst)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 403
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500