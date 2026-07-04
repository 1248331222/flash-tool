# -*- coding: utf-8 -*-
# Skytree Flasher / core/rom_handler.py
"""
core/rom_handler.py — ROM 类型识别、脚本解析
"""

import os
import glob
from typing import Tuple, List, Dict

from config import ROM_DIR, PUBLIC_DIR, logger
from core.step_engine import optimize_step_order
from core.utils import get_rom_base_name, sanitize_path
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
        # 将解析出的相对路径映射到 ROM 包内的绝对路径
        steps, found_files, missing_files = _resolve_image_paths(steps, rom_dir)
        # 静态展开通配符 for 循环（如 %%f → images/ 下实际文件）
        steps = _expand_wildcard_steps(steps, rom_dir)
        steps = optimize_step_order(steps)
        logger.info(f"天树引擎解析成功: {filepath}, 共 {len(steps)} 步")
        return True, (txt, steps, missing_files, result)

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


def _resolve_image_paths(steps: List[dict], rom_dir: str) -> Tuple[List[dict], Dict[str, str], List[str]]:
    """
    将步骤中的相对路径 fileName 解析为 ROM 包内的绝对路径。

    Args:
        steps: 旧版步骤列表 [{"type":"flash","fileName":"./images\\boot.img",...}, ...]
        rom_dir: ROM 包解压根目录

    Returns:
        (steps, found_files, missing_files)
        - steps: 更新后的步骤列表（flash 步骤加 imagePath 字段）
        - found_files: {原始fileName → 绝对路径}
        - missing_files: 未找到的 fileName 列表
    """
    found_files = {}
    missing_files = []

    for step in steps:
        if step["type"] not in ("flash",):
            continue
        raw_name = step.get("fileName", "")
        if not raw_name:
            continue
        # 标准化路径分隔符，去除引号、前导 ./ 和多余的空格
        rel = raw_name.strip().strip('"').replace("\\", "/").lstrip("/").lstrip("./")
        abs_path = os.path.abspath(os.path.join(rom_dir, rel))
        if os.path.exists(abs_path):
            found_files[raw_name] = abs_path
            step["imagePath"] = abs_path
        else:
            missing_files.append(raw_name)

    return steps, found_files, missing_files


def _expand_wildcard_steps(steps: List[dict], rom_dir: str) -> List[dict]:
    """
    将通配符占位步骤（%%~nf_a、%%~nf_b）静态展开为实际的 flash 步骤。

    当检测到步骤 part 包含 %% 时，扫描 rom_dir/images/ 目录下的实际镜像文件，
    展开为对应的分区名 + 镜像路径，并正确标记 A/B 双槽。

    Args:
        steps: 步骤列表
        rom_dir: ROM 包根目录

    Returns:
        List[dict]: 展开后的步骤列表
    """
    import re
    new_steps = []
    images_dir = os.path.join(rom_dir, 'images')

    # 收集需要跳过的分区——已在前面步骤中单独 flash 过的（不在通配符循环内）
    skip_names = set()
    for s in steps:
        if s['type'] == 'flash' and not ('%%' in str(s.get('part', ''))):
            p = s.get('part', '') or ''
            # modem_a → modem, vbmeta_system_a → vbmeta_system
            base = re.sub(r'_[ab]$', '', p)
            if base:
                skip_names.add(base)

    # 如果不存在 images 目录或没有 *.img 文件，无法展开
    if not os.path.isdir(images_dir):
        return steps

    img_files = sorted([
        f for f in os.listdir(images_dir)
        if f.lower().endswith('.img') and os.path.isfile(os.path.join(images_dir, f))
    ])

    if not img_files:
        return steps

    expanded = False  # 只展开一次

    for step in steps:
        part = step.get('part') or ''

        # 检测通配符占位
        if (('%%~nf_a' in part or '%%~nf_b' in part) and not expanded):
            expanded = True

            for img_file in img_files:
                # 提取基础名（不带 .img 后缀）
                base_name = os.path.splitext(img_file)[0]

                # 检查是否应该跳过：被前面步骤单独 flash 过的基础分区名
                #（modem, recovery, vbmeta, vbmeta_system, vbmeta_vendor, super）
                if base_name in skip_names:
                    continue

                img_abs_path = os.path.abspath(os.path.join(images_dir, img_file))

                for slot in ('a', 'b'):
                    partition = f'{base_name}_{slot}'
                    new_step = {
                        **{k: v for k, v in step.items() if k != 'part' and k != 'fileName' and k != 'imagePath'},
                        "type": "flash",
                        "part": partition,
                        "fileName": img_file,
                        "imagePath": img_abs_path,
                        "raw": f'flash {partition} {img_abs_path}',
                        "risk": "MEDIUM",
                    }
                    new_steps.append(new_step)

            continue  # 跳过原占位步骤

        elif '%%~nf_a' in part or '%%~nf_b' in part:
            continue  # 已经展开过了，跳过

        new_steps.append(step)

    return new_steps


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