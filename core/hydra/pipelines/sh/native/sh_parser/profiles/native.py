# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/sh_parser/profiles/native.py
"""
NativeShProfile — 标准厂商脚本 Profile

适用场景：小米/一加/三星等厂商的标准 flash_all.sh。
沙箱模拟 product/anti/current-slot 等常见 getvar 字段。
"""

from .base import BaseShProfile


class NativeShProfile(BaseShProfile):
    profile_id = "native"
    display_name = "Native（标准厂商脚本）"
    description = "适用于小米/一加/三星等厂商的标准 flash_all.sh"

    getvar_defs = {
        "product": "umi",
        "anti": "0",
        "current-slot": "_a",
        "max-download-size": "268435456",
        "unlocked": "yes",
        "slot-count": "2",
        "slot-suffixes": "_a,_b",
        "has-slot:boot": "yes",
        "has-slot:system": "yes",
        "is-userspace": "no",
    }
