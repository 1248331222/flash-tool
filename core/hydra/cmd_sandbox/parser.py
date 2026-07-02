# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/cmd_sandbox/parser.py
"""
Hydra — Win CMD 沙箱：单行 CMD 解析器

处理：
- & / && / || 操作符
- 重定向解析（> / >> / 2>&1 / 2> / >nul / 2>nul）
- 管道分割（|）
- cmd /c 子命令
- 变量展开 (委托给 runtime)
"""

import re
from typing import List, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class ParsedRedirection:
    """重定向解析结果"""
    stdout_redirect: Optional[str] = None   # > file
    stdout_append: bool = False             # >> file
    stderr_redirect: Optional[str] = None   # 2> file
    stderr_to_stdout: bool = False          # 2>&1
    stdout_to_nul: bool = False             # >nul 或 1>nul
    stderr_to_nul: bool = False             # 2>nul


@dataclass
class ParsedCommandLine:
    """完整解析结果：命令 + 重定向 + 管道"""
    command: str = ""
    redirect: ParsedRedirection = field(default_factory=ParsedRedirection)
    pipe_to: Optional[str] = None           # | 后的命令
    pipe_from: Optional[str] = None         # | 前的命令（仅用于查找）


def parse_redirection(command: str) -> Tuple[str, ParsedRedirection]:
    """
    从命令中解析重定向部分，返回 (纯命令, ParsedRedirection)。

    示例：
      "fastboot getvar product > product.txt 2>&1"
      -> ("fastboot getvar product", ParsedRedirection(stdout_redirect="product.txt", stderr_to_stdout=True))

    实现方式：按空格分割 tokens，逐个判断。
    """
    result = ParsedRedirection()
    tokens = command.split()
    clean_tokens = []
    skip_next = False
    for i, tok in enumerate(tokens):
        if skip_next:
            skip_next = False
            continue

        t = tok.strip()
        # 2>&1
        if t == '2>&1' or t == '2>&&1':
            result.stderr_to_stdout = True
            continue
        # 2>nul
        if t in ('2>nul', '2>NUL'):
            result.stderr_to_nul = True
            continue
        # >nul / 1>nul
        if t in ('>nul', '>NUL', '1>nul', '1>NUL'):
            result.stdout_to_nul = True
            continue
        # >> file
        if t == '>>' and i + 1 < len(tokens):
            result.stdout_redirect = tokens[i + 1].strip('"').strip("'")
            result.stdout_append = True
            skip_next = True
            continue
        # > file
        if t == '>' and i + 1 < len(tokens):
            result.stdout_redirect = tokens[i + 1].strip('"').strip("'")
            skip_next = True
            continue
        # 2> file
        if t == '2>' and i + 1 < len(tokens):
            result.stderr_redirect = tokens[i + 1].strip('"').strip("'")
            skip_next = True
            continue
        # 混合形式: >file (无空格)
        m = re.match(r'^>>(\S+)$', t)
        if m:
            result.stdout_redirect = m.group(1).strip('"').strip("'")
            result.stdout_append = True
            continue
        m = re.match(r'^>(\S+)$', t)
        if m:
            result.stdout_redirect = m.group(1).strip('"').strip("'")
            continue
        m = re.match(r'^2>(\S+)$', t)
        if m:
            result.stderr_redirect = m.group(1).strip('"').strip("'")
            continue
        # 混合 2>&1
        m = re.match(r'^2>&1$', t, re.IGNORECASE)
        if m:
            result.stderr_to_stdout = True
            continue

        clean_tokens.append(t)

    return ' '.join(clean_tokens), result


def split_pipe(line: str) -> Tuple[Optional[str], Optional[str]]:
    """
    检查是否有管道 |，返回 (left_cmd, right_cmd)。
    如果没有管道，返回 (line, None)。
    """
    # 避免在 &&/||/& 之前分割
    parts = line.split('|', 1)
    if len(parts) == 2:
        left = parts[0].strip()
        right = parts[1].strip()
        # 检查是否是 || 而不是 |（管道不是 ||）
        if right.startswith('|'):
            return line, None  # 这是 ||，不是管道
        if left:
            return left, right
    return line, None


def is_cmd_c(line: str) -> Optional[str]:
    """
    检查是否是 cmd /c "..." 或 cmd /c ...
    如果是，返回内部命令（去掉外层引号）。
    """
    m = re.match(
        r'^cmd\s*(?:\.exe)?\s*(?:/c|/k)\s+"(.+)"\s*$',
        line, re.IGNORECASE
    )
    if m:
        return m.group(1)
    m = re.match(
        r'^cmd\s*(?:\.exe)?\s*(?:/c|/k)\s+(.+)$',
        line, re.IGNORECASE
    )
    if m:
        return m.group(1).strip()
    return None


def is_set_line(line: str) -> Tuple[Optional[str], Optional[str]]:
    """检查是否是 set VAR=value 行，返回 (key, value) 或 (None, None)。"""
    m = re.match(r'^set\s+"?([A-Za-z0-9_]+)"?=(.*)$', line.strip(), re.I)
    if m:
        return m.group(1), m.group(2).strip().strip('"')
    return None, None


def is_echo_line(line: str) -> Optional[str]:
    """检查是否是 echo 行，返回 echo 的内容。"""
    m = re.match(r'^echo\s+(.*)', line.strip(), re.I)
    if m:
        text = m.group(1).strip()
        if text.lower() in ('off', 'on'):
            return None
        return text
    return None


def is_cd_line(line: str) -> Optional[str]:
    """检查是否是 cd / chdir 行，返回目标路径。"""
    m = re.match(r'^(?:cd|chdir)\s+(?:/d\s+)?(.+)$', line.strip(), re.I)
    if m:
        return m.group(1).strip()
    return None


def is_pushd_line(line: str) -> Optional[str]:
    m = re.match(r'^pushd\s+(.+)$', line.strip(), re.I)
    if m:
        return m.group(1).strip()
    return None


def is_popd_line(line: str) -> bool:
    return bool(re.match(r'^popd\s*$', line.strip(), re.I))


def split_operators(line: str) -> List[Tuple[Optional[str], str]]:
    """
    将包含 & / && / || 的行拆分成 [(operator, command)]。
    返回的 operator 可能是 None（第一个命令）、'&&'、'||'、'&'。
    示例：
      "fastboot devices && fastboot reboot"
      -> [(None, "fastboot devices"), ("&&", "fastboot reboot")]
    """
    result: List[Tuple[Optional[str], str]] = []
    pattern = re.compile(r'\s*(&&|\|\||&)\s*')
    parts = pattern.split(line)
    first = True
    for i in range(0, len(parts), 2):
        cmd = parts[i].strip()
        op: Optional[str] = None
        if not first and i > 0:
            op = parts[i - 1].strip()
        if cmd:
            result.append((op, cmd))
        first = False
    return result


def strip_redirection(command: str) -> str:
    """移除重定向部分，返回纯命令文本（向后兼容）。"""
    cmd, _ = parse_redirection(command)
    return cmd


__all__ = [
    "split_operators", "strip_redirection", "is_cmd_c",
    "is_set_line", "is_echo_line", "is_cd_line",
    "is_pushd_line", "is_popd_line",
    "parse_redirection", "ParsedRedirection", "ParsedCommandLine",
    "split_pipe",
]