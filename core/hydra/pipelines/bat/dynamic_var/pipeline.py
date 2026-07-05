# -*- coding: utf-8 -*-
import os
# Skytree Flasher / core/hydra/pipelines/bat/dynamic_var/pipeline.py
"""
动态变量

从 bat 基础管线复制并独立维护，可按需魔改。
原始模板: core/hydra/pipelines/bat/pipeline.py
"""
from core.hydra.bat_parser import get_parser


class DynamicVarBatPipeline:
    """动态变量"""
    class_id = "dynamic_var"
    class_name = "DynamicVarBatPipeline"

    def __init__(self):
        # 使用 BAT 解析器工厂按特征选解析器
        self._parser = None

    def _get_parser(self, content: str, script_name: str = ""):
        if self._parser is None:
            self._parser = get_parser(content, script_name)
        return self._parser

    def parse(self, content: str, script_path: str = "", rom_dir: str = "",
                  user_decisions=None):
        parser = self._get_parser(content, os.path.basename(script_path) if script_path else "")
        if parser is None:
            from core.hydra import HydraParseResult
            return HydraParseResult(script_type="bat")
        from core.hydra import _blocks_to_compat_steps
        blocks = parser.parse(content)
        from core.hydra import HydraParseResult
        return HydraParseResult(
            steps=_blocks_to_compat_steps(blocks),
            total_steps=len(blocks[0].steps) if blocks else 0,
            missing_files=[],
            blocks=blocks,
            script_type="bat",
        )
