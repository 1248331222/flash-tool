# -*- coding: utf-8 -*-
# flash_tool/core/pipeline.py
"""
Hydra 分析 → 执行引擎 协同中间层
===================================
将 HydraParseResult 的完整分析转化为可执行的 ExecutionPlan，
供 batch_flasher 等执行层消费。

核心流程：
    parse() → HydraParseResult → build_execution_plan() → ExecutionPlan
                                                              ↕
                                                         batch_flasher.create_batch_flash_task()

ExecutionPlan 包含：
    - steps:         向后兼容的旧格式步骤列表
    - analysis:      Hydra display_summary 完整摘要
    - blockers:      阻断原因（非空时 safe_to_flash=False）
    - suggestions:   建议提示（不阻断但用户应关注）
    - safe_to_flash: 是否可以安全刷写

用法：
    plan = build_execution_plan(hydra_result, source="rom", rom_name="xxx")
    if not plan.safe_to_flash:
        print("阻断原因:", plan.blockers)
        return
    # 消费 plan.steps
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class ExecutionPlan:
    """执行计划：Hydra 分析结论 + 刷机执行所需一切"""
    # 向后兼容的旧格式步骤列表
    steps: List[Dict]

    # Hydra display_summary 完整摘要
    analysis: Optional[Dict] = None

    # 阻断原因（为空表示可执行）
    blockers: List[str] = field(default_factory=list)

    # 建议提示（不阻断但对用户有价值）
    suggestions: List[str] = field(default_factory=list)

    # 是否可以安全刷写
    safe_to_flash: bool = True

    # 刷机源
    source: str = "rom"
    rom_name: str = ""

    def to_dict(self) -> Dict:
        return {
            "steps": self.steps,
            "analysis": self.analysis,
            "blockers": self.blockers,
            "suggestions": self.suggestions,
            "safe_to_flash": self.safe_to_flash,
            "source": self.source,
            "rom_name": self.rom_name,
        }


# ============================================================
# 规则引擎
# ============================================================

def build_execution_plan(result: Any,
                         source: str = "rom",
                         rom_name: str = "") -> ExecutionPlan:
    """
    将 Hydra 分析结果转化为可执行计划。

    Args:
        result: HydraParseResult 实例
        source: 刷机源类型（"rom" / "local"）
        rom_name: ROM 包名

    Returns:
        ExecutionPlan
    """
    from .step_engine import optimize_step_order
    from .rom_handler import _hydra_steps_to_old

    # 转换步骤为旧格式
    steps = _hydra_steps_to_old(result.steps) if hasattr(result, 'steps') else []
    steps = optimize_step_order(steps)

    # 获取全量分析摘要
    analysis = result.display_summary if hasattr(result, 'display_summary') else None

    blockers: List[str] = []
    suggestions: List[str] = []

    if analysis is None:
        return ExecutionPlan(
            steps=steps,
            analysis=None,
            blockers=["Hydra 分析结果不可用"],
            safe_to_flash=False,
            source=source,
            rom_name=rom_name,
        )

    quality = analysis.get("quality") or {}
    script_check = analysis.get("script_resource_check") or {}
    rom = analysis.get("rom") or {}
    case_profile = analysis.get("case_profile") or {}
    confidence = analysis.get("confidence") or {}

    # ① 质量评分过低 → 阻断
    score = quality.get("score", 100)
    if score < 55:
        blockers.append(
            f"解析质量评分过低（{score} 分），解析结果不可靠，不建议执行"
        )

    # ② 脚本引用文件缺失 → 阻断
    missing = script_check.get("missing_files") or []
    if missing:
        msg = f"脚本引用的 {len(missing)} 个文件在 ROM 中未找到：{', '.join(missing[:3])}"
        if len(missing) > 3:
            msg += f" 等 {len(missing)} 个"
        blockers.append(msg)

    # ③ ROM 缺少关键文件 → 建议
    missing_critical = rom.get("missing_critical") or []
    if missing_critical:
        msg = f"ROM 缺少 {len(missing_critical)} 个关键文件：{', '.join(missing_critical[:3])}"
        if len(missing_critical) > 3:
            msg += f" 等 {len(missing_critical)} 个"
        suggestions.append(msg)

    # ④ 底层固件风险 → 建议
    fw_risks = script_check.get("firmware_risks") or []
    if fw_risks:
        suggestions.append(
            f"涉及 {len(fw_risks)} 个底层固件刷写，请确认机型与平台一致"
        )

    # ⑤ case_profile 低置信度 → 建议
    cp_conf = case_profile.get("confidence", 0)
    if 0 < cp_conf < 0.5:
        suggestions.append(
            f"刷机包类型识别置信度较低（{case_profile.get('vendor_family', 'unknown')}，"
            f"置信度 {cp_conf}），建议人工确认包来源"
        )

    # ⑥ 存在不确定步骤 → 建议
    has_uncertain = analysis.get("has_uncertain_steps", False)
    if has_uncertain:
        placeholder = analysis.get("placeholder", 0)
        estimated = analysis.get("estimated", 0)
        suggestions.append(
            f"脚本包含 {placeholder} 个占位步骤和 {estimated} 个估计步骤，"
            f"实际执行内容可能与分析结果有差异"
        )

    # 安全判断
    safe_to_flash = len(blockers) == 0

    return ExecutionPlan(
        steps=steps,
        analysis=analysis,
        blockers=blockers,
        suggestions=suggestions,
        safe_to_flash=safe_to_flash,
        source=source,
        rom_name=rom_name,
    )


__all__ = [
    "ExecutionPlan",
    "build_execution_plan",
]