# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/quality_evaluator.py
"""
Hydra — 解析质量评估器
========================
基于 HydraParseResult 中的各项信号，输出统一的解析质量评分。

评分规则：
    初始 100 分，按以下规则扣分：

    扣分项：
    - placeholder_steps 每个 -8，最多 -30
    - estimated_steps 每个 -4，最多 -20
    - is_simple=False -10
    - script_resource_check.missing_files 每个 -10，最多 -30
    - rom_profile.missing_critical 每个 -6，最多 -24
    - firmware_risks 每个 -4，最多 -16

    加分项：
    - recipe_match.confidence >= 0.8 +5
    - rom_profile.platform != "unknown" +5
    - rom_profile.rom_flavor != "unknown" +3
    - script_resource_check 触发且无缺失 +5

    等级：
    90~100  excellent
    75~89   good
    55~74   fair
    0~54    poor

用法：
    from core.hydra.quality_evaluator import evaluate_quality

    report = evaluate_quality(result)
    print(report.score, report.level)
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field


@dataclass
class QualityReport:
    """解析质量报告"""
    score: int = 100
    level: str = "excellent"
    confidence: str = "high"
    warnings: List[str] = field(default_factory=list)
    positive_factors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "level": self.level,
            "confidence": self.confidence,
            "warnings": self.warnings,
            "positive_factors": self.positive_factors,
        }


def evaluate_quality(result: Any) -> QualityReport:
    """
    评估 HydraParseResult 的解析质量。

    Args:
        result: HydraParseResult 实例

    Returns:
        QualityReport
    """
    report = QualityReport()
    score = 100

    # ---- 扣分 ----

    # 1. placeholder_steps（通配符/未确定步骤）
    if result.placeholder_steps > 0:
        penalty = min(result.placeholder_steps * 8, 30)
        score -= penalty
        report.warnings.append(
            f"包含 {result.placeholder_steps} 个占位步骤（通配符或未展开命令）"
        )

    # 2. estimated_steps（条件分支估计步骤）
    if result.estimated_steps > 0:
        penalty = min(result.estimated_steps * 4, 20)
        score -= penalty
        report.warnings.append(
            f"包含 {result.estimated_steps} 个估计步骤（条件分支推断）"
        )

    # 3. is_simple 复杂标记
    if not result.is_simple:
        score -= 10
        report.warnings.append("脚本结构复杂，非完全静态可解析")

    # 4. script_resource_check 缺失文件
    src = getattr(result, 'script_resource_check', None)
    if src is not None:
        # src 是 ScriptResourceCheckResult，缺失文件在 src.existence.missing_files
        existence = getattr(src, 'existence', None)
        missing = getattr(existence, 'missing_files', None) if existence else []
        if missing:
            penalty = min(len(missing) * 10, 30)
            score -= penalty
            for f in missing[:3]:
                report.warnings.append(f"脚本引用 '{f}' 未在 ROM 中找到")

    # 5. ROM Profile 缺失关键文件
    rp = getattr(result, 'rom_profile', None)
    if rp is not None:
        critical = getattr(rp, 'missing_critical', None) or []
        if critical:
            penalty = min(len(critical) * 6, 24)
            score -= penalty
            report.warnings.append(f"ROM 缺少 {len(critical)} 个关键文件")

    # 6. 固件风险
    if src is not None:
        fw_risks = getattr(src, 'firmware_risks', None) or []
        if fw_risks:
            penalty = min(len(fw_risks) * 4, 16)
            score -= penalty
            report.warnings.append(f"涉及 {len(fw_risks)} 个底层固件刷写")

    # ---- 加分 ----

    # 7. 脚本分类匹配成功
    if result.recipe_match and result.recipe_match.matched:
        score += 5
        report.positive_factors.append(f"脚本分类: {result.recipe_match.class_id}")

    # 8. ROM Profile 识别成功
    if rp is not None:
        if getattr(rp, 'platform', 'unknown') != 'unknown':
            score += 5
            report.positive_factors.append(f"ROM 平台已识别: {rp.platform}")
        if getattr(rp, 'rom_flavor', 'unknown') != 'unknown':
            score += 3
            report.positive_factors.append(f"ROM 类型已识别: {rp.rom_flavor}")

    # 9. 资源校验无缺失
    if src is not None:
        existence = getattr(src, 'existence', None)
        if existence is not None:
            if not getattr(existence, 'missing_files', None):
                score += 5
                report.positive_factors.append("所有脚本引用文件均存在")

    # ---- 边界 ----
    score = max(0, min(100, score))

    # ---- 等级 ----
    if score >= 90:
        report.level = "excellent"
        report.confidence = "high"
    elif score >= 75:
        report.level = "good"
        report.confidence = "high"
    elif score >= 55:
        report.level = "fair"
        report.confidence = "medium"
    else:
        report.level = "poor"
        report.confidence = "low"

    report.score = score
    return report


__all__ = [
    "QualityReport",
    "evaluate_quality",
]