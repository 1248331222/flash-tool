# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/bat_parser/parsers/delayed_parser.py
"""
DelayedParser — 延迟展开脚本解析器

处理等级: L5 delayed_expansion
语法特征: L4 + !VAR! + setlocal enabledelayedexpansion

覆写: _expand() — 使用 expand_with_delayed 替代，
      在 for 循环体内逐迭代追踪 !VAR! 的 SET 更新。

用法:
    parser = DelayedParser()
    blocks = parser.parse(script_content)
"""

from ..parsers.nested_for_parser import NestedForParser
from ..pipeline.cmd_expander import expand_with_delayed


class DelayedParser(NestedForParser):
    """
    延迟展开脚本解析器。

    继承 NestedForParser（含嵌套 for 展开），
    在 L2 阶段使用 expand_with_delayed 加入 !VAR! 延迟展开。
    """

    def _expand(self, lines, var_env):
        """
        L2: 含延迟展开 + for 循环的命令展开。

        expand_with_delayed 内部处理:
        - for 循环展开
        - 嵌套 for 上下文传递
        - !VAR! 延迟展开（在 for 体内逐迭代追踪 SET 更新）
        """
        return expand_with_delayed(lines, var_env)


__all__ = ["DelayedParser"]
