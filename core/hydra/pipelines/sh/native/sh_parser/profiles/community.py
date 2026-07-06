# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/sh_parser/profiles/community.py
"""
CommunityShProfile — 社区脚本 Profile

适用场景：XDA/酷安等社区发布的第三方刷机脚本。
保守处理——最小 getvar 模拟集，较多未知分区标记为
HIGH 风险。
"""

from .base import BaseShProfile


class CommunityShProfile(BaseShProfile):
    profile_id = "community"
    display_name = "Community（社区脚本）"
    description = "适用于 XDA/酷安等社区的第三方脚本，保守模拟+高风险默认"

    # 最小集 — 只有最必要的字段
    getvar_defs = {
        "product": "unknown",
        "current-slot": "_a",
    }
