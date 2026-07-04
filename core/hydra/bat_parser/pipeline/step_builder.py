# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/bat_parser/pipeline/step_builder.py
"""
L4: StepBuilder — 步骤构建

作用: 将 fastboot 命令字符串转为结构化的 HydraStep。

处理内容:
    1. 解析子命令：flash / erase / reboot / reboot-bootloader / oem / 其他
    2. 提取目标分区名（flash 和 erase 有分区参数）
    3. 提取镜像文件路径（flash 命令的最后一个参数）
    4. 风险定级：基于分区名查风险表
    5. 传递条件标记

用法:
    from .pipeline.step_builder import build_steps
    steps = build_steps(commands)
"""

import re
from typing import List, Optional, Dict

from ..var_types import RawCommand, HydraStep


# ─────────────────────────────────────────────
# fastboot 命令解析正则
# ─────────────────────────────────────────────

# 匹配: ["][路径/]fastboot[.exe]["] [options] <subcommand> [args...]
# 支持: fastboot, ./fastboot, ./tools\fastboot.exe, "./tools/fastboot.exe" 等各种路径前缀
_FASTBOOT_PREFIX_RE = re.compile(
    r'^\s*"?'
    r'(?:.+\\)?fastboot(?:\.exe)?'
    r'"?(?:\s+[-][^\s]+\s+)*\s+',
    re.IGNORECASE,
)

# ─────────────────────────────────────────────
# 默认风险定级表
# ─────────────────────────────────────────────

# 风险等级: CRITICAL > HIGH > MEDIUM > LOW
_RISK_TABLE: Dict[str, str] = {
    # 高危：刷错可能彻底变砖
    "preloader": "CRITICAL",
    "lk": "HIGH",
    "lk2": "HIGH",
    "xbl": "CRITICAL",
    "xbl_config": "CRITICAL",
    "abl": "HIGH",
    "tz": "CRITICAL",
    "hyp": "CRITICAL",
    "devcfg": "CRITICAL",
    "rpm": "CRITICAL",
    "pmic": "CRITICAL",
    "keymaster": "HIGH",
    "cmnlib": "HIGH",
    "cmnlib64": "HIGH",
    "uefi": "CRITICAL",
    "sec": "HIGH",
    # 标准分区
    "boot": "MEDIUM",
    "dtbo": "MEDIUM",
    "recovery": "MEDIUM",
    "vendor": "MEDIUM",
    "system": "MEDIUM",
    "product": "MEDIUM",
    "vbmeta": "HIGH",
    "vbmeta_system": "HIGH",
    # 低风险
    "userdata": "LOW",
    "cache": "LOW",
    "cust": "LOW",
    # 擦除类
    "frp": "MEDIUM",
    "persist": "HIGH",
    "modem": "HIGH",
    "modemst1": "HIGH",
    "modemst2": "HIGH",
    "fsg": "HIGH",
    "fsc": "HIGH",
    "dsp": "HIGH",
    "devcfg": "CRITICAL",
    "mdtp": "HIGH",
    "splash": "LOW",
    "logo": "LOW",
    "misc": "MEDIUM",
    "metadata": "LOW",
    # 小米/高通特有
    "preflag": "CRITICAL",
    "flag": "HIGH",
    "xiaomi_info": "HIGH",
    "cpucp": "HIGH",
    "aop": "CRITICAL",
    "scp": "HIGH",
    "ssd": "HIGH",
    "spunvm": "HIGH",
    "multiimgqti": "HIGH",
    "multiimgoem": "HIGH",
    "storsec": "HIGH",
    "uefisecapp": "HIGH",
    "qupfw": "HIGH",
    "imagefv": "HIGH",
    "shrm": "HIGH",
}


def _split_command_parts(command: str) -> list:
    """
    去掉 fastboot 前缀后，分割参数，跳过前导 -- 选项。

    Args:
        command: 完整命令字符串

    Returns:
        list: 有效的参数部分（子命令、分区、路径等）
    """
    clean = re.sub(_FASTBOOT_PREFIX_RE, '', command, count=1).strip()
    parts = clean.split()
    # 跳过前导 --xxx 选项（如 --disable-verity）
    result = []
    skip_flags = True
    for p in parts:
        if skip_flags and p.startswith('--'):
            result.append(p)  # 保留选项参数，但记为选项
            continue
        skip_flags = False
        result.append(p)
    return result


def _parse_subcommand(command: str) -> str:
    """
    从 fastboot 命令中提取子命令。

    Args:
        command: 完整命令字符串

    Returns:
        str: 子命令（flash / erase / reboot / oem 等）
    """
    parts = _split_command_parts(command)
    for p in parts:
        if not p.startswith('--'):
            return p.lower()
    return "unknown"


