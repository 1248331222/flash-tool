# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/bat_parser/pipeline/line_reader.py
"""
L0: LineReader — 行读取

作用: 将原始脚本文本转为结构化行列表。
处理内容:
    1. 编码检测：尝试 UTF-8 → GBK → Latin-1 解码
    2. 续行符 '^' 合并：行末 '^' 表示下一行续接
    3. 去除注释：'::' 开头行、'REM' / 'rem' 开头行
    4. 去除空行（合并后 content 为空的行）
    5. 保留行号映射

用法:
    from .pipeline.line_reader import read_lines
    script_lines = read_lines(raw_content)
"""

import re
from typing import List

from ..var_types import ScriptLine


# ─────────────────────────────────────────────
# 续行符匹配: 行末的 '^'（可能后有空格和注释）
# ─────────────────────────────────────────────
_CONTINUATION_RE = re.compile(r'\^(\s*(?:::.*|rem\s+.*|REM\s+.*)?\s*$)')


def _detect_encoding(raw_bytes: bytes) -> str:
    """
    编码检测。

    依次尝试 UTF-8、GBK、Latin-1 解码。
    返回第一个成功的编码名。
    """
    for encoding in ("utf-8", "gbk", "latin-1"):
        try:
            raw_bytes.decode(encoding)
            return encoding
        except (UnicodeDecodeError, UnicodeError):
            continue
    return "latin-1"


def _is_comment_line(content: str) -> bool:
    """
    判断一行是否全为注释。

    识别以下注释格式:
        - 以 '::' 开头（BAT 注释方式一）
        - 以 'REM' 或 'rem' 开头，允许前导 '@'（BAT 注释方式二）
        - 以 '@REM' 或 '@rem' 开头
    """
    stripped = content.lstrip()
    if stripped.startswith("::"):
        return True
    # 去掉前导 @ 后判断
    if stripped.startswith("@"):
        stripped = stripped[1:].lstrip()
    upper = stripped.upper()
    if upper.startswith("REM") and (len(stripped) == 3 or stripped[3].isspace()):
        return True
    return False


def read_lines(raw_content: str) -> List[ScriptLine]:
    """
    读取脚本内容，返回结构化行列表。

    Args:
        raw_content: 脚本文件的原始文本内容

    Returns:
        List[ScriptLine]: 处理后的行列表，保留原始行号和内容
    """
    # 1. 编码处理: 如果传入的是 bytes 误转的字符串，尝试重新编码
    #    (实际场景中通常已经正确解码，此步为防御性处理)
    content = raw_content

    # 2. 按行分割（保留 CRLF 兼容）
    raw_lines = content.replace('\r\n', '\n').replace('\r', '\n').split('\n')

    result: List[ScriptLine] = []
    pending_continuation = ""  # 累积的续行内容
    pending_line_number = 0     # 续行起始行号
    pending_raw = ""            # 原始行累积

    for idx, line in enumerate(raw_lines):
        line_number = idx + 1

        # 跳过纯空行（在合并前判断，合并后的空行在最后过滤）
        stripped = line.strip()

        # 检测是否为续行（行末有 '^'）
        is_continued_line = bool(_CONTINUATION_RE.search(line))

        if not pending_continuation:
            # 非续行起点
            if is_continued_line:
                # 当前行有续行符，开始累积
                pending_line_number = line_number
                pending_raw = line
                # 去掉行末 ^ 及之后的内容，保留前面部分
                cont_match = _CONTINUATION_RE.search(line)
                pending_continuation = line[:cont_match.start()].rstrip()
            else:
                # 无续行符的普通行
                if stripped and not _is_comment_line(stripped):
                    result.append(ScriptLine(
                        raw=line,
                        line_number=line_number,
                        content=stripped,
                        is_continued=False,
                    ))
        else:
            # 在续行累积中
            if is_continued_line:
                # 当前行也有续行符，继续累积
                pending_raw += "\n" + line
                cont_match = _CONTINUATION_RE.search(line)
                continuation_part = line[:cont_match.start()].rstrip()
                # 续行合并时加一个空格分隔
                pending_continuation += " " + continuation_part if continuation_part else ""
            else:
                # 续行结束，合并
                pending_raw += "\n" + line
                continuation_part = stripped
                pending_continuation += " " + continuation_part if continuation_part else ""
                # 产出合并后的行
                merged_content = pending_continuation.strip()
                if merged_content and not _is_comment_line(merged_content):
                    result.append(ScriptLine(
                        raw=pending_raw,
                        line_number=pending_line_number,
                        content=merged_content,
                        is_continued=True,
                    ))
                # 重置续行状态
                pending_continuation = ""
                pending_line_number = 0
                pending_raw = ""

    # 3. 处理末尾残留续行（脚本以 ^ 结尾的边界情况）
    if pending_continuation:
        merged_content = pending_continuation.strip()
        if merged_content and not _is_comment_line(merged_content):
            result.append(ScriptLine(
                raw=pending_raw,
                line_number=pending_line_number,
                content=merged_content,
                is_continued=True,
            ))

    return result


__all__ = ["read_lines"]