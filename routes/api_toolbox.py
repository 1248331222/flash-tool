#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Skytree Flasher / routes/api_toolbox.py
"""工具箱路由 - 重启/擦除/切槽/OEM"""

from flask import Blueprint, request, jsonify

from core.device import reboot_device, erase_partition, set_active_slot, oem_command

toolbox_bp = Blueprint('toolbox', __name__, url_prefix='/api')


@toolbox_bp.route('/reboot', methods=['POST'])
def reboot_route():
    """重启设备"""
    data = request.get_json(silent=True) or {}
    target = data.get("target", "")

    result = reboot_device(target)
    return jsonify({
        "success": result["success"],
        "msg": "重启指令已发送" if result["success"] else result["error"]
    })


@toolbox_bp.route('/erase', methods=['POST'])
def erase_route():
    """擦除分区"""
    data = request.get_json(silent=True) or {}
    partition = data.get("partition")

    if not partition:
        return jsonify({"success": False, "error": "未指定分区"})

    result = erase_partition(partition)
    return jsonify({
        "success": result["success"],
        "output": result["output"],
        "error": result["error"],
        "diagnosis": result["diagnosis"]
    })


@toolbox_bp.route('/set_slot', methods=['POST'])
def set_slot_route():
    """切换槽位"""
    data = request.get_json(silent=True) or {}
    slot = data.get("slot")

    if not slot:
        return jsonify({"success": False, "error": "未指定槽位"})

    result = set_active_slot(slot)
    return jsonify({
        "success": result["success"],
        "msg": f"已切换到{slot}槽" if result["success"] else result["error"]
    })


@toolbox_bp.route('/oem', methods=['POST'])
def oem_route():
    """执行 OEM 命令"""
    data = request.get_json(silent=True) or {}
    command = data.get("command")

    if not command:
        return jsonify({"success": False, "error": "未指定命令"})

    result = oem_command(command)
    return jsonify({
        "success": result["success"],
        "output": result["output"],
        "error": result["error"]
    })