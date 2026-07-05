# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/bat_parser/pipeline/cmd_expander.py
"""
L2: CmdExpander — 命令展开（基础版）

作用: 将脚本行中的 %VAR% 变量引用替换为实际值。

处理内容:
    1. %VAR% → 替换为 VarEnv 中追踪到的值
    2. 未被追踪的 %VAR% 保持原样（记录 warning）
    3. 生成绑定了变量值的 ExpandedLine

注意:
    本模块为基础版，不处理:
    - %%i for 循环展开（由 ForLoopParser 覆写）
    - if 条件分支标记（由 ConditionalParser 覆写）
    - 嵌套 for 展开（由 NestedForParser 覆写）
    - !VAR! 延迟展开（由 DelayedParser 覆写）

用法:
    from .pipeline.cmd_expander import expand
    expanded_lines = expand(script_lines, var_env)
"""

import re
from typing import Dict, List, Tuple

from ..var_types import ScriptLine, VarEnv, VarDef, ExpandedLine


# %VAR% 引用匹配（标准变量名）
_PERCENT_VAR_RE = re.compile(r'%([A-Za-z_][A-Za-z0-9_]*)%')

# CMD 特殊路径/参数变量: %~dp0, %~nx0, %~f0, %*, %0 等
# 这些不是常规变量，但需要展开以保持命令可识别
_SPECIAL_PATH_VARS = {
    '%~dp0': './',           # 脚本所在目录 → 当前目录
    '%~d0': '',
    '%~p0': './',
    '%~dpnx0': '',
    '%0': '',
    '%*': '',
    '%cd%': '.',
}

# %~dp0 类特殊变量匹配（%~ 后跟字母数字）
_SPECIAL_PATH_RE = re.compile(r'%~[a-zA-Z0-9]+[a-zA-Z0-9_]*')


def _expand_single_line(line: ScriptLine, var_env: VarEnv) -> ExpandedLine:
    """
    展开单行中的 %VAR% 引用和特殊路径变量。

    Args:
        line: 脚本行
        var_env: 变量环境

    Returns:
        ExpandedLine: 展开后的命令行
    """
    content = line.content
    var_bindings = {}

    def replace_var(match):
        var_name = match.group(1).upper()
        if var_name in var_env.definitions:
            value = var_env.definitions[var_name].value
            var_bindings[var_name] = value
            return value
        else:
            # 未定义的变量，保持原样
            var_bindings[var_name] = f"<UNDEF:{var_name}>"
            return match.group(0)

    # 第一步: 展开特殊路径变量 (%~dp0 → ./)
    expanded_content = content
    for special_var, replacement in _SPECIAL_PATH_VARS.items():
        expanded_content = expanded_content.replace(special_var, replacement)

    # 第二步: 迭代展开 %VAR%（处理依赖链，最多 20 轮防死循环）
    for _ in range(20):
        prev = expanded_content
        expanded_content = _PERCENT_VAR_RE.sub(replace_var, expanded_content)
        if expanded_content == prev:
            break

    return ExpandedLine(
        content=expanded_content.strip(),
        source_lines=[line.line_number],
        is_conditional=False,
        condition=None,
        var_bindings=var_bindings,
    )


def expand(lines: List[ScriptLine], var_env: VarEnv) -> List[ExpandedLine]:
    """
    展开所有行中的 %VAR% 变量引用。

    Args:
        lines: L0 处理后的脚本行列表
        var_env: L1 追踪的变量环境

    Returns:
        List[ExpandedLine]: 展开变量后的命令行列表
    """
    result = []
    for line in lines:
        expanded = _expand_single_line(line, var_env)
        if expanded.content:
            result.append(expanded)
    return result


