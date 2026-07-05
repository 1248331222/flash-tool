# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/bat_parser/pipeline/code_block_builder.py
"""
L5: CodeBlockBuilder — 代码块构建

作用: 将步骤按逻辑边界分组。

处理内容:
    1. 按开关机命令分隔（reboot-bootloader、reboot 等为段边界）
    2. 标记代码块类型（flash / erase / reboot / mixed）
    3. 代码块级别风险汇总（取块内最高风险）

用法:
    from .pipeline.code_block_builder import build_blocks
    blocks = build_blocks(steps)
"""

from typing import List

from ..var_types import HydraStep, CodeBlock


# 可作为段边界的命令子类型
_BOUNDARY_SUBCOMMANDS = {
    "reboot",
    "reboot-bootloader",
    "reboot-fastboot",
    "reboot-edl",
    "reboot-recovery",
}


def _block_overall_risk(steps: List[HydraStep]) -> str:
    """
    计算块内最高风险等级。

    风险权重: CRITICAL > HIGH > MEDIUM > LOW
    """
    risk_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
    max_risk = "LOW"
    max_weight = 1
    for step in steps:
        weight = risk_order.get(step.risk, 1)
        if weight > max_weight:
            max_weight = weight
            max_risk = step.risk
    return max_risk


def _determine_block_type(steps: List[HydraStep]) -> str:
    """
    根据块内步骤的子命令确定块类型。
    """
    subcommands = {s.subcommand for s in steps}
    if subcommands.issubset({"reboot", "reboot-bootloader", "reboot-edl"}):
        return "reboot"
    if "erase" in subcommands and "flash" not in subcommands:
        return "erase"
    if "flash" in subcommands and "erase" not in subcommands:
        return "flash"
    return "mixed"


def build_blocks(steps: List[HydraStep]) -> List[CodeBlock]:
    """
    将步骤列表按开关机边界分组。

    每个 reboot 类命令前结束当前块，reboot 命令作为上一块的收尾。

    Args:
        steps: L4 构建的步骤列表

    Returns:
        List[CodeBlock]: 按逻辑边界分组的代码块列表
    """
    if not steps:
        return []

    blocks = []
    current_chunk = []
    block_index = 0

    for step in steps:
        reboot_like = step.subcommand in _BOUNDARY_SUBCOMMANDS

        if reboot_like and current_chunk:
            # 先把当前块收尾
            block_type = _determine_block_type(current_chunk)
            overall_risk = _block_overall_risk(current_chunk)
            block_index += 1
            blocks.append(CodeBlock(
                block_type=block_type,
                steps=list(current_chunk),
                label=f"block_{block_index}",
                overall_risk=overall_risk,
            ))
            current_chunk = []

            # reboot 命令作为单独块（可选）
            # 或者直接开始新块时不包含 reboot
            current_chunk.append(step)
        else:
            current_chunk.append(step)

    # 收尾最后一个块
    if current_chunk:
        block_type = _determine_block_type(current_chunk)
        overall_risk = _block_overall_risk(current_chunk)
        block_index += 1
        blocks.append(CodeBlock(
            block_type=block_type,
            steps=list(current_chunk),
            label=f"block_{block_index}",
            overall_risk=overall_risk,
        ))

    return blocks


__all__ = ["build_blocks"]
