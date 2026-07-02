# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/android_info_parser.py
"""
Hydra — android-info.txt 解析器
================================
解析 Pixel / AOSP 刷机包中的 android-info.txt 文件。

android-info.txt 格式（典型）：
    require board=slider
    require product=sailfish
    require version-bootloader=8996-012001
    require version-baseband=8996-012001
    require partition-exists=userdata
    require-for-product:sailfish recovery=recovery.img

输出：
    AndroidInfo 数据类
    - requirements: 全局要求（Dict[str, List[str]]）
    - products:     产品列表
    - boards:       board 列表
    - bootloader_versions: bootloader 版本要求
    - baseband_versions:   baseband 版本要求
    - raw_lines:    原始行列表

用法：
    from core.hydra.android_info_parser import parse_android_info
    
    info = parse_android_info(content)
    print(info.products)
    print(info.requirements)
"""

import re
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field


# ============================================================
# 解析正则
# ============================================================

# require key=value
_REQUIRE_GLOBAL = re.compile(
    r'^require\s+([\w\-]+)=(.+)$',
    re.IGNORECASE,
)

# require-for-product:product key=value
_REQUIRE_PER_PRODUCT = re.compile(
    r'^require-for-product:\s*(\w+)\s+(\w+)=(.+)$',
    re.IGNORECASE,
)

# require-for-board:board key=value
_REQUIRE_PER_BOARD = re.compile(
    r'^require-for-board:\s*(\w+)\s+(\w+)=(.+)$',
    re.IGNORECASE,
)

# partition=filename.img
_PARTITION_ASSIGNMENT = re.compile(
    r'^\s*(\w+)\s*=\s*(.+?)(?:\s*#.*)?$',
)


# ============================================================
# AndroidInfo — 数据类
# ============================================================

@dataclass
class AndroidInfo:
    """android-info.txt 解析结果"""
    raw_lines: List[str] = field(default_factory=list)           # 原始行

    # 全局 require
    requirements: Dict[str, List[str]] = field(default_factory=dict)  # key → [value1, value2]

    # require-for-product 分部要求
    per_product: Dict[str, Dict[str, List[str]]] = field(default_factory=dict)

    # 字段快捷访问
    products: List[str] = field(default_factory=list)            # require product=xxx
    boards: List[str] = field(default_factory=list)              # require board=xxx
    bootloader_versions: List[str] = field(default_factory=list)  # require version-bootloader=xxx
    baseband_versions: List[str] = field(default_factory=list)    # require version-baseband=xxx
    partition_requirements: List[str] = field(default_factory=list)  # require partition-exists=xxx

    # 分区 → 文件名引用（如 recovery=recovery.img）
    partition_assignments: Dict[str, str] = field(default_factory=dict)

    # 是否有内容
    has_content: bool = False


# ============================================================
# 解析函数
# ============================================================

def parse_android_info(content: str) -> AndroidInfo:
    """
    解析 android-info.txt 内容。

    Args:
        content: android-info.txt 文件内容

    Returns:
        AndroidInfo 数据类
    """
    info = AndroidInfo()

    if not content:
        return info

    lines = content.split('\n')
    info.raw_lines = lines

    for line in lines:
        stripped = line.strip()

        # 跳过空行和注释
        if not stripped or stripped.startswith('#'):
            continue

        # 1. require-for-product:product key=value
        m = _REQUIRE_PER_PRODUCT.match(stripped)
        if m:
            product = m.group(1).lower()
            key = m.group(2).lower()
            val = m.group(3).strip()
            if product not in info.per_product:
                info.per_product[product] = {}
            if key not in info.per_product[product]:
                info.per_product[product][key] = []
            info.per_product[product][key].append(val)
            continue

        # 2. require-for-board:board key=value
        m = _REQUIRE_PER_BOARD.match(stripped)
        if m:
            board = m.group(1).lower()
            key = m.group(2).lower()
            val = m.group(3).strip()
            if board not in info.per_product:
                info.per_product[board] = {}
            if key not in info.per_product[board]:
                info.per_product[board][key] = []
            info.per_product[board][key].append(val)
            continue

        # 3. require key=value
        m = _REQUIRE_GLOBAL.match(stripped)
        if m:
            key = m.group(1).lower()
            val = m.group(2).strip()
            if key not in info.requirements:
                info.requirements[key] = []
            info.requirements[key].append(val)

            # 快捷字段
            if key == 'product':
                info.products.append(val)
            elif key == 'board':
                info.boards.append(val)
            elif key == 'version-bootloader':
                info.bootloader_versions.append(val)
            elif key == 'version-baseband':
                info.baseband_versions.append(val)
            elif key == 'partition-exists':
                info.partition_requirements.append(val)
            continue

        # 4. partition=filename.img（简单赋值行，无 require 前缀）
        m = _PARTITION_ASSIGNMENT.match(stripped)
        if m and '=' in stripped and not stripped.startswith('require'):
            partition = m.group(1).lower()
            fname = m.group(2).strip()
            if partition and fname:
                info.partition_assignments[partition] = fname

    info.has_content = bool(info.requirements or info.per_product or info.partition_assignments)
    return info


def parse_android_info_file(filepath: str) -> AndroidInfo:
    """
    从文件路径解析 android-info.txt。

    Args:
        filepath: android-info.txt 文件路径

    Returns:
        AndroidInfo 数据类
    """
    import os
    if not filepath or not os.path.isfile(filepath):
        return AndroidInfo()
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        return parse_android_info(content)
    except Exception:
        return AndroidInfo()


__all__ = [
    "AndroidInfo",
    "parse_android_info",
    "parse_android_info_file",
]