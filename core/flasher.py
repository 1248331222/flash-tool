# -*- coding: utf-8 -*-
# flash_tool/core/flasher.py
"""
core/flasher.py — 单分区刷写
从单文件版提取，函数逻辑保持不变。

批量线刷任务已拆分至 core/batch_flasher.py，
此处通过 import 重新导出以保持对外接口不变。
emit_task_progress 通过延迟导入避免与 routes.socketio 循环依赖。
tasks / gen_task_id / persist_tasks 来自 core.extractor（全局共享）。
"""

import os
import json
import time
import shlex
import threading
import subprocess
from typing import Callable, Optional

from config import (
    TASK_LOG_LIMIT,
    FLASH_HISTORY_FILE,
    REBOOT_TIMEOUT,
    WAIT_FASTBOOT_INITIAL,
    BATTERY_LOW_THRESHOLD,
    logger,
)
from core.utils import (
    validate_partition_name,
    is_dangerous_partition,
    get_image_path,
    diagnose_error,
)
from core.extractor import tasks, gen_task_id, persist_tasks
from core.device import (
    run_fastboot_command,
    check_devices,
    get_device_info,
    get_fastboot_base_cmd,
    classify_fastboot_result,
)


# ======================================================================
# 模块: services/flasher.py
# ======================================================================


def create_flash_task(partition: str, image_path: str,
                      extra_params: str = "",
                      allow_dangerous: bool = False,
                      progress_callback: Optional[Callable] = None) -> dict:
    """
    创建刷写任务

    Args:
        partition: 分区名
        image_path: 镜像路径
        extra_params: 额外参数
        allow_dangerous: 是否允许高危分区
        progress_callback: 进度回调

    Returns:
        结果字典，包含 task_id 或 error
    """
    # 校验分区名
    try:
        partition = validate_partition_name(partition)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    # 检查高危分区
    if is_dangerous_partition(partition) and not allow_dangerous:
        return {
            "success": False,
            "error": "高危分区，需确认后才能刷",
            "dangerous": True,
            "partition": partition
        }

    # 校验镜像路径
    if not os.path.exists(image_path):
        return {"success": False, "error": "镜像不存在"}

    # 创建任务
    tid = gen_task_id()
    tasks[tid] = {
        "type": "flash",
        "status": "pending",
        "progress": 0,
        "logs": [],
        "error": "",
        "diagnosis": "",
        "created_at": time.time(),
        "updated_at": time.time(),
        "partition": partition,
        "image_path": image_path
    }
    persist_tasks()

    # 启动后台线程
    threading.Thread(
        target=flash_worker,
        args=(tid, partition, image_path, extra_params, progress_callback),
        daemon=True
    ).start()

    logger.info(f"创建刷写任务: {tid}, 分区: {partition}")

    return {
        "success": True,
        "task_id": tid,
        "msg": "刷写任务已启动"
    }


def flash_worker(task_id: str, partition: str, image_path: str,
                 extra_params: str = "",
                 progress_callback: Optional[Callable] = None):
    """
    刷写任务工作函数

    Args:
        task_id: 任务ID
        partition: 分区名
        image_path: 镜像路径
        extra_params: 额外参数
        progress_callback: 进度回调
    """
    task = tasks[task_id]
    task["status"] = "running"
    task["diagnosis"] = ""
    task["updated_at"] = time.time()
    persist_tasks()

    def log(msg: str):
        task["logs"].append(msg)
        task["logs"] = task["logs"][-TASK_LOG_LIMIT:]
        task["updated_at"] = time.time()
        logger.info(f"[{task_id}] {msg}")
        persist_tasks()
        if progress_callback:
            progress_callback(task["progress"], msg)

    try:
        # 获取镜像大小
        img_size_mb = round(os.path.getsize(image_path) / 1024 / 1024, 1)
        log(f"开始刷写分区：{partition}（大小：{img_size_mb} MB）")

        # 构建命令
        cmd = get_fastboot_base_cmd() + ["flash", partition, image_path]
        if extra_params:
            cmd += extra_params.strip().split()

        # 执行命令
        task["progress"] = 20
        log(f"执行命令: fastboot flash {partition} ...")

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env={**os.environ, "TERMUX_USB_AUTO_GRANT": "1"}
        )

        output = ""
        for line in proc.stdout:
            line = line.strip()
            if line:
                output += line + " "
                log(line)

                # 根据输出更新进度
                if "sending" in line.lower():
                    task["progress"] = 40
                elif "writing" in line.lower():
                    task["progress"] = 70

                if progress_callback:
                    progress_callback(task["progress"], line)

        # 等待完成，支持取消与超时（#11, #26）
        deadline = time.time() + 600
        try:
            while proc.poll() is None:
                if task.get('cancel_requested'):
                    proc.terminate()
                    raise Exception("任务已取消")
                if time.time() > deadline:
                    proc.kill()
                    proc.wait()
                    raise Exception("刷写超时（600秒），已终止")
                time.sleep(0.5)
        except Exception:
            if proc.poll() is None:
                proc.kill()
            raise

        if proc.returncode == 0:
            task["status"] = "success"
            task["progress"] = 100
            task["category"] = "success"
            log(f"刷写完成：{partition}")
            logger.info(f"[{task_id}] 刷写成功: {partition}")
        else:
            cls = classify_fastboot_result(output, ["flash", partition, image_path], proc.returncode)
            task["status"] = "error"
            task["error"] = output.strip()
            task["diagnosis"] = diagnose_error(output)
            task.update(cls)
            log(f"刷写失败：{output.strip()}")

            if task["diagnosis"]:
                log(f"解决办法：{task['diagnosis']}")

            logger.error(f"[{task_id}] 刷写失败: {output}")

    except Exception as e:
        task["status"] = "error"
        task["error"] = str(e)
        task["diagnosis"] = diagnose_error(str(e))
        task.update(classify_fastboot_result(str(e), ["flash", partition, image_path], 1))
        log(f"刷写失败：{str(e)}")

        if task["diagnosis"]:
            log(f"解决办法：{task['diagnosis']}")

        logger.error(f"[{task_id}] 刷写异常: {e}")


