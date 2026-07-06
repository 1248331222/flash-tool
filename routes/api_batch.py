#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Skytree Flasher / routes/api_batch.py
"""批量刷机任务路由 - 启动/状态/取消/导出日志/直接执行脚本

辅助函数（public_task / force_rewrite_fastboot_paths / inject_reconnect_wait /
_simulate_sh_execution）已拆分至 routes/api_batch_helpers.py，此处通过 import 引用。
"""

import os
import re
import shutil
import subprocess
import threading
import time

from flask import Blueprint, request, jsonify

from config import ROM_DIR, FASTBOOT_PATH, logger
from core.utils import api_err
from core.extractor import tasks, gen_task_id
from core.flasher import create_batch_flash_task, cancel_batch_flash_task, get_latest_batch_task
from core.rom_handler import resolve_rom_folder_name
from routes.api_batch_helpers import (
    public_task,
    force_rewrite_fastboot_paths,
    inject_reconnect_wait,
    _simulate_sh_execution,
)

batch_task_bp = Blueprint('batch_task', __name__, url_prefix='/api/batch-task')


@batch_task_bp.route('/export_log', methods=['GET'])
def export_batch_log():
    """导出结构化刷机日志，便于分享排错"""
    task = get_latest_batch_task()
    if not task:
        return api_err("没有刷机任务记录")

    log_lines = []
    log_lines.append(f"=== 刷机日志 ===")
    log_lines.append(f"任务ID: {task.get('id', 'N/A')}")
    log_lines.append(f"状态: {task.get('status', 'N/A')}")
    log_lines.append(f"总步骤: {task.get('step_total', 'N/A')}")
    log_lines.append(f"当前步骤: {task.get('current_index', 0) + 1}")
    log_lines.append(f"创建时间: {task.get('created_at', 'N/A')}")
    log_lines.append(f"更新时间: {task.get('updated_at', 'N/A')}")
    log_lines.append("")

    # 错误信息
    if task.get("error"):
        log_lines.append(f"错误: {task['error']}")
    if task.get("diagnosis"):
        log_lines.append(f"诊断: {task['diagnosis']}")
    if task.get("category"):
        log_lines.append(f"错误类别: {task['category']}")
    log_lines.append("")

    # 步骤列表
    steps = task.get("steps") or []
    log_lines.append("--- 步骤列表 ---")
    for i, step in enumerate(steps):
        stype = step.get("type", "?")
        part = step.get("part", "")
        fname = step.get("fileName", "")
        extra = ""
        if step.get("prefixParams"):
            extra += f" [参数: {step['prefixParams']}]"
        if step.get("cow_cleanup"):
            extra += " [COW动态清理]"
        if step.get("condition"):
            extra += f" [条件: {step['condition']}]"
        if stype == "flash":
            log_lines.append(f"  {i+1}. [刷写] {part} → {fname}{extra}")
        elif stype == "erase":
            log_lines.append(f"  {i+1}. [擦除] {part}{extra}")
        elif stype == "set_active":
            log_lines.append(f"  {i+1}. [设槽位] 激活 {part}")
        elif stype == "reboot":
            log_lines.append(f"  {i+1}. [重启] {part or '系统'}")
        else:
            log_lines.append(f"  {i+1}. [{stype}] {part}")
    log_lines.append("")

    # 执行日志
    logs = task.get("logs") or []
    log_lines.append("--- 执行日志 ---")
    for entry in logs:
        # logs 是字符串列表（日志行文本），不是 dict 列表
        if entry:
            log_lines.append(entry)

    content = "\n".join(log_lines)
    return jsonify({
        "success": True,
        "content": content,
        "filename": f"flash_log_{task.get('id', 'unknown')}.txt"
    })


