# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/sh_parser/block_builder.py
"""
ShBlockBuilder — 阶段 4d 步骤分块

将 ShStep 列表按 reboot 边界分组为 ShBlock。
每块有 block_type、label、overall_risk。
"""

from typing import List

from .types import ShBlock, ShStep


# 可作为段边界的子命令
_BOUNDARY_COMMANDS = {
    "reboot", "reboot-bootloader", "reboot-fastboot",
    "reboot-edl", "reboot-recovery",
}


class ShBlockBuilder:
    """步骤分块器"""

    def build(self, steps: List[ShStep]) -> List[ShBlock]:
        """
        按 reboot 边界分组。

        Args:
            steps: 已定级的 ShStep 列表

        Returns:
            List[ShBlock]: 分块后的块列表
        """
        if not steps:
            return []

        blocks = []
        current = []
        block_index = 0

        for step in steps:
            is_boundary = step.subcommand in _BOUNDARY_COMMANDS

            if is_boundary and current:
                # 当前块收尾
                blocks.append(self._make_block(current, block_index))
                block_index += 1
                current = []

                # reboot 命令放入新块（作为下个块的开头）
                current.append(step)
            else:
                current.append(step)

        # 最后一块
        if current:
            blocks.append(self._make_block(current, block_index))

        return blocks

    def _make_block(self, steps: List[ShStep],
                    index: int) -> ShBlock:
        """从步骤列表创建一个块"""
        block_type = self._determine_type(steps)
        overall_risk = self._calc_risk(steps)
        missing = self._collect_missing(steps)

        label = f"block_{index + 1}"
        if block_type != "mixed":
            label = f"{block_type}_{index + 1}"

        return ShBlock(
            block_type=block_type,
            steps=steps,
            label=label,
            overall_risk=overall_risk,
            missing_files=missing,
        )

    def _determine_type(self, steps: List[ShStep]) -> str:
        """确定块类型"""
        types = {s.subcommand for s in steps}

        if types.issubset(_BOUNDARY_COMMANDS):
            return "reboot"
        if "erase" in types and "flash" not in types:
            return "erase"
        if "flash" in types and "erase" not in types:
            return "flash"
        return "mixed"

    def _calc_risk(self, steps: List[ShStep]) -> str:
        """取块内最高风险"""
        risk_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
        max_risk = "LOW"
        max_weight = 1

        for step in steps:
            weight = risk_order.get(step.risk, 1)
            if weight > max_weight:
                max_weight = weight
                max_risk = step.risk

        return max_risk

    def _collect_missing(self, steps: List[ShStep]) -> List[str]:
        """收集块内缺失的文件"""
        missing = set()
        for step in steps:
            for note in step.notes:
                if note.startswith("[文件缺失]"):
                    # 提取文件名
                    parts = note.split(": ", 1)
                    if len(parts) > 1:
                        missing.add(parts[1])
        return sorted(missing)


__all__ = ["ShBlockBuilder"]
