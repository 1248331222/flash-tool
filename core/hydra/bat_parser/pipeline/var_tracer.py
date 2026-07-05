# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/bat_parser/pipeline/var_tracer.py
"""
L1: VarTracer — 变量追踪（基础版）

作用: 扫描脚本行，追踪所有 SET 变量定义，构建变量依赖图。

处理内容:
    1. 识别 'SET VAR=value' 直接定义
    2. 识别 'SET /A VAR=expression' 算术定义
    3. 构建变量 → 定义位置 → 引用位置的依赖图
    4. for 变量 '%%i' 严格单字母边界识别

注意:
    本模块为基础版，不处理 if 分支收集（由 ConditionalParser 覆写）。
    for 变量检测用于在 L2 展开时使用，不存入 VarEnv.definitions。

用法:
    from .pipeline.var_tracer import trace_variables, find_for_variables
    var_env = trace_variables(script_lines)
    for_info = find_for_variables(script_lines)
"""

import re
from typing import Dict, List, Set, Tuple, Optional

from ..var_types import ScriptLine, VarDef, VarEnv


# ─────────────────────────────────────────────
# if 分支收集 — ConditionalParser 使用
# ─────────────────────────────────────────────

def collect_if_blocks(lines: List[ScriptLine], var_env: VarEnv) -> VarEnv:
    """
    识别 if ... ( ... ) else ( ... ) 块，将块内 SET 标记为条件定义。

    轻量级行扫描：遇到 if xxx ( 时入栈，遇到匹配的 ) 时出栈。
    栈内的 SET 定义标记为条件定义，存入 conditional_defs。

    Args:
        lines: 脚本行列表
        var_env: 已追踪基础变量的 VarEnv（会被原地修改并返回）

    Returns:
        VarEnv: 更新后的变量环境（含条件定义）
    """
    # 检测 if ... ( 的行
    _IF_BLOCK_RE = re.compile(
        r'^\s*if\s+(.+?)\s*\(',
        re.IGNORECASE,
    )

    in_if_block = False
    current_condition: Optional[str] = None
    block_depth = 0  # 括号嵌套计数

    for line in lines:
        content = line.content

        # 检测 if 块开始
        if_match = _IF_BLOCK_RE.match(content)
        if if_match and not in_if_block:
            current_condition = if_match.group(1).strip()
            in_if_block = True
            block_depth = 1
            # 检查是否有 else 在同一行
            # 处理同行的第一个 (
            continue

        if not in_if_block:
            continue

        # 在 if 块内，更新括号深度
        block_depth += content.count('(') - content.count(')')

        # 检测块内 SET
        set_match = _SET_RE.match(content) or _SET_QUOTED_RE.match(content)
        if set_match:
            var_name = set_match.group("name").upper()
            var_value = set_match.group("value").strip()
            if len(var_value) >= 2:
                if (var_value.startswith('"') and var_value.endswith('"')) or \
                   (var_value.startswith("'") and var_value.endswith("'")):
                    var_value = var_value[1:-1]

            # 展开值中的特殊路径变量
            for sp_var, sp_replacement in _SPECIAL_PATH_VARS.items():
                var_value = var_value.replace(sp_var, sp_replacement)

            # 标记为条件定义
            var_def = VarDef(
                name=var_name,
                value=var_value,
                line_number=line.line_number,
                is_conditional=True,
                branch_condition=current_condition,
            )

            # 存入 conditional_defs
            cond_key = current_condition or "unknown"
            if cond_key not in var_env.conditional_defs:
                var_env.conditional_defs[cond_key] = []
            var_env.conditional_defs[cond_key].append(var_def)

            # 同时也存入 definitions（后续展开时查找）
            var_env.definitions[var_name] = var_def

            # 依赖关系
            refs = _PERCENT_REF_RE.findall(var_value)
            for ref in refs:
                ref_upper = ref.upper()
                if ref_upper != var_name:
                    var_env.dependencies.add((var_name, ref_upper))

        # 检测 else 关键字（说明进入了另一个分支）
        if re.match(r'^\s*\)\s*else\s*\(', content):
            # else 分支，保留相同条件（简化：else 视为条件的反向）
            pass

        # 块结束
        if block_depth <= 0:
            in_if_block = False
            current_condition = None

    return var_env


# ─────────────────────────────────────────────
# 正则模式
# ─────────────────────────────────────────────

# SET 语句: 支持多种格式
# SET VAR=value
# SET "VAR=value"  （整个赋值被引号包裹）
# SET /A VAR=expression
_SET_RE = re.compile(
    r'^\s*SET\s+'
    r'(?:/A\s+)?'
    r'(?P<name>[A-Za-z_][A-Za-z0-9_]*)'
    r'\s*=\s*(?P<value>.*)',
    re.IGNORECASE,
)
# 匹配 "NAME=value" 格式（整行被引号包裹再剥离）
_SET_QUOTED_RE = re.compile(
    r'^\s*SET\s+'
    r'(?:/A\s+)?'
    r'"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<value>[^"]*)"',
    re.IGNORECASE,
)

