#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Skytree Flasher / routes/api_images.py
"""本地镜像路由 - 列表/删除/同步"""

import os
import shutil

from flask import Blueprint, request, jsonify

from config import IMAGE_DIR, PUBLIC_IMAGE_DIR, logger
from core.utils import api_ok, sanitize_path

images_bp = Blueprint('images', __name__, url_prefix='/api/images')


@images_bp.route('')
def get_image_list():
    """获取手机目录镜像列表"""
    try:
        imgs = [f for f in os.listdir(PUBLIC_IMAGE_DIR)
                if f.lower().endswith(".img")]
        return jsonify({"success": True, "files": sorted(imgs)})
    except FileNotFoundError:
        return jsonify({"success": True, "files": []})
    except PermissionError:
        return jsonify({"success": False, "error": "存储权限不足，请执行 termux-setup-storage"})
    except Exception as e:
        logger.error(f"获取镜像列表失败: {e}")
        return jsonify({"success": False, "error": str(e)})


@images_bp.route('/delete', methods=['POST'])
def delete_project_image():
    """删除手机目录中的镜像"""
    data = request.get_json(silent=True) or {}
    fn = data.get("filename")

    if not fn:
        return jsonify({"success": False, "error": "文件名不能为空"})

    # 使用 sanitize_path 校验文件名，防止路径穿越
    try:
        fp = sanitize_path(PUBLIC_IMAGE_DIR, fn)
    except Exception as e:
        return jsonify({"success": False, "error": f"非法文件名: {e}"})

    if os.path.exists(fp):
        try:
            os.remove(fp)
            logger.info(f"删除镜像: {fn}")
            return api_ok(msg="已删除")
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})

    return api_ok(msg="文件不存在，已忽略")


@images_bp.route('/sync', methods=['POST'])
def sync_public_images():
    """同步公共目录镜像到本地"""
    count = 0
    errors = []

    try:
        for f in os.listdir(PUBLIC_IMAGE_DIR):
            if f.lower().endswith(".img"):
                src = os.path.join(PUBLIC_IMAGE_DIR, f)
                dst = os.path.join(IMAGE_DIR, f)

                try:
                    shutil.copy2(src, dst)
                    count += 1
                except Exception as e:
                    errors.append(f"{f}: {str(e)}")

        logger.info(f"同步镜像: {count} 个")

        return jsonify({
            "success": True,
            "count": count,
            "msg": f"同步{count}个镜像",
            "errors": errors
        })

    except Exception as e:
        logger.error(f"同步镜像失败: {e}")
        return jsonify({"success": False, "error": str(e)})