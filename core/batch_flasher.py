# Skytree Flasher / core/batch_flasher.py
# -*- coding: utf-8 -*-
"""
core/batch_flasher.py — 批量线刷任务
从 core/flasher.py 拆分而来，函数逻辑保持不变。

_now / _append_log 来自 core.flasher（公共辅助，保留在 flasher 中）。
tasks / gen_task_id / persist_tasks 来自 core.extractor（全局共享）。
"""

import os
import re
import json
import time
import shlex
import threading
import subprocess
from typing import Optional

from config import (
    ROM_DIR,
    FLASH_HISTORY_FILE,
    REBOOT_TIMEOUT,
    WAIT_FASTBOOT_INITIAL,
    BATCH_REBOOT_MAX_WAIT,
    FASTBOOT_FLASH_TIMEOUT,
    FASTBOOT_GETVAR_TIMEOUT,
    logger,
)
from core.utils import (
    validate_partition_name,
    is_dangerous_partition,
    get_image_path,
    diagnose_error,
    resolve_image_abs_path,
)
from core.extractor import tasks, gen_task_id, persist_tasks
from core.device import (
    run_fastboot_command,
    check_devices,
    get_fastboot_base_cmd,
    classify_fastboot_result,
)
from core.flasher import _now, _append_log


# ======================================================================
# 模块: services/batch_flasher.py
# ======================================================================

# ============ 刷机历史记录 ============
def _load_flash_history():
    """加载刷机历史记录"""
    if os.path.isfile(FLASH_HISTORY_FILE):
        try:
            with open(FLASH_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return []

def _save_flash_history(history):
    """保存刷机历史记录"""
    try:
        os.makedirs(os.path.dirname(FLASH_HISTORY_FILE), exist_ok=True)
        with open(FLASH_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history[-50:], f, ensure_ascii=False, indent=2)  # 只保留最近50条
    except Exception as e:
        logger.warning(f"保存历史记录失败: {e}")

def _add_flash_history(device, script_name, step_count, success, error_msg=""):
    """添加一条刷机记录"""
    from datetime import datetime
    history = _load_flash_history()
    history.append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "device": device,
        "script": script_name,
        "steps": step_count,
        "success": success,
        "error": error_msg,
    })
    _save_flash_history(history)


def _get_device_sn():
    """获取当前设备序列号（用于历史记录）"""
    try:
        result = run_fastboot_command(["getvar", "product"], timeout=FASTBOOT_GETVAR_TIMEOUT)
        output = (result.get("combined", "") or "")
        for line in output.strip().splitlines():
            if "product" in line.lower():
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip()
    except Exception:
        pass
    return "unknown"


def _set_status(task: dict, status: str, phase: str = "", progress: Optional[int] = None):
    task["status"] = status
    if phase:
        task["phase"] = phase
    if progress is not None:
        task["progress"] = max(0, min(100, int(progress)))
    task["updated_at"] = _now()
    persist_tasks()


def _is_reboot_disconnect(result: dict) -> bool:
    text = f"{result.get('error', '')}\n{result.get('output', '')}\n{result.get('combined', '')}".lower()
    return (
        result.get("category") == "reboot_disconnect"
        or (result.get("recoverable") and result.get("category") in ("timeout", "device_disconnected"))
        or "status read failed" in text
        or "no such device" in text
        or "device disconnected" in text
        or "命令执行超时" in text
        or "timeout" in text
    )


def _target_label(target: str) -> str:
    t = (target or "").lower()
    if t == "fastboot":
        return "Fastboot/fastbootd"
    if t == "bootloader":
        return "Bootloader Fastboot"
    return "Fastboot"


