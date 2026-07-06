# -*- coding: utf-8 -*-
# Skytree Flasher / core/extractor.py
"""
core/extractor.py — ROM 包解压任务管理
从单文件版提取，函数逻辑保持不变。

tasks 字典为本模块全局共享，其他模块通过 import 使用。
emit_task_progress 通过延迟导入避免与 routes.socketio 的循环依赖。
"""

import os
import re
import json
import time
import uuid
import shutil
import zipfile
import tarfile
import threading
import subprocess
from typing import Callable, Optional

from config import (
    TASK_STATE_FILE,
    ROM_DIR,
    PUBLIC_DIR,
    SUPPORTED_ROM_SUFFIXES,
    TASK_LOG_LIMIT,
    logger,
)
from core.utils import (
    sanitize_path,
    validate_rom_filename,
    get_rom_base_name,
    diagnose_error,
)


# ======================================================================
# 模块: services/extractor.py
# ======================================================================

# 任务存储（全局共享，其他模块 import 本字典）
tasks = {}
_tasks_lock = threading.Lock()  # #23: 保护 tasks 并发访问


def _load_tasks():
    """加载最近任务状态，运行中的旧任务标记为已中断"""
    if not os.path.exists(TASK_STATE_FILE):
        return {}
    try:
        with open(TASK_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        for t in data.values():
            if t.get("status") in ("pending", "running"):
                t["status"] = "interrupted"
                t["error"] = t.get("error") or "服务重启或任务中断"
        return data
    except Exception as e:
        logger.warning(f"加载任务状态失败: {e}")
        return {}


def persist_tasks():
    """持久化任务状态，减少页面刷新或服务重启后的信息丢失"""
    try:
        task_dir = os.path.dirname(TASK_STATE_FILE)
        if task_dir:
            os.makedirs(task_dir, exist_ok=True)
        slim = {}
        for tid, task in list(tasks.items())[-80:]:
            t = dict(task)
            t["logs"] = (t.get("logs") or [])[-TASK_LOG_LIMIT:]
            slim[tid] = t
        tmp = TASK_STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(slim, f, ensure_ascii=False, indent=2)
        os.replace(tmp, TASK_STATE_FILE)
    except Exception as e:
        logger.debug(f"持久化任务状态失败: {e}")


tasks.update(_load_tasks())


def gen_task_id() -> str:
    """生成任务ID"""
    return str(uuid.uuid4())[:8]


def create_extract_task(src_path: str, target_dir: str) -> str:
    """
    创建解压任务

    Args:
        src_path: 源文件路径
        target_dir: 目标目录

    Returns:
        任务ID
    """
    # 延迟导入，避免与 routes.socketio 循环依赖
    from routes.socketio import emit_task_progress

    tid = gen_task_id()
    tasks[tid] = {
        "type": "extract",
        "status": "pending",
        "progress": 0,
        "logs": [],
        "error": "",
        "created_at": time.time(),
        "updated_at": time.time(),
        "src_path": src_path,
        "target_dir": target_dir
    }
    persist_tasks()

    # 启动后台线程
    threading.Thread(
        target=extract_worker,
        args=(tid, src_path, target_dir),
        kwargs={"progress_callback": lambda p, m: emit_task_progress(tid, p, m)},
        daemon=True
    ).start()

    logger.info(f"创建解压任务: {tid}, 源: {src_path}")
    return tid


def extract_worker(task_id: str, src_path: str, target_dir: str,
                   progress_callback: Optional[Callable] = None):
    """
    解压任务工作函数

    Args:
        task_id: 任务ID
        src_path: 源文件路径
        target_dir: 目标目录
        progress_callback: 进度回调函数 (progress, message)
    """
    task = tasks[task_id]
    task["status"] = "running"
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
        name_lower = os.path.basename(src_path).lower()
        tmp_dir = f"{target_dir}.extracting-{task_id}"
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)
        os.makedirs(tmp_dir, exist_ok=True)
        log(f"开始解压：{os.path.basename(src_path)}")

        # ZIP 文件
        if name_lower.endswith('.zip'):
            extract_zip(src_path, tmp_dir, task, log, progress_callback)

        # TAR 文件（包括 .tar.gz, .tar.bz2 等）
        elif name_lower.endswith(('.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tbz2', '.tar.md5')):
            extract_tar(src_path, tmp_dir, task, log, progress_callback)

        # 7z 文件
        elif name_lower.endswith('.7z'):
            extract_7z(src_path, tmp_dir, task, log, progress_callback)

        # RAR 文件
        elif name_lower.endswith('.rar'):
            extract_rar(src_path, tmp_dir, task, log, progress_callback)

        else:
            raise Exception("不支持的压缩格式")

        validate_extracted_tree(tmp_dir)
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)
        os.replace(tmp_dir, target_dir)

        task["status"] = "success"
        task["progress"] = 100
        task["updated_at"] = time.time()
        log("解压完成")
        persist_tasks()

    except Exception as e:
        task["status"] = "error"
        task["error"] = str(e)
        task["diagnosis"] = diagnose_error(str(e))
        task["updated_at"] = time.time()
        log(f"解压失败：{str(e)}")
        logger.error(f"[{task_id}] 解压失败: {e}")
        try:
            tmp_dir = f"{target_dir}.extracting-{task_id}"
            if os.path.exists(tmp_dir):
                shutil.rmtree(tmp_dir)
        except Exception:
            pass
        persist_tasks()


