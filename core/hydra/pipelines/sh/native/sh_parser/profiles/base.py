# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/sh_parser/profiles/base.py
"""
BaseShProfile — Profile 基类

Profile 定义了沙箱参数差异（不是解析器差异）。
"""

from typing import Dict, Optional


class BaseShProfile:
    """Profile 基类"""
    profile_id: str = "base"
    display_name: str = "基础 Profile"
    description: str = ""
    getvar_defs: Optional[Dict[str, str]] = None
    extra_env: Dict[str, str] = {}
    timeout: int = 30

    def apply_getvar(self, default_getvars: Dict[str, str]) -> Dict[str, str]:
        if self.getvar_defs:
            result = dict(default_getvars)
            result.update(self.getvar_defs)
            return result
        return default_getvars

    def to_dict(self) -> Dict:
        return {
            "profile_id": self.profile_id,
            "display_name": self.display_name,
            "description": self.description,
            "timeout": self.timeout,
        }
