# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/step_classifier.py
"""
Hydra — 步骤分类器
===================
将提取出的命令步骤按语义分类，标识风险等级。

分类体系：
  write     刷写分区（flash/update）
  wipe      清除数据（erase/-w/format）
  boot      重启/切换模式（reboot/reboot-bootloader）
  slot      设置槽位（set_active）
  check     设备检测（devices/getvar）
  unlock    解锁（oem unlock/flashing unlock）
  other     辅助命令

风险等级：
  low       devices/getvar          —— 只读查询
  medium    reboot/set_active       —— 状态切换
  high      flash                   —— 写入
  critical  erase/-w/unlock/format  —— 破坏性操作
"""

import re
from typing import Dict, List, Optional, Set

from .rom_inventory import RomInventory

# 命令类型 → 分类映射
TYPE_TO_CATEGORY = {
    "flash": "write",
    "erase": "wipe",
    "reboot": "boot",
    "set_active": "slot",
    "devices": "check",
    "getvar": "check",
    "oem": "unlock",
    "boot": "boot",
}

# 风险等级映射
TYPE_TO_RISK = {
    "flash": "high",
    "erase": "critical",
    "reboot": "medium",
    "set_active": "medium",
    "devices": "low",
    "getvar": "low",
    "oem": "critical",
    "boot": "medium",
}

# 通配符/未展开变量检测
_WILDCARD_PATTERN = re.compile(r'[*?]')
_UNRESOLVED_VAR_PATTERN = re.compile(r'%[^%]+%|\$\{[^}]+\}|\$[a-zA-Z_][a-zA-Z0-9_]*')


def annotate_confidence(steps: list, dynamic_steps: set = None) -> None:
    """
    为步骤列表标注 confidence 字段。

    规则：
    - part 或 fileName 包含 * 或 ? → placeholder
    - part 或 fileName 包含未展开变量（%VAR% 或 $VAR）且不是已知变量 → estimated
    - dynamic=True 且 part/fileName 完整 → estimated
    - 其他 → certain

    参数：
        steps: HydraStep 列表（原地修改）
        dynamic_steps: 可选，来自动态追踪的步骤的语义 key 集合
    """
    if dynamic_steps is None:
        dynamic_steps = set()

    for s in steps:
        # 已经标注过的跳过
        if s.confidence != "certain":
            continue

        part = s.part or ""
        fname = s.fileName or ""
        target = f"{part} {fname}"

        # 通配符 → placeholder
        if _WILDCARD_PATTERN.search(part) or _WILDCARD_PATTERN.search(fname):
            s.confidence = "placeholder"
            s.note = (s.note + "; " if s.note else "") + "包含通配符，实际分区名运行时确定"
            continue

        # 未展开变量 → estimated
        if _UNRESOLVED_VAR_PATTERN.search(part) or _UNRESOLVED_VAR_PATTERN.search(fname):
            s.confidence = "estimated"
            s.note = (s.note + "; " if s.note else "") + "变量未完全解析"
            continue

        # 来自动态追踪的步骤：检查是否有残留变量，否则保留 certain
        if s.dynamic:
            # 如果 part/fileName 完整无模板残留，保留 certain（tracer 解析出的完整步骤）
            if not _UNRESOLVED_VAR_PATTERN.search(part) and not _UNRESOLVED_VAR_PATTERN.search(fname):
                # 确定步骤，跳过
                pass
            else:
                s.confidence = "estimated"
                s.note = (s.note + "; " if s.note else "") + "来自动态追踪，不完全确定"


def count_placeholder_steps(steps: list) -> int:
    """统计占位步骤数"""
    return sum(1 for s in steps if s.confidence == "placeholder")


def count_estimated_steps(steps: list) -> int:
    """统计估计步骤数"""
    return sum(1 for s in steps if s.confidence == "estimated")


def classify_step_type(step_type: str) -> str:
    """返回步骤语义分类"""
    return TYPE_TO_CATEGORY.get(step_type, "other")


def risk_level(step_type: str) -> str:
    """返回风险等级"""
    return TYPE_TO_RISK.get(step_type, "low")


