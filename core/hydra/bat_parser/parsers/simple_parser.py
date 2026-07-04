# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/bat_parser/parsers/simple_parser.py
"""
SimpleParser — 简单脚本解析器

处理等级: L1 simple
语法特征: SET 变量定义 + %VAR% 引用，无控制流（无 if/for/goto）

组装管道: L0 → L1(基础版) → L2(基础版) → L3 → L4 → L5

返回: List[CodeBlock]（结构化代码块列表）

用法:
    parser = SimpleParser()
    blocks = parser.parse(script_content)
"""

from typing import List

from ..var_types import HydraStep, CodeBlock
from ..parsers.base_parser import BaseParser
from ..pipeline.var_tracer import trace_variables
from ..pipeline.cmd_expander import expand
from ..pipeline.cmd_extractor import extract
from ..pipeline.step_builder import build_steps
from ..pipeline.code_block_builder import build_blocks


class SimpleParser(BaseParser):
    """
    简单脚本解析器。

    处理纯变量 + fastboot 命令的脚本。
    管道: L0(read_lines) → L1(trace_variables) → L2(expand)
          → L3(extract) → L4(build_steps) → L5(build_blocks)
    """

    def parse(self, content: str) -> List[CodeBlock]:
        """
        解析简单难度 BAT 脚本。

        Args:
            content: 脚本完整文本

        Returns:
            List[CodeBlock]: 按逻辑边界分组的步骤块列表
        """
        # L0: 行读取
        lines = self._read_lines(content)

        # L1: 变量追踪
        var_env = self._trace_variables(lines)

        # L2: 变量展开
        expanded = self._expand(lines, var_env)

        # L3: 命令提取
        commands = self._extract(expanded)

        # L4: 步骤构建
        steps = self._build_steps(commands)

        # L5: 代码块构建
        blocks = self._build_blocks(steps)

        return blocks

    # ─────────────────────────────────────────────
    # 管道阶段方法（可被子类覆写）
    # ─────────────────────────────────────────────

    def _trace_variables(self, lines):
        """
        L1: 变量追踪。

        子类覆写此方法以添加 if 分支收集 / !VAR! 追踪等。
        """
        return trace_variables(lines)

    def _expand(self, lines, var_env):
        """
        L2: 命令展开。

        子类覆写此方法以添加 for 展开 / 条件标记 / 延迟展开等。
        """
        return expand(lines, var_env)

    def _extract(self, expanded_lines):
        """
        L3: 命令提取。
        """
        return extract(expanded_lines)

    def _build_steps(self, commands):
        """
        L4: 步骤构建。
        """
        return build_steps(commands)

    def _build_blocks(self, steps):
        """
        L5: 代码块构建。
        """
        return build_blocks(steps)


__all__ = ["SimpleParser"]
