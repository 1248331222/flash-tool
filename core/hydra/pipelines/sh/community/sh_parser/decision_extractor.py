# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/sh_parser/decision_extractor.py
"""
ShDecisionExtractor — 阶段 2 决策点提取器

扫描沙箱输出的 jsonl，收集所有占位符，
合并同类决策点（${DECISION:slot} 出现 20 次 → 1 个决策点）。
"""

import json
from collections import defaultdict
from typing import Dict, List, Set

from .types import (
    DecisionPriority,
    DecisionType,
    ShDecisionPoint,
)


class ShDecisionExtractor:
    """决策点提取器"""

    def extract(self, jsonl_path: str) -> List[ShDecisionPoint]:
        """
        扫描 jsonl，提取所有决策点。

        Args:
            jsonl_path: 沙箱输出的 jsonl 文件路径

        Returns:
            List[ShDecisionPoint]: 去重合并后的决策点列表
        """
        # var_name → {line_number}
        pending_vars: Dict[str, Set[int]] = defaultdict(set)

        with open(jsonl_path) as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                pending_list = data.get("pending", [])
                if not pending_list:
                    continue
                for var in pending_list:
                    pending_vars[var].add(line_no)

        # 去重合并 → 决策点
        decisions = []
        seen = set()

        for var_name in sorted(pending_vars.keys()):
            # 提取占位符名称（${DECISION:xxx} → xxx）
            name = var_name.strip()
            if name.startswith("${DECISION:") and name.endswith("}"):
                decision_id = name[11:-1]
            else:
                decision_id = name

            if decision_id in seen:
                continue
            seen.add(decision_id)

            decision = self._classify_decision(
                decision_id,
                pending_vars[var_name],
            )
            if decision:
                decisions.append(decision)

        return decisions

    def _classify_decision(self, var_id: str,
                           line_numbers: Set[int]) -> ShDecisionPoint:
        """根据占位符名称推断决策点类型"""
        # 槽位选择
        if var_id == "slot":
            return ShDecisionPoint(
                id="slot",
                type=DecisionType.SLOT_CHOICE,
                description="目标刷机槽位",
                options=["_a", "_b"],
                default="_a",
                affects_lines=len(line_numbers),
            )

        # getvar 未知字段
        if var_id.startswith("getvar_"):
            field = var_id.replace("getvar_", "", 1)
            return ShDecisionPoint(
                id=var_id,
                type=DecisionType.UNKNOWN_GETVAR,
                description=f"getvar {field} 的返回值",
                default="0",
                option_type="text",
                affects_lines=len(line_numbers),
            )

        # 通用决策
        return ShDecisionPoint(
            id=var_id,
            type=DecisionType.INTERACTIVE,
            description=f"需要用户提供的参数: {var_id}",
            default="",
            option_type="text",
            affects_lines=len(line_numbers),
        )


__all__ = ["ShDecisionExtractor"]
