# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/pipelines/sh/native/pipeline.py
"""
minimal类脚本管线

从 sh 基础管线复制并独立维护，可按需魔改。
原始模板: core/hydra/pipelines/sh/pipeline.py
"""
from core.hydra.sh_parser import ShEngine
from core.hydra.sh_parser.types import ShParseMode


class MinimalPipeline:
    """minimal类脚本管线"""
    class_id = "minimal"
    class_name = "MinimalPipeline"

    def __init__(self, mode: str = "full"):
        mode_map = {
            "full": ShParseMode.FULL,
            "dry_run": ShParseMode.DRY_RUN,
            "sketch": ShParseMode.SKETCH,
        }
        self.engine = ShEngine(
            mode=mode_map.get(mode, ShParseMode.FULL),
            profile="minimal",
            filter_getvar=False,  # minimal 类默认过滤 getvar（使用共享 expander 的 filter_getvar=True）
        )

    def parse(self, content: str, script_path: str, rom_dir: str,
              user_decisions=None):
        return self.engine.parse(
            content=content,
            script_path=script_path,
            rom_dir=rom_dir,
            user_decisions=user_decisions,
        )
