# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/pipelines/bat/pipeline.py
"""
BAT 脚本解析管线基类（样本模板）— 仅供复制，永远不得实例化或调用。

新管线请从本文件复制到 bat_001/bat_002/... 目录下，
并按实际特征设置 COVERS 集合和 class_id。
"""


class BatPipeline:
    """BAT 脚本解析管线基类 — 禁止直接实例化，请使用子管线"""

    is_base = True
    __slots__ = ()

    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            "\n"
            "╔══════════════════════════════════════════════════════════════╗\n"
            "║  BatPipeline 是样本模板，禁止直接实例化或调用。          ║\n"
            "║                                                            ║\n"
            "║  请使用已注册的子管线:                                     ║\n"
            "║    bat_001  bat_002  bat_003  bat_004  ...                 ║\n"
            "║                                                            ║\n"
            "║  新建管线: 复制此文件到 bat_XXX/ 目录并修改 COVERS 即可。  ║\n"
            "╚══════════════════════════════════════════════════════════════╝"
        )

    def parse(self, *args, **kwargs):
        raise RuntimeError(
            "BatPipeline.parse() 是样本模板，禁止直接调用。"
            "请使用已注册的子管线实例。"
        )