def extract_zip(src_path: str, target_dir: str, task: dict,
                log: Callable, progress_callback: Optional[Callable] = None):
    """解压 ZIP 文件"""
    with zipfile.ZipFile(src_path, 'r') as zf:
        members = zf.infolist()
        total = len(members)

        for i, member in enumerate(members):
            # 处理中文文件名
            try:
                member_name = member.filename.encode('cp437').decode('gbk')
            except:
                member_name = member.filename

            target_path = safe_member_path(target_dir, member_name)
            mode = (member.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                raise Exception(f"ZIP包含符号链接，已阻止：{member_name}")

            if member.is_dir():
                os.makedirs(target_path, exist_ok=True)
            else:
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with zf.open(member) as src, open(target_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst)

            # 更新进度
            progress = int((i + 1) / total * 100)
            task["progress"] = progress

            if progress_callback and i % 10 == 0:  # 每10个文件回调一次
                progress_callback(progress, f"解压: {member_name}")

        task["status"] = "success"
        log("ZIP解压完成")


def safe_member_path(base_dir: str, member_name: str) -> str:
    """计算安全解压路径，阻止绝对路径和 .. 逃逸"""
    if not member_name or '\x00' in member_name:
        raise Exception("压缩包包含非法空路径")
    raw = member_name.replace("\\", "/")
    if raw.startswith("/") or re.match(r'^[A-Za-z]:/', raw):
        raise Exception(f"压缩包包含绝对路径：{member_name}")
    normalized = os.path.normpath(raw)
    if normalized in ("", ".") or normalized.startswith("../") or normalized == "..":
        raise Exception(f"压缩包包含危险路径：{member_name}")
    full = os.path.abspath(os.path.join(base_dir, normalized))
    base = os.path.abspath(base_dir)
    if full != base and not full.startswith(base + os.sep):
        raise Exception(f"压缩包路径越界：{member_name}")
    return full


def validate_extracted_tree(base_dir: str):
    """检查解压后的目录树，阻止符号链接或路径逃逸"""
    # 用 realpath 而非 abspath，避免 Termux 中 storage 符号链接导致误判
    base = os.path.realpath(base_dir)
    for root, dirs, files in os.walk(base, followlinks=False):
        for name in dirs + files:
            full = os.path.join(root, name)
            real = os.path.realpath(full)
            if os.path.islink(full):
                raise Exception(f"解压内容包含符号链接，已阻止：{os.path.relpath(full, base)}")
            if real != base and not real.startswith(base + os.sep):
                raise Exception(f"解压内容越界，已阻止：{os.path.relpath(full, base)}")


def extract_tar(src_path: str, target_dir: str, task: dict,
                log: Callable, progress_callback: Optional[Callable] = None):
    """解压 TAR 文件"""
    with tarfile.open(src_path, 'r:*') as tf:
        members = tf.getmembers()
        total = len(members)

        for i, member in enumerate(members):
            # 处理中文文件名
            try:
                member.name = member.name.encode('cp437').decode('gbk')
            except:
                pass

            target_path = safe_member_path(target_dir, member.name)
            if member.issym() or member.islnk():
                raise Exception(f"TAR包含链接文件，已阻止：{member.name}")
            if member.isdir():
                os.makedirs(target_path, exist_ok=True)
            elif member.isfile():
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                src = tf.extractfile(member)
                if src is None:
                    raise Exception(f"无法读取TAR成员：{member.name}")
                with src, open(target_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
            else:
                raise Exception(f"TAR包含不支持的特殊文件，已阻止：{member.name}")

            # 更新进度
            progress = int((i + 1) / total * 100)
            task["progress"] = progress

            if progress_callback and i % 10 == 0:
                progress_callback(progress, f"解压: {member.name}")

        task["status"] = "success"
        log("TAR解压完成")


def extract_7z(src_path: str, target_dir: str, task: dict,
               log: Callable, progress_callback: Optional[Callable] = None):
    """解压 7z 文件"""
    if not shutil.which('7z'):
        raise Exception("缺少7z工具，请手动安装 p7zip")

    proc = subprocess.Popen(
        ['7z', 'x', '-y', '-bb1', f'-o{target_dir}', src_path],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )

    for line in proc.stdout:
        line = line.strip()
        if line:
            log(line)
            # 7z 输出包含进度信息
            if progress_callback and '%' in line:
                try:
                    # 尝试解析进度
                    match = re.search(r'(\d+)%', line)
                    if match:
                        progress = int(match.group(1))
                        task["progress"] = progress
                        progress_callback(progress, line)
                except:
                    pass

    try:
        proc.wait(timeout=300)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise Exception("7z解压超时（300秒），已终止")

    if proc.returncode != 0:
        raise Exception("7z解压失败，压缩包损坏")

    # 解压后检查路径逃逸（#18）
    base = os.path.realpath(target_dir)
    for root, dirs, files in os.walk(target_dir, followlinks=False):
        for name in dirs + files:
            full = os.path.join(root, name)
            real = os.path.realpath(full)
            if real != base and not real.startswith(base + os.sep):
                raise Exception(f"解压内容越界，已阻止：{os.path.relpath(full, target_dir)}")

    task["status"] = "success"
    log("7z解压完成")


def extract_rar(src_path: str, target_dir: str, task: dict,
                log: Callable, progress_callback: Optional[Callable] = None):
    """解压 RAR 文件"""
    if not shutil.which('unrar'):
        raise Exception("缺少unrar工具，请手动安装 unrar")

    proc = subprocess.Popen(
        ['unrar', 'x', '-y', src_path, target_dir],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )

    for line in proc.stdout:
        line = line.strip()
        if line:
            log(line)

    try:
        proc.wait(timeout=300)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise Exception("rar解压超时（300秒），已终止")

    if proc.returncode != 0:
        raise Exception("rar解压失败，压缩包损坏")

    # 解压后检查路径逃逸（#18）
    base = os.path.realpath(target_dir)
    for root, dirs, files in os.walk(target_dir, followlinks=False):
        for name in dirs + files:
            full = os.path.join(root, name)
            real = os.path.realpath(full)
            if real != base and not real.startswith(base + os.sep):
                raise Exception(f"解压内容越界，已阻止：{os.path.relpath(full, target_dir)}")

    task["status"] = "success"
    log("RAR解压完成")


def get_task_status(task_id: str) -> dict:
    """
    获取任务状态

    Args:
        task_id: 任务ID

    Returns:
        任务状态字典
    """
    with _tasks_lock:
        t = tasks.get(task_id)
        if not t:
            return {"success": False, "error": "任务不存在"}
        return {
            "success": True,
            "task_id": task_id,
            "type": t["type"],
            "status": t["status"],
            "progress": t.get("progress", 0),
            "logs": list(t.get("logs", [])),
            "error": t.get("error", ""),
            "diagnosis": t.get("diagnosis", "")
        }


def start_extract_from_public(rom_name: str) -> dict:
    """
    从公共目录解压 ROM 包

    Args:
        rom_name: ROM 包文件名

    Returns:
        结果字典，包含 task_id
    """
    # 校验文件名
    validate_rom_filename(rom_name)

    # 构建路径
    src_path = sanitize_path(PUBLIC_DIR, rom_name)

    if not os.path.exists(src_path):
        return {"success": False, "error": "文件不存在"}

    # 目标目录
    rom_folder = get_rom_base_name(rom_name)
    target_dir = os.path.join(ROM_DIR, rom_folder)

    # 清理旧目录
    try:
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)
        os.makedirs(target_dir, exist_ok=True)
    except Exception as e:
        return {"success": False, "error": str(e)}

    # 创建任务
    task_id = create_extract_task(src_path, target_dir)

    return {
        "success": True,
        "task_id": task_id,
        "msg": "解压任务已启动",
        "target_dir": target_dir
    }