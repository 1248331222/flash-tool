# -*- coding: utf-8 -*-
# flash_tool/core/rom_handler.py
"""
core/rom_handler.py — ROM 类型识别、脚本复杂度检测、脚本解析
BAT -> Shell 转换逻辑已拆分至 core/bat_converter.py，函数逻辑保持不变。
"""

import os
import re
import glob
import time
import subprocess
from typing import Tuple, List

from config import ROM_DIR, PUBLIC_DIR, FASTBOOT_PATH, logger
from core.bat_parser import parse_bat_script
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


def detect_script_complexity(content: str, script_path: str = '') -> Tuple[bool, str]:
    """
    v3.0.7: 基于变量展开后的语义判断复杂度
    先做完整变量展开，再检查是否还有无法静态解析的语法
    """
    lines = content.split('\n')
    # 预扫描变量
    variables = {}
    for line in lines:
        m = re.match(r'^set\s+"?(\w+)=(.*?)"?$', line, re.IGNORECASE)
        if m:
            variables[m.group(1).upper()] = m.group(2)

    def resolve(text: str) -> str:
        if script_path:
            sp_abs = os.path.abspath(script_path)
            sp_dir = os.path.dirname(sp_abs)
            sp_name = os.path.basename(sp_abs)
            sp_base, sp_ext = os.path.splitext(sp_name)
            for mod, val in [('~dp0', sp_dir + os.sep), ('~n0', sp_base),
                             ('~x0', sp_ext), ('~nx0', sp_name)]:
                text = text.replace('%' + mod, val)
        for _ in range(10):
            prev = text
            text = re.sub(r'!(\w+)!', lambda m: variables.get(m.group(1).upper(), m.group(0)), text)
            text = re.sub(r'%(?!\w+%)(\w+)%', lambda m: variables.get(m.group(1).upper(), m.group(0)), text)
            if text == prev:
                break
        return text

    for line in lines:
        stripped = line.strip().lstrip('@').strip()
        if not stripped:
            continue
        expanded = resolve(stripped)
        lower = expanded.lower()

        # ===== 绝对拦截（展开后仍有 = 真复杂）=====
        if re.match(r'^goto\s+\w', lower):
            return True, "goto 跳转"
        if re.match(r'^shift\b', lower):
            return True, "shift 参数移位"
        if re.match(r'^call\s+\w+\.(bat|cmd)', lower):
            return True, "call 外部批处理"
        # for /f 命令输出捕获
        if re.match(r'^for\s+/f\s+.*\s+in\s*\(\s*[\'"]', lower):
            return True, "for /f 命令输出捕获"
        # for /r /d
        if re.match(r'^for\s+/[rd]\b', lower):
            return True, "for /r 或 for /d 递归遍历"
        # if errorlevel
        if re.match(r'^if\s+.*errorlevel', lower):
            return True, "if errorlevel"
        # if defined
        if re.match(r'^if\s+.*\bdefined\b', lower):
            return True, "if defined"
        # else 分支
        if re.match(r'^\)\s*else\s*\(', lower):
            return True, "else 分支"

        # if 比较：展开后仍含变量 → 未定义变量
        cm = re.match(r'^if\s+(not\s+)?(.+?)\s+(equ|neq|lss|leq|gtr|geq|==)\s+(.+?)\s*\(', lower)
        if cm:
            left, right = cm.group(2).strip(), cm.group(4).strip()
            if '%' in left or '%' in right or '!' in left or '!' in right:
                return True, "if 比较含未定义变量"

        # if exist：展开后路径仍含变量
        em = re.match(r'^if\s+(not\s+)?exist\s+["\']?([^"\'(]+)', lower)
        if em:
            path = em.group(2).strip()
            if '%' in path or '!' in path:
                return True, "if exist 路径含未定义变量"

        # for 列表：展开后仍含变量
        fm = re.match(r'^for\s+%%\w+\s+in\s*\(([^)]+)\)', lower)
        if fm and '%' in fm.group(1):
            return True, "for 列表含未定义变量"

    return False, ""


