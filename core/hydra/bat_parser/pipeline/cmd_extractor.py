# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/bat_parser/pipeline/cmd_extractor.py
"""
L3: CmdExtractor — 命令提取

作用: 从展开后的行中提取 fastboot 命令。

处理内容:
    1. 识别以 'fastboot' 或 'fastboot.exe' 开头的命令
    2. 识别通过变量展开后以 'fastboot' 开头的命令
    3. 丢弃非 fastboot 行（echo、pause、set、if 等）
    4. 命令参数标准化（去除多余空格）

用法:
    from .pipeline.cmd_extractor import extract
    commands = extract(expanded_lines)
"""

import re
from typing import List

from ..var_types import ExpandedLine, RawCommand


# fastboot 命令识别（行首或行中以 fastboot 开头的命令）
_FASTBOOT_RE = re.compile(r'^\s*(fastboot(\.exe)?)\s+', re.IGNORECASE)


def _is_fastboot_command(content: str) -> bool:
    """
    判断一行是否为 fastboot 命令。

    检测以下模式:
        - fastboot flash ...
        - fastboot.exe flash ...
        - ./tools/fastboot flash ...
        - "./tools/fastboot" flash ...  （双引号包裹的路径）
        - 展开后路径中含有 fastboot 的调用

    Args:
        content: 展开后的行内容

    Returns:
        bool
    """
    lower = content.lower().lstrip()
    # 去掉前导双引号
    unquoted = lower.lstrip('"')

    # 各种可能的前缀
    if any(unquoted.startswith(prefix) for prefix in (
        "fastboot ", "fastboot.exe ",
        "./fastboot ", "./fastboot.exe ",
        "./tools/fastboot ", "./tools/fastboot.exe ",
    )):
        return True

    # 提取第一个单词（可能是引号包裹的路径），检查是否以 fastboot 结尾
    first_word = lower.split()[0] if lower.split() else ""
    first_word = first_word.strip('"')
    if first_word.endswith("fastboot") or first_word.endswith("fastboot.exe"):
        return True

    # 检查是否包含 fastboot 作为路径后缀（如 tools\\fastboot.exe）
    if "fastboot" in lower:
        return True

    return False


def extract(expanded_lines: List[ExpandedLine]) -> List[RawCommand]:
    """
    从展开后的行中提取 fastboot 命令。

    跳过纯变量定义行（SET 语句在变量展开后如果是单独的定义行则丢弃）、
    echo、pause、goto 等非执行命令。

    Args:
        expanded_lines: L2 展开后的命令行列表

    Returns:
        List[RawCommand]: 提取到的 fastboot 命令列表
    """
    result = []

    for el in expanded_lines:
        content = el.content

        # 跳过 SET 定义行
        if content.upper().lstrip().startswith("SET "):
            continue

        # 跳过非 fastboot 命令（echo/pause/cls/title/color/exit/timeout/if/chcp）
        skip_prefixes = ('ECHO ', 'PAUSE ', 'CLS ', 'TITLE ', 'COLOR ', 'EXIT ', 'TIMEOUT ', 'IF ', 'CHCP ')
        if content.upper().lstrip()[:20] and any(
            content.upper().lstrip().startswith(p) for p in skip_prefixes
        ):
            continue

        # 跳过以 ( 开头的行（if 块的残留）
        if content.strip().startswith('('):
            continue

        # 跳过空行
        if not content.strip():
            continue

        # 必须是 fastboot 命令
        if not _is_fastboot_command(content):
            continue

        # 去除多余空格
        clean_command = re.sub(r'\s+', ' ', content).strip()

        result.append(RawCommand(
            command=clean_command,
            source_lines=el.source_lines,
            is_conditional=el.is_conditional,
            condition=el.condition,
        ))

    return result


__all__ = ["extract"]