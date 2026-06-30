# -*- coding: utf-8 -*-
# flash_tool/core/hydra/__init__.py
"""
Hydra（九头蛇）动态解析引擎 — 入口模块
========================================

“动态解析，遇变则变” — 九头蛇引擎的三大核心理念：

  1. 不依赖静态规则，通过环境模拟理解脚本的执行逻辑
  2. 无论脚本多复杂（BAT/SH），最终都要提取出 fastboot 命令列表
  3. 采用「静态结构提取 + 动态环境模拟 + 真实执行追踪」三层混合架构

组件概览：
  ast_parser         AST 解析器 — 将脚本解析为抽象语法树
  symbol_table       变量符号表 — 追踪变量赋值与引用
  environment        环境模拟器 — 轻量级执行环境模拟
  command_extractor  命令提取器 — 从 AST 中提取 fastboot 命令
  complexity_judge   复杂度判定 — 判定脚本是否可静态解析
  execution_tracer   执行追踪器 — 真实执行 SH 脚本捕获命令
"""

from .ast_parser import ASTParser
from .symbol_table import SymbolTable
from .environment import Environment
from .command_extractor import CommandExtractor
from .complexity_judge import ComplexityJudge
from .execution_tracer import ExecutionTracer
from .types import HydraStep, HydraParseResult

from typing import List, Dict, Optional, Tuple


# ============================================================
# HydraEngine — 引擎主类
# ============================================================

class HydraEngine:
    """
    九头蛇动态解析引擎主类 — 协调各组件，组装解析结果

    用法：
        engine = HydraEngine()
        result = engine.parse(content="...", script_type="bat", rom_dir="/path/to/rom")

    数据流：
        输入脚本
            ↓
        【AST 解析器】→ AST 树 + 标签映射
            ↓
        【环境模拟器】→ 变量表 + 展开的循环体
            ↓
        【命令提取器】→ 步骤列表 + 动态命令标记
            ↓
        【复杂度判定】→ 是否简单可解析
            ↓
        输出：HydraParseResult
    """

    def __init__(self):
        self.ast_parser = ASTParser()
        self.symbol_table = SymbolTable()
        self.environment = Environment(symbol_table=self.symbol_table)
        self.command_extractor = CommandExtractor()
        self.complexity_judge = ComplexityJudge()
        self.execution_tracer = ExecutionTracer()

    def parse(
        self,
        content: str,
        script_type: str = "bat",
        rom_dir: str = "",
        script_path: str = "",
    ) -> HydraParseResult:
        """
        解析脚本，返回结构化结果

        Args:
            content: 脚本字符串内容
            script_type: "bat" | "sh"
            rom_dir: ROM 包根目录（用于文件存在性检查）
            script_path: 脚本文件路径（用于 %~dp0 等路径修饰符）

        Returns:
            HydraParseResult 包含所有解析步骤
        """
        # Step 1: AST 解析
        ast_result = self.ast_parser.parse(content, script_type=script_type, script_path=script_path)
        if ast_result is None:
            return HydraParseResult(
                script_type=script_type,
                steps=[],
                is_simple=False,
                complex_reason="AST 解析失败",
                warnings=["脚本无法被解析为有效语法树"],
            )

        # Step 2: 环境模拟 — 变量展开 + 循环/条件展开
        env_result = self.environment.simulate(
            ast=ast_result,
            content=content,
            script_type=script_type,
            rom_dir=rom_dir,
            script_path=script_path,
        )

        # Step 3: 命令提取
        steps = self.command_extractor.extract(
            env_result=env_result,
            rom_dir=rom_dir,
        )

        # Step 4: 复杂度判定
        is_simple, reason = self.complexity_judge.judge(
            steps=steps,
            symbol_table=self.symbol_table,
            script_type=script_type,
        )

        # 尝试真实执行追踪（仅 SH 脚本可用）
        executed_steps = []
        if not is_simple and script_type == "sh" and script_path:
            try:
                executed_steps = self.execution_tracer.trace(
                    script_path=script_path,
                    rom_dir=rom_dir,
                )
            except Exception as e:
                pass  # 追踪失败不影响主体流程

        result = HydraParseResult(
            script_type=script_type,
            steps=executed_steps if executed_steps else steps,
            is_simple=is_simple,
            complex_reason=reason,
            missing_files=env_result.missing_files,
            variables=dict(self.symbol_table.get_all()),
            warnings=env_result.warnings,
            total_steps=len(executed_steps if executed_steps else steps),
            dynamic_commands=env_result.dynamic_commands,
            has_delayed_expansion=env_result.has_delayed_expansion,
        )

        return result


# ============================================================
# 便捷工厂函数
# ============================================================

_engine_instance = None


def get_hydra_engine() -> HydraEngine:
    """获取全局单例 HydraEngine"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = HydraEngine()
    return _engine_instance


__all__ = [
    "HydraEngine",
    "HydraStep",
    "HydraParseResult",
    "get_hydra_engine",
    "ASTParser",
    "SymbolTable",
    "Environment",
    "CommandExtractor",
    "ComplexityJudge",
    "ExecutionTracer",
]