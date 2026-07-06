# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/pipelines/bat/pipeline.py
"""
BAT 脚本解析管线基类 — 每个 class 应有自己的副本，此基类永远不得调用。
"""


class BatPipeline:
    """BAT 脚本解析管线基类 — 请勿直接实例化或调用，使用子管线"""
    class_id = "bat"
    class_name = "BatPipeline（基类）"
    is_base = True

    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            "\n"
            "╔══════════════════════════════════════════════════════════╗\n"
            "║  BatPipeline 是基类模板，永远不得直接实例化或调用。   ║\n"
            "║  请使用子管线: plain / simple / conditional /          ║\n"
            "║  for_loop / nested_for / delayed_expansion /            ║\n"
            "║  dynamic_var / goto_label / interactive                 ║\n"
            "╚══════════════════════════════════════════════════════════╝"
        )

    def parse(self, *args, **kwargs):
        self.__init__()
