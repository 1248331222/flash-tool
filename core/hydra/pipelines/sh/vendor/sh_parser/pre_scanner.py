# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/sh_parser/pre_scanner.py
"""
ShPreScanner — 阶段 0 前置扫描器

纯文本正则扫描，不执行任何 shell 命令。
在沙箱执行之前运行，产出健康度报告，
用来判断脚本是否适合沙箱执行、需要什么 Profile。
"""

import re
from typing import List

from .types import ShPreScanReport

# ─────────────────────────────────────────────
# 已知的 getvar 字段（只需要知道名称，值由沙箱决定）
# ─────────────────────────────────────────────

_KNOWN_GETVARS = {
    "product", "anti", "current-slot", "max-download-size",
    "unlocked", "secure", "serialno", "version",
    "token", "hw-version", "battery-voltage", "slot-count",
    "slot-suffixes", "has-slot", "is-userspace",
}

# ─────────────────────────────────────────────
# 检测正则
# ─────────────────────────────────────────────

RE_INTERACTIVE = re.compile(r'^\s*read\s+\S', re.MULTILINE)

RE_DANGEROUS = re.compile(
    r'(?:'
    r'rm\s+(?:-rf\s+)?/[^\s]*'
    r'|dd\s+if=\S+\s+of=\S+'
    r'|mkfs(?:\.[^\s]+)?\s+'
    r'|mke2fs\s+'
    r'|mkswap\s+'
    r'|dd\s+if=/dev/zero'
    r')',
    re.MULTILINE,
)

RE_SOURCE = re.compile(r'^\s*(?:source|\.)\s+(\S+)', re.MULTILINE)

RE_UNKNOWN_TOOL = re.compile(
    r'^\s*(sptool|sctool|bootctl|fastbootd)\s+',
    re.MULTILINE,
)

RE_GETVAR = re.compile(r'getvar\s+(\S+)', re.IGNORECASE)

RE_FOR = re.compile(r'^\s*for\s+', re.MULTILINE)
RE_WHILE = re.compile(r'^\s*while\s+', re.MULTILINE)
RE_IF = re.compile(r'^\s*if\s+', re.MULTILINE)

RE_FASTBOOT_CMD = re.compile(r'^\s*fastboot\s+', re.MULTILINE)

RE_EXIT = re.compile(r'^\s*exit\s+', re.MULTILINE)

RE_SLOT = re.compile(
    r'(?:current-slot|slot-count|slot-suffixes|_a|_b)',
    re.IGNORECASE,
)


class ShPreScanner:
    """前置扫描器"""

    def scan(self, content: str) -> ShPreScanReport:
        """
        执行一次完整扫描，返回报告。

        Args:
            content: 原始 SH 脚本内容

        Returns:
            ShPreScanReport
        """
        lines = content.strip().split('\n') if content else []
        total_lines = len(lines)

        report = ShPreScanReport(
            total_lines=total_lines,
            estimated_steps=self._count_fastboot_commands(content),
        )

        # 检测交互式输入
        if self._detect_interactive(content):
            report.has_interactive_input = True
            report.blocked_reasons.append("脚本包含 read 交互输入，无法沙箱自动执行")

        # 检测非 fastboot 刷机工具
        if self._detect_unknown_tools(content):
            report.has_unknown_flash_tool = True
            report.blocked_reasons.append("脚本包含非 fastboot 刷机工具(sptool/sctool/bootctl)，命令无法被劫持")

        # 检测危险命令
        report.dangerous_commands = self._detect_dangerous(content)

        # 检测 source 引入
        report.has_source_import = self._detect_source(content) is not None

        # 检测 exit 逻辑
        report.exit_logic_detected = self._detect_exit_logic(content)

        # 提取未知 getvar
        report.unknown_getvars = self._extract_unknown_getvars(content)

        # 综合评估健康度
        report.sandbox_feasible = self._assess_sandbox_feasibility(report)
        report.health = self._assess_health(report)
        report.recommended_mode = self._recommend_mode(report)
        report.action_items = self._generate_actions(report)

        return report

    def _detect_interactive(self, content: str) -> bool:
        """检测 read 交互输入"""
        return bool(RE_INTERACTIVE.search(content))

    def _detect_dangerous(self, content: str) -> List[str]:
        """检测危险系统命令"""
        matches = RE_DANGEROUS.findall(content)
        # 去重并截断
        seen = set()
        result = []
        for m in matches:
            if m not in seen:
                seen.add(m)
                result.append(m.strip()[:60])
        return result

    def _detect_source(self, content: str) -> List[str]:
        """检测 source 引入的外部文件"""
        return RE_SOURCE.findall(content)

    def _detect_unknown_tools(self, content: str) -> bool:
        """检测非 fastboot 刷机工具"""
        return bool(RE_UNKNOWN_TOOL.search(content))

    def _detect_exit_logic(self, content: str) -> bool:
        """检测 exit 语句（用于提示）"""
        return bool(RE_EXIT.search(content))

    def _extract_unknown_getvars(self, content: str) -> List[str]:
        """提取未注册的 getvar 字段"""
        matches = RE_GETVAR.findall(content)
        unknown = []
        seen = set()
        for field in matches:
            if field not in seen:
                seen.add(field)
                if field not in _KNOWN_GETVARS:
                    unknown.append(field)
        return unknown

    def _count_fastboot_commands(self, content: str) -> int:
        """粗略估计 fastboot 命令数量"""
        return len(RE_FASTBOOT_CMD.findall(content))

    def _has_slot_related(self, content: str) -> bool:
        """检测脚本是否涉及槽位操作"""
        return bool(RE_SLOT.search(content))

    def _assess_sandbox_feasibility(self, report: ShPreScanReport) -> bool:
        """判断是否适合沙箱执行"""
        if report.has_interactive_input:
            return False
        if report.has_unknown_flash_tool:
            return False
        return True

    def _assess_health(self, report: ShPreScanReport) -> str:
        """评估健康度"""
        if not report.sandbox_feasible:
            return "blocked"
        if report.dangerous_commands:
            return "warning"
        if report.unknown_getvars or report.has_source_import:
            return "good"
        return "excellent"

    def _recommend_mode(self, report: ShPreScanReport) -> str:
        """推荐执行模式"""
        if not report.sandbox_feasible:
            return "static"
        if report.dangerous_commands:
            return "sandbox_with_caution"
        return "sandbox"

    def _generate_actions(self, report: ShPreScanReport) -> List[str]:
        """生成给用户的提示列表"""
        actions = []
        if not report.sandbox_feasible:
            actions.append("脚本含有交互式或未知工具，推荐使用静态解析模式")
        if report.dangerous_commands:
            actions.append(f"检测到危险命令: {', '.join(report.dangerous_commands[:3])}")
            actions.append("沙箱执行时这些命令不会被拦截，请在执行前确认")
        if report.unknown_getvars:
            actions.append(f"发现未注册的 getvar 字段: {', '.join(report.unknown_getvars)}")
            actions.append("将使用占位符，等待用户填值")
        if report.has_source_import:
            actions.append("脚本 source 了外部文件，沙箱执行时请确保文件完整")
        if report.exit_logic_detected:
            actions.append("脚本含 exit 失败中止逻辑，沙箱绕过此检查")
        return actions


__all__ = ["ShPreScanner"]