def expand_with_conditionals(
    lines: List[ScriptLine],
    var_env: VarEnv,
) -> List[ExpandedLine]:
    """
    展开变量，对条件变量生成多份输出（每个条件值一份）。

    当条件变量（如 SLOT 通过 if-else 同时定义为 _a 和 _b）
    在后续行中被引用时，生成多个 ExpandedLine，分别标记对应条件。

    Args:
        lines: L0 处理后的脚本行列表
        var_env: L1 追踪的变量环境（含条件定义）

    Returns:
        List[ExpandedLine]: 含条件标记的展开命令行列表
    """
    result = []

    # 1. 收集条件变量的多值映射: SLOT → {cond: [_a, _b], ...}
    cond_var_values: Dict[str, Dict[str, List[str]]] = {}
    for cond_key, defs in var_env.conditional_defs.items():
        for vd in defs:
            if vd.name not in cond_var_values:
                cond_var_values[vd.name] = {}
            if cond_key not in cond_var_values[vd.name]:
                cond_var_values[vd.name][cond_key] = []
            cond_var_values[vd.name][cond_key].append(vd.value)

    # 2. 定位 if 块范围和 for 块范围
    if_blocks, for_blocks = _find_block_ranges(lines)

    # 3. 逐行展开
    for line in lines:
        # 跳过 if 块内部的 SET 定义行
        in_any_if = any(start <= line.line_number <= end for start, end in if_blocks)
        is_set_line = bool(re.match(r'^\s*SET\s+', line.content, re.IGNORECASE))

        if in_any_if and is_set_line:
            continue

        if in_any_if and not is_set_line:
            expanded = _expand_single_line(line, var_env)
            if expanded.content:
                result.append(expanded)
            continue

        # 在 if 块之后的行，检测条件变量使用
        if line.line_number > (if_blocks[-1][1] if if_blocks else -1) and cond_var_values:
            uses_cond_var = False
            for var_name in cond_var_values:
                if f'%{var_name}%' in line.content.upper():
                    uses_cond_var = True
                    break

            if uses_cond_var:
                for cond_key, values_map in cond_var_values.items():
                    for cond_expr, cond_vals in values_map.items():
                        for cond_val in cond_vals:
                            cond_content = line.content
                            cond_content = re.sub(
                                rf'%{cond_key}%',
                                cond_val,
                                cond_content,
                                flags=re.IGNORECASE,
                            )
                            temp_line = ScriptLine(
                                raw=line.raw,
                                line_number=line.line_number,
                                content=cond_content,
                                is_continued=line.is_continued,
                            )
                            cond_expanded = _expand_single_line(temp_line, var_env)
                            cond_expanded.is_conditional = True
                            cond_expanded.condition = cond_expr
                            if cond_expanded.content:
                                result.append(cond_expanded)
                continue

        expanded = _expand_single_line(line, var_env)
        if expanded.content:
            result.append(expanded)

    return result


def _find_block_ranges(
    lines: List[ScriptLine],
) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int, str, str]]]:
    """
    定位 if 块和 for 块的行范围。

    Returns:
        if_blocks: [(start_line, end_line), ...]
        for_blocks: [(start_line, end_line, var_name, range_expr), ...]
    """
    if_blocks: List[Tuple[int, int]] = []
    for_blocks: List[Tuple[int, int, str, str]] = []

    # 检测 if 块
    in_if = False
    depth = 0
    start = 0
    for line in lines:
        if_match = re.match(r'^\s*if\s+.+\s*\(', line.content, re.IGNORECASE)
        if if_match and not in_if:
            in_if = True
            depth = 1
            start = line.line_number
            continue
        if in_if:
            depth += line.content.count('(') - line.content.count(')')
            if depth <= 0:
                if_blocks.append((start, line.line_number))
                in_if = False

    # 检测 for 块: for ... do ( ... )
    # 支持嵌套：检测 for 声明行入栈，检测独立 ) 行出栈
    _FOR_DECL_RE = re.compile(
        r'^\s*for\s+(/L\s+)?%%([a-zA-Z])\s+in\s+\(([^)]+)\)\s+do\s*\(',
        re.IGNORECASE,
    )
    for_stack: List[Tuple[int, str, str]] = []
    for line in lines:
        for_match = _FOR_DECL_RE.search(line.content)
        if for_match:
            for_stack.append((
                line.line_number,
                for_match.group(2),
                for_match.group(3).strip(),
            ))
            continue

        # 独立的 ) 行（不带 for 声明和 if 声明），弹出一层 for
        if re.match(r'^\s*\)\s*$', line.content) and for_stack:
            start, var_name, range_expr = for_stack.pop()
            for_blocks.append((start, line.line_number, var_name, range_expr))

    return if_blocks, for_blocks



