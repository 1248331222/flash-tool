# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/script_class.py
"""
脚本分类数据类型定义
======================
脚本分类器（classifier.py）和解析管线之间的数据契约。
"""

from dataclasses import dataclass


@dataclass
class ClassMatchResult:
    """
    脚本分类匹配结果。
    matched: 是否匹配成功
    class_id: 分类 ID，如 "linear"、"conditional"、"function"、"payload"、"legacy"
    class_name: 分类名称（人类可读）
    """
    matched: bool = False
    class_id: str = "legacy"
    class_name: str = "无法解析，回退旧版"


__all__ = ["ClassMatchResult"]