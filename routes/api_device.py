#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Skytree Flasher / routes/api_device.py
"""设备路由 - 设备检测/ADB/Fastboot/环境检查"""

import os
import shutil

from flask import Blueprint, request, jsonify

from config import TERMUX_USB_CMD, PUBLIC_DIR, REBOOT_TIMEOUT, FASTBOOT_DEFAULT_TIMEOUT
from core.device import (
    check_devices,
    select_adb_device,
    select_fastboot_device,
    get_combined_device_state,
    check_adb_devices,
    run_adb_command,
    get_bl_unlock_info,
    get_device_slot,
    get_device_info,
    run_fastboot_command,
)

device_bp = Blueprint('device', __name__, url_prefix='/api')


@device_bp.route('/device')
def check_device_route():
    """检查 Fastboot 设备"""
    result = check_devices()
    return jsonify({
        "connected": result["connected"],
        "count": result["count"],
        "list": result["list"],
        "devices": result.get("devices", []),
        "selected": result.get("selected", "")
    })


@device_bp.route('/device/select', methods=['POST'])
def select_device_route():
    """选择设备"""
    data = request.get_json(silent=True) or {}
    serial = data.get("serial", "")
    mode = data.get("mode", "fastboot")
    if mode == "adb":
        return jsonify(select_adb_device(serial))
    return jsonify(select_fastboot_device(serial))


@device_bp.route('/device/state')
def device_state_route():
    """同时检测 ADB/Fastboot 状态"""
    return jsonify(get_combined_device_state())


@device_bp.route('/adb')
def adb_devices_route():
    """检查 ADB 设备"""
    return jsonify(check_adb_devices())


@device_bp.route('/adb', methods=['POST'])
def exec_adb():
    """执行 ADB 命令"""
    data = request.get_json(silent=True) or {}
    args = data.get("args", [])
    if not args:
        return jsonify({"success": False, "error": "未提供 ADB 命令参数"})
    result = run_adb_command(args)
    return jsonify({
        "success": result["success"],
        "output": result.get("output", ""),
        "error": result.get("error", ""),
        "diagnosis": result.get("diagnosis", "")
    })


@device_bp.route('/device/bl')
def get_bl_unlock_info_route():
    """兼容查询 BL 锁状态"""
    return jsonify(get_bl_unlock_info())


@device_bp.route('/device/slot')
def get_device_slot_route():
    """获取设备槽位"""
    result = get_device_slot()
    return jsonify(result)


@device_bp.route('/device/info')
def get_device_info_route():
    """获取设备详细信息"""
    result = get_device_info()
    return jsonify(result)


@device_bp.route('/fastboot', methods=['POST'])
def exec_fastboot():
    """执行自定义 fastboot 命令"""
    data = request.get_json(silent=True) or {}
    args = data.get("args", [])

    if not args:
        return jsonify({"success": False, "error": "未提供命令参数"})

    timeout = data.get("timeout")
    if timeout is None and args and args[0] == "reboot":
        timeout = REBOOT_TIMEOUT
    try:
        timeout = int(timeout) if timeout is not None else FASTBOOT_DEFAULT_TIMEOUT
    except Exception:
        timeout = FASTBOOT_DEFAULT_TIMEOUT
    result = run_fastboot_command(args, timeout=timeout)

    return jsonify({
        "success": result.get("success", False),
        "output": result.get("output", ""),
        "error": result.get("error", ""),
        "diagnosis": result.get("diagnosis", ""),
        "combined": result.get("combined", ""),
        "category": result.get("category", ""),
        "recoverable": result.get("recoverable", False),
        "message": result.get("message", "")
    })


@device_bp.route('/env/check')
def env_check():
    """环境检查"""
    deps = {
        "fastboot": shutil.which("fastboot") is not None,
        "adb": shutil.which("adb") is not None,
        "7z": shutil.which("7z") is not None,
        "unrar": shutil.which("unrar") is not None,
        "termux_api": shutil.which(TERMUX_USB_CMD) is not None,
    }
    deps["all_ok"] = all(deps.values())

    return jsonify({
        "success": True,
        "dependencies": deps,
        "storage_permission": os.path.exists(PUBLIC_DIR),
        "fastboot_available": shutil.which("fastboot") is not None
    })


@device_bp.route('/health')
def health_check():
    """健康检查"""
    return jsonify({
        "status": "ok",
        "storage_permission": os.path.exists(PUBLIC_DIR),
        "fastboot_available": shutil.which("fastboot") is not None
    })