def expand_with_for_loops(
    lines: List[ScriptLine],
    var_env: VarEnv,
) -> List[ExpandedLine]:
    """
    展开变量 + for 循环（不含延迟展开）。

    Args:
        lines: L0 行列表
        var_env: 变量环境

    Returns:
        List[ExpandedLine]: 展开后的命令行列表
    """
    result = []

    if_blocks, for_blocks = _find_block_ranges(lines)

    for_start_lines = {start for start, _, _, _ in for_blocks}
    for_end_lines = {end for _, end, _, _ in for_blocks}

    for_body_map: Dict[int, List[Tuple[str, str, int, int]]] = {}
    for start, end, var_name, range_expr in for_blocks:
        for ln in range(start + 1, end):
            if ln not in for_body_map:
                for_body_map[ln] = []
            for_body_map[ln].append((var_name, range_expr, start, end))

    for line in lines:
        ln = line.line_number

        if ln in for_start_lines or ln in for_end_lines:
            continue

        in_if = any(s <= ln <= e for s, e in if_blocks)
        is_set = bool(re.match(r'^\s*SET\s+', line.content, re.IGNORECASE))
        if in_if and is_set:
            continue

        # 在 for 块内
        if ln in for_body_map:
            for_entries = for_body_map[ln]
            var_name, range_expr, start, end = max(for_entries, key=lambda x: x[2])

            outer_fors = []
            for fs, fe, fv, fr in for_blocks:
                if fs < ln < fe and fs != start:
                    outer_fors.append((fv, fr, fs, fe))

            iter_values = _parse_for_range(range_expr)

            for cur_val in iter_values:
                content = line.content
                content = re.sub(rf'%%{var_name}', str(cur_val), content, flags=re.IGNORECASE)

                if outer_fors:
                    for ov, ofr, ofs, ofe in outer_fors:
                        outer_vals = _parse_for_range(ofr)
                        for oval in outer_vals:
                            nested_content = content
                            nested_content = re.sub(rf'%%{ov}', str(oval), nested_content, flags=re.IGNORECASE)
                            temp_line = ScriptLine(
                                raw=line.raw, line_number=ln,
                                content=nested_content,
                                is_continued=line.is_continued,
                            )
                            expanded = _expand_single_line(temp_line, var_env)
                            if expanded.content:
                                result.append(expanded)
                else:
                    temp_line = ScriptLine(
                        raw=line.raw, line_number=ln,
                        content=content,
                        is_continued=line.is_continued,
                    )
                    expanded = _expand_single_line(temp_line, var_env)
                    if expanded.content:
                        result.append(expanded)
            continue

        expanded = _expand_single_line(line, var_env)
        if expanded.content:
            result.append(expanded)

    return result


