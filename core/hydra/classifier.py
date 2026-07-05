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


class ScriptClassifier:
    """
    脚本分类器。
    """

    def classify(self, content: str = "",
                 script_type: str = "") -> ClassMatchResult:
        if not content:
            return ClassMatchResult(
                matched=False,
                class_id="generic",
                class_name="空内容",
            )

        # SH 脚本自动选 Profile
        if script_type == "sh":
            profile = self._classify_sh(content)
            return ClassMatchResult(
                matched=True,
                class_id=profile,
                class_name=f"Sh 模板 ({profile})",
            )

        return ClassMatchResult(
            matched=True,
            class_id="generic",
            class_name="普通模板",
        )

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