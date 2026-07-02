# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/command_extractor.py
"""
Hydra — 命令提取器
====================
从环境模拟的输出结果中提取所有 fastboot 命令，转换为标准化的步骤格式。

核心职责：
  1. 从展开的命令行中识别 fastboot 命令
  2. 解析命令类型（flash/erase/reboot/set_active/oem/getvar/devices/boot）
  3. 提取分区名和镜像文件名
  4. 调用 core/fastboot_cmd_parser.py 的 parse_fastboot_tail 进行解析
  5. 标记动态命令（运行时才能确定具体命令的步骤）
  6. 过滤掉非 fastboot 命令（echo/set/pause 等）

与现有代码的集成：
  复用 core/fastboot_cmd_parser.py 中的 parse_fastboot_tail 和 _assess_risk
"""

import re
import os
from typing import List, Dict, Optional

from .environment import EnvSimulateResult
from .types import HydraStep


# ============================================================
# CommandExtractor — 命令提取器
# ============================================================

class CommandExtractor:
    """
    命令提取器 — 从环境模拟结果中提取 fastboot 命令

    用法:
        extractor = CommandExtractor()
        steps = extractor.extract(env_result=env_result, rom_dir="/rom")
    """

    def __init__(self):
        # 延迟导入 fastboot_cmd_parser（避免循环导入）
        self._parser = None

    @property
    def _cmd_parser(self):
        if self._parser is None:
            # 延迟导入避免循环导入
            from core.fastboot_cmd_parser import parse_fastboot_tail, _assess_risk
            self._parser_parse = parse_fastboot_tail
            self._parser_risk = _assess_risk
            self._parser = True
        return self

    def extract(
        self,
        env_result: EnvSimulateResult,
        rom_dir: str = "",
    ) -> List[HydraStep]:
        """
        从环境模拟结果中提取所有 fastboot 步骤

        Args:
            env_result: 环境模拟器的输出
            rom_dir: ROM 包根目录

        Returns:
            HydraStep 列表
        """
        steps: List[HydraStep] = []

        for line in env_result.expanded_lines:
            # 处理链式命令：按 && 或 || 拆分
            chained_parts = re.split(r'\s*(?:&&|\|\|)\s*', line)
            for part_line in chained_parts:
                part_line = part_line.strip()
                if not part_line:
                    continue

                # 跳过注释、赋值、echo 等非 fastboot 行
                if not self._is_fastboot_line(part_line):
                    continue

                # 提取 fastboot 命令部分（去掉前缀 fastboot/fastboot.exe 等）
                cmd_tail = self._extract_fastboot_tail(part_line)

                if not cmd_tail:
                    continue

                # 调用 core.fastboot_cmd_parser 解析命令
                step_dict = self._cmd_parser._parser_parse(cmd_tail, part_line)
                if step_dict is None:
                    continue

                step = HydraStep(
                    type=step_dict.get("type", "unknown"),
                    part=step_dict.get("part", ""),
                    fileName=step_dict.get("fileName", ""),
                    params=step_dict.get("params", "") or step_dict.get("prefixParams", ""),
                    raw=part_line,
                    risk=step_dict.get("risk", "B"),
                    dynamic=self._is_dynamic(part_line),
                    note=step_dict.get("note", ""),
                )
                steps.append(step)

        # 评估风险等级
        for step in steps:
            step_dict = {"type": step.type, "part": step.part, "params": step.params, "raw": step.raw}
            step.risk = self._cmd_parser._parser_risk(step_dict)

        return steps

    def extract_from_lines(
        self,
        lines: List[str],
        rom_dir: str = "",
    ) -> List[HydraStep]:
        """
        从已展开的命令行列表中提取 fastboot 命令
        （用于轻量调用，无需完整环境模拟）

        Args:
            lines: 命令行字符串列表
            rom_dir: ROM 包根目录

        Returns:
            HydraStep 列表
        """
        steps = []

        for line in lines:
            # 处理链式命令：按 && 或 || 拆分
            chained_parts = re.split(r'\s*(?:&&|\|\|)\s*', line)
            for part_line in chained_parts:
                part_line = part_line.strip()
                if not part_line:
                    continue

                if not self._is_fastboot_line(part_line):
                    continue

                cmd_tail = self._extract_fastboot_tail(part_line)
                if not cmd_tail:
                    continue

                step_dict = self._cmd_parser._parser_parse(cmd_tail, part_line)
                if step_dict is None:
                    continue

                step = HydraStep(
                    type=step_dict.get("type", "unknown"),
                    part=step_dict.get("part", ""),
                    fileName=step_dict.get("fileName", ""),
                    params=step_dict.get("params", "") or step_dict.get("prefixParams", ""),
                    raw=part_line,
                    risk=step_dict.get("risk", "B"),
                    dynamic=self._is_dynamic(part_line),
                    note=step_dict.get("note", ""),
                )
                steps.append(step)

        for step in steps:
            step_dict = {"type": step.type, "part": step.part, "params": step.params, "raw": step.raw}
            step.risk = self._cmd_parser._parser_risk(step_dict)

        return steps

    # ----------------------------------------------------------
    # 工具方法
    # ----------------------------------------------------------

    def _is_fastboot_line(self, line: str) -> bool:
        """判断一行是否包含 fastboot 命令"""
        if not line or line.startswith('#'):
            return False

        # 去除循环展开前缀
        stripped = line.strip()
        if stripped.startswith('__LOOP_EXPANDED__'):
            stripped = stripped[len('__LOOP_EXPANDED__'):]
        lower = stripped.lower()

        # 跳过明显的非 fastboot 行
        skip_patterns = [
            r'^@?echo\b', r'^set\b', r'^rem\b', r'^::', r'^pause\b',
            r'^cls\b', r'^title\b', r'^color\b', r'^chcp\b',
            r'^timeout\b', r'^sleep\b', r'^cd\b', r'^md\b', r'^mkdir\b',
            r'^del\b', r'^copy\b', r'^move\b', r'^ren\b', r'^type\b',
            r'^exit\b', r'^goto\b', r'^call\b', r'^start\b',
            r'^if\s+', r'^for\s+', r'^setlocal\b', r'^endlocal\b',
            r'^#', r'^\$\s*$', r'^:\w',
            r'^export\b', r'^readonly\b', r'^local\b', r'^function\b',
        ]

        for pat in skip_patterns:
            if re.match(pat, lower):
                return False

        # 展开 %VAR% 后再检查一次（将变量内容替换为 fastboot 以暴露内部的命令）
        # 注意：不能直接移除变量，否则 "%~dp0tools\\fastboot.exe" 会损失 fastboot 信息
        cleaned = re.sub(r'%(\w+)%', 'fastboot', lower)
        has_fastboot = bool(
            re.search(r'\bfastboot(?:\.exe)?\b', lower)
            or re.search(r'\bfastboot(?:\.exe)?\b', cleaned)
            or '$fastboot' in lower
        )
        return has_fastboot

    def _extract_fastboot_tail(self, line: str) -> str:
        """
        从行中提取 fastboot 命令的尾部参数
        
        "fastboot flash boot boot.img"    → "flash boot boot.img"
        "path\\to\\fastboot.exe flash"    → "flash ..."
        ""%TOOL_PATH%" flash boot"        → "flash boot"
        "$FASTBOOT flash ..."             → "flash ..."
        "__LOOP_EXPANDED__fastboot flash" → "flash ..."
        """
        line = line.strip()
        # 去除循环展开前缀
        if line.startswith('__LOOP_EXPANDED__'):
            line = line[len('__LOOP_EXPANDED__'):]

        # 1. 替换变量引用为 fastboot，同时处理引号包裹
        #    "$FASTBOOT" → fastboot（去掉外层引号）
        #    "${FASTBOOT}" → fastboot
        line = re.sub(r'["\']?\$\{FASTBOOT\}["\']?', 'fastboot', line, flags=re.I)
        line = re.sub(r'["\']?\$FASTBOOT\b["\']?', 'fastboot', line, flags=re.I)
        line = re.sub(r'["\']?%(\w+)%["\']?', 'fastboot', line, flags=re.I)

        # 2. 提取引号内的路径 + fastboot
        #    "path\to\fastboot.exe" flash boot → fastboot flash boot
        m = re.search(r'["\']?([^"\'\s]*(?:fastboot(?:\.exe)?)[^"\'\s]*)["\']?\s+(.*)', line, re.I)
        if m:
            return m.group(2).strip()

        # 3. 匹配 fastboot 命令（前面可带路径）
        m = re.search(r'(?:^|[\\/])(?:fastboot(?:\.exe)?)\s+(.*)', line, re.I)
        if m:
            return m.group(1).strip()

        # 4. 如果行本身以 fastboot 开头
        m = re.match(r'^fastboot(?:\.exe)?\s+(.*)', line, re.I)
        if m:
            return m.group(1).strip()

        return ""

    def _is_dynamic(self, line: str) -> bool:
        """检查命令行是否包含未展开的变量（动态命令）"""
        # 包含未展开的 BAT 变量
        if '%' in line:
            # 排除已展开的路径修饰符
            cleaned = re.sub(r'%~[\w]+', '', line)
            if '%' in cleaned:
                return True
        # 包含未展开的 SH 变量（排除 $FASTBOOT、$ADB、$?、$(...) 等非变量引用）
        if '$' in line:
            # 排除已知的固定命令变量
            known_sh_vars = {'FASTBOOT', 'ADB', '?', '@', '*', '#', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9'}
            # 查找 ${VAR} 形式的引用
            for m in re.finditer(r'\$\{(\w+)\}', line):
                if m.group(1) not in known_sh_vars:
                    return True
            # 查找 $VAR 形式的引用（排除 ${} 已处理的）
            for m in re.finditer(r'(?<!\$)\$(\w+)', line):
                if m.group(1) not in known_sh_vars:
                    return True
        # 包含延迟扩展变量
        if '!' in line:
            if re.search(r'!\w+!', line):
                return True
        return False


__all__ = ["CommandExtractor"]