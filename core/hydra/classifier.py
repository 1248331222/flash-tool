# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/classifier.py
"""
脚本分类器
==========
分为两类：
- generic：普通模板（通用解析管线）
- vip：VIP 模板（AI 直出模式，内容相似度匹配）

待新脚本开发流程后补充 VIP 模板匹配逻辑。
"""

from .script_class import ClassMatchResult


class ScriptClassifier:
    """
    脚本分类器。
    当前版本统一返回 generic，VIP 匹配逻辑待实现。
    """

    def classify(self, content: str = "", script_type: str = "") -> ClassMatchResult:
        if not content:
            return ClassMatchResult(
                matched=False,
                class_id="generic",
                class_name="空内容",
            )
        return ClassMatchResult(
            matched=True,
            class_id="generic",
            class_name="普通模板",
        )


__all__ = ["ScriptClassifier"]