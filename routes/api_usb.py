#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# flash_tool/routes/api_usb.py
"""USB 设备路由 - 列表与授权"""

from flask import Blueprint, request, jsonify

from core.device import check_usb_devices, grant_usb_permission

usb_bp = Blueprint('usb', __name__, url_prefix='/api/usb')


@usb_bp.route('/list')
def usb_list_route():
    """获取 USB 设备列表"""
    result = check_usb_devices()
    return jsonify(result)


@usb_bp.route('/grant', methods=['POST'])
def usb_grant_route():
    """授权 USB 设备"""
    data = request.get_json(silent=True) or {}
    device = data.get("device", "")

    result = grant_usb_permission(device)
    return jsonify(result)
