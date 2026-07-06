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
    """脚本分类匹配结果。"""
    matched: bool = False
    class_id: str = "generic"
    class_name: str = "普通模板"


__all__ = ["ClassMatchResult"]