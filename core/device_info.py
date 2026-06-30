# flash_tool/core/device_info.py
# -*- coding: utf-8 -*-
"""
core/device_info.py — 设备信息查询与操作（BL锁/槽位/重启/擦除/USB）
从 core/device.py 拆分而来，函数逻辑保持不变。

run_fastboot_command / get_fastboot_base_cmd / get_selected_fastboot_device /
classify_fastboot_result 来自 core.device（核心命令执行层）。
"""

import re
import subprocess

from config import (
    TERMUX_USB_CMD,
    BL_QUERY_TIMEOUT,
    DEVICE_INFO_TIMEOUT,
    USB_CHECK_TIMEOUT,
    USB_GRANT_TIMEOUT,
    logger,
)
from core.device import (
    run_fastboot_command,
    get_fastboot_base_cmd,
    get_selected_fastboot_device,
    classify_fastboot_result,
)


def get_bl_unlock_info() -> dict:
    """
    查询 BL 锁状态，兼容一加/通用 fastboot 命令。
    有些一加/新设备不支持 fastboot oem device-info，会返回 unknown command。
    """
    attempts = [
        {"name": "一加/旧设备 oem device-info", "args": ["oem", "device-info"]},
        {"name": "通用 getvar unlocked", "args": ["getvar", "unlocked"]},
        {"name": "通用 flashing get_unlock_ability", "args": ["flashing", "get_unlock_ability"]},
        {"name": "通用 getvar secure", "args": ["getvar", "secure"]},
    ]
    logs = []
    info = {}
    for item in attempts:
        res = run_fastboot_command(item["args"], timeout=BL_QUERY_TIMEOUT)
        combined = res.get("combined", "") or (res.get("output", "") + res.get("error", ""))
        logs.append({
            "name": item["name"],
            "args": item["args"],
            "success": res.get("success", False),
            "output": combined.strip(),
            "diagnosis": res.get("diagnosis", "")
        })

        unlocked = re.search(r'unlocked:\s*(yes|no|true|false|1|0)', combined, re.IGNORECASE)
        secure = re.search(r'secure:\s*(yes|no|true|false|1|0)', combined, re.IGNORECASE)
        ability = re.search(r'get_unlock_ability:\s*(\d+)', combined, re.IGNORECASE)
        device_unlocked = re.search(r'Device unlocked:\s*(true|false)', combined, re.IGNORECASE)

        if unlocked:
            info["unlocked"] = unlocked.group(1)
        if secure:
            info["secure"] = secure.group(1)
        if ability:
            info["unlock_ability"] = ability.group(1)
        if device_unlocked:
            info["device_unlocked"] = device_unlocked.group(1)

    def _truthy(v):
        return str(v).strip().lower() in ("yes", "true", "1", "unlocked")

    def _falsy(v):
        return str(v).strip().lower() in ("no", "false", "0", "locked")

    bl_unlocked = None
    if "unlocked" in info:
        bl_unlocked = _truthy(info["unlocked"])
    elif "device_unlocked" in info:
        bl_unlocked = _truthy(info["device_unlocked"])
    elif "secure" in info:
        # secure:no 通常表示非安全/已解锁，secure:yes 通常表示仍为安全锁定状态
        bl_unlocked = _falsy(info["secure"])

    if bl_unlocked is True:
        chinese_status = "Bootloader状态：已解锁。"
    elif bl_unlocked is False:
        chinese_status = "Bootloader状态：未解锁。"
    else:
        chinese_status = "Bootloader状态：未能明确判断。"

    ok = bool(info) or any(x["success"] for x in logs)
    return {
        "success": ok,
        "info": info,
        "bl_unlocked": bl_unlocked,
        "status_text": chinese_status,
        "attempts": logs,
        "analysis": (
            chinese_status + " 当前设备不支持 fastboot oem device-info，已自动尝试 getvar/flashing 通用查询。"
            if any("unknown command" in x["output"].lower() for x in logs)
            else chinese_status
        )
    }


def get_device_slot() -> dict:
    """
    获取设备当前槽位（AB分区）

    Returns:
        槽位信息字典
    """
    res = run_fastboot_command(["getvar", "current-slot"])

    output = res["combined"]
    match = re.search(r'current-slot:\s*(\w)', output, re.IGNORECASE)

    if match:
        slot = match.group(1).lower()
        return {
            "success": True,
            "slot": slot,
            "ab_device": True
        }
    else:
        return {
            "success": True,
            "slot": "",
            "ab_device": False
        }


