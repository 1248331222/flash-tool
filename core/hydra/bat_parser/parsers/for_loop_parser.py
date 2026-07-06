# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/bat_parser/parsers/for_loop_parser.py
"""
ForLoopParser — for 循环脚本解析器

处理等级: L3 for_loop
语法特征: L2 + for /L / for %%i in (set)

覆写: _expand() — 使用 expand_with_for_loops 替代基础展开，
      支持 for /L 和 for %%i in (list) 的展开。

用法:
    parser = ForLoopParser()
    blocks = parser.parse(script_content)
"""

from ..parsers.conditional_parser import ConditionalParser
from ..pipeline.cmd_expander import expand_with_for_loops


class ForLoopParser(ConditionalParser):
    """
    for 循环脚本解析器。

    继承 ConditionalParser（含 if 处理），
    在 L2 阶段使用 expand_with_for_loops 加入 for 循环展开。
    """

    def _expand(self, lines, var_env):
        """
        L2: 含 for 展开的命令展开。

        使用 expand_with_for_loops 替代父类的 expand_with_conditionals，
        expand_with_for_loops 内部已包含条件变量处理 + for 循环展开。
        """
        return expand_with_for_loops(lines, var_env)


__all__ = ["ForLoopParser"]