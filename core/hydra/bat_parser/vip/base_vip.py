# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/bat_parser/vip/base_vip.py
"""
VIPBaseParser — VIP 解析器基类

继承 BaseParser，不走标准管道。
子类需实现 parse()，直接返回 List[HydraStep] 或 List[CodeBlock]。

待阶段 4 详细实现。
"""

from typing import List

from ..var_types import HydraStep, CodeBlock
from ..parsers.base_parser import BaseParser


class VIPBaseParser(BaseParser):
    """
    VIP 解析器基类。

    不经过标准管道，parse() 由子类硬编码实现。
    """

    def parse(self, content: str):
        raise NotImplementedError("VIP 子类必须实现 parse() 方法")


__all__ = ["VIPBaseParser"]