def _parse_partition(command: str, subcommand: str) -> Optional[str]:
    """
    提取命令中的目标分区名。

    跳过前导 -- 选项，取子命令后的第一个参数作为分区名。

    flash 格式: fastboot [--opts] flash <partition> <file>
    erase 格式: fastboot erase <partition>

    Args:
        command: 完整命令字符串
        subcommand: 子命令

    Returns:
        Optional[str]: 分区名，如果没有则返回 None
    """
    if subcommand not in ("flash", "erase", "format", "delete-logical-partition", "set_active", "reboot", "reboot-bootloader", "reboot-fastboot"):
        return None

    parts = _split_command_parts(command)
    # 找子命令位置
    try:
        idx = parts.index(subcommand) if subcommand in parts else (0 if parts and parts[0] == subcommand else -1)
    except ValueError:
        idx = -1
    # 简单策略：子命令后第一个非 -- 参数是分区名
    found_cmd = False
    for p in parts:
        if p.lower() == subcommand:
            found_cmd = True
            continue
        if found_cmd and not p.startswith('--'):
            return p.lower()
    # 回退：parts[1]
    if len(parts) >= 2:
        return parts[1].lower()
    return None


def _parse_flash_options(command: str, subcommand: str) -> str:
    """
    提取 flash/erase 命令中的 -- 选项（如 --disable-verity --disable-verification）。

    Args:
        command: 完整命令字符串
        subcommand: 子命令

    Returns:
        str: 选项字符串（空格分隔），没有则返回空串
    """
    if subcommand not in ("flash", "erase"):
        return ""
    parts = _split_command_parts(command)
    opts = [p for p in parts if p.startswith('--')]
    return " ".join(opts)


def _parse_path(command: str, subcommand: str) -> Optional[str]:
    """
    提取 flash 命令中的镜像文件路径。

    flash 格式: fastboot [--opts] flash <partition> <file> [-S size]

    Args:
        command: 完整命令字符串
        subcommand: 子命令

    Returns:
        Optional[str]: 文件路径，如果没有则返回 None
    """
    if subcommand != "flash":
        return None

    parts = _split_command_parts(command)
    # 跳过 -S 选项及其值，取最后一个有效参数作为路径
    valid = []
    skip_next = False
    for p in parts:
        if skip_next:
            skip_next = False
            continue
        if p.startswith('-') and not p.startswith('--'):
            skip_next = True  # -S 64M，跳过选项值和选项
            continue
        if not p.startswith('--') and p.lower() != subcommand:
            valid.append(p)
    return valid[-1] if valid else None


def _assess_risk(subcommand: str, partition: Optional[str]) -> str:
    """
    根据子命令和分区名评估风险等级。

    Args:
        subcommand: 子命令
        partition: 分区名

    Returns:
        str: CRITICAL / HIGH / MEDIUM / LOW
    """
    # 擦除操作整体提高一级
    if subcommand == "erase":
        if partition and partition in ("userdata", "cache", "metadata"):
            return "MEDIUM"
        if partition and partition in _RISK_TABLE:
            base = _RISK_TABLE[partition]
            if base == "MEDIUM":
                return "HIGH"
            if base == "LOW":
                return "MEDIUM"
            return base
        return "HIGH"

    # format 同理
    if subcommand == "format":
        return "HIGH"

    # reboot 类无风险
    if subcommand in ("reboot", "reboot-bootloader", "reboot-fastboot"):
        return "LOW"

    # oem 命令不确定，中等风险
    if subcommand in ("oem", "flashing"):
        return "MEDIUM"

    # flash 命令查表
    if partition and partition in _RISK_TABLE:
        return _RISK_TABLE[partition]

    # 未知分区默认中等风险
    return "MEDIUM"


def build_steps(commands: List[RawCommand]) -> List[HydraStep]:
    """
    将 RawCommand 列表转为 HydraStep 列表。

    Args:
        commands: L3 提取到的命令列表

    Returns:
        List[HydraStep]: 结构化的刷机步骤列表
    """
    steps = []

    for cmd in commands:
        subcommand = _parse_subcommand(cmd.command)
        partition = _parse_partition(cmd.command, subcommand)
        path = _parse_path(cmd.command, subcommand)
        params = _parse_flash_options(cmd.command, subcommand)
        risk = _assess_risk(subcommand, partition)

        step = HydraStep(
            command=cmd.command,
            subcommand=subcommand,
            partition=partition,
            path=path,
            params=params,
            risk=risk,
            is_conditional=cmd.is_conditional,
            condition=cmd.condition,
            source_lines=cmd.source_lines,
        )
        steps.append(step)

    return steps


__all__ = ["build_steps"]