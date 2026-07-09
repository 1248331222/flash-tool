#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Skytree Flasher / routes/api_flash.py
"""刷机核心路由 - 任务状态/刷写/预校验/镜像流"""

import os

from flask import Blueprint, request, jsonify, send_file

from config import PUBLIC_DIR, ROM_DIR, IMAGE_DIR
from core.utils import api_err, get_image_path, get_allowed_image_roots, is_path_under_allowed_roots
from core.extractor import get_task_status
from core.flasher import flash_partition, batch_precheck
from core.step_engine import generate_preview_commands, estimate_execution_time

flash_bp = Blueprint('flash', __name__, url_prefix='/api')


# 镜像路径安全校验已迁移至 core.utils，保持这里别名以兼容旧调用。
def _allowed_image_roots():
    """WebUSB 模式允许查找镜像的目录"""
    return get_allowed_image_roots()


def _safe_under_allowed(full: str) -> bool:
    """限制只能读取公共刷机目录/已解压目录中的文件"""
    return is_path_under_allowed_roots(full)


def _find_image_by_name(image_name: str):
    """按脚本中的相对路径或文件名递归查找镜像"""
    if not image_name or '\x00' in image_name or '..' in image_name:
        return None
    rel = image_name.replace("\\", "/").lstrip("/")
    base = os.path.basename(rel)
    if not base.lower().endswith(".img"):
        return None
    candidates = []
    for root in _allowed_image_roots():
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            # 避免扫描明显无关/隐藏的大目录
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in ("Android", "DCIM", "Pictures", "Movies", "Music")]
            for fn in filenames:
                if fn != base:
                    continue
                full = os.path.join(dirpath, fn)
                norm = full.replace("\\", "/")
                score = 0
                if norm.endswith("/" + rel):
                    score += 100
                if "/image/" in norm:
                    score += 20
                if root == os.path.abspath(PUBLIC_DIR):
                    score += 10
                candidates.append((score, full))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def _find_images_batch(image_names):
    """一次扫描匹配多个镜像，避免逐个递归导致导入脚本很慢"""
    wanted = {}
    for image_name in image_names:
        if not image_name or '\x00' in image_name or '..' in image_name:
            continue
        rel = image_name.replace("\\", "/").lstrip("/")
        base = os.path.basename(rel)
        if base.lower().endswith(".img"):
            wanted[image_name] = {"rel": rel, "base": base, "matches": []}
    if not wanted:
        return {}

    wanted_bases = {v["base"] for v in wanted.values()}
    for root in _allowed_image_roots():
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in ("Android", "DCIM", "Pictures", "Movies", "Music")]
            hit_names = wanted_bases.intersection(filenames)
            if not hit_names:
                continue
            for fn in hit_names:
                full = os.path.join(dirpath, fn)
                norm = full.replace("\\", "/")
                for original, meta in wanted.items():
                    if meta["base"] != fn:
                        continue
                    score = 0
                    if norm.endswith("/" + meta["rel"]):
                        score += 100
                    if "/image/" in norm:
                        score += 20
                    if root == os.path.abspath(PUBLIC_DIR):
                        score += 10
                    meta["matches"].append((score, full))

    result = {}
    for original, meta in wanted.items():
        if meta["matches"]:
            meta["matches"].sort(key=lambda x: x[0], reverse=True)
            result[original] = meta["matches"][0][1]
    return result


@flash_bp.route('/task/status')
def task_status():
    """查询任务状态"""
    tid = request.args.get("task_id", "")

    if not tid:
        return api_err("未提供任务ID")

    result = get_task_status(tid)
    return jsonify(result)


@flash_bp.route('/flash', methods=['POST'])
def flash_partition_route():
    """刷写分区"""
    data = request.get_json(silent=True) or {}

    partition = data.get("partition")
    image = data.get("image")
    extra = data.get("extra", "")
    source = data.get("source", "local")
    rom_name = data.get("rom_name", "")
    allow_dangerous = data.get("allow_dangerous", False)

    if not partition or not image:
        return jsonify({"success": False, "error": "参数不完整"})

    result = flash_partition(
        partition=partition,
        image_name=image,
        source=source,
        rom_name=rom_name,
        extra=extra,
        allow_dangerous=allow_dangerous
    )

    return jsonify(result)


