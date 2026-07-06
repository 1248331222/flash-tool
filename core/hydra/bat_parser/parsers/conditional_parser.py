# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/bat_parser/parsers/conditional_parser.py
"""
ConditionalParser — 条件分支脚本解析器

处理等级: L2 conditional
语法特征: L1 + if exist / if errorlevel + 括号块

覆写: _trace_variables() — 加 if 分支收集（调用 collect_if_blocks）
      _expand() — 加条件多值展开（调用 expand_with_conditionals）

用法:
    parser = ConditionalParser()
    blocks = parser.parse(script_content)
"""

from ..parsers.simple_parser import SimpleParser
from ..pipeline.var_tracer import trace_variables, collect_if_blocks
from ..pipeline.cmd_expander import expand_with_conditionals


class ConditionalParser(SimpleParser):
    """
    条件分支脚本解析器。

    继承 SimpleParser，增强 L1 和 L2:
    - L1: trace_variables 后追加 collect_if_blocks，标记条件定义
    - L2: 使用 expand_with_conditionals，为条件变量生成多版本输出
    """

    def _trace_variables(self, lines):
        """
        L1: 变量追踪 + if 分支收集。

        先调用父类的基础追踪，再用 collect_if_blocks
        识别 if-else 块内的条件 SET 定义。
        """
        var_env = trace_variables(lines)
        var_env = collect_if_blocks(lines, var_env)
        return var_env

    def _expand(self, lines, var_env):
        """
        L2: 条件感知的命令展开。

        使用 expand_with_conditionals 替代基础 expand，
        对条件变量（如 SLOT=_a vs _b）生成多个条件分支版本。
        """
        return expand_with_conditionals(lines, var_env)


__all__ = ["ConditionalParser"]