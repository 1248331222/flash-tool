# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/sh_parser/__init__.py
"""
SH 解析器引擎 — 基类模板

此文件是公共基类模板，禁止直接实例化。
各子管线(core/hydra/pipelines/sh/*/) 下的 sh_parser 私有副本
才是可用的解析引擎，子管线的 pipeline.py 从私有副本 import 可正常使用。

如需修改沙箱行为，请修改各子管线私有副本，
或修改此基类模板后重新分发到各子管线。
"""

import json
import os
from typing import Dict, List, Optional

from .types import (
    DecisionPriority,
    DecisionType,
    ShParseMode,
    ShDecisionPoint,
    ShPreScanReport,
    ShParseResult,
)
from .profiles import get_profile
from .pre_scanner import ShPreScanner
from .sandbox.runner import ShSandboxRunner
from .decision_extractor import ShDecisionExtractor
from .command_expander import ShCommandExpander
from .command_reader import ShCommandReader
from .risk_analyzer import ShRiskAnalyzer
from .block_builder import ShBlockBuilder


class ShEngine:
    """
    SH 解析器引擎 — 基类模板

    标记为 is_base=True 的为公共模板，直接实例化会报错。
    各子管线私有副本（位于 pipelines/sh/*/sh_parser/）可正常使用。
    """
    is_base = True

    def __init__(self, mode: ShParseMode = ShParseMode.FULL,
                 profile: Optional[str] = None,
                 getvar_defs: Optional[Dict[str, str]] = None,
                 extra_env: Optional[Dict[str, str]] = None,
                 filter_getvar: bool = True):
        # ─────────────────────────────────────────────────────
        # 防调用策略：检测当前文件是否位于公共模板目录
        # 公共模板路径: core/hydra/sh_parser/
        # 子管线私有路径: core/hydra/pipelines/sh/*/sh_parser/
        # ─────────────────────────────────────────────────────
        caller_dir = os.path.dirname(os.path.abspath(__file__))
        if 'pipelines/sh/' not in caller_dir:
            raise RuntimeError(
                "\n"
                "╔══════════════════════════════════════════════════════════════╗\n"
                "║  ShEngine 是基类模板，永久禁止直接实例化或调用。         ║\n"
                "║  请使用各 SH 子管线私有副本:                                ║\n"
                "║  core/hydra/pipelines/sh/*/sh_parser/__init__.py            ║\n"
                "║  子管线: native / vendor / community /                      ║\n"
                "║  converted / minimal / generic                               ║\n"
                "╚══════════════════════════════════════════════════════════════╝"
            )
        """
        Args:
            mode: 解析模式
            profile: Profile 名称（"native" / "minimal" / ...）
            getvar_defs: 覆盖默认 getvar 模拟值
            extra_env: 额外的沙箱环境变量
        """
        self.mode = mode

        # 加载 Profile
        self.profile = get_profile(profile) if profile else None

        # 合并 getvar_defs
        final_getvars = getvar_defs
        if self.profile and hasattr(self.profile, 'apply_getvar'):
            # Profile 的 getvar 覆盖默认值
            if final_getvars:
                final_getvars = self.profile.apply_getvar(final_getvars)
            else:
                final_getvars = self.profile.getvar_defs

        # 合并 extra_env
        final_env = dict(extra_env or {})
        if self.profile:
            final_env.update(self.profile.extra_env)

        # 初始化各阶段组件
        self.pre_scanner = ShPreScanner()
        self.sandbox_runner = ShSandboxRunner(
            getvar_defs=final_getvars,
            extra_env=final_env,
            timeout=self.profile.timeout if self.profile else 30,
        )
        self.decision_extractor = ShDecisionExtractor()
        self.filter_getvar = filter_getvar
        self.command_expander = ShCommandExpander(filter_getvar=filter_getvar)
        self.command_reader = ShCommandReader()
        self.risk_analyzer = ShRiskAnalyzer()
        self.block_builder = ShBlockBuilder()

    def parse(self, content: str, script_path: str, rom_dir: str,
              user_decisions: Optional[Dict[str, str]] = None,
              jsonl_path: Optional[str] = None) -> ShParseResult:
        """
        执行完整解析流程。

        Args:
            content: 原始 SH 脚本内容
            script_path: SH 脚本的完整路径
            rom_dir: ROM 包根目录
            user_decisions: 用户已做的决议（None 表示等待用户决策）
            jsonl_path: 可选的沙箱输出 jsonl 路径（供测试用）

        Returns:
            ShParseResult:
                - pending_decisions 非空 → 需要用户先选择
                - steps/blocks 非空 → 解析已完成
        """
        # 阶段 0: 前置扫描
        report = self.pre_scanner.scan(content)

        # 速览模式 → 不进沙箱
        if self.mode == ShParseMode.SKETCH:
            return ShParseResult(
                mode=self.mode,
                pre_scan_report=report,
            )

        # 沙箱不可用 → 在此处可以降级到静态解析
        if not report.sandbox_feasible:
            return ShParseResult(
                mode=self.mode,
                pre_scan_report=report,
                pending_decisions=self._make_blocking_decisions(report),
            )

        # 阶段 1: 沙箱执行
        if jsonl_path is None:
            jsonl_path = self.sandbox_runner.run(script_path, rom_dir)
        if not os.path.exists(jsonl_path):
            return ShParseResult(
                mode=self.mode,
                total_steps=0,
                pre_scan_report=report,
            )

        # 阶段 2: 决策点提取
        decisions = self.decision_extractor.extract(jsonl_path)

        # 阶段 3: 等待用户决议
        if decisions and user_decisions is None:
            return ShParseResult(
                mode=self.mode,
                pre_scan_report=report,
                pending_decisions=decisions,
            )

        resolutions = user_decisions or {}

        # 阶段 4: 展开 + 分析
        return self._expand_and_analyze(
            jsonl_path, resolutions, rom_dir, report
        )

    def resolve(self, result: ShParseResult,
                resolutions: Dict[str, str],
                jsonl_path: str, rom_dir: str) -> ShParseResult:
        """
        用户做出决议后继续解析。

        Args:
            result: 之前的 ShParseResult（有 pending_decisions）
            resolutions: 用户决议 {决策id: 值}
            jsonl_path: 沙箱输出的 jsonl 路径
            rom_dir: ROM 包根目录

        Returns:
            ShParseResult: 最终解析结果
        """
        report = result.pre_scan_report or ShPreScanReport()
        return self._expand_and_analyze(
            jsonl_path, resolutions, rom_dir, report
        )

    def _expand_and_analyze(self, jsonl_path: str,
                            resolutions: Dict[str, str],
                            rom_dir: str,
                            report: ShPreScanReport) -> ShParseResult:
        """阶段 4 内部实现"""
        # 4a: 展开占位符
        commands = self.command_expander.expand(jsonl_path, resolutions)

        # 4b: 命令结构化
        steps = self.command_reader.parse(commands)

        # 4c: 风险分析
        steps = self.risk_analyzer.analyze(steps, rom_dir, self.mode)

        # 4d: 分组
        blocks = self.block_builder.build(steps)

        # 统计
        total_steps = len(steps)
        missing_files = []
        for block in blocks:
            missing_files.extend(block.missing_files)

        return ShParseResult(
            mode=self.mode,
            steps=steps,
            blocks=blocks,
            total_steps=total_steps,
            missing_files=missing_files,
            decisions_resolved=resolutions,
            pre_scan_report=report,
        )

    def _make_blocking_decisions(
        self, report: ShPreScanReport
    ) -> List[ShDecisionPoint]:
        """沙箱不可用时的阻塞性决策"""
        decisions = []
        for reason in report.blocked_reasons:
            decisions.append(ShDecisionPoint(
                id="blocked",
                type=DecisionType.INTERACTIVE,
                description=reason,
                options=["继续使用静态解析", "取消"],
                default="继续使用静态解析",
            ))
        return decisions


__all__ = ["ShEngine"]