def get_device_info() -> dict:
    """
    获取设备详细信息

    Returns:
        设备信息字典
    """
    info = {}

    def parse_getvar_value(var_name: str, text: str) -> str:
        """只从真正的 getvar 行提取值，过滤 fastboot 的 OKAY/FAILED/Finished 统计输出"""
        text = text or ""
        patterns = [
            rf'^\s*(?:\(bootloader\)\s*)?{re.escape(var_name)}\s*:\s*(.+?)\s*$',
            rf'^\s*{re.escape(var_name)}\s*=\s*(.+?)\s*$',
        ]
        for line in text.splitlines():
            clean = line.strip()
            low = clean.lower()
            if not clean or low.startswith(("finished.", "okay", "failed", "waiting for", "getvar:")):
                continue
            for pat in patterns:
                m = re.search(pat, clean, re.IGNORECASE)
                if m:
                    value = m.group(1).strip().strip("'\"")
                    vlow = value.lower()
                    if value and not vlow.startswith(("finished.", "okay", "failed")):
                        return value
        return ""

    # 获取各种信息
    vars_to_get = [
        ('product', 'product'),
        ('product-name', 'product_name'),
        ('variant', 'variant'),
        ('current-slot', 'current_slot'),
        ('serial-number', 'serial'),
        ('is-userspace', 'is_userspace'),
        ('version-bootloader', 'bootloader_version'),
        ('version', 'fastboot_version'),
        ('battery-voltage', 'battery'),
        ('battery-soc', 'battery_soc'),
    ]

    for var_name, key in vars_to_get:
        res = run_fastboot_command(["getvar", var_name], timeout=DEVICE_INFO_TIMEOUT)
        value = parse_getvar_value(var_name, res.get("combined", ""))
        if value:
            info[key] = value

    # 一些设备 product-name 不稳定或返回统计文本，展示时优先使用 product。
    bad_values = ("finished", "okay", "failed", "getvar")
    for k in list(info.keys()):
        if str(info[k]).strip().lower().startswith(bad_values):
            info.pop(k, None)
    if info.get("product"):
        info["product_display"] = info["product"]
    elif info.get("product_name"):
        info["product_display"] = info["product_name"]

    return {
        "success": True,
        "info": info
    }


def reboot_device(target: str = "") -> dict:
    """
    重启设备

    Args:
        target: 重启目标 (空=系统, recovery, bootloader)

    Returns:
        结果字典
    """
    if target:
        args = ["reboot", target]
    else:
        args = ["reboot"]

    return run_fastboot_command(args)


def erase_partition(partition: str) -> dict:
    """
    擦除分区

    Args:
        partition: 分区名

    Returns:
        结果字典
    """
    return run_fastboot_command(["erase", partition])


def set_active_slot(slot: str) -> dict:
    """
    设置活动槽位

    Args:
        slot: 槽位名 (a/b)

    Returns:
        结果字典
    """
    return run_fastboot_command(["set_active", slot])


def oem_command(command: str) -> dict:
    """
    执行 OEM 命令

    Args:
        command: OEM 命令 (如 unlock, lock, device-info)

    Returns:
        结果字典
    """
    return run_fastboot_command(["oem", command])


def check_usb_devices() -> dict:
    """
    检查 USB 设备列表（通过 termux-usb）

    Returns:
        USB 设备列表
    """
    try:
        res = subprocess.run(
            [TERMUX_USB_CMD, "-l"],
            capture_output=True,
            text=True,
            timeout=USB_CHECK_TIMEOUT
        )

        devices = [l.strip() for l in res.stdout.splitlines() if l.strip()]

        return {
            "success": True,
            "devices": devices,
            "count": len(devices)
        }

    except Exception as e:
        logger.error(f"检查USB设备失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "devices": []
        }


def grant_usb_permission(device: str = "") -> dict:
    """
    授权 USB 设备

    Args:
        device: 设备路径（可选，不提供则自动选择第一个）

    Returns:
        结果字典
    """
    try:
        if not device:
            # 自动获取第一个设备
            usb_res = check_usb_devices()
            if not usb_res["success"] or not usb_res["devices"]:
                return {
                    "success": False,
                    "error": "未检测到USB设备"
                }
            device = usb_res["devices"][0]

        subprocess.run(
            [TERMUX_USB_CMD, "-r", device],
            capture_output=True,
            timeout=USB_GRANT_TIMEOUT
        )

        return {
            "success": True,
            "msg": "权限申请已发送，请在弹窗点击允许",
            "device": device
        }

    except Exception as e:
        logger.error(f"USB授权失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }
