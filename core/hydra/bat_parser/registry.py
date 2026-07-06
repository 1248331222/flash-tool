# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/bat_parser/registry.py
"""
VIP 注册表

映射脚本文件名 → VIP 解析器类。
当自动分类器无法处理的脚本，通过文件名匹配走一对一硬编码解析。

用法:
    from .registry import VIP_REGISTRY
    parser_cls = VIP_REGISTRY.get("D1bat.bat")
"""

from typing import Dict, Optional, Type


# 占位类型，后续导入了实际 VIP 解析器后替换
_VIPParserType = Type["VIPBaseParser"] if False else type  # type: ignore


# VIP 注册表: 脚本文件名 → VIP 解析器类
VIP_REGISTRY: Dict[str, _VIPParserType] = {
    # "D1bat.bat": D1BatVIPParser,   # 待阶段 4 实现
}

__all__ = ["VIP_REGISTRY"]
