# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/sh_parser/profiles/__init__.py
"""
Profile 包入口
"""

from typing import Optional

from .base import BaseShProfile
from .minimal import MinimalShProfile
from .native import NativeShProfile
from .converted import ConvertedShProfile
from .vendor import VendorShProfile
from .community import CommunityShProfile


_PROFILE_MAP = {
    "minimal": MinimalShProfile,
    "native": NativeShProfile,
    "converted": ConvertedShProfile,
    "vendor": VendorShProfile,
    "community": CommunityShProfile,
}


def get_profile(profile_id: Optional[str] = None) -> BaseShProfile:
    """
    获取指定 Profile 实例。

    Args:
        profile_id: Profile 名称（None 返回默认 native）

    Returns:
        BaseShProfile 实例
    """
    if profile_id is None:
        return NativeShProfile()
    cls = _PROFILE_MAP.get(profile_id)
    if cls is None:
        return NativeShProfile()
    return cls()


def list_profiles() -> list:
    """列出所有可用 Profile"""
    return [
        {
            "id": pid,
            "name": cls.display_name,
            "desc": cls.description,
        }
        for pid, cls in _PROFILE_MAP.items()
    ]