def wait_for_fastboot(task: dict, target: str = "", start_index: int = 0) -> bool:
    label = _target_label(target)
    _set_status(task, "running", "waiting_reconnect")
    task["next_index"] = start_index
    _append_log(task, f"设备已发送 reboot {target}，先等待 2 秒让设备离线...")
    time.sleep(2)
    _append_log(task, f"开始检测设备重新进入 {label}，重连后自动继续...")
    max_wait = BATCH_REBOOT_MAX_WAIT  # 默认 5 分钟
    waited = 0
    while waited < max_wait:
        if task.get("cancel_requested"):
            _set_status(task, "cancelled", "cancelled")
            _append_log(task, "任务已取消")
            return False
        try:
            d = check_devices()
            if d.get("connected"):
                _append_log(task, f"已检测到 Fastboot 设备，继续执行")
                return True
        except Exception as e:
            _append_log(task, f"检测 Fastboot 设备失败，继续等待：{e}")
        # 每 10 秒检查 USB 设备是否存在但无授权，尝试自动重新授权
        if waited >= 5 and waited % 10 < WAIT_FASTBOOT_INITIAL:
            try:
                from core.device_info import check_usb_devices, grant_usb_permission
                usb_res = check_usb_devices()
                if usb_res.get("success") and usb_res.get("count", 0) > 0:
                    _append_log(task, "检测到 USB 设备但 Fastboot 不可用，正在自动重新授权...")
                    grant_usb_permission()
            except Exception:
                pass
        time.sleep(1.5)
        waited += 1.5
        task["wait_seconds"] = int(waited)
        task["updated_at"] = _now()
        if int(waited) % 30 < 2:
            _append_log(task, f"仍在等待 {label} 重连，已等待 {int(waited)} 秒。")
        else:
            persist_tasks()
    _append_log(task, f"等待 {label} 重连超时（{max_wait} 秒），已停止等待。")
    return False  # 超时返回 False


def _run_decompress_step(task: dict, step: dict) -> dict:
    """执行解压步骤：zstd / 7z 等压缩格式"""
    import shutil

    fmt = step.get("format", "zstd")
    input_file = step.get("inputFile", "")
    output_file = step.get("outputFile", "")
    remove_source = step.get("removeSource", False)

    if not input_file:
        return {"success": False, "error": "解压步骤缺少输入文件路径"}

    # 如果 inputFile 是相对路径，尝试在 ROM 目录下查找
    if not os.path.isabs(input_file):
        input_file = os.path.join(ROM_DIR, input_file)
    if not os.path.exists(input_file):
        # 递归查找
        from core.utils import resolve_image_abs_path
        found_path, found = resolve_image_abs_path(
            os.path.basename(input_file), "", task.get("rom_name", "")
        )
        if found:
            input_file = found_path
        else:
            return {"success": False, "error": f"压缩文件不存在：{input_file}"}

    # 如果 outputFile 是相对路径，与输入文件同目录
    if output_file and not os.path.isabs(output_file):
        output_file = os.path.join(os.path.dirname(input_file), output_file)

    size_mb = round(os.path.getsize(input_file) / 1024 / 1024, 1)
    _append_log(task, f"开始解压 {os.path.basename(input_file)}（{size_mb} MB）→ {os.path.basename(output_file) if output_file else '同目录'}")

    try:
        if fmt == "zstd":
            result = _decompress_zstd(input_file, output_file, task)
        elif fmt in ("7z", "zip", "gz", "tar", "bz2"):
            result = _decompress_7z(input_file, output_file, fmt, task)
        else:
            return {"success": False, "error": f"不支持的压缩格式：{fmt}"}

        if result.get("success") and remove_source:
            try:
                os.remove(input_file)
                _append_log(task, f"已删除源文件 {os.path.basename(input_file)}")
            except Exception as e:
                _append_log(task, f"删除源文件失败（非致命）：{e}")

        return result
    except Exception as e:
        return {"success": False, "error": f"解压失败：{e}", "combined": str(e)}


