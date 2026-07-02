# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/script_resource_checker.py
"""
Hydra — 脚本-资源一致性校验器
==============================
检查脚本引用的资源（镜像文件）是否与 ROM 目录中的实际文件一致。

核心功能：
    20A：从步骤列表中提取脚本引用的资源清单
    20B：基于 RomInventory.flashable_files 做存在性校验
    20D：底层固件风险交叉检查（与 RomProfile 联动）

用法：
    from core.hydra.script_resource_checker import check_script_resources
    
    result = check_script_resources(steps, rom_inv, rom_profile)
    print(result.missing_files)
"""

import os
import re
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass, field

from .types import HydraStep
from .rom_inventory import RomInventory
from .rom_profile import RomProfile


# ============================================================
# 20A：引用资源提取
# ============================================================

# 非刷写操作类型（不计入资源引用）
_NON_FLASH_TYPES = {"devices", "getvar", "reboot", "reboot-bootloader", "set_active"}

# 已知非镜像文件名（辅助命令）
_KNOWN_NON_IMAGE = {"", "null", "none", "empty", "zero"}


@dataclass
class ScriptResourceInfo:
    """脚本引用的资源清单"""
    referenced_files: List[str] = field(default_factory=list)       # 引用的镜像文件名
    referenced_partitions: List[str] = field(default_factory=list)  # 引用的分区名
    firmware_files: List[str] = field(default_factory=list)         # 固件类引用


def extract_script_resources(steps: List[HydraStep]) -> ScriptResourceInfo:
    """
    从步骤列表中提取脚本引用的资源。

    Args:
        steps: HydraStep 列表

    Returns:
        ScriptResourceInfo
    """
    info = ScriptResourceInfo()
    seen_files: Set[str] = set()
    seen_parts: Set[str] = set()

    for s in steps:
        if s.type in _NON_FLASH_TYPES:
            continue

        # 提取镜像文件名
        fname = (s.fileName or "").strip().strip('"').strip("'")
        if fname and fname.lower() not in _KNOWN_NON_IMAGE:
            normalized = fname.replace('\\', '/')
            if normalized not in seen_files:
                seen_files.add(normalized)
                info.referenced_files.append(normalized)

        # 提取分区名
        part = (s.part or "").strip().strip('"').strip("'")
        if part and part.lower() not in _KNOWN_NON_IMAGE:
            part_lower = part.lower()
            if part_lower not in seen_parts:
                seen_parts.add(part_lower)
                info.referenced_partitions.append(part)

    # 固件归类
    fw_keywords = ("non-hlos", "btfm", "dsp", "modem", "preloader",
                   "xbl", "tz", "hyp", "abl", "cmnlib", "keymaster")
    for f in info.referenced_files:
        f_lower = f.lower()
        if any(kw in f_lower for kw in fw_keywords):
            info.firmware_files.append(f)

    info.firmware_files = list(dict.fromkeys(info.firmware_files))
    return info


# ============================================================
# 20B：资源存在性校验
# ============================================================

@dataclass
class ResourceCheckResult:
    """脚本-资源一致性校验结果"""
    referenced_files: List[str] = field(default_factory=list)       # 脚本引用的文件
    resolved_files: List[Tuple[str, bool, str]] = field(default_factory=list)  # (原始引用, 存在, 解析路径)
    missing_files: List[str] = field(default_factory=list)          # 缺失的引用
    missing_partitions: List[str] = field(default_factory=list)     # 缺失的分区
    warnings: List[str] = field(default_factory=list)               # 警告说明
    notes: List[str] = field(default_factory=list)                  # 一般说明


def _resolve_file(
    ref: str,
    flashable_basenames: Set[str],
    flashable_fullpaths_lower: Set[str],
) -> Tuple[bool, str]:
    """
    单文件存在性解析。

    解析顺序：
        1. 精确匹配 basename（boot.img → boot.img）
        2. 路径包含匹配（images/boot.img → 包含在 flashable_files 中）
        3. basename 模糊匹配（boot → 可能匹配 boot.img 或 boot_a.img）
    """
    ref_normalized = ref.replace('\\', '/')
    ref_lower = ref_normalized.lower()
    ref_basename = os.path.basename(ref_normalized).lower()

    # 1. 精确 basename
    if ref_basename in flashable_basenames:
        return True, f"匹配: {ref_basename}"

    # 2. 完整路径匹配
    if ref_lower in flashable_fullpaths_lower:
        return True, f"匹配完整路径"

    # 3. 模糊匹配
    for fb in flashable_basenames:
        if fb.startswith(ref_basename) or ref_basename.startswith(fb):
            return True, f"模糊匹配: {fb}"

    return False, "未找到"


