# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/pipelines/registry.py
"""
管线注册表 — script_type/class_id → Pipeline 映射

每个 SH class 有完全独立的管线副本，
修改一个不会影响其他。
"""
from typing import Optional

# SH 管线注册表
_SH_PIPELINES = {}

def _register_sh_pipelines():
    """延迟导入并注册所有 SH 管线"""
    global _SH_PIPELINES
    if _SH_PIPELINES:
        return
    from .sh.native import NativePipeline
    from .sh.vendor import VendorPipeline
    from .sh.community import CommunityPipeline
    from .sh.converted import ConvertedPipeline
    from .sh.minimal import MinimalPipeline
    from .sh.generic import GenericPipeline
    _SH_PIPELINES = {
        "native": NativePipeline,
        "vendor": VendorPipeline,
        "community": CommunityPipeline,
        "converted": ConvertedPipeline,
        "minimal": MinimalPipeline,
        "generic": GenericPipeline,
    }

def get_pipeline(script_type: str, class_id: str) -> Optional[object]:
    """
    获取指定类型和分类的管线类。
    
    Args:
        script_type: "sh" 或 "bat"
        class_id: 分类器返回的 class_id
    
    Returns:
        Pipeline 类（未实例化），None 表示未找到
    """
    if script_type == "sh":
        _register_sh_pipelines()
        cls = _SH_PIPELINES.get(class_id)
        if cls:
            return cls
        # fallback 到 generic
        return _SH_PIPELINES.get("generic")
    # BAT 管线
    if script_type == "bat":
        _register_bat_pipelines()
        cls = _BAT_PIPELINES.get(class_id)
        if cls:
            return cls
        return _BAT_PIPELINES.get("plain")

# BAT 管线注册表
_BAT_PIPELINES = {}

def _register_bat_pipelines():
    """延迟导入并注册所有 BAT 管线"""
    global _BAT_PIPELINES
    if _BAT_PIPELINES:
        return
    from .bat.plain import PlainBatPipeline
    from .bat.simple import SimpleBatPipeline
    from .bat.conditional import ConditionalBatPipeline
    from .bat.for_loop import ForLoopBatPipeline
    from .bat.nested_for import NestedForBatPipeline
    from .bat.delayed_expansion import DelayedExpansionBatPipeline
    from .bat.dynamic_var import DynamicVarBatPipeline
    from .bat.goto_label import GotoLabelBatPipeline
    from .bat.interactive import InteractiveBatPipeline
    _BAT_PIPELINES = {
        "plain": PlainBatPipeline,
        "simple": SimpleBatPipeline,
        "conditional": ConditionalBatPipeline,
        "for_loop": ForLoopBatPipeline,
        "nested_for": NestedForBatPipeline,
        "delayed_expansion": DelayedExpansionBatPipeline,
        "dynamic_var": DynamicVarBatPipeline,
        "goto_label": GotoLabelBatPipeline,
        "interactive": InteractiveBatPipeline,
    }

