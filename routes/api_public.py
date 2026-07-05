#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Skytree Flasher / routes/api_public.py
"""公共目录路由 - 刷机包与镜像列表"""

import os

from flask import Blueprint, jsonify

from config import PUBLIC_DIR, PUBLIC_IMAGE_DIR, SUPPORTED_ROM_SUFFIXES, logger

public_bp = Blueprint('public', __name__, url_prefix='/api/public')


@public_bp.route('/roms')
def list_public_roms():
    """获取公共目录的刷机包列表"""
    try:
        files = [f for f in os.listdir(PUBLIC_DIR)
                 if f.lower().endswith(SUPPORTED_ROM_SUFFIXES)]
        return jsonify({"success": True, "files": sorted(files)})
    except PermissionError:
        return jsonify({
            "success": False,
            "error": "存储权限不足，请执行termux-setup-storage"
        })
    except Exception as e:
        logger.error(f"获取公共ROM列表失败: {e}")
        return jsonify({"success": False, "error": str(e)})


@public_bp.route('/images')
def list_public_images():
    """获取公共目录的镜像列表"""
    try:
        imgs = [f for f in os.listdir(PUBLIC_IMAGE_DIR)
                if f.lower().endswith(".img")]
        return jsonify({"success": True, "files": sorted(imgs)})
    except Exception as e:
        logger.error(f"获取公共镜像列表失败: {e}")
        return jsonify({"success": False, "error": str(e)})