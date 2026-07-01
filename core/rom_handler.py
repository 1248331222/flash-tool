# -*- coding: utf-8 -*-
# flash_tool/core/rom_handler.py
"""
core/rom_handler.py — ROM 类型识别、脚本解析
"""

import os
import glob
from typing import Tuple, List

from config import ROM_DIR, PUBLIC_DIR, logger
from core.step_engine import optimize_step_order
from core.utils import get_rom_base_name
from core.hydra import get_hydra_engine


# ======================================================================
# 模块: services/rom_handler.py
# ======================================================================


def detect_rom_type(rom_dir):
    """自动检测刷机包类型"""
    markers = {
        'xiaomi': ['images/', 'bat/', 'flash_all.bat', 'flash_all_except_data.bat'],
        'qualcomm': ['prog_emmc_firehose_*.mbn', 'rawprogram*.xml', 'patch*.xml'],
        'mtk': ['preloader_*.bin', 'lk_*.img', 'scatter*.txt'],
        'generic_fastboot': ['flash_all.bat', 'flash.bat'],
    }
    detected = []
    for rom_type, patterns in markers.items():
        for pat in patterns:
            if glob.glob(os.path.join(rom_dir, pat)):
                detected.append(rom_type)
                break
    return detected[0] if detected else 'unknown'


def resolve_rom_folder_name(rom_name: str) -> str:
    """兼容压缩包文件名和已解压项目目录名"""
    if rom_name and os.path.isdir(os.path.join(ROM_DIR, rom_name)):
        return rom_name
    return get_rom_base_name(rom_name)


def _read_and_parse_script(filepath):
    """
    读取并解析刷机脚本（公共逻辑）
    使用天树引擎解析。

    Args:
        filepath: 脚本文件的完整路径

    Returns:
        (success, result) — success=True 时 result 为
        (txt, steps, missing_files, hydra_result)
        hydra_result 为 HydraParseResult 实例。
        success=False 时 result 为 error 字符串
    """
    if not os.path.exists(filepath):
        return False, "脚本不存在"

    with open(filepath, "rb") as f:
        raw = f.read()

    # 尝试解码
    try:
        txt = raw.decode("gbk")
    except Exception:
        txt = raw.decode("utf-8", errors="ignore")

    # 推断 rom_dir（脚本所在目录的父目录通常是 ROM 包根目录）
    rom_dir = os.path.dirname(filepath)

    # === 天树引擎解析 ===
    hydra = get_hydra_engine()

    lower_path = filepath.lower()
    is_sh = lower_path.endswith('.sh')

    if is_sh:
        logger.info(f"SH 脚本（天树引擎解析）: {filepath}")
        result = hydra.parse(txt, script_type="sh", rom_dir=rom_dir, script_path=filepath)
    else:
        logger.info(f"BAT 脚本（天树引擎解析）: {filepath}")
        result = hydra.parse(txt, script_type="bat", rom_dir=rom_dir, script_path=filepath)

    if result.total_steps > 0:
        steps = _hydra_steps_to_old(result.steps)
        steps = optimize_step_order(steps)
        logger.info(f"天树引擎解析成功: {filepath}, 共 {len(steps)} 步")
        return True, (txt, steps, result.missing_files, result)

    # === 天树引擎未能解析时的回退处理 ===
    logger.warning(f"天树引擎解析为空（内容 {len(txt)} 字符）: {filepath}")
    lower_txt = txt.lower()
    if 'edl ' in lower_txt or 'edl.exe' in lower_txt or 'qdl ' in lower_txt or 'sahara' in lower_txt or 'firehose' in lower_txt or '9008' in lower_txt:
        return False, "该脚本使用的是 EDL（9008）模式刷机工具（edl/qdl），当前工具仅支持 Fastboot 模式线刷，无法解析此脚本。"
    elif 'miko' in lower_txt or 'miro' in lower_txt or 'qpst' in lower_txt or 'qfil' in lower_txt:
        return False, "该脚本使用的是高通专用刷机工具（QPST/QFIL/Miko），当前工具仅支持 Fastboot 模式线刷，无法解析此脚本。"
    elif 'sp flash' in lower_txt or 'mtk' in lower_txt or 'mediatek' in lower_txt or 'mrt' in lower_txt:
        return False, "该脚本使用的是 MTK（联发科）刷机工具，当前工具仅支持 Fastboot 模式线刷，无法解析此脚本。"
    elif 'fastboot' not in lower_txt:
        return False, "该脚本中未检测到 fastboot 命令，可能使用了其他刷机方式，当前工具仅支持 Fastboot 模式线刷。"
    else:
        return False, "脚本解析结果为空，该脚本格式可能暂不支持。此脚本可帮助改进天树引擎，请点击 📤 上传按钮提交样本。"


def _hydra_steps_to_old(hydra_steps):
    """将 HydraStep 列表转换为旧版 step dict 列表（兼容前端渲染）"""
    old_steps = []
    for hs in hydra_steps:
        # 从 raw 中提取 fastboot/adb 动词之前的 --xxx 前缀参数
        prefix_params = ""
        if hs.type in ("flash", "erase", "boot", "update") and hs.raw:
            # 去引号后分词：["%~dp0tools\\fastboot.exe", "--disable-verity", ..., "flash", "vbmeta_a", ...]
            # 找第一个 flash/erase/boot/update，取它之前所有 --xxx 参数
            tokens = hs.raw.replace('"', '').split()
            action_keywords = {'flash', 'erase', 'boot', 'update'}
            action_idx = -1
            for i, t in enumerate(tokens):
                if t.lower() in action_keywords:
                    action_idx = i
                    break
            if action_idx > 0:
                prefixes = [t for t in tokens[1:action_idx] if t.startswith('--')]
                if prefixes:
                    prefix_params = " ".join(prefixes)

        step = {
            "type": hs.type,
            "part": hs.part,
            "fileName": hs.fileName,
            "params": hs.params,
            "raw": hs.raw,
            "risk": hs.risk,
            "dynamic": hs.dynamic,
        }
        if prefix_params:
            step["prefixParams"] = prefix_params
        if hs.loop:
            step["loop"] = hs.loop
        if hs.call:
            step["call"] = hs.call
        if hs.condition:
            step["condition"] = hs.condition
        old_steps.append(step)
    return old_steps