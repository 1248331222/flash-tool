# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/__init__.py
"""
天树引擎 — 入口模块
=====================
提供统一入口 get_hydra_engine()，返回兼容旧接口的 HydraEngine 实例。
"""

import os
from typing import Optional, List
from dataclasses import dataclass, field

from .classifier import ScriptClassifier
from .pipelines.bat.pipeline import BatPipeline
from .pipelines.sh.pipeline import ShPipeline
from .pipelines.vip.pipeline import VipPipeline
from .bat_parser import get_parser
from .bat_parser.var_types import CodeBlock, HydraStep


# ─────────────────────────────────────────────
# 兼容旧接口的适配类型
# ─────────────────────────────────────────────

@dataclass
class HydraStepCompat:
    """
    兼容旧版 rom_handler.py 期望的 HydraStep 字段。
    从新 HydraStep + 完整命令字符串映射过来。
    """
    type: str = ""
    part: Optional[str] = None
    fileName: Optional[str] = None
    params: str = ""
    raw: str = ""
    risk: str = "MEDIUM"
    dynamic: bool = False
    loop: Optional[str] = None
    call: Optional[str] = None
    condition: Optional[str] = None


@dataclass
class HydraParseResult:
    """
    兼容旧版 rom_handler.py 期望的解析结果。
    """
    steps: List[HydraStepCompat] = field(default_factory=list)
    total_steps: int = 0
    missing_files: List[str] = field(default_factory=list)
    blocks: List[CodeBlock] = field(default_factory=list)
    script_type: str = ""

    @property
    def display_summary(self) -> str:
        """生成摘要文本，供前端展示"""
        if not self.blocks:
            return "解析结果为空"
        lines = []
        for i, block in enumerate(self.blocks):
            lines.append(f"块{i+1} [{block.block_type}] 风险:{block.overall_risk}  步数:{len(block.steps)}")
        lines.append(f"\n总计 {self.total_steps} 步")
        return "\n".join(lines)


class HydraEngine:
    """
    天树引擎实例（兼容旧接口）。

    用法（兼容 rom_handler.py）:
        engine = get_hydra_engine()
        result = engine.parse(txt, script_type="bat", rom_dir=..., script_path=...)
    """

    def parse(
        self,
        content: str,
        script_type: str = "bat",
        rom_dir: str = "",
        script_path: str = "",
    ) -> HydraParseResult:
        """
        解析脚本内容，返回 HydraParseResult。

        Args:
            content: 脚本文本内容
            script_type: 脚本类型 ("bat" / "sh")
            rom_dir: ROM 包根目录
            script_path: 脚本文件完整路径

        Returns:
            HydraParseResult
        """
        script_name = os.path.basename(script_path) if script_path else ""
        is_bat = script_type == "bat" or script_name.lower().endswith('.bat')

        if is_bat:
            parser = get_parser(content, script_name)
            if parser is not None:
                blocks = parser.parse(content)
                steps = _blocks_to_compat_steps(blocks)
                return HydraParseResult(
                    steps=steps,
                    total_steps=len(steps),
                    missing_files=[],
                    blocks=blocks,
                    script_type="bat",
                )
            return HydraParseResult(script_type="bat")

        # SH 脚本暂不支持
        return HydraParseResult(script_type="sh")


def get_hydra_engine() -> HydraEngine:
    """
    获取天树引擎实例。

    兼容旧接口，允许无参调用。
    """
    return HydraEngine()


def _blocks_to_compat_steps(blocks: List[CodeBlock]) -> List[HydraStepCompat]:
    """
    将新 CodeBlock 列表转为旧版兼容步骤列表。
    """
    compat_steps = []
    for block in blocks:
        for step in block.steps:
            cs = HydraStepCompat(
                type=step.subcommand,
                part=step.partition,
                fileName=step.path,
                params=step.params,
                raw=step.command,
                risk=step.risk,
                dynamic=step.is_conditional,
                condition=step.condition,
            )
            compat_steps.append(cs)
    return compat_steps


__all__ = [
    "ScriptClassifier",
    "BatPipeline",
    "ShPipeline",
    "VipPipeline",
    "get_hydra_engine",
    "HydraEngine",
    "HydraParseResult",
    "HydraStepCompat",
]