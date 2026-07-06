# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/sh_parser/risk_analyzer.py
"""
ShRiskAnalyzer — 阶段 4c 风险分析器

功能：
  1. 分区风险定级（查 partition_knowledge 表）
  2. 参数风险检测（--disable-verity → CRITICAL）
  3. 顺序校验（对照标准刷写顺序）
  4. 文件存在性校验（受解析模式控制）
  5. reanalyze 接口（供前端编辑步骤后调用）
"""

import os
import re
from typing import List, Optional

from .types import ShParseMode, ShStep
from .partition_knowledge import (
    CRITICAL_PARTITIONS,
    HIGH_PARTITIONS,
    get_partition_risk,
    get_standard_order_position,
    PARAM_RISK_RULES,
)


class ShRiskAnalyzer:
    """风险分析器"""

    # 参数风险检测正则（预编译）
    _PARAM_RULES = [
        (re.compile(rule, re.IGNORECASE), desc)
        for rule, desc in PARAM_RISK_RULES
    ]

    def analyze(self, steps: List[ShStep], rom_dir: str,
                mode: ShParseMode = ShParseMode.FULL) -> List[ShStep]:
        """
        完整分析：风险定级 + 顺序校验 + 文件校验。

        Args:
            steps: ShCommandReader 解析后的步骤
            rom_dir: ROM 包根目录（文件校验用）
            mode: 解析模式

        Returns:
            List[ShStep]: 已定级+校验后的步骤
        """
        # 1. 风险定级
        steps = self._apply_risk(steps)

        # 2. 参数检测
        steps = self._check_params(steps)

        # 3. 顺序校验
        steps = self._check_order(steps)

        # 4. 文件校验（受模式控制）
        if mode == ShParseMode.FULL:
            steps = self._check_files(steps, rom_dir)

        return steps

    def reanalyze(self, steps: List[ShStep],
                  rom_dir: str) -> List[ShStep]:
        """
        用户编辑步骤后重新分析。
        仅做风险定级和文件校验，顺序校验保持用户编辑后的顺序。

        Args:
            steps: 用户编辑后的步骤
            rom_dir: ROM 包根目录

        Returns:
            List[ShStep]: 重新定级后的步骤
        """
        steps = self._apply_risk(steps)
        steps = self._check_params(steps)
        steps = self._check_files(steps, rom_dir)
        return steps

    def _apply_risk(self, steps: List[ShStep]) -> List[ShStep]:
        """分区风险定级"""
        for step in steps:
            if step.subcommand == "flash" and step.partition:
                step.risk = get_partition_risk(step.partition)
            elif step.subcommand == "erase":
                # 擦除操作整体升高一级
                base_risk = get_partition_risk(step.partition) if step.partition else "MEDIUM"
                step.risk = self._bump_risk(base_risk)
            elif step.subcommand in ("reboot", "reboot-bootloader"):
                step.risk = "LOW"
            else:
                step.risk = "MEDIUM"
        return steps

    def _check_params(self, steps: List[ShStep]) -> List[ShStep]:
        """参数风险检测（独立于分区风险）"""
        for step in steps:
            for pattern, desc in self._PARAM_RULES:
                if pattern.search(step.command):
                    step.risk = "CRITICAL"
                    step.notes.append(f"[参数风险] {desc}")
        return steps

    def _check_order(self, steps: List[ShStep]) -> List[ShStep]:
        """顺序校验"""
        # 只对 flash/erase 类步骤做顺序校验
        flash_steps = [
            (i, s) for i, s in enumerate(steps)
            if s.partition and s.subcommand in ("flash", "erase")
        ]

        last_position = -1
        for idx, step in flash_steps:
            pos = get_standard_order_position(step.partition)
            if pos != -1:
                if pos < last_position:
                    note = (
                        f"顺序异常: '{step.partition}' "
                        f"在第 {pos} 位，但前一个标准分区在第 {last_position} 位"
                    )
                    step.notes.append(f"[顺序] {note}")
                last_position = pos
        return steps

    def _check_files(self, steps: List[ShStep],
                     rom_dir: str) -> List[ShStep]:
        """文件存在性校验"""
        for step in steps:
            if step.subcommand != "flash" or not step.file_path:
                continue

            # 跳过 sparsechunk 合成步骤
            if step.sparse_chunk_count > 1:
                continue

            # 构造绝对路径
            file_path = step.file_path
            if not os.path.isabs(file_path):
                file_path = os.path.join(rom_dir, file_path)

            if not os.path.exists(file_path):
                step.notes.append(f"[文件缺失] 镜像文件不存在: {step.file_path}")
            elif os.path.getsize(file_path) == 0:
                step.notes.append(f"[文件错误] 镜像文件大小为 0: {step.file_path}")

        return steps

    def _bump_risk(self, risk: str) -> str:
        """风险等级升一级"""
        bump_map = {
            "LOW": "MEDIUM",
            "MEDIUM": "HIGH",
            "HIGH": "CRITICAL",
            "CRITICAL": "CRITICAL",
        }
        return bump_map.get(risk, "MEDIUM")


__all__ = ["ShRiskAnalyzer"]