def check_resource_existence(
    resource_info: ScriptResourceInfo,
    rom_inv: RomInventory,
) -> ResourceCheckResult:
    """
    检查脚本引用的资源是否存在。

    Args:
        resource_info: ScriptResourceInfo
        rom_inv: RomInventory

    Returns:
        ResourceCheckResult
    """
    result = ResourceCheckResult()
    result.referenced_files = list(resource_info.referenced_files)

    # 构建 ROM 索引
    flashable_basenames: Set[str] = set()
    flashable_fullpaths_lower: Set[str] = set()
    for f in rom_inv.flashable_files:
        flashable_basenames.add(os.path.basename(f).lower())
        flashable_fullpaths_lower.add(f.lower())

    # 逐个检查
    for ref in resource_info.referenced_files:
        exists, note = _resolve_file(ref, flashable_basenames, flashable_fullpaths_lower)
        result.resolved_files.append((ref, exists, note))
        if not exists:
            result.missing_files.append(ref)
            result.warnings.append(f"脚本引用的 '{ref}' 未在 ROM 目录中找到")

    return result


# ============================================================
# 20D：底层固件风险交叉检查
# ============================================================

def check_firmware_risk(
    resource_info: ScriptResourceInfo,
    rom_profile: RomProfile,
) -> List[str]:
    """
    检查脚本引用的固件文件风险。

    Returns:
        风险说明列表
    """
    risks: List[str] = []

    for f in resource_info.firmware_files:
        f_lower = f.lower()
        if 'preloader' in f_lower:
            risks.append(f"'{f}'（MTK preloader，刷写底层引导加载器，风险极高）")
        elif 'non-hlos' in f_lower:
            risks.append(f"'{f}'（Qualcomm 基带/无线固件，刷写后可能影响信号）")
        elif 'btfm' in f_lower:
            risks.append(f"'{f}'（蓝牙固件，缺失可能导致蓝牙异常）")
        elif 'xbl' in f_lower:
            risks.append(f"'{f}'（XBL 引导加载器，刷写错误可能导致变砖）")
        elif 'tz' in f_lower or 'hyp' in f_lower:
            risks.append(f"'{f}'（TrustZone/Hypervisor 固件，安全性关键）")
        elif 'abl' in f_lower:
            risks.append(f"'{f}'（ABL 引导加载器，刷写错误可能导致设备无法进入 bootloader）")
        elif 'dsp' in f_lower:
            risks.append(f"'{f}'（DSP 固件，影响音视频处理）")
        elif 'modem' in f_lower:
            risks.append(f"'{f}'（基带固件，刷写后可能需要重新校准）")
        elif 'cmnlib' in f_lower or 'keymaster' in f_lower:
            risks.append(f"'{f}'（安全相关固件，刷写错误可能导致 DRM/认证失效）")
        else:
            risks.append(f"'{f}'（底层固件，请确认来源正确）")

    return risks


# ============================================================
# 20E：统一入口
# ============================================================

@dataclass
class ScriptResourceCheckResult:
    """脚本-资源一致性校验完整结果"""
    resource_info: ScriptResourceInfo = field(default_factory=ScriptResourceInfo)
    existence: ResourceCheckResult = field(default_factory=ResourceCheckResult)
    firmware_risks: List[str] = field(default_factory=list)
    all_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """转为 dict 供 display_summary 使用"""
        return {
            "referenced_files": self.existence.referenced_files,
            "missing_files": self.existence.missing_files,
            "all_notes": self.all_notes,
            "firmware_risks": self.firmware_risks,
        }


def check_script_resources(
    steps: List[HydraStep],
    rom_inv: RomInventory,
    rom_profile: Optional[RomProfile] = None,
) -> ScriptResourceCheckResult:
    """
    脚本-资源一致性校验总入口。

    Args:
        steps: HydraStep 列表
        rom_inv: RomInventory
        rom_profile: RomProfile（可选，如果不传则跳过槽位/固件检查）

    Returns:
        ScriptResourceCheckResult
    """
    result = ScriptResourceCheckResult()
    all_notes: List[str] = []

    # 20A：提取资源
    resource_info = extract_script_resources(steps)
    result.resource_info = resource_info

    if not resource_info.referenced_files and not resource_info.referenced_partitions:
        result.all_notes.append("脚本未引用可刷写文件")
        return result

    # 20B：存在性校验
    existence = check_resource_existence(resource_info, rom_inv)
    result.existence = existence
    all_notes.extend(existence.warnings)
    all_notes.extend(existence.notes)

    # 20D：固件风险（需要 RomProfile）
    if rom_profile is not None:
        firmware_risks = check_firmware_risk(resource_info, rom_profile)
        result.firmware_risks = firmware_risks
        all_notes.extend(
            f"⚠️ {r}" for r in firmware_risks
        )

    # 总结 note
    if existence.missing_files:
        all_notes.append(
            f"脚本引用的 {len(existence.missing_files)} 个文件在 ROM 中未找到"
        )

    result.all_notes = all_notes
    return result


__all__ = [
    "ScriptResourceInfo",
    "ResourceCheckResult",
    "ScriptResourceCheckResult",
    "extract_script_resources",
    "check_resource_existence",
    "check_firmware_risk",
    "check_script_resources",
]