# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/sh_parser/profiles/minimal.py
"""
MinimalShProfile — 最简线刷 Profile

适用场景：老设备、纯 fastboot 命令序列。
沙箱不模拟任何 getvar，不创建占位文件。
"""

from .base import BaseShProfile


class MinimalShProfile(BaseShProfile):
    profile_id = "minimal"
    display_name = "Minimal（最简线刷）"
    description = "适用于纯 fastboot 命令序列，不做任何额外模拟"

    getvar_defs = {
        "product": "unknown",
        "anti": "0",
        "current-slot": "_a",
    }
