# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/sh_parser/static_extractor.py
"""
StaticExtractor — 静态正则提取器（沙箱不可用时的降级方案）

当 pre_scanner 标记脚本不可沙箱执行时（read 交互/非 fastboot 工具），
用纯正则提取所有 fastboot 命令。

能力：
  - 提取所有 fastboot flash/erase/getvar/reboot/... 行
  - 识别分区名和文件路径
  - 标记条件分支（if/else 内的命令标记为 conditional）
  - 基本风险定级

限制：
  - 变量展开（$SLOT）保持原样
  - 命令替换（`dirname $0`）保持原样
  - if 分支不展开路径，所有分支的命令都提取并标记 dynamic
"""

import re
from typing import Dict, List, Optional, Set

from .types import ShParseMode, ShStep, ShBlock, ShParseResult
from .command_reader import ShCommandReader
from .risk_analyzer import ShRiskAnalyzer
from .block_builder import ShBlockBuilder


# fastboot 命令检测（宽松：行内 fastboot 所在行，跳过注释行）
_RE_FASTBOOT_LINE = re.compile(
    r'^\s*(?:`[^`]+`)?\s*fastboot',
    re.IGNORECASE | re.MULTILINE,
)

# if 分支检测
_RE_IF = re.compile(r'^\s*if\s+', re.MULTILINE)
_RE_ELSE = re.compile(r'^\s*else\s*', re.MULTILINE)
_RE_FI = re.compile(r'^\s*fi\s*', re.MULTILINE)

# 变量展开检测（仅标记，不做展开）
_RE_VAR = re.compile(r'\$\{?\w+\}?')
_RE_CMD_SUBST = re.compile(r'`[^`]+`|\$\([^)]+\)')


class StaticExtractor:
    """静态正则提取器"""

    def __init__(self):
        self.reader = ShCommandReader()
        self.risk = ShRiskAnalyzer()
        self.blocker = ShBlockBuilder()

    def extract(self, content: str, rom_dir: str = "") -> ShParseResult:
        """从脚本内容中静态提取刷机步骤"""
        steps = []
        _RE_FASTBOOT_LINE = re.compile(r'^\s*fastboot', re.IGNORECASE)
        lines = content.split('\n')

        # 跟踪 if/else/fi 嵌套
        if_nesting = {}
        depth = 0
        for line_no, line in enumerate(lines, 1):
            stripped = line.strip()
            if _RE_IF.match(stripped):
                depth += 1
            if _RE_FI.match(stripped):
                depth = max(0, depth - 1)
            if_nesting[line_no] = depth

        # 逐行扫描 fastboot 命令
        for line_no, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('#') or not stripped:
                continue

            # 跳过命令替换行（行首为反引号）
            if stripped.startswith('`'):
                continue

            if not _RE_FASTBOOT_LINE.match(stripped):
                continue

            cmd = stripped
            notes = []
            if _RE_VAR.search(cmd) or _RE_CMD_SUBST.search(cmd):
                notes.append("[静态] 含未展开变量或命令替换")
            if if_nesting.get(line_no, 0) > 0:
                notes.append("[静态] 位于条件分支内")

            step = self.reader.parse_single(cmd)
            if step:
                step.source_line = line_no
                step.notes.extend(notes)
                steps.append(step)

        # 风险定级
        steps = self.risk.analyze(steps, rom_dir, ShParseMode.FULL)

        # 分组
        blocks = self.blocker.build(steps)

        missing_files = []
        for b in blocks:
            missing_files.extend(b.missing_files)

        return ShParseResult(
            mode=ShParseMode.FULL,
            steps=steps,
            blocks=blocks,
            total_steps=len(steps),
            missing_files=list(set(missing_files)),
        )
__all__ = ["StaticExtractor"]