# -*- coding: utf-8 -*-
# flash_tool/core/hydra/types.py
"""
Hydra — 数据类型定义
======================
独立的数据类，避免循环导入问题。
"""

from typing import List, Dict
from dataclasses import dataclass, field


@dataclass
class HydraStep:
    """解析出的单步命令"""
    type: str                       # flash / erase / reboot / set_active / oem / getvar / devices / boot
    part: str = ""                  # 目标分区
    fileName: str = ""              # 镜像文件（flash 类型）
    params: str = ""                # 附加参数
    raw: str = ""                   # 原始命令文本
    risk: str = "B"                 # 风险等级 S/A/B/C
    condition: str = ""             # 条件（if 后的表达式）
    loop: str = ""                  # 所属循环原始文本
    call: str = ""                  # call 来源
    dynamic: bool = False           # 是否为动态生成（运行时才能确定）
    line_no: int = 0                # 原始脚本行号
    note: str = ""                  # 步骤说明（例如 devices→检测设备连接）


@dataclass
class HydraParseResult:
    """引擎解析的完整结果"""
    script_type: str                # "bat" | "sh" | "unknown"
    steps: List[HydraStep] = field(default_factory=list)
    is_simple: bool = True          # 是否可静态完全解析
    complex_reason: str = ""        # 复杂原因
    missing_files: List[str] = field(default_factory=list)
    variables: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    total_steps: int = 0
    dynamic_commands: int = 0
    has_delayed_expansion: bool = False


__all__ = ["HydraStep", "HydraParseResult"]