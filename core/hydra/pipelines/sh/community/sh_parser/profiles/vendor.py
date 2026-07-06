# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/sh_parser/profiles/vendor.py
"""
VendorShProfile — 厂商高危脚本 Profile

适用场景：包含 flashing unlock、--disable-verity 等
高危操作的厂商救砖脚本。
"""

from .base import BaseShProfile


class VendorShProfile(BaseShProfile):
    profile_id = "vendor"
    display_name = "Vendor（厂商救砖）"
    description = "适用于含解锁/关闭验证的厂商救砖脚本，高危参数标注更严格"

    # 厂商脚本可能带厂商特有字段
    getvar_defs = {
        "product": "umi",
        "anti": "0",
        "current-slot": "_a",
        "max-download-size": "268435456",
        "unlocked": "yes",
        "secure": "yes",
        "slot-count": "2",
        "slot-suffixes": "_a,_b",
        "has-slot:boot": "yes",
        "has-slot:system": "yes",
        "is-userspace": "no",
        "token": "${DECISION:getvar_token}",
    }

    extra_env = {
        "SKYTREE_VENDOR_MODE": "1",
    }