def _decompress_zstd(input_file: str, output_file: str, task: dict) -> dict:
    """使用 zstd 命令行工具解压"""
    import shutil

    # 优先尝试 zstd 命令行工具
    zstd_bin = shutil.which("zstd")
    if zstd_bin:
        if not output_file:
            output_file = input_file.rsplit(".zst", 1)[0]
        cmd = [zstd_bin, "-d", "-f", input_file, "-o", output_file]
        _append_log(task, f"执行命令：zstd -d -f ... -o {os.path.basename(output_file)}")
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        output = ""
        for line in proc.stdout:
            line = line.strip()
            if line:
                output += line + "\n"
                _append_log(task, line)
        try:
            proc.wait(timeout=300)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            return {"success": False, "error": "解压超时（300秒），已终止"}
        return {
            "success": proc.returncode == 0,
            "returncode": proc.returncode,
            "output": output,
            "error": "" if proc.returncode == 0 else output,
            "combined": output,
        }

    # 回退：尝试 Python zstandard 库
    try:
        import zstandard as zstd
        if not output_file:
            output_file = input_file.rsplit(".zst", 1)[0]
        _append_log(task, f"使用 Python zstandard 库解压...")
        with open(input_file, "rb") as fin, open(output_file, "wb") as fout:
            dctx = zstd.ZstdDecompressor()
            dctx.copy_stream(fin, fout)
        _append_log(task, "解压完成")
        return {"success": True, "output": "解压完成", "error": "", "combined": "解压完成"}
    except ImportError:
        return {"success": False, "error": "系统未安装 zstd 命令行工具或 Python zstandard 库，请在 Termux 中执行 pkg install zstd"}


def _decompress_7z(input_file: str, output_file: str, fmt: str, task: dict) -> dict:
    """使用 7z 或 unzip 命令解压"""
    import shutil

    # 对于 zip 格式，优先尝试 unzip
    if fmt == "zip":
        unzip_bin = shutil.which("unzip")
        if unzip_bin:
            out_dir = output_file if output_file else os.path.dirname(input_file)
            cmd = [unzip_bin, "-o", input_file, "-d", out_dir]
            _append_log(task, f"执行命令：unzip -o ... -d {out_dir}")
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            output = ""
            for line in proc.stdout:
                line = line.strip()
                if line:
                    output += line + "\n"
                    _append_log(task, line)
            try:
                proc.wait(timeout=300)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                return {"success": False, "error": "解压超时（300秒），已终止"}
            return {
                "success": proc.returncode == 0,
                "returncode": proc.returncode,
                "output": output,
                "error": "" if proc.returncode == 0 else output,
                "combined": output,
            }

    # 尝试 7z 命令
    z7_bin = shutil.which("7z") or shutil.which("7za") or shutil.which("7zr")
    if z7_bin:
        out_dir = output_file if output_file else os.path.dirname(input_file)
        cmd = [z7_bin, "x", input_file, f"-o{out_dir}", "-y"]
        _append_log(task, f"执行命令：7z x ... -o{out_dir} -y")
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        output = ""
        for line in proc.stdout:
            line = line.strip()
            if line:
                output += line + "\n"
                _append_log(task, line)
        try:
            proc.wait(timeout=300)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            return {"success": False, "error": "解压超时（300秒），已终止"}
        return {
            "success": proc.returncode == 0,
            "returncode": proc.returncode,
            "output": output,
            "error": "" if proc.returncode == 0 else output,
            "combined": output,
        }

    return {"success": False, "error": f"系统未安装 7z 或 unzip 命令，请在 Termux 中执行 pkg install p7zip"}


