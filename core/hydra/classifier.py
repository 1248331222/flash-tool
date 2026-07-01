# -*- coding: utf-8 -*-
# flash_tool/core/hydra/classifier.py
"""
脚本分类器 — 按步骤结构特征分类
===================================
分析脚本内容的步骤结构特征，将其归类。
分类不依赖脚本语言（bat/sh），只看结构。

可扩展：class_id 不固定，新增脚本类型时在此加规则即可。
"""

import re
from .script_class import ClassMatchResult


class ScriptClassifier:
    """
    脚本分类器。
    分析脚本的步骤结构模式，输出 class_id。
    """

    def classify(self, content: str = "") -> ClassMatchResult:
        """
        对脚本内容进行分类。

        Args:
            content: 脚本内容字符串

        Returns:
            ClassMatchResult
        """
        if not content:
            return ClassMatchResult(matched=False, class_id="legacy", class_name="空内容")

        class_id = self._classify(content)
        class_name = self._class_name(class_id)

        return ClassMatchResult(
            matched=True,
            class_id=class_id,
            class_name=class_name,
        )

    def _classify(self, content: str) -> str:
        """
        按步骤结构特征分类。
        优先级：payload > function > conditional > linear > legacy
        不区分 bat/sh。
        """
        lower = content.lower()

        # --- D_payload：payload 包 ---
        if "payload.bin" in lower:
            return "payload"

        # --- C_function：有函数/标签定义 + 调用 ---
        lines = content.split("\n")
        label_count = 0
        call_count = 0
        for line in lines:
            stripped = line.strip()
            # BAT 标签定义（:label，不是 :: 注释）
            if re.match(r'^:[a-zA-Z]', stripped) and not stripped.startswith("::"):
                label_count += 1
            # BAT call 调用
            if re.match(r'^call\s+:', stripped.lower()):
                call_count += 1
        # SH 函数定义：name() {
        func_defs = re.findall(r'^\s*[a-zA-Z_]\w*\s*\(\s*\)\s*\{', content, re.MULTILINE)

        has_functions = (label_count >= 2 and call_count >= 1) or len(func_defs) >= 2
        if has_functions:
            return "function"

        # --- B_conditional：通配符 for 循环 + 条件守卫 ---
        has_wildcard_for = bool(re.search(r'\bfor\b.*\*\.\w+', lower))
        has_if_exist = "if exist" in lower or "if [" in lower or "if -f " in lower
        has_skip_list = bool(re.search(r'skip_list|!skip!|\$skip', lower, re.I))

        if has_wildcard_for and (has_if_exist or has_skip_list):
            return "conditional"

        # --- A_linear：有 fastboot 命令 ---
        has_fastboot = bool(
            re.search(r'\bfastboot\b', lower)
            or re.search(r'%\w*fastboot\w*%', lower)
            or re.search(r'\$\{?\w*fastboot\w*\}?', lower)
        )
        if has_fastboot:
            return "linear"

        # --- D_legacy：无法解析 ---
        return "legacy"

    def _class_name(self, class_id: str) -> str:
        """class_id 转可读名称"""
        names = {
            "linear": "简单线性",
            "conditional": "条件文件遍历",
            "function": "函数封装",
            "payload": "Payload",
            "legacy": "无法解析，回退旧版",
        }
        return names.get(class_id, f"未知({class_id})")


__all__ = ["ScriptClassifier"]