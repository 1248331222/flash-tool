# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/bat_parser/var_types.py
"""
BAT 解析器所有管道阶段使用的数据类型定义。
所有模块从此文件导入类型定义。

数据类型流转链路:
    L0: ScriptLine
     → L1: VarDef → VarEnv
     → L2: ExpandedLine
     → L3: RawCommand
     → L4: HydraStep
     → L5: CodeBlock
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


# ─────────────────────────────────────────────
# L0: LineReader 输出
# ─────────────────────────────────────────────

@dataclass
class ScriptLine:
    """
    一行脚本的结构化表示。

    用途: L0 (LineReader) 的输出类型，
         将原始文本行转为便于后续处理的结构。

    Attributes:
        raw: 原始行内容（含前后空白）
        line_number: 在原始脚本中的行号（从 1 开始）
        content: 去除注释和首尾空白后的有效内容
        is_continued: 是否由续行符 '^' 合并而来
    """
    raw: str
    line_number: int
    content: str
    is_continued: bool = False


# ─────────────────────────────────────────────
# L1: VarTracer 输出
# ─────────────────────────────────────────────

@dataclass
class VarDef:
    """
    单个变量的定义信息。

    用途: VarEnv 的子结构。
         追踪某个变量在何处被定义、值是什么、是否条件性的。

    Attributes:
        name: 变量名（大写形式，如 "FASTBOOT"）
        value: SET 语句中 = 右侧的原始值（可能含未展开的 %VAR%）
        line_number: 定义所在的行号
        is_conditional: 是否在 if 分支内定义
        branch_condition: 如果是条件定义，记录条件表达式文本
    """
    name: str
    value: str
    line_number: int
    is_conditional: bool = False
    branch_condition: Optional[str] = None


@dataclass
class VarEnv:
    """
    变量环境——L1 VarTracer 的输出。

    用途: 包含脚本中所有追踪到的变量定义和依赖关系，
         供 L2 CmdExpander 使用。

    Attributes:
        definitions: 变量名 → VarDef 的映射
        dependencies: (引用者, 被引用者) 的依赖边集合
        conditional_defs: 条件分支内的定义（按条件分组）
    """
    definitions: Dict[str, VarDef] = field(default_factory=dict)
    dependencies: Set[Tuple[str, str]] = field(default_factory=set)
    conditional_defs: Dict[str, List[VarDef]] = field(default_factory=dict)


# ─────────────────────────────────────────────
# L2: CmdExpander 输出
# ─────────────────────────────────────────────

@dataclass
class ExpandedLine:
    """
    变量展开后的单行命令。

    用途: L2 (CmdExpander) 的输出类型。

    Attributes:
        content: 展开所有变量后的命令字符串
        source_lines: 此行来源的原始行号列表（for 展开后会对应多个原始行）
        is_conditional: 是否来自条件分支
        condition: 条件表达式文本
        var_bindings: 此行的变量绑定快照（变量名 → 展开时的值）
    """
    content: str
    source_lines: List[int] = field(default_factory=list)
    is_conditional: bool = False
    condition: Optional[str] = None
    var_bindings: Dict[str, str] = field(default_factory=dict)


# ─────────────────────────────────────────────
# L3: CmdExtractor 输出
# ─────────────────────────────────────────────

@dataclass
class RawCommand:
    """
    从展开行中提取到的 fastboot 命令。

    用途: L3 (CmdExtractor) 的输出类型。

    Attributes:
        command: 完整的 fastboot 命令字符串
        source_lines: 来源行号列表
        is_conditional: 是否来自条件分支
        condition: 条件表达式文本
    """
    command: str
    source_lines: List[int] = field(default_factory=list)
    is_conditional: bool = False
    condition: Optional[str] = None


# ─────────────────────────────────────────────
# L4: StepBuilder 输出
# ─────────────────────────────────────────────

@dataclass
class HydraStep:
    """
    一个结构化的刷机步骤。

    用途: L4 (StepBuilder) 的输出类型，
         也是最终供可视化界面使用的步骤单元。

    Attributes:
        command: 完整的 fastboot 命令字符串
        subcommand: 子命令类型: flash / erase / reboot / oem 等
        partition: 目标分区名，如 "boot"、"system"。非分区命令为 None
        path: 镜像文件路径。非 flash 命令为 None
        risk: 风险等级: CRITICAL / HIGH / MEDIUM / LOW
        is_conditional: 是否为条件执行步骤
        condition: 条件表达式文本
        source_lines: 来源行号列表
    """
    command: str
    subcommand: str = ""
    partition: Optional[str] = None
    path: Optional[str] = None
    params: str = ""           # 额外选项参数（如 --disable-verity）
    risk: str = "MEDIUM"
    is_conditional: bool = False
    condition: Optional[str] = None
    source_lines: List[int] = field(default_factory=list)


# ─────────────────────────────────────────────
# L5: CodeBlockBuilder 输出
# ─────────────────────────────────────────────

@dataclass
class CodeBlock:
    """
    按逻辑边界分组后的步骤块。

    用途: L5 (CodeBlockBuilder) 的输出类型。

    Attributes:
        block_type: 块类型: flash / erase / reboot / mixed
        steps: 块内包含的步骤列表
        label: 块的标签（来自脚本注释分隔符或自动命名）
        overall_risk: 块内最高风险等级
    """
    block_type: str = "mixed"
    steps: List[HydraStep] = field(default_factory=list)
    label: str = ""
    overall_risk: str = "MEDIUM"


__all__ = [
    "ScriptLine",
    "VarDef",
    "VarEnv",
    "ExpandedLine",
    "RawCommand",
    "HydraStep",
    "CodeBlock",
]