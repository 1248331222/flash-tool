# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/sh_parser/profiles/converted.py
"""
ConvertedShProfile — BAT 转换脚本 Profile

适用场景：从天树刷机工具 BAT 模板转换而来的脚本。
脚本结构规整，但可能带遗留的 %VAR% 注释或
source 引用。
"""

from .base import BaseShProfile


class ConvertedShProfile(BaseShProfile):
    profile_id = "converted"
    display_name = "Converted（BAT 转换脚本）"
    description = "适用于从天树 BAT 模板转换而来的脚本，占位文件覆盖最全"

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

    # BAT 转换脚本通常每条 flash 命令对应一个文件
    # 如果脚本在 if [ -f ... ] 分支依赖文件存在性，
    # 这些文件需要先 touch 出来让分支走 True
    # 这里不做具体文件列表 — 由 pre_scanner 动态检测后提示

    extra_env = {
        "SKYTREE_CONVERTED": "1",
    }
