# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/sh_parser/command_expander.py
"""
ShCommandExpander — 阶段 4a 占位符替换器

将沙箱输出的 jsonl 中的 ${DECISION:xxx} 占位符
替换为用户选择的值，输出纯 fastboot 命令列表。
"""

import json
import re
from typing import Dict, List


class ShCommandExpander:
    """占位符替换器"""

    def __init__(self, filter_getvar: bool = True):
        self.filter_getvar = filter_getvar

    _PLACEHOLDER_RE = re.compile(r'\$\{DECISION:(\w+)\}')

    def expand(self, jsonl_path: str,
               resolutions: Dict[str, str]) -> List[str]:
        """
        展开占位符，返回纯命令列表。

        Args:
            jsonl_path: 沙箱输出的 jsonl 路径
            resolutions: 用户决议映射 {决策id: 值}

        Returns:
            List[str]: 展开后的纯 fastboot 命令字符串列表
        """
        commands = []

        with open(jsonl_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                cmd = data["cmd"]

                # 替换所有占位符
                cmd = self._replace_placeholders(cmd, resolutions)

                # 去除 getvar 命令（非刷机操作，不纳入步骤）
                if self.filter_getvar and self._is_getvar_command(cmd):
                    continue

                commands.append(cmd)

        return commands

    def _replace_placeholders(self, cmd: str,
                              resolutions: Dict[str, str]) -> str:
        """替换命令中的占位符"""

        def replacer(match):
            key = match.group(1)
            return resolutions.get(key, match.group(0))

        return self._PLACEHOLDER_RE.sub(replacer, cmd)

    def _is_getvar_command(self, cmd: str) -> bool:
        """判断是否为 getvar 验证命令（不纳入刷机步骤）"""
        return " getvar " in cmd.lower()


__all__ = ["ShCommandExpander"]