@flash_bp.route('/batch/precheck', methods=['POST'])
def batch_precheck_route():
    """批量刷机预校验"""
    data = request.get_json(silent=True) or {}

    steps = data.get("steps", [])
    source = data.get("source", "local")
    rom_name = data.get("rom_name", "")

    if not steps:
        return jsonify({"success": False, "error": "未提供步骤列表"})

    result = batch_precheck(steps, source, rom_name)
    return jsonify(result)


@flash_bp.route('/batch/simulate', methods=['POST'])
def batch_simulate():
    """模拟批量刷机（不实际执行）"""

    data = request.get_json(silent=True) or {}
    steps = data.get("steps", [])

    if not steps:
        return jsonify({"success": False, "error": "未提供步骤列表"})

    commands = generate_preview_commands(steps)
    estimated_time = estimate_execution_time(steps)

    return jsonify({
        "success": True,
        "commands": commands,
        "estimated_time": estimated_time,
        "total_steps": len(steps)
    })


@flash_bp.route('/image/blob')
def image_blob():
    """为 WebUSB Fastboot 模式提供镜像文件流"""
    source = request.args.get("source", "local")
    image = request.args.get("image", "")
    rom_name = request.args.get("rom_name", "")
    if not image:
        return jsonify({"success": False, "error": "未指定镜像"}), 400
    try:
        image_path = get_image_path(source, image, rom_name)
        return send_file(image_path, as_attachment=False, mimetype="application/octet-stream")
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@flash_bp.route('/image/path_blob')
def image_path_blob():
    """按路径读取镜像，用于 WebUSB 模式手动解压后刷写"""
    image_path = request.args.get("path", "")
    if not image_path:
        return jsonify({"success": False, "error": "未指定镜像路径"}), 400
    if '\x00' in image_path or '..' in image_path:
        return jsonify({"success": False, "error": "非法镜像路径"}), 400
    try:
        full = os.path.abspath(os.path.expanduser(image_path))
        if not _safe_under_allowed(full):
            return jsonify({"success": False, "error": "镜像路径不在允许目录内，请放到 123456 或已解压目录"}), 400
        if not os.path.exists(full):
            return jsonify({"success": False, "error": "镜像不存在"}), 404
        if not full.lower().endswith(".img"):
            return jsonify({"success": False, "error": "只支持 .img 镜像"}), 400
        return send_file(full, as_attachment=False, mimetype="application/octet-stream")
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@flash_bp.route('/image/find_blob')
def image_find_blob():
    """递归查找并读取镜像，用于用户只选择脚本文件时的兜底匹配"""
    image = request.args.get("image", "")
    validate_only = request.args.get("validate", "0") == "1"
    found = _find_image_by_name(image)
    if not found:
        return jsonify({"success": False, "error": f"未找到镜像：{image}"}), 404
    if validate_only:
        return jsonify({"success": True, "path": found})
    return send_file(found, as_attachment=False, mimetype="application/octet-stream")


@flash_bp.route('/image/validate_batch', methods=['POST'])
def image_validate_batch():
    """批量验证脚本引用的镜像是否存在"""
    data = request.get_json(silent=True) or {}
    images = data.get("images", [])
    if not isinstance(images, list):
        return jsonify({"success": False, "error": "images 必须是列表"}), 400
    unique = []
    seen = set()
    for img in images:
        if isinstance(img, str) and img not in seen:
            unique.append(img)
            seen.add(img)
    found = _find_images_batch(unique)
    missing = [img for img in unique if img not in found]
    return jsonify({
        "success": len(missing) == 0,
        "found": found,
        "missing": missing,
        "total": len(unique),
        "found_count": len(found),
    })