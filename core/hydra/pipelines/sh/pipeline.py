# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/pipelines/sh/pipeline.py
"""
SH 脚本解析管线基类（样本模板）— 仅供复制，永远不得实例化或调用。

新管线请从本文件复制到 sh_001/sh_002/... 目录下，
并按实际特征设置 COVERS 集合和 class_id。
"""


class ShPipeline:
    """SH 脚本解析管线基类 — 禁止直接实例化，请使用子管线"""

    is_base = True
    __slots__ = ()

    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            "\n"
            "╔══════════════════════════════════════════════════════════════╗\n"
            "║  ShPipeline 是样本模板，禁止直接实例化或调用。          ║\n"
            "║                                                            ║\n"
            "║  请使用已注册的子管线:                                     ║\n"
            "║    sh_001  sh_002  ...                                     ║\n"
            "║                                                            ║\n"
            "║  新建管线: 复制此文件到 sh_XXX/ 目录并修改 COVERS 即可。  ║\n"
            "╚══════════════════════════════════════════════════════════════╝"
        )

    def parse(self, *args, **kwargs):
        raise RuntimeError(
            "ShPipeline.parse() 是样本模板，禁止直接调用。"
            "请使用已注册的子管线实例。"
        )