def _run_flash_step(task: dict, step: dict) -> dict:
    partition = validate_partition_name(step.get("part", ""))
    if is_dangerous_partition(partition) and not task.get("allow_dangerous"):
        raise ValueError(f"高危分区 {partition} 未确认")
    # 优先使用解析阶段已校验的 imagePath（绝对路径，存在性已确认）
    image_path = step.get("imagePath") or ""
    if not image_path or not os.path.exists(image_path):
        # 回退：用统一解析器重新查找（覆盖 ROM 根目录 + 递归）
        image_path, found = resolve_image_abs_path(
            step.get("fileName", ""),
            "",  # 执行阶段无脚本目录，依赖 rom_name 定位 ROM 根
            task.get("rom_name", ""),
        )
        if not found:
            # 最后回退到旧的 get_image_path（向后兼容）
            try:
                image_path = get_image_path(task.get("source", "rom"), step.get("fileName", ""), task.get("rom_name", ""))
            except (ValueError, FileNotFoundError):
                raise FileNotFoundError(f"镜像不存在：{step.get('fileName', '')}")
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"镜像不存在：{step.get('fileName', '')}")
        # 找到了就回写到 step，供断点续传复用
        step["imagePath"] = image_path
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"镜像不存在：{step.get('fileName', '')}")
    size_mb = round(os.path.getsize(image_path) / 1024 / 1024, 1)
    _append_log(task, f"开始刷写分区 {partition}，镜像大小 {size_mb} MB")
    cmd = get_fastboot_base_cmd() + ["flash", partition, image_path]
    extra = step.get("prefixParams") or step.get("params") or step.get("extra") or ""
    if extra:
        prefix_parts = shlex.split(extra) if extra.strip() else extra.strip().split()
        # prefixParams 必须放在 flash 子命令之前
        # cmd 结构: ["fastboot", "flash", partition, image_path]
        cmd = cmd[:1] + prefix_parts + cmd[1:]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env={**os.environ, "TERMUX_USB_AUTO_GRANT": "1"},
    )
    output = ""
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        output += line + "\n"
        _append_log(task, line)
        low = line.lower()
        base = int((task["current_index"] / max(1, task["step_total"])) * 100)
        span = max(1, int(100 / max(1, task["step_total"])))
        if "sending" in low:
            task["progress"] = min(99, base + int(span * 0.35))
        elif "writing" in low:
            task["progress"] = min(99, base + int(span * 0.7))
        task["updated_at"] = _now()
        persist_tasks()
    try:
        proc.wait(timeout=600)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise Exception("刷写超时（600秒），已终止")
    result = {
        "success": proc.returncode == 0,
        "returncode": proc.returncode,
        "output": output,
        "error": "" if proc.returncode == 0 else output,
        "combined": output,
    }
    result.update(classify_fastboot_result(output, ["flash", partition, image_path], proc.returncode))
    return result


def create_batch_flash_task(
    steps: list,
    source: str = "rom",
    rom_name: str = "",
    start_index: int = 0,
    allow_dangerous: bool = True,
    plan: Optional['ExecutionPlan'] = None,
    step_offset: int = 0,
    step_total: int = 0,
) -> dict:
    """
    创建批量刷机任务。

    Args:
        steps: 步骤列表（旧格式 dict 列表）
        source: 刷机源
        rom_name: ROM 包名
        start_index: 起始步骤索引
        allow_dangerous: 是否允许高危分区
        plan: ExecutionPlan（可选）。传入时优先检查 plan.blockers
        step_offset: 本段步骤在全局步骤列表中的偏移量（用于日志显示全局序号）
        step_total: 全局步骤总数（用于日志显示全局序号，0 表示用本段长度）

    Returns:
        任务字典
    """
    # 延迟导入，避免循环依赖
    from routes.socketio import emit_task_progress

    # 如果有 ExecutionPlan，优先检查阻断
    if plan is not None:
        if not plan.safe_to_flash:
            return {
                "success": False,
                "error": "；".join(plan.blockers),
                "blockers": plan.blockers,
            }
        # 使用 plan 中的 steps（已经过 optimize_step_order）
        steps = plan.steps

    if not isinstance(steps, list) or not steps:
        return {"success": False, "error": "线刷步骤为空"}
    tid = gen_task_id()
    start_index = max(0, min(int(start_index or 0), len(steps)))
    # 全局步骤总数：优先用传入的 step_total，否则用本段长度
    global_total = int(step_total) if int(step_total or 0) > 0 else len(steps)
    global_offset = int(step_offset) if int(step_offset or 0) > 0 else 0
    task = {
        "id": tid,
        "type": "batch_flash",
        "status": "pending",
        "phase": "pending",
        "progress": 0,
        "logs": [],
        "error": "",
        "diagnosis": "",
        "source": source,
        "rom_name": rom_name,
        "steps": steps,
        "step_total": len(steps),
        "step_offset": global_offset,
        "step_global_total": global_total,
        "current_index": start_index,
        "next_index": start_index,
        "allow_dangerous": bool(allow_dangerous),
        "cancel_requested": False,
        "pause_requested": False,
        "created_at": _now(),
        "updated_at": _now(),
    }
    tasks[tid] = task
    persist_tasks()
    threading.Thread(
        target=batch_flash_worker,
        args=(tid,),
        kwargs={"progress_callback": lambda p, m: emit_task_progress(tid, p, m)},
        daemon=True
    ).start()
    return {"success": True, "task_id": tid, "msg": "后端线刷任务已启动"}


