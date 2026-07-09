# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/bat_parser/parsers/base_parser.py
"""
BaseParser — 所有解析器的基类

实现 L0 行读取。
子类覆写 parse() 方法，组装各管道阶段。

用法:
    class MyParser(BaseParser):
        def parse(self, content: str):
            lines = self._read_lines(content)
            # ... 调用管道函数
"""

from typing import List

from ..var_types import ScriptLine
from ..pipeline.line_reader import read_lines


class BaseParser:
    """
    BAT 解析器基类。

    提供 L0 行读取能力。
    子类需覆写 parse() 实现完整的解析链路。
    """

    def parse(self, content: str):
        """
        解析脚本。子类必须覆写。

        Args:
            content: 脚本原始文本

        Returns:
            解析结果，类型由子类定义
        """
        raise NotImplementedError("子类必须实现 parse() 方法")

    def _read_lines(self, content: str) -> List[ScriptLine]:
        """
        L0: 行读取。

        调用 pipeline/line_reader.py 的 read_lines 函数。
        处理编码、续行合并、去注释、去空行。

        Args:
            content: 脚本原始文本

        Returns:
            List[ScriptLine]: 结构化的行列表
        """
        return read_lines(content)


__all__ = ["BaseParser"]
