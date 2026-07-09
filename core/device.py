# -*- coding: utf-8 -*-
# Skytree Flasher / core/device.py
"""
core/device.py — 设备通信层（fastboot / adb 核心命令执行）
从单文件版提取，函数逻辑保持不变。

SELECTED_FASTBOOT_DEVICE / SELECTED_ADB_DEVICE 为本模块全局变量，
其他模块通过本模块的 *_base_cmd / select_* 系列函数间接使用。

设备信息查询与操作（BL锁/槽位/重启/擦除/USB）已拆分至 core/device_info.py，
此处通过 import 重新导出以保持对外接口不变。
"""

import os
import re
import subprocess
import threading

from config import (
    FASTBOOT_PATH,
    ADB_PATH,
    TERMUX_USB_CMD,
    FASTBOOT_DEFAULT_TIMEOUT,
    ADB_DEFAULT_TIMEOUT,
    ADB_DEVICES_TIMEOUT,
    BL_QUERY_TIMEOUT,
    DEVICE_INFO_TIMEOUT,
    USB_CHECK_TIMEOUT,
    USB_GRANT_TIMEOUT,
    logger,
)
from core.utils import validate_fastboot_args, diagnose_error


# ======================================================================
# 模块: services/device.py
# ======================================================================

# 当前选中的设备序列号（隐式全局变量）
SELECTED_FASTBOOT_DEVICE = ""
SELECTED_ADB_DEVICE = ""
_device_lock = threading.Lock()  # #24: 保护 SELECTED_FASTBOOT_DEVICE 读写


def classify_fastboot_result(text: str, args: list = None, returncode: int = 0) -> dict:
    """统一分类 fastboot/adb 返回，便于前端和线刷流程一致处理"""
    raw = (text or "")
    s = raw.lower()
    args = args or []
    category = "success" if returncode == 0 else "command_failed"
    recoverable = False
    message = ""

    if "status read failed" in s or "no such device" in s or "device disconnected" in s:
        category = "reboot_disconnect" if args and args[0] == "reboot" else "device_disconnected"
        recoverable = args and args[0] == "reboot"
        message = "设备已断开，若发生在重启命令后通常表示重启已发送"
    elif "timeout" in s or "超时" in s:
        category = "timeout"
        recoverable = args and args[0] == "reboot"
        message = "命令超时"
    elif "flashing is not allowed" in s or "bootloader is locked" in s or "not unlocked" in s:
        category = "bootloader_locked"
        message = "Bootloader未解锁或不允许刷写"
    elif "no such partition" in s or "partition" in s and "not found" in s:
        category = "partition_missing"
        message = "分区不存在或当前模式不支持该分区"
    elif "cannot load" in s or "no such file" in s:
        category = "image_missing"
        message = "镜像文件不存在或无法读取"
    elif returncode == 0:
        message = "命令成功"

    return {"category": category, "recoverable": bool(recoverable), "message": message}


def parse_device_serial(line: str) -> str:
    """从 fastboot devices 输出行提取序列号"""
    return (line or "").strip().split()[0] if (line or "").strip() else ""


def select_fastboot_device(serial: str) -> dict:
    """选择当前要操作的 fastboot 设备"""
    global SELECTED_FASTBOOT_DEVICE
    SELECTED_FASTBOOT_DEVICE = (serial or "").strip()
    return {
        "success": True,
        "selected": SELECTED_FASTBOOT_DEVICE,
        "msg": f"已选择设备：{SELECTED_FASTBOOT_DEVICE}" if SELECTED_FASTBOOT_DEVICE else "已清除设备选择"
    }


def get_selected_fastboot_device() -> str:
    """获取当前选择的 fastboot 设备序列号"""
    return SELECTED_FASTBOOT_DEVICE


def get_fastboot_base_cmd(include_device: bool = True) -> list:
    """生成 fastboot 基础命令，自动附加 -s 设备序列号"""
    cmd = [FASTBOOT_PATH]
    if include_device:
        with _device_lock:
            dev = SELECTED_FASTBOOT_DEVICE
        if dev:
            cmd += ["-s", dev]
    return cmd


def parse_adb_device_line(line: str) -> dict:
    """解析 adb devices 输出行"""
    parts = (line or "").strip().split()
    if len(parts) >= 2:
        return {"serial": parts[0], "state": parts[1], "raw": line.strip()}
    return {}


def select_adb_device(serial: str) -> dict:
    """选择当前要操作的 adb 设备"""
    global SELECTED_ADB_DEVICE
    SELECTED_ADB_DEVICE = (serial or "").strip()
    return {
        "success": True,
        "selected": SELECTED_ADB_DEVICE,
        "msg": f"已选择 ADB 设备：{SELECTED_ADB_DEVICE}" if SELECTED_ADB_DEVICE else "已清除 ADB 设备选择"
    }


def get_adb_base_cmd(include_device: bool = True) -> list:
    """生成 adb 基础命令，自动附加 -s 设备序列号"""
    cmd = [ADB_PATH]
    if include_device and SELECTED_ADB_DEVICE:
        cmd += ["-s", SELECTED_ADB_DEVICE]
    return cmd


