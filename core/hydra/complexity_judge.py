# -*- coding: utf-8 -*-
# flash_tool/core/hydra/complexity_judge.py
"""
Hydra — 复杂度判定
====================
判定脚本是否可静态解析，或者需要运行时执行追踪。

判定规则：
  规则                                判定        说明
  ──────────────────────────────────────────────────────────
  无 fastboot 命令                    复杂        无法执行刷机
  包含 goto 跳转                      复杂        执行路径不可预测
  包含 shift 参数移位                复杂        参数列表动态变化
  延迟扩展变量实际使用                复杂        需要运行时执行
  call 外部批处理                    复杂        子脚本不可控
  for /f 命令输出捕获                复杂        需要实际执行命令
  未定义变量影响 fastboot 命令         复杂        需要运行时决策
  动态命令 ≤ 3                       简单(混合)  可通过符号执行处理
  动态命令 > 3                       复杂(追踪)  需要执行追踪

整体判定：
  - 简单（is_simple=True）:   可以完全静态解析，所有 fastboot 命令都已确定
  - 复杂（is_simple=False）:  需要真实执行追踪或用户手工转换
"""

import re
from typing import List, Tuple, Optional

from .symbol_table import SymbolTable
from .types import HydraStep


class ComplexityJudge:
    """
    复杂度判定器 — 判断脚本是否可以完全静态解析

    用法:
        judge = ComplexityJudge()
        is_simple, reason = judge.judge(steps=steps, symbol_table=st, script_type="bat")
    """

    def __init__(self):
        pass

    def judge(
        self,
        steps: List[HydraStep],
        symbol_table: "SymbolTable" = None,
        script_type: str = "bat",
    ) -> Tuple[bool, str]:
        """
        主判定入口

        Args:
            steps: 已提取的步骤列表
            symbol_table: 变量符号表（可选，用于检查未定义变量）
            script_type: 脚本类型

        Returns:
            (is_simple, reason) — is_simple=True 表示可完全静态解析
        """
        # 1. 无 fastboot 命令
        if not steps:
            return False, "无 fastboot 命令，无法执行刷机"

        # 2. 统计动态命令数量
        dynamic_count = sum(1 for s in steps if s.dynamic)

        # 3. 检查延迟扩展变量实际使用
        has_delayed = False
        if symbol_table and symbol_table.has_delayed_expansion():
            # 检查是否有 !VAR! 出现在步骤中
            for step in steps:
                if '!' in step.raw and re.search(r'!\w+!', step.raw):
                    has_delayed = True
                    break

        # 4. 检查未定义变量
        undefined_vars = []
        if symbol_table:
            for step in steps:
                vars_in_step = self._find_variables(step.raw, script_type)
                for v in vars_in_step:
                    if not symbol_table.is_defined(v):
                        undefined_vars.append(v)

        # 5. 综合判定
        if not steps:
            return False, "无 fastboot 命令"

        if dynamic_count > 3:
            return False, f"动态命令过多（{dynamic_count} 个），需要执行追踪"

        if has_delayed and dynamic_count > 0:
            return False, "延迟扩展变量与动态命令并存，需要运行时执行"

        if len(undefined_vars) > 2:
            # 多个未定义变量可能影响命令
            return False, f"存在 {len(undefined_vars)} 个未定义变量，可能影响命令解析"

        # 动态命令 ≤ 3 — 标记为混合简单
        if dynamic_count > 0:
            return True, f"简单（含 {dynamic_count} 个动态命令，可通过符号执行处理）"

        return True, "简单"

    def judge_raw(
        self,
        content: str,
        script_type: str = "bat",
    ) -> Tuple[bool, str]:
        """
        原始文本快速判定（不经过完整解析流程）

        Args:
            content: 脚本内容
            script_type: 脚本类型

        Returns:
            (is_complex, reason) — is_complex=True 表示复杂脚本
        """
        lines = content.split('\n')
        variables = {}

        # 预扫描变量
        for line in lines:
            m = re.match(r'^set\s+"?(\w+)=(.*?)"?$', line, re.IGNORECASE)
            if m:
                variables[m.group(1).upper()] = m.group(2)

        def resolve(text: str) -> str:
            for _ in range(10):
                prev = text
                text = re.sub(
                    r'%(\w+)%',
                    lambda m: variables.get(m.group(1).upper(), m.group(0)),
                    text
                )
                if text == prev:
                    break
            return text

        for line in lines:
            stripped = line.strip().lstrip('@').strip()
            if not stripped:
                continue

            expanded = resolve(stripped)
            lower = expanded.lower()

            # 绝对拦截
            if re.match(r'^goto\s+\w', lower):
                return True, "goto 跳转"
            if re.match(r'^shift\b', lower):
                return True, "shift 参数移位"
            if re.match(r'^call\s+\w+\.(bat|cmd)', lower):
                return True, "call 外部批处理"
            if re.match(r'^for\s+/f\s+.*\s+in\s*\(\s*[\'"]', lower):
                return True, "for /f 命令输出捕获"
            if re.match(r'^for\s+/[rd]\b', lower):
                return True, "for /r 或 for /d 递归遍历"
            if re.match(r'^if\s+.*errorlevel', lower):
                return True, "if errorlevel"
            if re.match(r'^if\s+.*\bdefined\b', lower):
                return True, "if defined"
            if re.match(r'^\)\s*else\s*\(', lower):
                return True, "else 分支"

            # if 比较含未定义变量
            cm = re.match(r'^if\s+(not\s+)?(.+?)\s+(equ|neq|lss|leq|gtr|geq|==)\s+(.+?)\s*\(', lower)
            if cm:
                left, right = cm.group(2).strip(), cm.group(4).strip()
                if '%' in left or '%' in right or '!' in left or '!' in right:
                    return True, "if 比较含未定义变量"

            # if exist 含未定义变量
            em = re.match(r'^if\s+(not\s+)?exist\s+["\']?([^"\'(]+)', lower)
            if em:
                path = em.group(2).strip()
                if '%' in path or '!' in path:
                    return True, "if exist 路径含未定义变量"

            # for 列表含未定义变量
            fm = re.match(r'^for\s+%%\w+\s+in\s*\(([^)]+)\)', lower)
            if fm and '%' in fm.group(1):
                return True, "for 列表含未定义变量"

        return False, ""

    # ----------------------------------------------------------
    # 工具方法
    # ----------------------------------------------------------

    def _find_variables(self, text: str, script_type: str) -> List[str]:
        """
        从文本中找出所有变量引用

        BAT: %VAR%、!VAR!
        SH:  $VAR、${VAR}
        """
        vars_found = set()

        if script_type == "bat":
            for m in re.finditer(r'%(\w+)%', text):
                vars_found.add(m.group(1))
            for m in re.finditer(r'!(\w+)!', text):
                vars_found.add(m.group(1))
        else:
            for m in re.finditer(r'\$\{(\w+)\}', text):
                vars_found.add(m.group(1))
            for m in re.finditer(r'\$(\w+)', text):
                if m.group(1) not in ('FASTBOOT', 'ADB', '?', '@'):
                    vars_found.add(m.group(1))

        return list(vars_found)


__all__ = ["ComplexityJudge"]