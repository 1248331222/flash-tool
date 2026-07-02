# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/script_preprocessor.py
"""
Hydra — 脚本预处理层
======================
在进入 AST / Environment / Tracer 之前统一处理脚本文本。

处理的文本问题：
  1. BOM 头移除（UTF-8 BOM / UTF-16 BOM）
  2. CRLF → LF（统一换行符）
  3. 控制字符清理（保留 \t）
  4. 注释行标准化（BAT: rem/:: → #; SH: 保留原有 #）
  5. BAT ^ 行续接合并
  6. SH \\ 行续接合并
  7. BAT @echo off 等特殊预处理
  8. 空行折叠

用法：
    from core.hydra.script_preprocessor import preprocess_script
    
    clean = preprocess_script(content, script_type="bat")
"""

import re
from typing import Optional

# BOM 头
UTF8_BOM = '\ufeff'
UTF16_BE_BOM = '\ufffe'
UTF16_LE_BOM = '\xfe\xff'

# BAT 续接行正则：行尾 ^ 后可能跟换行
_BAT_LINE_CONTINUATION = re.compile(r'\^\s*\n')

# SH 续接行正则：行尾 \ 后跟换行（注意：\\n 被转义为 \n）
_SH_LINE_CONTINUATION = re.compile(r'\\\s*\n')

# BAT rem 和 :: 注释（行首）
_BAT_REM_COMMENT = re.compile(r'^\s*@?\s*$', re.IGNORECASE)
_BAT_REM_LINE = re.compile(r'^\s*(?:rem\s|::).*$', re.IGNORECASE)

# BAT @echo off / @echo on
_BAT_AT_ECHO = re.compile(r'^\s*@\s*echo\s+(off|on)\s*$', re.IGNORECASE)

# SH #!/bin/bash
_SH_SHEBANG = re.compile(r'^#!')

# 控制字符（保留 \t \n \r → \n 已在 CRLF 处理中）
_CONTROL_CHARS = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')


def remove_bom(text: str) -> str:
    """移除 BOM 头"""
    if text.startswith(UTF8_BOM):
        text = text[1:]
    elif text.startswith(UTF16_BE_BOM) or text.startswith(UTF16_LE_BOM):
        # UTF-16 BOM 标记：尝试以 utf-16 重新解码
        try:
            text = text.encode('raw_unicode_escape').decode('utf-16', errors='ignore')
        except Exception:
            pass
    return text


def normalize_line_endings(text: str) -> str:
    """CRLF → LF"""
    return text.replace('\r\n', '\n').replace('\r', '\n')


def clean_control_chars(text: str) -> str:
    """移除不可见控制字符，保留 \t \n"""
    return _CONTROL_CHARS.sub('', text)


def collapse_blank_lines(text: str) -> str:
    """将连续空行折叠为单空行"""
    # 保留至少一个换行作为分隔
    return re.sub(r'\n\s*\n\s*\n', '\n\n', text)


def merge_bat_continuation(text: str) -> str:
    """合并 BAT ^ 行续接"""
    # ^ 后面的换行和空白被合并，同时清理续接前后多余空格

    def _merge_caret(m):
        return ''

    prev = None
    current = text
    while prev != current:
        prev = current
        current = _BAT_LINE_CONTINUATION.sub(_merge_caret, current)
    # 清理 ^ 位置留下的多余空格（^ 前可能有空格，下一行开头也可能有空格）
    current = re.sub(r'  +', ' ', current)
    return current


def merge_sh_continuation(text: str) -> str:
    """合并 SH \\ 行续接"""
    prev = None
    current = text
    while prev != current:
        prev = current
        current = _SH_LINE_CONTINUATION.sub(' ', current)
    return current


def has_bat_comment(line: str) -> bool:
    """判断 BAT 行是否为注释"""
    stripped = line.strip()
    if not stripped:
        return False
    # @rem、rem、:: 行
    if stripped.upper().startswith('REM ') or stripped.upper().startswith('REM\t'):
        return True
    if stripped.startswith('::') or stripped.startswith('rem ') or stripped.startswith('rem\t'):
        return True
    return False


def preprocess_script(
    content: str,
    script_type: str = "bat",
    **kwargs,
) -> str:
    """
    预处理脚本文本，返回净化后的内容。

    Args:
        content: 原始脚本文本
        script_type: "bat" | "sh"
        **kwargs:
            collapse_blank: bool = True  折叠连续空行
            strip_trailing_spaces: bool = True  移除行尾空白
            remove_comments: bool = False  是否移除注释行（默认保留）

    Returns:
        预处理后的脚本文本
    """
    if not content:
        return content

    collapse_blank = kwargs.get('collapse_blank', True)
    strip_trailing = kwargs.get('strip_trailing_spaces', True)
    remove_comments = kwargs.get('remove_comments', False)

    # 1. BOM 移除
    text = remove_bom(content)

    # 2. 换行标准化
    text = normalize_line_endings(text)

    # 3. 控制字符清理
    text = clean_control_chars(text)

    # 4. 行续接合并
    if script_type == "bat":
        text = merge_bat_continuation(text)
    elif script_type == "sh":
        text = merge_sh_continuation(text)

    # 5. 行尾空白清理
    if strip_trailing:
        text = '\n'.join(line.rstrip() for line in text.split('\n'))

    # 6. 注释移除（可选）
    if remove_comments:
        lines = text.split('\n')
        cleaned = []
        for line in lines:
            if script_type == "bat" and has_bat_comment(line):
                continue
            elif script_type == "sh" and not _SH_SHEBANG.match(line):
                # 移除以 # 开头的行（但保留 shebang）
                stripped = line.strip()
                if stripped.startswith('#') and not _SH_SHEBANG.match(stripped):
                    continue
            cleaned.append(line)
        text = '\n'.join(cleaned)

    # 7. 空行折叠
    if collapse_blank:
        text = collapse_blank_lines(text)

    return text


def preprocess_lines(
    lines: list,
    script_type: str = "bat",
    **kwargs,
) -> list:
    """
    预处理行列表，返回净化后的行列表（保留空行结构）。

    用于已经 splitlines 的脚本行列表，避免重新 join/split 的损失。
    """
    if not lines:
        return lines

    result = []
    # 先合并所有行（续接需要）
    raw = '\n'.join(lines)
    clean = preprocess_script(raw, script_type=script_type, **kwargs)
    return clean.split('\n')


# 便捷函数
def is_bat_line_continuation(expected: str, actual: str) -> bool:
    """判断实际行是否可能是续接后的结果（用于测试调试）"""
    return '^' in expected or '\\' in expected


__all__ = [
    "preprocess_script",
    "preprocess_lines",
    "remove_bom",
    "normalize_line_endings",
    "clean_control_chars",
    "merge_bat_continuation",
    "merge_sh_continuation",
    "collapse_blank_lines",
    "has_bat_comment",
]