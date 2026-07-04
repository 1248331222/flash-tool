# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/bat_parser/parsers/nested_for_parser.py
"""
NestedForParser — 嵌套 for 循环脚本解析器

处理等级: L4 nested_for
语法特征: L3 + 嵌套 for + %%i_%%j 边界

覆写: _expand() — 加嵌套 for 展开，处理父子 for 变量上下文传递。

注意:
    不处理延迟展开 !VAR!（由 DelayedParser 后续处理）。

待阶段 3 详细实现。
"""

from typing import List, Dict, Tuple

from ..parsers.for_loop_parser import ForLoopParser
from ..var_types import ScriptLine, VarEnv, ExpandedLine
from ..pipeline.cmd_expander import (
    _expand_single_line,
    _find_block_ranges,
    _parse_for_range,
)
import re


class NestedForParser(ForLoopParser):
    """
    嵌套 for 循环脚本解析器。

    继承 ForLoopParser，在 L2 阶段加入嵌套 for 的上下文传递。
    内侧 for 展开时同时替换外侧 for 变量的当前迭代值。
    """

    def _expand(self, lines, var_env):
        """
        L2: 含嵌套 for 展开的命令展开。
        """
        return _expand_with_nested_for(lines, var_env)


def _expand_with_nested_for(
    lines: List[ScriptLine],
    var_env: VarEnv,
) -> List[ExpandedLine]:
    """
    展开变量 + 嵌套 for 循环。

    支持多层嵌套 for，内层展开时传递外层迭代上下文。

    Args:
        lines: L0 行列表
        var_env: 变量环境

    Returns:
        List[ExpandedLine]: 展开后的命令行列表
    """
    result = []

    if_blocks, for_blocks = _find_block_ranges(lines)

    # 构建 for 父子关系: 按行号排序后，若 for A 的 start < for B 的 start < for A 的 end
    # 则 B 是 A 的子 for
    def _get_outer_for_ctx(line_number: int, for_blocks, current_iter_vals):
        """获取当前行的外层 for 变量迭代上下文"""
        ctx = {}
        for start, end, var_name, range_expr in for_blocks:
            if start < line_number < end:
                if var_name in current_iter_vals:
                    ctx[var_name] = current_iter_vals[var_name]
        return ctx

    # 跳过行集合
    for_start_lines = {start for start, _, _, _ in for_blocks}
    for_end_lines = {end for _, end, _, _ in for_blocks}

    # for 体内的行映射（一行可能属于多个嵌套 for）
    for_body_map: Dict[int, List[Tuple[str, str, int, int]]] = {}
    for start, end, var_name, range_expr in for_blocks:
        for ln in range(start + 1, end):
            if ln not in for_body_map:
                for_body_map[ln] = []
            for_body_map[ln].append((var_name, range_expr, start, end))

    for line in lines:
        ln = line.line_number

        # 跳过 for 声明行
        if ln in for_start_lines:
            continue

        # 跳过 for 结束行
        if ln in for_end_lines:
            continue

        # 跳过 if 块内 SET
        in_if = any(s <= ln <= e for s, e in if_blocks)
        is_set = bool(re.match(r'^\s*SET\s+', line.content, re.IGNORECASE))
        if in_if and is_set:
            continue

        # 跳过 for 块内 SET
        if ln in for_body_map and is_set:
            continue

        # 在 for 块内
        if ln in for_body_map:
            for_entries = for_body_map[ln]
            # 取最内层的 for（start 最大）作为当前展开层
            var_name, range_expr, start, end = max(for_entries, key=lambda x: x[2])

            # 找到所有外层的 for 块（嵌套层级）
            outer_fors = []
            for fs, fe, fv, fr in for_blocks:
                if fs < ln < fe and fs != start:
                    outer_fors.append((fv, fr, fs, fe))

            # 展开当前层
            iter_values = _parse_for_range(range_expr)

            for cur_val in iter_values:
                content = line.content
                # 替换当前层 %%var
                content = re.sub(rf'%%{var_name}', str(cur_val), content, flags=re.IGNORECASE)

                # 展开外层 for 变量
                # 外层需要也展开——但外层值可能是一个范围。
                # 简化策略：外层 for 变量也替换为第一个迭代值
                # 更完善的做法是笛卡尔积展开，但先简化
                for ov, ofr, ofs, ofe in outer_fors:
                    outer_vals = _parse_for_range(ofr)
                    for oval in outer_vals:
                        nested_content = content
                        nested_content = re.sub(
                            rf'%%{ov}', str(oval), nested_content, flags=re.IGNORECASE
                        )

                        temp_line = ScriptLine(
                            raw=line.raw,
                            line_number=ln,
                            content=nested_content,
                            is_continued=line.is_continued,
                        )
                        expanded = _expand_single_line(temp_line, var_env)
                        if expanded.content:
                            result.append(expanded)
                else:
                    # 无外层 for
                    temp_line = ScriptLine(
                        raw=line.raw,
                        line_number=ln,
                        content=content,
                        is_continued=line.is_continued,
                    )
                    expanded = _expand_single_line(temp_line, var_env)
                    if expanded.content:
                        result.append(expanded)
            continue

        # 普通行
        expanded = _expand_single_line(line, var_env)
        if expanded.content:
            result.append(expanded)

    return result


__all__ = ["NestedForParser"]