# CMD 特殊路径变量，在追踪阶段就展开
_SPECIAL_PATH_VARS = {
    '%~dp0': './',
    '%~d0': '',
    '%~p0': './',
    '%~dpnx0': '',
    '%0': '',
    '%*': '',
    '%cd%': '.',
}

# %VAR% 引用: 变量名由字母、数字、下划线组成
_PERCENT_REF_RE = re.compile(r'%([A-Za-z_][A-Za-z0-9_]*)%')

# for 变量: %% 后跟严格单个 ASCII 字母
# 使用负向前瞻确保只匹配单字母，避免 %%i_ 被错误匹配
_FOR_VAR_RE = re.compile(r'%%([a-zA-Z])(?![a-zA-Z])')

# for 循环检测: 用于识别哪些行是 for 循环体
_FOR_START_RE = re.compile(
    r'^\s*for\s+(/L\s+|/F\s+|/R\s+|/D\s+)?',
    re.IGNORECASE,
)


# ─────────────────────────────────────────────
# 核心函数
# ─────────────────────────────────────────────

def trace_variables(lines: List[ScriptLine]) -> VarEnv:
    """
    追踪脚本中的 SET 变量定义。

    扫描所有行，识别 SET 语句，构建变量定义表。

    Args:
        lines: L0 处理后的脚本行列表

    Returns:
        VarEnv: 包含变量定义和依赖关系的环境对象
    """
    env = VarEnv()

    for line in lines:
        content = line.content

        # 匹配 SET 语句
        set_match = _SET_RE.match(content) or _SET_QUOTED_RE.match(content)
        if set_match:
            var_name = set_match.group("name").upper()
            var_value = set_match.group("value").strip()

            # 去包裹引号（如果值被引号包围）
            if len(var_value) >= 2:
                if (var_value.startswith('"') and var_value.endswith('"')) or \
                   (var_value.startswith("'") and var_value.endswith("'")):
                    var_value = var_value[1:-1]

            # 展开值中的特殊路径变量（%~dp0 → ./ 等）
            for sp_var, sp_replacement in _SPECIAL_PATH_VARS.items():
                var_value = var_value.replace(sp_var, sp_replacement)

            var_def = VarDef(
                name=var_name,
                value=var_value,
                line_number=line.line_number,
                is_conditional=False,
                branch_condition=None,
            )

            env.definitions[var_name] = var_def

            # 构建依赖关系: 值中的 %VAR% 引用 → 该变量
            refs = _PERCENT_REF_RE.findall(var_value)
            for ref in refs:
                ref_upper = ref.upper()
                if ref_upper != var_name:
                    env.dependencies.add((var_name, ref_upper))

        # 收集命令中的变量引用（用于依赖图补全）
        refs = _PERCENT_REF_RE.findall(content)
        for ref in refs:
            ref_upper = ref.upper()
            if ref_upper not in env.definitions:
                # 被引用但未定义，记录引用方为脚本自身
                env.dependencies.add(("__script__", ref_upper))

    return env


def find_for_variables(lines: List[ScriptLine]) -> Dict[str, List[Tuple[int, str]]]:
    """
    扫描脚本中的 for 变量使用情况。

    检测所有 'for %%x in (...)' 语句，提取变量名和对应的行范围。

    Args:
        lines: L0 处理后的脚本行列表

    Returns:
        Dict[str, List[Tuple[int, str]]]:
            变量名 → [(行号, 循环范围表达式), ...] 的映射
            例如: {"i": [(10, "1,1,2"), (20, "boot dtbo vendor")]}
    """
    for_vars: Dict[str, List[Tuple[int, str]]] = {}

    # for %%x in (set) do ...
    # 注意: 这是简化检测，只提取 for 语句本身的行
    _FOR_DECL_RE = re.compile(
        r'for\s+.*?%%([a-zA-Z])\s+in\s+\(([^)]*)\)',
        re.IGNORECASE
    )

    for line in lines:
        decl_match = _FOR_DECL_RE.search(line.content)
        if decl_match:
            var_name = decl_match.group(1)
            range_expr = decl_match.group(2).strip()
            if var_name not in for_vars:
                for_vars[var_name] = []
            for_vars[var_name].append((line.line_number, range_expr))

    return for_vars


def is_for_start(line_content: str) -> bool:
    """
    判断一行是否为 for 循环的起始行。

    Args:
        line_content: 行内容字符串

    Returns:
        bool: 是否为 for 起始行
    """
    return bool(_FOR_START_RE.match(line_content.lower()))


__all__ = ["trace_variables", "find_for_variables", "is_for_start", "collect_if_blocks"]