def cancel_batch_flash_task(task_id: str) -> dict:
    task = tasks.get(task_id)
    if not task or task.get("type") != "batch_flash":
        return {"success": False, "error": "任务不存在"}
    task["cancel_requested"] = True
    task["updated_at"] = _now()
    _append_log(task, "已请求取消，当前命令结束后停止。")
    return {"success": True}


def get_latest_batch_task() -> Optional[dict]:
    batch_tasks = [t for t in tasks.values() if t.get("type") == "batch_flash"]
    if not batch_tasks:
        return None
    return sorted(batch_tasks, key=lambda x: x.get("updated_at", 0), reverse=True)[0]


def batch_flash_worker(task_id: str, progress_callback=None):
    task = tasks.get(task_id)
    if not task:
        return
    _set_status(task, "running", "running", task.get("progress", 0))
    # 全局步骤序号信息
    step_offset = int(task.get("step_offset", 0))
    global_total = int(task.get("step_global_total", 0)) or task.get("step_total", 0)
    _append_log(task, f"后端线刷任务启动，本段 {task.get('step_total', 0)} 步（全局第 {step_offset + 1}-{step_offset + task.get('step_total', 0)} 步 / 共 {global_total} 步），从第 {task.get('next_index', 0) + 1} 步开始。")
    try:
        steps = task.get("steps") or []
        for i in range(int(task.get("next_index", 0)), len(steps)):
            if task.get("cancel_requested"):
                _set_status(task, "cancelled", "cancelled")
                _append_log(task, "任务已取消")
                return
            # 暂停检查
            if task.get("pause_requested"):
                task["pause_requested"] = False
                _set_status(task, "paused", "paused")
                task["next_index"] = i
                _append_log(task, f"任务已在第 {i + 1} 步前暂停")
                return
            step = steps[i] or {}
            task["current_index"] = i
            task["next_index"] = i
            task["current_step"] = step
            _set_status(task, "running", "running", int(i / max(1, len(steps)) * 100))
            # 全局步骤序号：step_offset + i + 1
            global_idx = step_offset + i + 1
            global_msg = f"[{global_idx}/{global_total}]"
            if progress_callback:
                progress_callback(task["progress"], f"{global_msg} 执行：{step.get('raw') or step.get('type')}")
            _append_log(task, f"{global_msg} 执行：{step.get('raw') or step.get('type')}")
            stype = step.get("type")
            if stype == "flash":
                result = _run_flash_step(task, step)
            elif stype == "erase":
                # COW 动态清理：先查询设备上实际存在的 COW 分区
                if step.get("cow_cleanup"):
                    cow_part = step.get("part", "")
                    _append_log(task, f"COW 动态清理：检查分区 {cow_part} 是否存在...")
                    # 查询设备分区列表
                    check_result = run_fastboot_command(["getvar", "partition-size:" + cow_part], timeout=10)
                    check_output = (check_result.get("combined", "") or "").lower()
                    if "not found" in check_output or "no such" in check_output or not check_result.get("success"):
                        _append_log(task, f"COW 分区 {cow_part} 不存在，跳过删除")
                        result = {"success": True, "category": "skipped"}
                    else:
                        _append_log(task, f"COW 分区 {cow_part} 存在，执行删除")
                        result = run_fastboot_command(["delete-logical-partition", cow_part], timeout=FASTBOOT_FLASH_TIMEOUT)
                else:
                    result = run_fastboot_command(["erase", step.get("part", "")], timeout=FASTBOOT_FLASH_TIMEOUT)
            elif stype == "set_active":
                # 非AB设备执行 set_active 会报错，先检测设备是否AB分区
                # 如果非AB则跳过该步骤
                slot_target = step.get("part", "")
                try:
                    check_result = run_fastboot_command(["getvar", "current-slot"], timeout=10)
                    check_output = (check_result.get("combined", "") or "").lower()
                    # current-slot 返回值格式: "current-slot: a" 或 "a"
                    # 非AB设备没有这个变量，返回空或 not found
                    has_slot = bool(re.search(r'(?:current-slot)?\s*:\s*[ab]', check_output))
                    if has_slot:
                        result = run_fastboot_command(["set_active", slot_target], timeout=FASTBOOT_FLASH_TIMEOUT)
                    else:
                        _append_log(task, f"非AB分区设备，跳过 set_active {slot_target}")
                        result = {"success": True, "category": "skipped"}
                except Exception as e:
                    # 查询失败也视为非AB，跳过
                    _append_log(task, f"检测槽位失败({e})，视为非AB设备，跳过 set_active {slot_target}")
                    result = {"success": True, "category": "skipped"}
            elif stype == "reboot":
                task["next_index"] = i + 1
                persist_tasks()
                part = step.get("part", "")
                args = ["reboot"] + ([part] if part and part != "system" else [])
                result = run_fastboot_command(args, timeout=REBOOT_TIMEOUT)
                if not result.get("success") and _is_reboot_disconnect(result):
                    _append_log(task, "重启后设备断开，视为重启命令已发送。")
                    result = {"success": True, "category": "reboot_disconnect"}
            elif stype == "decompress":
                result = _run_decompress_step(task, step)
            else:
                _append_log(task, f"跳过暂不支持的步骤类型：{stype}")
                result = {"success": True, "category": "skipped"}
            if not result.get("success"):
                task["error"] = result.get("error") or result.get("combined") or "命令失败"
                task["diagnosis"] = result.get("diagnosis") or diagnose_error(task["error"])
                task["category"] = result.get("category", "command_failed")
                task["next_index"] = i
                _set_status(task, "error", "failed")
                _append_log(task, f"{global_msg} 失败：{task['error']}")
                if task["diagnosis"]:
                    _append_log(task, f"诊断建议：{task['diagnosis']}")
                _add_flash_history(
                    device=_get_device_sn(),
                    script_name=task.get("rom_name", ""),
                    step_count=global_total,
                    success=False,
                    error_msg=task["error"],
                )
                return
            task["next_index"] = i + 1
            task["progress"] = min(99, int(((i + 1) / max(1, len(steps))) * 100))
            if progress_callback:
                progress_callback(task["progress"], f"{global_msg} 完成")
            _append_log(task, f"{global_msg} 完成")
        task["current_index"] = len(steps)
        task["next_index"] = len(steps)
        _set_status(task, "completed", "done", 100)
        _append_log(task, f"后端线刷任务全部完成（本段 {len(steps)} 步，全局第 {step_offset + 1}-{step_offset + len(steps)} 步 / 共 {global_total} 步）")
        _add_flash_history(
            device=_get_device_sn(),
            script_name=task.get("rom_name", ""),
            step_count=global_total,
            success=True,
        )
        emit_task_complete(task_id, True, "刷机完成")
    except Exception as e:
        task["error"] = str(e)
        task["diagnosis"] = diagnose_error(str(e))
        _set_status(task, "error", "failed")
        _append_log(task, f"后端线刷异常：{e}")
        if task["diagnosis"]:
            _append_log(task, f"诊断建议：{task['diagnosis']}")
        _add_flash_history(
            device=_get_device_sn(),
            script_name=task.get("rom_name", ""),
            step_count=len(steps),
            success=False,
            error_msg=str(e),
        )
        emit_task_complete(task_id, False, str(e))


# ----------------------------------------------------------------------
# 延迟导入 emit_task_complete，避免与 routes.socketio 循环依赖（#2）
# ----------------------------------------------------------------------
from routes.socketio import emit_task_complete  # noqa: E402