# -*- coding: utf-8 -*-
# Skytree Flasher / core/updater.py
"""
core/updater.py — 版本检查与自更新
从单文件版提取，原 Flask 路由 api_update_check / api_update_do 的核心逻辑
改为普通函数 check_update() / do_update()，返回 dict（由路由层 jsonify）。

注意：原 do_update 下载单文件 app.py / index.html，模块化后项目以
flash_tool.zip 形式分发，config 提供 UPDATE_ZIP_URL，因此 do_update
适配为下载并解压 zip 包到 PROJECT_DIR。
"""

import os
import re

from config import (
    TOOL_VERSION,
    UPDATE_CHECK_URL,
    UPDATE_ZIP_URL,
    PROJECT_DIR,
    UPDATE_CHECK_TIMEOUT,
    UPDATE_DOWNLOAD_TIMEOUT,
    logger,
)


def check_update():
    """
    检查更新（从远程配置文件中提取 TOOL_VERSION 版本号进行比较）

    Returns:
        dict — success / local_version / remote_version / has_update（失败时含 error）
    """
    import urllib.request
    try:
        req = urllib.request.Request(UPDATE_CHECK_URL, method='GET')
        with urllib.request.urlopen(req, timeout=UPDATE_CHECK_TIMEOUT) as resp:
            content = resp.read().decode('utf-8', errors='ignore')
        # 从远程配置中提取 TOOL_VERSION = "x.x.x"
        m = re.search(r'TOOL_VERSION\s*=\s*["\'](\d+\.\d+\.\d+)["\']', content)
        if not m:
            return {
                "success": False,
                "error": "无法从远程配置中提取版本号",
                "local_version": TOOL_VERSION,
                "remote_version": "未知",
                "has_update": False
            }
        remote_version = m.group(1)
        # 简单版本号比较（防御性解析，异常时视为无更新）
        try:
            local_parts = [int(x) for x in TOOL_VERSION.split('.')]
            remote_parts = [int(x) for x in remote_version.split('.')]
            has_update = remote_parts > local_parts
        except (ValueError, TypeError):
            has_update = False
        return {
            "success": True,
            "local_version": TOOL_VERSION,
            "remote_version": remote_version,
            "has_update": has_update
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "local_version": TOOL_VERSION,
            "remote_version": "未知",
            "has_update": False
        }


def do_update():
    """
    执行更新：下载新版 flash_tool.zip 并解压替换当前项目目录

    Returns:
        dict — success / message / details（失败时含 error）
    """
    import urllib.request
    import zipfile
    import shutil
    try:
        results = []
        tmp_zip = os.path.join(PROJECT_DIR, '.update_tmp.zip')

        # --- 下载更新包 ---
        req = urllib.request.Request(UPDATE_ZIP_URL, method='GET')
        with urllib.request.urlopen(req, timeout=UPDATE_DOWNLOAD_TIMEOUT) as resp:
            new_content = resp.read()
        with open(tmp_zip, 'wb') as f:
            f.write(new_content)
        results.append('更新包下载成功')

        # --- 解压到项目目录 ---
        try:
            with zipfile.ZipFile(tmp_zip, 'r') as zf:
                zf.extractall(PROJECT_DIR)
            results.append('更新包解压成功')
        except Exception as e:
            raise Exception(f"更新包解压失败: {e}")

        # 清理临时文件
        try:
            os.remove(tmp_zip)
        except Exception:
            pass

        logger.info(f"已更新: {TOOL_VERSION} -> 新版本, {', '.join(results)}")
        return {
            "success": True,
            "message": "更新成功，请重启服务生效",
            "details": results
        }
    except Exception as e:
        # 清理可能残留的临时文件
        tmp_zip = os.path.join(PROJECT_DIR, '.update_tmp.zip')
        try:
            if os.path.exists(tmp_zip):
                os.remove(tmp_zip)
        except Exception:
            pass
        logger.error(f"更新失败: {e}")
        return {
            "success": False,
            "error": f"更新失败: {str(e)}"
        }