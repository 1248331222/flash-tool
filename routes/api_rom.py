#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Skytree Flasher / routes/api_rom.py
"""ROM 管理路由 - 列表/删除/解压/镜像/脚本导入"""

import os
import shutil

from flask import Blueprint, request, jsonify

from config import ROM_DIR, PUBLIC_DIR, IMAGE_DIR, logger
from core.utils import api_err, api_ok, sanitize_path
from core.rom_handler import detect_rom_type, resolve_rom_folder_name, _read_and_parse_script
from core.extractor import start_extract_from_public

rom_bp = Blueprint('rom', __name__, url_prefix='/api/rom')


@rom_bp.route('/list')
def list_extracted_roms():
    """获取已解压的刷机包列表"""
    try:
        dirs = [d for d in os.listdir(ROM_DIR)
                if os.path.isdir(os.path.join(ROM_DIR, d))]
        # 为每个目录自动识别刷机包类型
        dir_list = []
        for d in sorted(dirs):
            full_path = os.path.join(ROM_DIR, d)
            rom_type = detect_rom_type(full_path)
            # 尝试用 hydra 分类器获取 class_id
            class_id = ""
            try:
                from core.hydra.bat_parser import classify as bat_classify
                from core.hydra.classifier import ScriptClassifier
                for fname in os.listdir(full_path):
                    if fname.endswith('.bat'):
                        with open(os.path.join(full_path, fname), 'rb') as f:
                            raw = f.read()
                        try:
                            txt = raw.decode('gbk')
                        except Exception:
                            txt = raw.decode('utf-8', errors='replace')
                        class_id = bat_classify(txt)
                        break
                    elif fname.endswith('.sh'):
                        with open(os.path.join(full_path, fname), 'rb') as f:
                            raw = f.read()
                        txt = raw.decode('utf-8', errors='replace')
                        classifier = ScriptClassifier()
                        match = classifier.classify(txt, script_type="sh")
                        class_id = match.class_id if match.matched else ""
                        break
            except Exception:
                pass
            dir_list.append({"name": d, "type": rom_type, "class_id": class_id})
        return jsonify({"success": True, "dirs": dir_list})
    except Exception as e:
        logger.error(f"获取ROM列表失败: {e}")
        return api_err(str(e))


@rom_bp.route('/delete', methods=['POST'])
def delete_extracted_rom():
    """删除已解压的刷机包"""
    data = request.get_json(silent=True) or {}
    rom_dir = data.get("rom_dir", "")

    # 批量删除（清空全部）
    if rom_dir == "__ALL__":
        try:
            if os.path.isdir(ROM_DIR):
                shutil.rmtree(ROM_DIR)
                os.makedirs(ROM_DIR, exist_ok=True)
            logger.info("已清空全部刷机包")
            return api_ok(msg="已清空全部刷机包")
        except Exception as e:
            logger.error(f"清空刷机包失败: {e}")
            return jsonify({"success": False, "error": str(e)})

    # 安全校验：拒绝空、当前目录、父目录及含路径分隔符的目录名
    if not rom_dir or rom_dir in ('.', '..') or '/' in rom_dir or '\\' in rom_dir:
        return api_err("非法目录名")

    target = os.path.join(ROM_DIR, rom_dir)

    if not os.path.isdir(target):
        return api_err("目录不存在")

    try:
        shutil.rmtree(target)
        logger.info(f"删除刷机包: {rom_dir}")
        return api_ok(msg="删除成功")
    except Exception as e:
        logger.error(f"删除刷机包失败: {e}")
        return jsonify({"success": False, "error": str(e)})


@rom_bp.route('/copy_extract', methods=['POST'])
def copy_and_extract_rom():
    """复制并解压刷机包"""
    data = request.get_json(silent=True) or {}
    rom_name = data.get("rom_name", "")

    if not rom_name:
        return jsonify({"success": False, "error": "文件名不能为空"})

    result = start_extract_from_public(rom_name)
    return jsonify(result)


@rom_bp.route('/images')
def list_rom_images():
    """获取刷机包内的镜像列表"""
    rom_name = request.args.get("rom_name", "")

    if not rom_name:
        return api_err("未指定刷机包")

    rom_folder = resolve_rom_folder_name(rom_name)
    target_dir = os.path.join(ROM_DIR, rom_folder)

    if not os.path.exists(target_dir):
        return jsonify({"success": False, "error": "刷机包未解压"})

    imgs = []
    for root, _, files in os.walk(target_dir):
        for f in files:
            if f.lower().endswith(".img"):
                rel = os.path.relpath(os.path.join(root, f), target_dir)
                imgs.append(rel)

    return jsonify({"success": True, "files": sorted(imgs)})


@rom_bp.route('/bats')
def list_rom_bats():
    """获取刷机包内的刷机脚本列表（bat/cmd/sh）"""
    rom_name = request.args.get("rom_name", "")

    if not rom_name:
        return jsonify({"success": False, "error": "未指定刷机包"})

    rom_folder = resolve_rom_folder_name(rom_name)
    target_dir = os.path.join(ROM_DIR, rom_folder)

    if not os.path.exists(target_dir):
        return jsonify({"success": False, "error": "刷机包未解压"})

    bat_files = []
    for root, _, files in os.walk(target_dir):
        for f in files:
            if f.lower().endswith(('.bat', '.cmd', '.sh')):
                rel = os.path.relpath(os.path.join(root, f), target_dir)
                bat_files.append(rel)

    return jsonify({"success": True, "files": sorted(bat_files)})


