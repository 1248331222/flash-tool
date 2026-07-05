# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/bat_parser/classifier.py
"""
分类器 — 按 BAT 语法复杂度分级

扫描脚本内容，检测语法特征，返回难度等级字符串。

检测逻辑（从高到低，命中即返回）:
    1. set /p 或 choice → "interactive"
    2. goto 或 call     → "goto_label"
    3. for /f 或 getvar  → "dynamic_var"
    4. !VAR! 或 setlocal delayed → "delayed_expansion"
    5. 嵌套 for          → "nested_for"
    6. for               → "for_loop"
    7. if                → "conditional"
    8. SET 或 %VAR%      → "simple"
    9. 以上均无          → "plain"

用法:
    from .classifier import classify
    level = classify(raw_content)
"""

import re
from typing import List


# ─────────────────────────────────────────────
# 检测模式（按优先级从高到低）
# ─────────────────────────────────────────────

def _has_interactive(content: str) -> bool:
    """检测 set /p 或 choice 交互命令"""
    if re.search(r'set\s+/[pP]\b', content, re.IGNORECASE):
        return True
    if re.search(r'^\s*choice\s+', content, re.MULTILINE | re.IGNORECASE):
        return True
    return False


def _has_goto_label(content: str) -> bool:
    """检测 goto 或 call"""
    if re.search(r'^\s*goto\s+\S', content, re.MULTILINE | re.IGNORECASE):
        return True
    if re.search(r'^\s*call\s+:\S', content, re.MULTILINE | re.IGNORECASE):
        return True
    return False


def _has_dynamic_var(content: str) -> bool:
    """
    检测 for /f 或 getvar 作为变量赋值（SET 形式）的动态变量。
    
    注意: 排除 fastboot getvar current-slot 这类命令中的 getvar，
    只检测由 for /f + 命令捕获产生的动态变量场景。
    """
    if re.search(r'for\s+/[fF]\b', content, re.IGNORECASE):
        return True
    # getvar 只在被 for /f 捕获时才视为动态变量
    # 单独一行 'fastboot getvar xxx' 不是动态变量
    return False


def _has_delayed_expansion(content: str) -> bool:
    """
    检测真正的延迟展开变量（!自定义变量!，排除 !errorlevel! 等内置伪变量）。
    
    CMD 内置变量（不视为延迟展开）:
        !errorlevel!, !cmdcmdline!, !date!, !time!, !random!, !cd!
    """
    # 检测 setlocal enabledelayedexpansion — 但仅作为辅助信号
    has_setlocal_delayed = bool(re.search(
        r'setlocal\s+.*enabledelayedexpansion', content, re.IGNORECASE
    ))
    
    # 检测非内置的 !自定义变量! 
    _BUILTIN_VARS = {
        'errorlevel', 'cmdcmdline', 'date', 'time', 'random', 'cd',
        'cmdextversion', 'cmdcmdline',
    }
    for match in re.finditer(r'!([\w]+)!', content):
        var_name = match.group(1).lower()
        if var_name not in _BUILTIN_VARS:
            return True
    
    # 只有 setlocal delayed 但没有自定义 !VAR! 时，不触发延迟展开
    return False


def _has_nested_for(content: str) -> bool:
    """
    检测嵌套 for。
    简化检测：统计独立的 for 关键字，如果在同一个括号块内出现多个 for，
    或 for 行内包含另一个 for 关键字。
    """
    # 简化: 如果一行内有两个 for 关键字，或者 for 行在括号体内含另一 for
    # 只看有没有两行 for 在连续的括号块内
    lines = content.split('\n')
    in_block = 0
    for_count_in_block = 0

    for line in lines:
        stripped = line.strip()
        if '(' in stripped:
            in_block += 1
        if ')' in stripped and in_block > 0:
            if for_count_in_block > 1:
                return True
            in_block -= 1
            for_count_in_block = 0
        if re.match(r'^\s*for\s+', stripped, re.IGNORECASE):
            if in_block > 0:
                for_count_in_block += 1

    return False


def _has_for(content: str) -> bool:
    """检测 for 循环"""
    return bool(re.search(r'^\s*for\s+', content, re.MULTILINE | re.IGNORECASE))


def _has_if(content: str) -> bool:
    """检测 if 语句"""
    return bool(re.search(r'^\s*if\s+', content, re.MULTILINE | re.IGNORECASE))


def _has_set_or_percent(content: str) -> bool:
    """检测 SET 或 %VAR%"""
    if re.search(r'^\s*SET\s+', content, re.MULTILINE | re.IGNORECASE):
        return True
    if re.search(r'%[\w]+%', content):
        return True
    return False


# ─────────────────────────────────────────────
# 主分类函数
# ─────────────────────────────────────────────

def classify(raw_content: str) -> str:
    """
    按语法复杂度对 BAT 脚本分级。

    Args:
        raw_content: 脚本完整文本内容

    Returns:
        str: 难度等级，取值:
            "interactive" "goto_label" "dynamic_var" "delayed_expansion"
            "nested_for" "for_loop" "conditional" "simple" "plain"
    """
    content = raw_content

    # 按优先级从高到低依次检测
    if _has_interactive(content):
        return "interactive"
    if _has_goto_label(content):
        return "goto_label"
    if _has_dynamic_var(content):
        return "dynamic_var"
    if _has_delayed_expansion(content):
        return "delayed_expansion"
    if _has_nested_for(content):
        return "nested_for"
    if _has_for(content):
        return "for_loop"
    if _has_if(content):
        return "conditional"
    if _has_set_or_percent(content):
        return "simple"

    return "plain"


__all__ = ["classify"]