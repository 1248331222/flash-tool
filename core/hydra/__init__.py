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
    parse_method: str = ""
    class_id: str = ""

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
            from .pipelines.registry import get_pipeline
            from .bat_parser import classify as bat_classify
            bat_class_id = bat_classify(content)
            PipelineCls = get_pipeline("bat", bat_class_id)
            if PipelineCls is not None:
                pipeline = PipelineCls()
                result = pipeline.parse(content, script_path, rom_dir)
                result.class_id = bat_class_id
                return result
            return HydraParseResult(script_type="bat", class_id=bat_class_id)

        # SH 脚本 — 使用专用解析器
        if script_type == "sh" or (script_name and script_name.lower().endswith('.sh')):
            from .sh_parser import ShEngine
            from .sh_parser.static_extractor import StaticExtractor
            from .classifier import ScriptClassifier

            # 使用分类器自动选择 Profile
            classifier = ScriptClassifier()
            match = classifier.classify(content, script_type="sh")
            profile = match.class_id if match.matched else None

            from .pipelines.registry import get_pipeline
            # 走独立的 class 管线（每个 class 有自己的副本）
            PipelineCls = get_pipeline("sh", profile)
            if PipelineCls is not None:
                engine = PipelineCls(mode="full")
                result = engine.parse(content, script_path, rom_dir)
            else:
                engine = ShEngine(profile=profile)
                result = engine.parse(content, script_path, rom_dir)
            

            # 沙箱不可用 → 降级到静态提取
            # 沙箱不可用 或 沙箱执行失败 → 降级到静态提取
            no_sandbox = result.pre_scan_report and not result.pre_scan_report.sandbox_feasible
            _sandbox_used = True
            if no_sandbox or (not result.steps and not result.pending_decisions):
                static = StaticExtractor()
                result = static.extract(content, rom_dir)
                _sandbox_used = False

            if not result.steps and not result.pending_decisions:
                return HydraParseResult(script_type="sh", class_id=profile or "generic")

            # 转换为兼容格式
            compat_steps = [
                HydraStepCompat(
                    type=s.subcommand,
                    part=s.partition,
                    fileName=s.file_path,
                    raw=s.command,
                    risk=s.risk,
                    dynamic=bool(s.notes),
                )
                for s in result.steps
            ]

            blocks = _sh_blocks_to_codeblocks(result.blocks)

            _pm = "沙箱(纯Python)" if _sandbox_used else "静态提取"
            return HydraParseResult(
                steps=compat_steps,
                total_steps=result.total_steps,
                missing_files=result.missing_files,
                parse_method=_pm,
                blocks=blocks,
                script_type="sh",
                class_id=profile or "generic",
            )

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


def _sh_blocks_to_codeblocks(sh_blocks) -> List[CodeBlock]:
    """
    将 SH 解析器的 ShBlock 列表转为 HydraEngine 的 CodeBlock 列表。
    """
    code_blocks = []
    for i, sb in enumerate(sh_blocks):
        steps = [
            HydraStep(
                command=s.command,
                subcommand=s.subcommand,
                partition=s.partition,
                path=s.file_path,
                params=s.params,
                risk=s.risk,
                is_conditional=bool(s.notes),
                source_lines=[s.source_line] if s.source_line else [],
            )
            for s in sb.steps
        ]
        code_blocks.append(CodeBlock(
            block_type=sb.block_type,
            steps=steps,
            label=sb.label,
            overall_risk=sb.overall_risk,
        ))
    return code_blocks


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