def expand_with_delayed(
    lines: List[ScriptLine],
    var_env: VarEnv,
) -> List[ExpandedLine]:
    """
    展开变量 + for 循环 + 延迟展开 !VAR!。

    在 for 循环体内逐行处理 SET 更新延迟变量表，
    使后续行的 !VAR! 引用取到最新值。

    Args:
        lines: L0 行列表
        var_env: 变量环境

    Returns:
        List[ExpandedLine]: 展开后的命令行列表
    """
    result = []

    if_blocks, for_blocks = _find_block_ranges(lines)

    # 检测是否启用了延迟展开
    has_delayed = any(
        'setlocal' in l.content.lower() and 'enabledelayedexpansion' in l.content.lower()
        for l in lines
    )

    for_start_lines = {start for start, _, _, _ in for_blocks}
    for_end_lines = {end for _, end, _, _ in for_blocks}

    # for 体内的行映射
    for_body_map: Dict[int, List[Tuple[str, str, int, int]]] = {}
    for start, end, var_name, range_expr in for_blocks:
        for ln in range(start + 1, end):
            if ln not in for_body_map:
                for_body_map[ln] = []
            for_body_map[ln].append((var_name, range_expr, start, end))

    # 按 for 块分组处理（而非逐行），确保同一次迭代的延迟变量共享
    processed_lines: set = set()  # 已处理的行号

    for line in lines:
        ln = line.line_number

        if ln in processed_lines:
            continue
        if ln in for_start_lines or ln in for_end_lines:
            continue

        in_if = any(s <= ln <= e for s, e in if_blocks)
        is_set = bool(re.match(r'^\s*SET\s+', line.content, re.IGNORECASE))

        if in_if and is_set:
            continue

        # 检查是否属于某个 for 块
        if ln in for_body_map and has_delayed:
            for_entries = for_body_map[ln]
            var_name, range_expr, start, end = max(for_entries, key=lambda x: x[2])

            outer_fors = []
            for fs, fe, fv, fr in for_blocks:
                if fs < ln < fe and fs != start:
                    outer_fors.append((fv, fr, fs, fe))

            # 收集此 for 块的所有内部行（按行号排序）
            block_lines = [l for l in lines if start < l.line_number < end]
            block_lines.sort(key=lambda l: l.line_number)

            # 预展开 range_expr 中的 %VAR% 引用（如 %PARTITIONS% → 单词列表）
            def _expand_range_var(m):
                name = m.group(1).upper()
                vd = var_env.definitions.get(name)
                return vd.value if vd else m.group(0)
            expanded_range = _PERCENT_VAR_RE.sub(_expand_range_var, range_expr)
            iter_values = _parse_for_range(expanded_range)

            for cur_val in iter_values:
                iter_delayed: Dict[str, str] = {}
                for bl in block_lines:
                    bl_ln = bl.line_number
                    bl_is_set = bool(re.match(r'^\s*SET\s+', bl.content, re.IGNORECASE))
                    bl_content = bl.content
                    bl_content = re.sub(rf'%%{var_name}', str(cur_val), bl_content, flags=re.IGNORECASE)

                    for ov, ofr, ofs, ofe in outer_fors:
                        outer_vals = _parse_for_range(ofr)
                        for oval in outer_vals:
                            bl_content = re.sub(rf'%%{ov}', str(oval), bl_content, flags=re.IGNORECASE)

                    if bl_is_set:
                        set_match = (
                            re.match(r'^\s*SET\s+(/A\s+)?(\w+)\s*=\s*(.+)', bl_content, re.IGNORECASE) or
                            re.match(r'^\s*SET\s+(/A\s+)?"(\w+)\s*=\s*([^"]*)"', bl_content, re.IGNORECASE)
                        )
                        if set_match:
                            dvar_name = set_match.group(2).upper()
                            dvar_value = set_match.group(3).strip()
                            iter_delayed[dvar_name] = dvar_value
                        processed_lines.add(bl_ln)
                        continue

                    bl_content = _expand_delayed_refs(bl_content, iter_delayed)
                    temp_line = ScriptLine(
                        raw=bl.raw, line_number=bl_ln,
                        content=bl_content,
                        is_continued=bl.is_continued,
                    )
                    expanded = _expand_single_line(temp_line, var_env)
                    if expanded.content:
                        result.append(expanded)
                    processed_lines.add(bl_ln)
            continue

        # 非 for 块内的行: 标准展开
        if is_set and has_delayed and ln not in for_body_map:
            # 非 for 块内的 SET 定义保留（如 SKIP_LIST），后续可能被引用
            pass
        expanded = _expand_single_line(line, var_env)
        if expanded.content:
            result.append(expanded)

    return result


def _expand_delayed_refs(content: str, delayed_vars: Dict[str, str]) -> str:
    """
    展开 !VAR! 引用为延迟变量表中的值。

    Args:
        content: 行内容
        delayed_vars: 当前延迟变量表

    Returns:
        str: 替换 !VAR! 后的内容
    """
    def _replace_delayed(match):
        var_name = match.group(1).upper()
        if var_name in delayed_vars:
            return delayed_vars[var_name]
        return match.group(0)

    return re.sub(r'!(\w+)!', _replace_delayed, content)


def _parse_for_range(range_expr: str) -> List[str]:
    """
    解析 for 循环的范围表达式。

    支持:
        - for %%i in (a b c) → ["a", "b", "c"]
        - for %%i in (%VAR%) → 外部需先展开为字符串，本函数不做展开
        - for /L %%i in (start,step,end) → ["1", "2", ..., "end"]

    Args:
        range_expr: 范围表达式字符串

    Returns:
        List[str]: 迭代值列表
    """
    parts = [p.strip() for p in range_expr.split(',')]

    if len(parts) >= 3:
        # /L 形式: (start,step,end)
        try:
            start = int(parts[0])
            step = int(parts[1])
            end = int(parts[2])
            values = []
            current = start
            if step > 0:
                while current <= end:
                    values.append(str(current))
                    current += step
            else:
                while current >= end:
                    values.append(str(current))
                    current += step
            return values
        except ValueError:
            pass

    # 集合形式 / 单元素: 按空格分割
    items = range_expr.replace(',', ' ').split()
    # 返回所有非空项（不限定数字）
    return [item for item in items if item]


__all__ = ["expand", "expand_with_conditionals", "expand_with_for_loops", "expand_with_delayed"]