def flash_partition(partition: str, image_name: str,
                    source: str = "local",
                    rom_name: str = "",
                    extra: str = "",
                    allow_dangerous: bool = False) -> dict:
    """
    刷写分区（API入口）

    Args:
        partition: 分区名
        image_name: 镜像文件名
        source: 来源 (local/rom/public)
        rom_name: ROM包名（source=rom时需要）
        extra: 额外参数
        allow_dangerous: 是否允许高危分区

    Returns:
        结果字典
    """
    # 获取镜像路径
    try:
        image_path = get_image_path(source, image_name, rom_name)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    if not os.path.exists(image_path):
        return {"success": False, "error": "镜像不存在"}

    # 创建任务
    return create_flash_task(partition, image_path, extra, allow_dangerous)


def batch_precheck(steps: list, source: str, rom_name: str = "") -> dict:
    """
    批量刷机预校验

    Args:
        steps: 步骤列表
        source: 来源
        rom_name: ROM包名

    Returns:
        校验结果
    """
    missing = []
    dangerous = []
    warnings = []

    # 电量检查
    try:
        dev_result = get_device_info()
        dev_info = dev_result.get("info", {}) if dev_result.get("success") else {}
        soc = dev_info.get("battery_soc")
        if soc is not None:
            try:
                soc_val = int(soc)
                if soc_val < BATTERY_LOW_THRESHOLD:
                    warnings.append(f"设备电量较低（{soc_val}%），建议充电至 {BATTERY_LOW_THRESHOLD}% 以上再刷机")
            except (ValueError, TypeError):
                pass
    except Exception:
        pass

    for step in steps:
        if step["type"] != "flash":
            continue

        img_name = step["fileName"]
        part = step["part"]

        # 检查高危分区
        if is_dangerous_partition(part):
            dangerous.append({
                "stepName": f"{part} -> {img_name}",
                "fileName": img_name,
                "partition": part
            })

        # 检查文件存在
        try:
            image_path = get_image_path(source, img_name, rom_name)
            if not os.path.exists(image_path):
                missing.append({
                    "stepName": f"{part} -> {img_name}",
                    "fileName": img_name
                })
        except ValueError as e:
            missing.append({
                "stepName": f"{part} -> {img_name}",
                "fileName": img_name,
                "error": str(e)
            })

    return {
        "success": len(missing) == 0,
        "missingList": missing,
        "dangerousList": dangerous,
        "warnings": warnings,
        "totalSteps": len(steps),
        "flashSteps": len([s for s in steps if s["type"] == "flash"])
    }


# ======================================================================
# 公共辅助：时间戳与日志追加（供 core/batch_flasher.py 使用）
# ======================================================================


def _now():
    return time.time()


def _append_log(task: dict, msg: str):
    task.setdefault("logs", []).append(msg)
    task["logs"] = task["logs"][-TASK_LOG_LIMIT:]
    task["updated_at"] = _now()
    logger.info(f"[{task.get('id', 'batch')}] {msg}")
    persist_tasks()


# ----------------------------------------------------------------------
# 重新导出批量线刷接口（已拆分至 core/batch_flasher.py）
# 放在文件末尾，确保 _now / _append_log 先定义，避免循环导入。
# ----------------------------------------------------------------------
from core.batch_flasher import (  # noqa: E402
    create_batch_flash_task,
    cancel_batch_flash_task,
    get_latest_batch_task,
    _load_flash_history,
)