@rom_bp.route('/save_custom_script', methods=['POST'])
def save_custom_script():
    """v3.0.0: 保存用户手动输入的自定义 .sh 脚本并授权执行"""
    data = request.get_json(silent=True) or {}
    rom_name = data.get("rom_name")
    script_content = data.get("script_content", "")

    if not rom_name:
        return jsonify({"success": False, "error": "未指定 ROM 包名"})
    if not script_content or not script_content.strip():
        return jsonify({"success": False, "error": "脚本内容为空"})

    # 安全校验：过滤危险字符
    dangerous_chars = ['\x00']
    for ch in dangerous_chars:
        if ch in script_content:
            return jsonify({"success": False, "error": "脚本包含非法字符"})

    # 保存到 ROM 包目录下（P0: 使用 sanitize_path 校验 rom_name 防止路径穿越）
    try:
        rom_dir = sanitize_path(ROM_DIR, rom_name)
    except Exception as e:
        return jsonify({"success": False, "error": f"非法 ROM 名称: {e}"})
    if not os.path.isdir(rom_dir):
        os.makedirs(rom_dir, exist_ok=True)

    script_path = os.path.join(rom_dir, "custom_flash.sh")

    try:
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_content)
        # 授予执行权限
        os.chmod(script_path, 0o755)
        logger.info(f"自定义脚本已保存: {script_path}")
        return jsonify({"success": True, "script_path": script_path})
    except Exception as e:
        logger.error(f"保存自定义脚本失败: {e}")
        return jsonify({"success": False, "error": str(e)})


@rom_bp.route('/import_bat', methods=['POST'])
def import_bat_file():
    """导入并解析刷机脚本（bat/cmd/sh）"""
    data = request.get_json(silent=True) or {}
    rom_name = data.get("rom_name")
    bat_path = data.get("bat_path")

    if not rom_name or not bat_path:
        return api_err("参数不完整")

    rom_folder = resolve_rom_folder_name(rom_name)
    full = sanitize_path(os.path.join(ROM_DIR, rom_folder), bat_path)

    try:
        ok, result = _read_and_parse_script(full)
        if not ok:
            return jsonify({"success": False, "error": result})
        txt, steps, missing_files, hydra_result = result

        # 生成 Hydra 全量分析摘要（仅当 hydra_result 可用时）
        hydra_summary = hydra_result.display_summary if hydra_result else None
        parse_method = getattr(hydra_result, 'parse_method', '') if hydra_result else ''

        resp = {
            "success": True,
            "content": txt,
            "steps": steps,
            "step_count": len(steps),
            "missing_files": missing_files or [],
            "hydra_summary": hydra_summary,
            "parse_method": parse_method,
            "class_id": getattr(hydra_result, 'class_id', ''),
        }
        return jsonify(resp)
    except Exception as e:
        logger.error(f"导入BAT脚本失败: {e}")
        return jsonify({"success": False, "error": str(e)})


@rom_bp.route('/import_path', methods=['POST'])
def import_script_by_path():
    """按用户填写的路径导入刷机脚本（用于 WebUSB 模式手动解压后选择）"""
    data = request.get_json(silent=True) or {}
    script_path = data.get("script_path", "")
    if not script_path:
        return jsonify({"success": False, "error": "脚本路径不能为空"})
    if '\x00' in script_path or '..' in script_path:
        return jsonify({"success": False, "error": "非法脚本路径"})
    try:
        full = os.path.abspath(os.path.expanduser(script_path))
        allowed_roots = [
            os.path.abspath(PUBLIC_DIR),
            os.path.abspath(ROM_DIR),
            os.path.abspath(IMAGE_DIR),
            "/sdcard",
            "/storage/emulated/0",
        ]
        if not any(full == root or full.startswith(root + os.sep) for root in allowed_roots):
            return jsonify({"success": False, "error": "脚本路径不在允许目录内，请放到 123456 或已解压目录"})
        if not full.lower().endswith((".bat", ".cmd", ".sh")):
            return jsonify({"success": False, "error": "只支持 bat/cmd/sh 脚本"})

        ok, result = _read_and_parse_script(full)
        if not ok:
            return jsonify({"success": False, "error": result})
        txt, steps, missing_files, hydra_result = result

        hydra_summary = hydra_result.display_summary if hydra_result else None

        resp = {
            "success": True,
            "content": txt,
            "steps": steps,
            "step_count": len(steps),
            "base_dir": os.path.dirname(full),
            "missing_files": missing_files or [],
            "hydra_summary": hydra_summary,
            "parse_method": parse_method,
            "class_id": getattr(hydra_result, 'class_id', ''),
        }
        return jsonify(resp)
    except Exception as e:
        logger.error(f"导入脚本失败: {e}")
        return jsonify({"success": False, "error": str(e)})
