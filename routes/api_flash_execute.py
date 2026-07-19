# Skytree Flasher / routes/api_flash_execute.py
"""步骤执行 API — 接收前端解析器产出的步骤列表，按顺序执行 fastboot/adb 命令"""

import os, re, subprocess, threading, time
from flask import Blueprint, request, jsonify

from config import ROM_DIR, FASTBOOT_PATH, ADB_PATH, BATCH_PROC_WAIT_TIMEOUT, logger
from core.flasher import create_batch_flash_task

flash_exec_bp = Blueprint('flash_exec', __name__, url_prefix='/api/flash')


@flash_exec_bp.route('/execute', methods=['POST'])
def execute_steps():
    """
    接收前端解析器产出的步骤列表，按顺序执行。

    请求体:
    {
        "steps": [
            {
                "type": "flash",          // flash | erase | reboot | set_active | getvar | oem | flashing | shell | raw
                "partition": "boot",
                "imagePath": "/sdcard/.../boot.img",
                "raw": "fastboot flash boot /sdcard/.../boot.img",
                "risk": "MEDIUM",
                "params": ""
            }
        ],
        "extra_args": ""         // 脚本整体参数（替换 %1 %2 等）
    }
    """
    data = request.get_json(silent=True) or {}
    steps = data.get('steps') or []
    extra_args = data.get('extra_args', '')

    if not steps:
        return jsonify({"success": False, "error": "步骤列表为空"})

    # 将前端步骤格式转换为后端 batch_flasher 需要的格式
    backend_steps = []
    for i, step in enumerate(steps):
        raw = step.get('raw', '')

        # 替换占位符 %1 %2 ... %* → extra_args
        if '%' in raw:
            # 将 %1, %2, ..., %* 按顺序替换为 extra_args 按空格分割的参数
            arg_parts = extra_args.split() if extra_args else []
            def _replace_placeholder(m):
                if m.group(1) == '*':
                    return extra_args  # 空字符串也会替换掉 %*
                idx = int(m.group(1))
                if 1 <= idx <= len(arg_parts):
                    return arg_parts[idx - 1]
                return ''  # 无对应参数时移除占位符
            raw = re.sub(r'%(\d+|\*)', _replace_placeholder, raw)
            # 清理多余空格
            raw = re.sub(r'\s+', ' ', raw).strip()

        backend_steps.append({
            "type": step.get('type', 'raw'),
            "part": step.get('partition') or step.get('target', ''),
            "fileName": step.get('imagePath', ''),
            "imagePath": step.get('imagePath', ''),
            "raw": raw,
            "risk": step.get('risk', 'MEDIUM'),
            "params": step.get('params', ''),
            "format": step.get('format', ''),
            "inputFile": step.get('inputFile', ''),
            "outputFile": step.get('outputFile', ''),
            "removeSource": step.get('removeSource', False),
        })

    try:
        start_index = int(data.get('start_index', 0))
        step_offset = int(data.get('step_offset', 0))
        step_total = int(data.get('step_total', 0))

        result = create_batch_flash_task(
            steps=backend_steps,
            source="webusb_parser",
            rom_name="",
            start_index=start_index,
            allow_dangerous=True,
            step_offset=step_offset,
            step_total=step_total,
        )
        return jsonify(result)
    except Exception as e:
        logger.error(f"创建步骤执行任务失败: {e}")
        return jsonify({"success": False, "error": str(e)})