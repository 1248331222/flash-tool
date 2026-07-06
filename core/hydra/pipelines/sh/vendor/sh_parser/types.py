# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/sh_parser/types.py
"""
SH 解析器所有数据类型定义。

数据类型流转:
    pre_scanner  → ShPreScanReport
    sandbox      → jsonl（外部文件格式）
    decision_extractor → List[ShDecisionPoint]
    user_resolution    → Dict[str, str]（决策 id → 值）
    command_expander   → List[str]（纯命令字符串）
    command_reader     → List[ShStep]
    risk_analyzer      → List[ShStep]（已定级+校验）
    block_builder      → List[ShBlock]
    engine 输出        → ShParseResult
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict


# ─────────────────────────────────────────────
# 枚举类型
# ─────────────────────────────────────────────

class DecisionPriority(Enum):
    """决策点优先级 — 决定前端是否弹出交互"""
    SILENT = "silent"   # 不出对话框，信息记录在步骤/摘要中
    CHOOSE = "choose"   # 弹出让用户选择（真正有分叉路径时）


class DecisionType(Enum):
    """决策点类型"""
    SLOT_CHOICE = "slot_choice"
    FILE_EXISTS = "file_exists"
    UNKNOWN_GETVAR = "unknown_getvar"
    INTERACTIVE = "interactive"
    EXIT_LOGIC_SKIPPED = "exit_logic_skipped"


class ShParseMode(Enum):
    """解析模式"""
    FULL = "full"       # 完整：沙箱 + 文件校验 + 风险定级
    DRY_RUN = "dry_run" # 干跑：沙箱执行，跳过文件存在性校验
    SKETCH = "sketch"   # 速览：只做前置扫描，不跑沙箱


# ─────────────────────────────────────────────
# 数据类型
# ─────────────────────────────────────────────

@dataclass
class ShDecisionPoint:
    """一个需要用户决议的决策点"""
    id: str                             # 唯一标识
    type: DecisionType                  # 决策类型
    priority: DecisionPriority = DecisionPriority.CHOOSE
    description: str = ""               # 人类可读描述
    options: List[str] = field(default_factory=list)  # 选项列表
    default: str = ""                   # 默认值
    option_type: str = "choice"         # "choice" | "text"
    affects_lines: int = 0              # 影响多少条命令


@dataclass
class ShPreScanReport:
    """前置扫描报告"""
    total_lines: int = 0
    estimated_steps: int = 0
    health: str = "excellent"           # "excellent"|"good"|"warning"|"blocked"
    sandbox_feasible: bool = True
    blocked_reasons: List[str] = field(default_factory=list)
    unknown_getvars: List[str] = field(default_factory=list)
    dangerous_commands: List[str] = field(default_factory=list)
    has_source_import: bool = False
    has_interactive_input: bool = False
    has_unknown_flash_tool: bool = False
    exit_logic_detected: bool = False
    auto_decisions: List[str] = field(default_factory=list)
    recommended_mode: str = "sandbox"
    action_items: List[str] = field(default_factory=list)


@dataclass
class ShStep:
    """一条结构化的刷机步骤"""
    command: str                        # 完整 fastboot 命令
    subcommand: str = ""                # flash/erase/reboot/getvar/...
    partition: Optional[str] = None     # 目标分区名
    file_path: Optional[str] = None     # 镜像文件路径
    params: str = ""                    # 额外选项参数（--disable-verity 等）
    risk: str = "MEDIUM"                # CRITICAL/HIGH/MEDIUM/LOW

    is_reboot: bool = False             # 是否为重启类命令
    is_getvar: bool = False             # 是否为 getvar（仅验证用，非刷机操作）
    is_skippable: bool = False          # 用户可跳过（如最后的 reboot）
    sparse_chunk_of: Optional[str] = None  # 如果是 sparsechunk 分片，指向总分区名
    sparse_chunk_count: int = 0         # 分片总数（0 表示非分片）
    source_line: int = 0                # 脚本行号（近似）
    notes: List[str] = field(default_factory=list)  # 分析器附加的备注


@dataclass
class ShBlock:
    """按逻辑边界分组的步骤块"""
    block_type: str = "mixed"           # flash/erase/reboot/mixed
    steps: List[ShStep] = field(default_factory=list)
    label: str = ""
    overall_risk: str = "MEDIUM"
    missing_files: List[str] = field(default_factory=list)


@dataclass
class ShParseResult:
    """SH 解析的最终产出"""
    mode: ShParseMode = ShParseMode.FULL
    steps: List[ShStep] = field(default_factory=list)
    blocks: List[ShBlock] = field(default_factory=list)
    total_steps: int = 0
    missing_files: List[str] = field(default_factory=list)
    decisions_resolved: Dict[str, str] = field(default_factory=dict)
    pre_scan_report: Optional[ShPreScanReport] = None
    pending_decisions: List[ShDecisionPoint] = field(default_factory=list)


__all__ = [
    "DecisionPriority",
    "DecisionType",
    "ShParseMode",
    "ShDecisionPoint",
    "ShPreScanReport",
    "ShStep",
    "ShBlock",
    "ShParseResult",
]
