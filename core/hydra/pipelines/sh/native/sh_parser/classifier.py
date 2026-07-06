# -*- coding: utf-8 -*-
import re

class ShScriptClassifier:
    """SH 脚本分类器 — 判断脚本属于哪个 class_id"""
    def classify(self, content: str, script_path: str = "") -> str:
        if "getvar product" in content:
            return "native"
        if "getvar anti" in content:
            return "native"
        if any(kw in content for kw in ["vendor", "VENDOR"]):
            return "vendor"
        if "community" in content.lower():
            return "community"
        if "converted" in content.lower():
            return "converted"
        # 统计 fastboot 命令数
        fb_count = len(re.findall(r'fastboot\s+\$?\*?\s+', content))
        if fb_count <= 5:
            return "minimal"
        return "generic"

__all__ = ["ShScriptClassifier"]