def _read_and_parse_script(filepath):
    """
    读取并解析刷机脚本（公共逻辑）
    v3.1.0: 集成 Hydra 九头蛇动态解析引擎，支持 BAT 和 SH 脚本解析
    保留原有 parse_bat_script 作为 BAT 回退方案

    Args:
        filepath: 脚本文件的完整路径

    Returns:
        (success, result) — success=True 时 result 为 (txt, steps, is_complex, is_native_sh, complex_reason, missing_files)，
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

    # 检测脚本类型
    lower_path = filepath.lower()
    is_native_sh = lower_path.endswith('.sh')

    # 推断 rom_dir（脚本所在目录的父目录通常是 ROM 包根目录）
    rom_dir = os.path.dirname(filepath)

    # === Hydra 解析路径 ===
    hydra = get_hydra_engine()

    if is_native_sh:
        # SH 脚本：直接用 Hydra 解析
        logger.info(f"SH 脚本（Hydra 解析模式）: {filepath}")
        result = hydra.parse(txt, script_type="sh", rom_dir=rom_dir, script_path=filepath)

        if result.total_steps > 0:
            # 将 HydraStep 转换为旧版 step 格式
            steps = _hydra_steps_to_old(result.steps)
            steps = optimize_step_order(steps)
            logger.info(f"Hydra 解析 SH 成功: {filepath}, 共 {len(steps)} 步")
            # SH 脚本是否视为"原生"取决于复杂度：可完全解析=False，需要执行追踪=True
            sh_is_native = not result.is_simple
            return True, (txt, steps, not result.is_simple, sh_is_native,
                         result.complex_reason if not result.is_simple else "",
                         result.missing_files)
        else:
            # SH 解析为空，回退到原始直接执行模式
            logger.info(f"SH 脚本（直接执行模式）: {filepath}")
            return True, (txt, [], False, True, "", [])

    # === BAT 脚本：先用 Hydra 解析 ===
    logger.info(f"BAT 脚本（Hydra 解析）: {filepath}")
    result = hydra.parse(txt, script_type="bat", rom_dir=rom_dir, script_path=filepath)

    if result.total_steps > 0:
        # Hydra 解析成功
        steps = _hydra_steps_to_old(result.steps)
        steps = optimize_step_order(steps)
        logger.info(f"Hydra 解析 BAT 成功: {filepath}, 共 {len(steps)} 步"
                    + (f"（含 {result.dynamic_commands} 个动态命令）" if result.dynamic_commands else ""))
        return True, (txt, steps, not result.is_simple, False,
                     result.complex_reason if not result.is_simple else "",
                     result.missing_files)

    # === 回退：旧版 parse_bat_script（Hydra 未能解析时） ===
    logger.info(f"BAT 脚本（回退到旧版解析器）: {filepath}")
    is_complex, complex_reason = detect_script_complexity(txt, filepath)

    if is_complex:
        logger.info(f"复杂 BAT 脚本（需用户手动转换）: {filepath}, 原因: {complex_reason}")
        fb_path_hint = FASTBOOT_PATH or '/data/data/com.termux/files/home/.termux-adb/fastboot'
        header = (
            ":: ============================================================\n"
            ":: [Termux 线刷工具提示] 此脚本包含复杂语法，无法自动解析。\n"
            ":: 请转换为 Bash (.sh) 格式后粘贴到下方输入框执行。\n"
            f":: 内置免root fastboot 路径: {fb_path_hint}\n"
            ":: 转换建议: 将所有 fastboot.exe 路径替换为 $FASTBOOT 或直接使用 fastboot 命令。\n"
            ":: ============================================================\n\n"
        )
        txt = header + txt
        return True, (txt, [], True, False, complex_reason, [])

    # 旧版解析器
    steps, missing_files = parse_bat_script(txt, rom_dir, filepath)

    if len(steps) == 0:
        logger.warning(f"脚本解析为空（内容 {len(txt)} 字符）: {filepath}")
        lower_txt = txt.lower()
        if 'edl ' in lower_txt or 'edl.exe' in lower_txt or 'qdl ' in lower_txt or 'sahara' in lower_txt or 'firehose' in lower_txt or '9008' in lower_txt:
            return False, "该脚本使用的是 EDL（9008）模式刷机工具（edl/qdl），当前工具仅支持 Fastboot 模式线刷，无法解析此脚本。"
        elif 'miko' in lower_txt or 'miro' in lower_txt or 'qpst' in lower_txt or 'qfil' in lower_txt:
            return False, "该脚本使用的是高通专用刷机工具（QPST/QFIL/Miko），当前工具仅支持 Fastboot 模式线刷，无法解析此脚本。"
        elif 'sp flash' in lower_txt or 'mtk' in lower_txt or 'mediatek' in lower_txt or 'mrt' in lower_txt:
            return False, "该脚本使用的是 MTK（联发科）刷机工具，当前工具仅支持 Fastboot 模式线刷，无法解析此脚本。"
        elif 'fastboot' not in lower_txt:
            return False, "该脚本中未检测到 fastboot 命令，可能使用了其他刷机方式，当前工具仅支持 Fastboot 模式线刷。"
        elif missing_files:
            return False, f"脚本中引用的镜像文件未找到: {', '.join(missing_files)}。请确认 ROM 包已正确解压。"
        else:
            return False, "脚本解析结果为空，该脚本格式可能暂不支持。请截图脚本内容联系作者适配。"

    logger.info(f"简单脚本（旧版解析模式）: {filepath}, 共 {len(steps)} 步, 缺失文件: {missing_files}")
    steps = optimize_step_order(steps)
    return True, (txt, steps, False, False, "", missing_files)


def _hydra_steps_to_old(hydra_steps):
    """将 HydraStep 列表转换为旧版 step dict 列表（兼容前端渲染）"""
    old_steps = []
    for hs in hydra_steps:
        step = {
            "type": hs.type,
            "part": hs.part,
            "fileName": hs.fileName,
            "params": hs.params,
            "raw": hs.raw,
            "risk": hs.risk,
            "dynamic": hs.dynamic,
        }
        if hs.loop:
            step["loop"] = hs.loop
        if hs.call:
            step["call"] = hs.call
        if hs.condition:
            step["condition"] = hs.condition
        old_steps.append(step)
    return old_steps