def run_adb_command(args: list, timeout: int = ADB_DEFAULT_TIMEOUT) -> dict:
    """执行 adb 命令"""
    try:
        validate_fastboot_args(args)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    try:
        include_device = not (len(args) > 0 and args[0] == "devices")
        res = subprocess.run(
            get_adb_base_cmd(include_device=include_device) + args,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        output = res.stdout.strip()
        error = res.stderr.strip()
        combined = output + error
        return {
            "success": res.returncode == 0,
            "returncode": res.returncode,
            "output": output,
            "error": error,
            "combined": combined,
            "diagnosis": diagnose_error(combined)
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "ADB 命令执行超时", "diagnosis": "设备可能未授权、离线或命令执行时间过长"}
    except Exception as e:
        return {"success": False, "error": str(e), "diagnosis": diagnose_error(str(e))}


def check_adb_devices() -> dict:
    """检查 ADB 设备"""
    res = run_adb_command(["devices"], timeout=ADB_DEVICES_TIMEOUT)
    if not res["success"]:
        return {"connected": False, "count": 0, "devices": [], "list": [], "selected": SELECTED_ADB_DEVICE, "error": res.get("error", "")}

    lines = [l.strip() for l in res["output"].splitlines() if l.strip()]
    device_lines = [l for l in lines if not l.lower().startswith("list of devices")]
    parsed = [parse_adb_device_line(l) for l in device_lines]
    parsed = [d for d in parsed if d]
    ready = [d for d in parsed if d.get("state") in ("device", "recovery", "sideload")]
    return {
        "connected": len(parsed) > 0,
        "ready": len(ready) > 0,
        "count": len(parsed),
        "ready_count": len(ready),
        "devices": parsed,
        "list": device_lines,
        "selected": SELECTED_ADB_DEVICE
    }


def get_combined_device_state() -> dict:
    """同时检测 ADB 与 Fastboot 设备，并判断当前可用功能"""
    adb = check_adb_devices()
    fastboot = check_devices()

    mode = "none"
    state = "none"
    selected = ""
    can_adb = False
    can_fastboot = False

    if fastboot.get("connected"):
        mode = "fastboot"
        state = "bootloader/fastboot"
        selected = fastboot.get("selected") or (fastboot.get("devices", [{}])[0].get("serial", "") if fastboot.get("devices") else "")
        can_fastboot = True
    elif adb.get("connected"):
        mode = "adb"
        first = adb.get("devices", [{}])[0]
        state = first.get("state", "unknown")
        selected = adb.get("selected") or first.get("serial", "")
        can_adb = state in ("device", "recovery", "sideload")

    return {
        "success": True,
        "mode": mode,
        "state": state,
        "selected": selected,
        "can_adb": can_adb,
        "can_fastboot": can_fastboot,
        "adb": adb,
        "fastboot": fastboot
    }


def run_fastboot_command(args: list, timeout: int = FASTBOOT_DEFAULT_TIMEOUT) -> dict:
    """
    执行 fastboot 命令

    Args:
        args: 命令参数列表
        timeout: 超时时间（秒）

    Returns:
        结果字典
    """
    # 校验参数
    try:
        validate_fastboot_args(args)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    try:
        logger.info(f"执行 fastboot 命令: {args}")

        include_device = not (len(args) > 0 and args[0] == "devices")
        res = subprocess.run(
            get_fastboot_base_cmd(include_device=include_device) + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "TERMUX_USB_AUTO_GRANT": "1"}
        )

        output = res.stdout.strip()
        error = res.stderr.strip()
        combined = output + error

        result = {
            "success": res.returncode == 0,
            "returncode": res.returncode,
            "output": output,
            "error": error,
            "combined": combined,
            "diagnosis": diagnose_error(combined),
            **classify_fastboot_result(combined, args, res.returncode)
        }

        logger.info(f"fastboot 命令结果: returncode={res.returncode}")

        return result

    except subprocess.TimeoutExpired:
        logger.error("fastboot 命令超时")
        return {
            "success": False,
            "output": "",
            "error": "命令执行超时",
            "combined": "命令执行超时",
            "diagnosis": "连接超时，请勿锁屏、重新插拔数据线",
            **classify_fastboot_result("命令执行超时", args, 124)
        }

    except Exception as e:
        logger.error(f"fastboot 命令异常: {e}")
        return {
            "success": False,
            "output": "",
            "error": str(e),
            "combined": str(e),
            "diagnosis": diagnose_error(str(e)),
            **classify_fastboot_result(str(e), args, 1)
        }


def check_devices() -> dict:
    """
    检查连接的 Fastboot 设备

    Returns:
        设备信息字典
    """
    res = run_fastboot_command(["devices"])

    if not res["success"]:
        return {
            "connected": False,
            "count": 0,
            "list": [],
            "error": res["error"]
        }

    global SELECTED_FASTBOOT_DEVICE
    devices = [l.strip() for l in res["output"].splitlines() if l.strip()]
    parsed = [
        {"serial": parse_device_serial(line), "raw": line}
        for line in devices
        if parse_device_serial(line)
    ]
    serials = [d["serial"] for d in parsed]
    with _device_lock:
        if serials and (not SELECTED_FASTBOOT_DEVICE or SELECTED_FASTBOOT_DEVICE not in serials):
            SELECTED_FASTBOOT_DEVICE = serials[0]
            logger.info(f"自动选择 Fastboot 设备: {SELECTED_FASTBOOT_DEVICE}")
        selected = SELECTED_FASTBOOT_DEVICE

    return {
        "connected": len(devices) > 0,
        "count": len(devices),
        "list": devices,
        "devices": parsed,
        "selected": selected
    }


# ----------------------------------------------------------------------
# 重新导出设备信息查询接口（已拆分至 core/device_info.py）
# 放在文件末尾，确保核心命令执行函数先定义，避免循环导入。
# routes 等模块通过 `from core.device import ...` 仍可正常引用。
# ----------------------------------------------------------------------
from core.device_info import (  # noqa: E402
    get_bl_unlock_info,
    get_device_slot,
    get_device_info,
    reboot_device,
    erase_partition,
    set_active_slot,
    oem_command,
    check_usb_devices,
    grant_usb_permission,
)