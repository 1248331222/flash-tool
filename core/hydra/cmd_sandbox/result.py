# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/cmd_sandbox/result.py
"""
Hydra — Win CMD 沙箱：命令执行结果类型
"""

from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class CommandResult:
    """CMD 内置命令或外部命令的执行结果"""
    errorlevel: int = 0
    stdout: List[str] = field(default_factory=list)
    stderr: List[str] = field(default_factory=list)
    captured: Optional[str] = None       # 如果是 fastboot/adb，捕获到的原始命令
    is_fastboot: bool = False           # 是否是 fastboot/adb 命令


__all__ = ["CommandResult"]