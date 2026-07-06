# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/classifier.py
"""
脚本分类器

通用:
  - generic：普通模板（通用解析管线）
  - vip：VIP 模板（AI 直出模式，内容相似度匹配）

SH 扩展:
  根据前置扫描报告自动推荐 Profile
"""

import re

from .script_class import ClassMatchResult


# SH 脚本特征检测正则
_RE_VENDOR = re.compile(
    r'flashing\s+unlock|--disable-verit|fastboot\s+flash\s+partition\b',
    re.IGNORECASE,
)
_RE_COMMUNITY = re.compile(
    r'XDA|酷安|forum\.xda-developers|telegra\.ph',
    re.IGNORECASE,
)
_RE_CONVERTED = re.compile(
    r'%VAR%|setlocal|set\s+\w+=\w+.*rem\b',
    re.IGNORECASE,
)

# BAT 脚本特征检测正则
_RE_BAT_INTERACTIVE = re.compile(r'\bset\s+/p\b', re.IGNORECASE)
_RE_BAT_GOTO = re.compile(r'\bgoto\b', re.IGNORECASE)
_RE_BAT_FOR = re.compile(r'\bfor\s+%%\w+\s+in\b', re.IGNORECASE)
_RE_BAT_CONDITIONAL = re.compile(r'\bif\s+(exist|not|errorlevel|\S+\s*==|/i)', re.IGNORECASE)
_RE_BAT_DELAYED = re.compile(r'\bsetlocal\s+enabledelayedexpansion\b', re.IGNORECASE)
_RE_BAT_DYNAMIC = re.compile(r'!\w+!', re.IGNORECASE)
_RE_BAT_NESTED_FOR = re.compile(r'for\s+%%\w+\s+in\b.*\bfor\s+%%\w+\s+in\b', re.IGNORECASE)
_RE_BAT_LABEL = re.compile(r'^:\w+', re.MULTILINE)


class ScriptClassifier:
    """
    脚本分类器。
    支持 BAT 和 SH 两种脚本的特征分类。
    """

    def classify(self, content: str = "",
                 script_type: str = "") -> ClassMatchResult:
        if not content:
            return ClassMatchResult(
                matched=False,
                class_id="generic",
                class_name="空内容",
            )

        if script_type == "sh":
            profile = self._classify_sh(content)
            return ClassMatchResult(
                matched=True,
                class_id=profile,
                class_name=f"Sh 模板 ({profile})",
            )

        if script_type == "bat":
            profile = self._classify_bat(content)
            return ClassMatchResult(
                matched=True,
                class_id=profile,
                class_name=f"Bat 模板 ({profile})",
            )

        return ClassMatchResult(
            matched=True,
            class_id="generic",
            class_name="普通模板",
        )

    def _classify_bat(self, content: str) -> str:
        """根据脚本特征推荐 BAT 管线"""
        # 交互式脚本（set /p）→ interactive
        if _RE_BAT_INTERACTIVE.search(content):
            return "interactive"
        
        # 嵌套 FOR → nested_for
        if _RE_BAT_NESTED_FOR.search(content):
            return "nested_for"
        
        # 有 FOR 循环 → for_loop
        if _RE_BAT_FOR.search(content):
            return "for_loop"
        
        # 延迟展开 → delayed_expansion
        if _RE_BAT_DELAYED.search(content):
            return "delayed_expansion"
        
        # 动态变量（!VAR!）→ dynamic_var
        if _RE_BAT_DYNAMIC.search(content):
            return "dynamic_var"
        
        # 有 GOTO 标签跳转 → goto_label
        if _RE_BAT_GOTO.search(content) and _RE_BAT_LABEL.search(content):
            return "goto_label"
        
        # 有条件分支（if exist/if ==）→ conditional
        if _RE_BAT_CONDITIONAL.search(content):
            return "conditional"
        
        # 简单脚本（纯 fastboot 命令）→ simple
        fastboot_cmds = re.findall(r'^\s*(?:".*?\\fastboot\.exe"|fastboot)\s+', content, re.MULTILINE)
        if fastboot_cmds:
            if len(fastboot_cmds) <= 3:
                return "simple"
            return "plain"
        
        return "plain"

    def _classify_sh(self, content: str) -> str:
        """根据脚本特征推荐 SH Profile"""
        # 厂商高危操作 → vendor
        if _RE_VENDOR.search(content):
            return "vendor"

        # 社区来源 → community
        if _RE_COMMUNITY.search(content):
            return "community"

        # BAT 转换遗留 → converted
        if _RE_CONVERTED.search(content):
            return "converted"

        # 有 for/while/复杂变量 → native
        if re.search(r'\bfor\s+\S+\s+in\b|\bwhile\s+\S+\s+do\b|\$\(|`[^`]+`', content):
            return "native"

        # 基础结构 → minimal
        fastboot_lines = re.findall(r'^\s*fastboot\s+', content, re.MULTILINE)
        if len(fastboot_lines) <= 10:
            return "minimal"

        return "native"


__all__ = ["ScriptClassifier"]