@batch_task_bp.route('/start', methods=['POST'])
def start_batch_task():
    data = request.get_json(silent=True) or {}
    steps = data.get("steps") or []
    source = data.get("source") or "rom"
    rom_name = data.get("rom_name") or ""
    start_index = int(data.get("start_index") or 0)
    allow_dangerous = bool(data.get("allow_dangerous", False))

    # 25C：如果前端传了 hydra_summary，通过 Pipeline 检查阻断
    hydra_summary = data.get("hydra_summary")
    if hydra_summary:
        quality = hydra_summary.get("quality") or {}
        script_check = hydra_summary.get("script_resource_check") or {}

        blockers = []
        if quality.get("score", 100) < 55:
            blockers.append(f"解析质量评分过低（{quality['score']} 分），解析结果不可靠，不建议执行")

        missing = script_check.get("missing_files") or []
        if missing:
            msg = f"脚本引用的 {len(missing)} 个文件在 ROM 中未找到：{', '.join(missing[:3])}"
            if len(missing) > 3:
                msg += f" 等 {len(missing)} 个"
            blockers.append(msg)

        if blockers:
            return jsonify({"success": False, "error": "；".join(blockers), "blockers": blockers})

    result = create_batch_flash_task(
        steps=steps,
        source=source,
        rom_name=rom_name,
        start_index=start_index,
        allow_dangerous=allow_dangerous,
    )
    return jsonify(result)


@batch_task_bp.route('/status/<task_id>')
def batch_task_status(task_id):
    task = tasks.get(task_id)
    if not task or task.get("type") not in ("batch_flash", "direct_execute"):
        return jsonify({"success": False, "error": "任务不存在"}), 404
    return jsonify({"success": True, "task": public_task(task)})


@batch_task_bp.route('/latest')
def latest_batch_task():
    task = get_latest_batch_task()
    if not task:
        return jsonify({"success": True, "task": None})
    return jsonify({"success": True, "task": public_task(task)})


@batch_task_bp.route('/cancel/<task_id>', methods=['POST'])
def cancel_batch_task(task_id):
    return jsonify(cancel_batch_flash_task(task_id))