def build_summary(steps: list) -> Dict[str, int]:
    """
    从步骤列表构建 summary 统计。

    返回示例：
    {
        "total_commands": 57,
        "write_steps": 51,
        "wipe_steps": 3,
        "boot_steps": 1,
        "slot_steps": 1,
        "check_steps": 1,
        "unlock_steps": 0,
        "other_steps": 0,
        "high_risk_steps": 51,
        "critical_risk_steps": 3,
        "medium_risk_steps": 2,
        "low_risk_steps": 1,
    }
    """
    categories = {"write": 0, "wipe": 0, "boot": 0, "slot": 0, "check": 0, "unlock": 0, "other": 0}
    risks = {"low": 0, "medium": 0, "high": 0, "critical": 0}

    for s in steps:
        cat = classify_step_type(getattr(s, "type", ""))
        categories[cat] = categories.get(cat, 0) + 1
        rl = risk_level(getattr(s, "type", ""))
        risks[rl] = risks.get(rl, 0) + 1

    return {
        "total_commands": len(steps),
        "write_steps": categories["write"],
        "wipe_steps": categories["wipe"],
        "boot_steps": categories["boot"],
        "slot_steps": categories["slot"],
        "check_steps": categories["check"],
        "unlock_steps": categories["unlock"],
        "other_steps": categories["other"],
        "high_risk_steps": risks["high"],
        "critical_risk_steps": risks["critical"],
        "medium_risk_steps": risks["medium"],
        "low_risk_steps": risks["low"],
    }


# ============================================================
# 阶段 15C：步骤级标注
# ============================================================

# 高风险分区（擦除/刷写这类分区可能变砖）
_CRITICAL_PARTITIONS = {
    "preloader", "lk", "tee", "tz", "sbl", "abl", "xbl", "pbl",
    "boot", "recovery", "vbmeta", "vbmeta_system", "dtbo",
}
# bootloader 分区（刷写后必须重启才能生效）
_BOOTLOADER_PARTITIONS = {
    "boot", "recovery", "dtbo", "vbmeta", "vbmeta_system", "dTB",
    "super", "system", "vendor", "product", "odm", "vendor_dlkm",
    "system_dlkm", "system_ext",
}
# 槽位分区
_SLOT_AWARE_PARTITIONS = {
    "boot", "recovery", "vbmeta", "dtbo", "super", "system", "vendor",
    "product", "odm", "vendor_dlkm", "system_dlkm", "system_ext",
}


def annotate_risk_subtype(steps: list) -> None:
    """为每个步骤标注风险子类型 (risk_subtype)。

    规则：
    - type=erase → "erase"
    - type=oem → "oem"
    - type=devices/getvar → "check"
    - type=reboot → "reboot"
    - type=set_active → "slot"
    - type=flash 且 partition 在 _CRITICAL_PARTITIONS 中 → "critical_part"
    - type=flash 且 partition 在 _BOOTLOADER_PARTITIONS 中 → "bootloader_part"
    - 其他 flash → "flash_normal"
    """
    for s in steps:
        t = s.type
        part = (s.part or "").lower()
        if t == "erase":
            s.risk_subtype = "erase"
        elif t == "oem":
            s.risk_subtype = "oem"
        elif t in ("devices", "getvar"):
            s.risk_subtype = "check"
        elif t == "reboot":
            s.risk_subtype = "reboot"
        elif t == "set_active":
            s.risk_subtype = "slot"
        elif t == "flash":
            if part in _CRITICAL_PARTITIONS:
                s.risk_subtype = "critical_part"
            elif part in _BOOTLOADER_PARTITIONS:
                s.risk_subtype = "bootloader_part"
            else:
                s.risk_subtype = "flash_normal"
        else:
            s.risk_subtype = "other"


def annotate_source(steps: list, tracer_key_set: set = None, expander_steps: int = 0) -> None:
    """标注步骤来源 (source)。

    参数：
        steps: HydraStep 列表
        tracer_key_set: 来自动态追踪/沙箱的步骤语义 key 集合
        expander_steps: 食谱展开器添加的步骤数（从末尾计）

    规则：
    - 最后 N 步且来自 expander → "expander"
    - key 在 tracer_key_set 中 → "tracer" 或 "sandbox"
    - 其他 → "static"
    """
    if tracer_key_set is None:
        tracer_key_set = set()

    # 标记 expander 生成的步骤（从末尾计 expander_steps 个）
    expander_source_count = 0
    if expander_steps > 0:
        for i in range(len(steps) - 1, -1, -1):
            if expander_source_count >= expander_steps:
                break
            s = steps[i]
            if s.source == "static":
                s.source = "expander"
                expander_source_count += 1

    for s in steps:
        if s.source != "static":
            continue
        key = _step_key(s)
        if key in tracer_key_set:
            # 保留已标记的 sandbox，否则标记为 tracer
            pass  # 已在外部标记
        # 静态步骤保持默认


def _step_key(s) -> tuple:
    """生成用于来源追溯的语义 key"""
    t = s.type.strip().lower() if s.type else ""
    p = s.part.strip().lower() if s.part else ""
    f = s.fileName.strip().lower() if s.fileName else ""
    return (t, p, f)


