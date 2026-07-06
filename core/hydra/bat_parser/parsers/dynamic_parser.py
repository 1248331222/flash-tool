# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/bat_parser/parsers/dynamic_parser.py
"""
DynamicParser — 动态变量脚本解析器

处理等级: L6 dynamic_var
语法特征: L5 + for /f 命令输出捕获 + getvar

覆写: _trace_variables() — 识别 for /f 块，标记捕获变量为动态
      _expand() — 继承 DelayedParser 的延迟展开 + 条件多值展开

注：for /f 实际输出值在运行时才能确定，静态解析保留两套分支。

用法:
    parser = DynamicParser()
    blocks = parser.parse(script_content)
"""

import re
from typing import List, Dict

from ..var_types import ScriptLine, VarEnv, VarDef
from ..parsers.delayed_parser import DelayedParser
from ..pipeline.var_tracer import trace_variables, collect_if_blocks
from ..pipeline.cmd_expander import expand_with_delayed, _find_block_ranges


def _collect_for_f_blocks(lines: List[ScriptLine], var_env: VarEnv) -> VarEnv:
    """
    识别 for /f 块，将块内 SET 标记为动态捕获变量。

    for /f "options" %%x in ('command') do ( ... )
    块内的 SET 变量标记为 is_dynamic=True。

    Args:
        lines: 脚本行列表
        var_env: 已追踪基础变量的 VarEnv

    Returns:
        VarEnv: 更新后的变量环境
    """
    _FOR_F_RE = re.compile(
        r'^\s*for\s+/[fF]\b',
        re.IGNORECASE,
    )
    _SET_RE = re.compile(
        r'^\s*SET\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<value>.*)',
        re.IGNORECASE,
    )

    _, for_blocks = _find_block_ranges(lines)

    for line in lines:
        if _FOR_F_RE.match(line.content):
            # 找到 for /f 块，标记块内的 SET 为动态
            start_ln = line.line_number
            # 找到对应 for 块的 end
            for fs, fe, fv, fr in for_blocks:
                if fs == start_ln:
                    # 标记这个块内的所有 SET 变量
                    for inner_line in lines:
                        if fs < inner_line.line_number < fe:
                            set_match = _SET_RE.match(inner_line.content)
                            if set_match:
                                var_name = set_match.group("name").upper()
                                if var_name in var_env.definitions:
                                    var_env.definitions[var_name].is_conditional = True
                                    var_env.definitions[var_name].branch_condition = "for/f_dynamic"
                    break

    return var_env


class DynamicParser(DelayedParser):
    """
    动态变量脚本解析器。

    继承 DelayedParser（含延迟展开 + 嵌套 for），
    在 L1 阶段加入 for /f 动态变量标记。
    L2 阶段使用 expand_with_delayed（已含 !VAR! + for 展开）。
    """

    def _trace_variables(self, lines):
        """
        L1: 变量追踪 + if 分支收集 + for /f 动态变量标记。
        """
        var_env = trace_variables(lines)
        var_env = collect_if_blocks(lines, var_env)
        var_env = _collect_for_f_blocks(lines, var_env)
        return var_env


__all__ = ["DynamicParser"]