@batch_task_bp.route('/direct_execute', methods=['POST'])
def direct_execute_script():
    """
    v3.0.3: 直接执行 .sh 脚本。
    1. force_rewrite_fastboot_paths() — 预处理替换硬编码 fastboot 路径
    2. inject_reconnect_wait() — 注入等待函数 + fastboot() 命令覆盖
    3. 创建 ROM 目录 fastboot 软链接（覆盖 ./fastboot 写法）
    4. 单一 bash 进程执行，环境变量注入 FASTBOOT 路径
    """
    data = request.get_json(silent=True) or {}
    sh_content = data.get("sh_content", "")
    rom_name = data.get("rom_name", "")
    dry_run = data.get("dry_run", False)

    if not sh_content:
        return jsonify({"success": False, "error": "脚本内容为空"})

    try:
        script_dir = os.path.join(ROM_DIR, resolve_rom_folder_name(rom_name)) if rom_name else ROM_DIR
        os.makedirs(script_dir, exist_ok=True)

        # 1. 预处理：替换硬编码 fastboot 路径为 $FASTBOOT
        try:
            rewritten_content = force_rewrite_fastboot_paths(sh_content)
        except Exception as e:
            logger.warning(f"force_rewrite_fastboot_paths 失败，使用原文: {e}")
            rewritten_content = sh_content

        # 2. 注入重连等待函数 + fastboot() 命令覆盖
        try:
            injected_content = inject_reconnect_wait(rewritten_content)
        except Exception as e:
            logger.warning(f"inject_reconnect_wait 失败，使用预处理结果: {e}")
            injected_content = rewritten_content

        # 3. 在 ROM 目录下创建 fastboot 软链接（覆盖 ./fastboot 写法）
        fb_path = FASTBOOT_PATH or shutil.which("fastboot") or "fastboot"
        fb_link = os.path.join(script_dir, 'fastboot')
        try:
            if os.path.islink(fb_link) or os.path.exists(fb_link):
                os.remove(fb_link)
            os.symlink(fb_path, fb_link)
        except Exception:
            pass  # 软链接创建失败不影响执行（函数覆盖兜底）

        sh_path = os.path.join(script_dir, '_converted_flash.sh')
        with open(sh_path, 'w', encoding='utf-8') as f:
            f.write(injected_content)
        os.chmod(sh_path, 0o755)

        task_id = gen_task_id()
        tasks[task_id] = {
            "type": "direct_execute",
            "status": "running",
            "phase": "executing",
            "created_at": time.time(),
            "sh_path": sh_path,
            "rom_name": rom_name,
            "dry_run": dry_run,
            "total_lines": injected_content.count('\n'),
            "current_line": 0,
            "output": [],
            "errors": [],
            "task_id": task_id,
        }

        def _run_script():
            # socketio 由 app.py 注入到 routes.socketio，此处延迟导入获取最新引用
            # #2: 同时导入 emit_task_complete 以便在任务完成时推送事件
            from routes.socketio import emit_task_complete
            task = tasks.get(task_id)
            if not task:
                return
            proc = None
            try:
                if dry_run:
                    _simulate_sh_execution(task, injected_content)
                    # #2: 推送任务完成事件（成功）
                    emit_task_complete(task_id, True, "执行完成")
                    return

                fb_path = FASTBOOT_PATH or shutil.which("fastboot") or "fastboot"
                env = os.environ.copy()
                env["FASTBOOT"] = fb_path
                env["PATH"] = os.path.dirname(fb_path) + ":" + env.get("PATH", "")

                # #29: 合并 stderr 到 stdout，避免单独读取 stderr 导致管道死锁
                proc = subprocess.Popen(
                    ['bash', sh_path],
                    cwd=script_dir,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )

                for line in iter(proc.stdout.readline, ''):
                    line = line.rstrip('\n')
                    if line:
                        task["output"].append(line)
                        task["current_line"] += 1
                        # #15: 包裹 emit 调用，防止推送异常导致任务卡死
                        try:
                            socketio.emit('task_progress', {
                                "task_id": task_id,
                                "type": "direct_execute",
                                "line": line,
                                "current_line": task["current_line"],
                                "total_lines": task["total_lines"],
                            })
                        except Exception as emit_err:
                            logger.warning(f"emit task_progress 失败: {emit_err}")

                proc.stdout.close()
                proc.wait()

                if proc.returncode == 0:
                    task["status"] = "completed"
                    task["phase"] = "completed"
                    # #2: 推送任务完成事件（成功）
                    emit_task_complete(task_id, True, "执行完成")
                else:
                    task["status"] = "failed"
                    task["phase"] = "failed"
                    err_msg = f"脚本退出码: {proc.returncode}"
                    task["errors"].append(err_msg)
                    # #2: 推送任务完成事件（失败）
                    emit_task_complete(task_id, False, err_msg)

            except Exception as e:
                task["status"] = "failed"
                task["phase"] = "failed"
                task["errors"].append(str(e))
                logger.error(f"直接执行脚本失败: {e}")
                # #2: 推送任务完成事件（异常）
                emit_task_complete(task_id, False, str(e))
            finally:
                # #15: 确保子进程被终止，避免产生孤儿子进程
                try:
                    if proc is not None and proc.poll() is None:
                        proc.terminate()
                        try:
                            proc.wait(timeout=5)
                        except Exception:
                            try:
                                proc.kill()
                            except Exception:
                                pass
                except Exception:
                    pass
                try:
                    if sh_path and os.path.exists(sh_path):
                        os.remove(sh_path)
                except:
                    pass
                try:
                    if fb_link and (os.path.islink(fb_link) or os.path.exists(fb_link)):
                        os.remove(fb_link)
                except:
                    pass

        threading.Thread(target=_run_script, daemon=True).start()

        return jsonify({"success": True, "task_id": task_id})

    except Exception as e:
        logger.error(f"创建直接执行任务失败: {e}")
        return jsonify({"success": False, "error": str(e)})