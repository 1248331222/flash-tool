# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/bat_parser/__init__.py
"""
BAT 解析器模块入口。
提供 get_parser(script_content, script_name) 函数，
根据脚本内容自动判定难度等级并返回对应解析器实例。
"""

from typing import Optional

from .classifier import classify
from .registry import VIP_REGISTRY
from .parsers.base_parser import BaseParser
from .parsers.simple_parser import SimpleParser
from .parsers.conditional_parser import ConditionalParser
from .parsers.for_loop_parser import ForLoopParser
from .parsers.nested_for_parser import NestedForParser
from .parsers.delayed_parser import DelayedParser
from .parsers.dynamic_parser import DynamicParser

# 各级解析器映射表
_PARSER_CLASSES = {
    "simple": SimpleParser,
    "conditional": ConditionalParser,
    "for_loop": ForLoopParser,
    "nested_for": NestedForParser,
    "delayed_expansion": DelayedParser,
    "dynamic_var": DynamicParser,
    # "goto_label": GotoParser,
}


def get_parser(script_content: str, script_name: str = "") -> Optional[BaseParser]:
    """
    根据脚本内容自动选择解析器。

    Args:
        script_content: 脚本的完整文本内容
        script_name: 脚本文件名（用于 VIP 注册表匹配）

    Returns:
        对应级别的解析器实例，无法识别时返回 None
    """
    # 1. 先查 VIP 注册表
    if script_name in VIP_REGISTRY:
        vip_cls = VIP_REGISTRY[script_name]
        return vip_cls()

    # 2. 按语法特征分级
    level = classify(script_content)
    if level == "interactive":
        # 交互式脚本，VIP 表未注册则无法解析
        return None

    # 3. plain 级别也用 SimpleParser（纯 fastboot 命令直接提取）
    if level == "plain":
        return SimpleParser()

    # 3. 返回对应级别的解析器
    parser_cls = _PARSER_CLASSES.get(level)
    if parser_cls is None:
        return None

    return parser_cls()


__all__ = ["get_parser", "classify"]