# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/pipelines/sh/pipeline.py
"""
SH 脚本解析管线基类 — 每个 class 应有自己的副本，此基类永远不得调用。
"""
import sys


class ShPipeline:
    """SH 脚本解析管线基类 — 请勿直接实例化或调用，使用子管线"""
    class_id = "sh"
    class_name = "ShPipeline（基类）"
    is_base = True

    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            "\n"
            "╔══════════════════════════════════════════════════════════╗\n"
            "║  ShPipeline 是基类模板，永远不得直接实例化或调用。   ║\n"
            "║  请使用子管线: native / vendor / community /          ║\n"
            "║  converted / minimal / generic                         ║\n"
            "╚══════════════════════════════════════════════════════════╝"
        )

    def parse(self, *args, **kwargs):
        self.__init__()
