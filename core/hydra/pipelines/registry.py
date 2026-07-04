# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/pipelines/registry.py
"""
管线注册表 — script_type/class_id → Pipeline 映射
管线实现移除后，预留扩展点。
"""

from typing import Optional


def get_pipeline(script_type: str, class_id: str) -> Optional[object]:
    return None


__all__ = ["get_pipeline"]