def annotate_resource(
    steps: list,
    rom_inv: "RomInventory" = None,
    rom_dir: str = "",
    script_dir: str = "",
    script_path: str = "",
    script_type: str = "bat",
) -> None:
    """为每个步骤标注资源状态 (resource_note)。

    参数：
        steps: HydraStep 列表
        rom_inv: ROM Inventory 对象
        rom_dir: ROM 目录路径
        script_dir: 脚本所在目录（用于 %~dp0 等路径解析）
        script_path: 脚本文件路径
        script_type: "bat" | "sh"

    规则：
    - type=devices/getvar → "无镜像依赖（只读查询）"
    - type=erase → "操作不依赖镜像文件"
    - type=reboot/set_active → "无镜像依赖（状态切换）"
    - type=flash 且 fileName 为空 → "需运行时确定镜像文件"
    - type=flash 且 fileName 用 PathResolver 解析成功 → 精确描述
    - type=oem → "需外部命令（OEM 指令）"
    其他情况 → "未知"
    """
    # 构建 PathResolver（如果目录信息可用）
    resolver = None
    if script_dir or rom_dir:
        from .path_resolver import PathResolver
        resolver = PathResolver(
            script_dir=script_dir or "",
            rom_dir=rom_dir or "",
        )

    # 构建 rom 中已知文件集合（兜底用）
    known_files: Set[str] = set()
    if rom_inv:
        known_files = set(rom_inv.available_images) if hasattr(rom_inv, 'available_images') else set()
        if hasattr(rom_inv, 'image_files'):
            known_files.update(rom_inv.image_files)
    elif rom_dir:
        import os
        if os.path.isdir(rom_dir):
            for root, dirs, files in os.walk(rom_dir):
                for f in files:
                    known_files.add(f.lower())

    for s in steps:
        t = s.type
        fname = (s.fileName or "").strip()

        if t in ("devices", "getvar"):
            s.resource_note = "无镜像依赖（只读查询）"
        elif t == "erase":
            s.resource_note = "操作不依赖镜像文件"
        elif t in ("reboot", "set_active"):
            s.resource_note = "无镜像依赖（状态切换）"
        elif t == "oem":
            s.resource_note = "需外部命令（OEM 指令）"
        elif t == "flash":
            if not fname:
                s.resource_note = "需运行时确定镜像文件"
            elif resolver:
                # 用 PathResolver 做精确解析
                pr = resolver.resolve_image(fname, script_type=script_type)
                if pr.exists:
                    if pr.source == "rom_dir":
                        s.resource_note = f"在 ROM 中找到: {pr.normalized}"
                    elif pr.source == "script_dir":
                        s.resource_note = f"在脚本目录中找到: {pr.normalized}"
                    elif pr.source == "cwd":
                        s.resource_note = f"在当前目录中找到: {pr.normalized}"
                    elif pr.source == "rom_dir_basename":
                        s.resource_note = f"在 ROM 中找到（basename）: {pr.normalized}"
                    else:
                        s.resource_note = f"镜像文件存在: {pr.normalized}"
                else:
                    # 解析后不存在，看是否有 rom_dir 可判断
                    if rom_dir:
                        s.resource_note = f"镜像文件缺失: {pr.normalized}"
                    else:
                        s.resource_note = f"镜像文件存在（未验证）: {pr.normalized}"
            elif known_files:
                # 无 resolver，fallback 到旧逻辑
                fname_lower = fname.lower()
                if known_files and fname_lower in known_files:
                    s.resource_note = "镜像文件存在"
                elif known_files:
                    s.resource_note = "镜像文件缺失"
                else:
                    s.resource_note = "镜像文件存在（未验证）"
            else:
                s.resource_note = "镜像文件存在（未验证）"
        else:
            s.resource_note = "未知"


def annotate_all_steps(
    steps: list,
    rom_inv: "RomInventory" = None,
    rom_dir: str = "",
    tracer_key_set: set = None,
    expander_count: int = 0,
    script_dir: str = "",
    script_path: str = "",
    script_type: str = "bat",
) -> None:
    """一站式标注所有步骤级字段。

    依次调用：
    1. annotate_risk_subtype
    2. annotate_resource
    3. annotate_confidence（已有）
    4. annotate_source（需在 expander/tracer 标记后调用）
    """
    annotate_risk_subtype(steps)
    annotate_resource(steps, rom_inv=rom_inv, rom_dir=rom_dir,
                      script_dir=script_dir, script_path=script_path,
                      script_type=script_type)
    annotate_source(steps, tracer_key_set=tracer_key_set, expander_steps=expander_count)


__all__ = [
    "classify_step_type", "risk_level", "build_summary",
    "annotate_confidence", "count_placeholder_steps", "count_estimated_steps",
    "annotate_risk_subtype", "annotate_source", "annotate_resource",
    "annotate_all_steps",
    "TYPE_TO_CATEGORY", "TYPE_TO_RISK",
]