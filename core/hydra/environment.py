# -*- coding: utf-8 -*-
# flash_tool/core/hydra/environment.py
"""
Hydra — 环境模拟器
====================
轻量级执行环境模拟，理解脚本的执行逻辑。

核心职责：
  1. 遍历 AST 节点，理解执行流程
  2. 模拟变量赋值/修改（更新符号表）
  3. 展开 for 循环（数值/列表/通配符）
  4. 评估 if 条件（exist/比较/恒真/恒假/未知）
  5. 识别延迟扩展变量（!VAR!）
  6. 处理 call :label 的内联展开
  7. 记录动态命令和警告信息

“静态结构提取 + 动态环境模拟” — 这是九头蛇引擎的心脏。
"""

import os
import re
import glob
import fnmatch
import shlex
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field

from .ast_parser import (
    ASTNode, ASTParseResult,
    CommandNode, ForNode, IfNode, IfElseNode,
    LabelNode, CallNode, GotoNode, AssignmentNode,
    DirectiveNode, FunctionNode, WhileNode, CaseNode,
)
from .symbol_table import SymbolTable


# ============================================================
# EnvSimulateResult — 环境模拟输出
# ============================================================

@dataclass
class EnvSimulateResult:
    """环境模拟器的输出"""
    expanded_lines: List[str] = field(default_factory=list)        # 展开后的命令列表
    missing_files: List[str] = field(default_factory=list)         # 缺失文件
    warnings: List[str] = field(default_factory=list)              # 警告信息
    dynamic_commands: int = 0                                      # 动态命令数量
    has_delayed_expansion: bool = False                            # 是否包含延迟扩展
    expanded_bodies: List[str] = field(default_factory=list)       # 展开后的体内容（用于调试）
    unresolved_vars: List[str] = field(default_factory=list)       # 未解析的变量
    call_count: Dict[str, int] = field(default_factory=dict)       # call 内联计数器


# ============================================================
# Environment — 环境模拟器
# ============================================================

class Environment:
    """
    环境模拟器 — 理解脚本执行逻辑

    用法:
        env = Environment(symbol_table=symbol_table)
        result = env.simulate(ast=ast, content=content, script_type="bat", rom_dir="/rom")
    """

    def __init__(self, symbol_table: Optional[SymbolTable] = None):
        self.symbol_table = symbol_table or SymbolTable()
        self._rom_dir: str = ""
        self._script_path: str = ""
        self._script_type: str = "bat"
        self._result: EnvSimulateResult = None
        self._call_depth: int = 0

    def simulate(
        self,
        ast: ASTParseResult,
        content: str = "",
        script_type: str = "bat",
        rom_dir: str = "",
        script_path: str = "",
    ) -> EnvSimulateResult:
        """
        主入口：模拟执行脚本环境

        Args:
            ast: AST 解析结果
            content: 原始脚本内容（用于回退分析）
            script_type: "bat" / "sh"
            rom_dir: ROM 包根目录
            script_path: 脚本文件路径

        Returns:
            EnvSimulateResult
        """
        self._script_type = script_type
        self._rom_dir = rom_dir
        self._script_path = script_path
        self._call_depth = 0
        self._ast = ast
        self._functions: Dict[str, FunctionNode] = ast.functions if hasattr(ast, 'functions') else {}

        # 初始化符号表
        self.symbol_table.reset()
        self.symbol_table._script_type = script_type

        # 结果容器
        self._result = EnvSimulateResult()

        # 预设 BAT 路径修饰符变量
        if script_type == "bat" and script_path:
            sp_abs = os.path.abspath(script_path)
            sp_dir = os.path.dirname(sp_abs)
            sp_name = os.path.basename(sp_abs)
            sp_base, sp_ext = os.path.splitext(sp_name)
            self.symbol_table.define("~dp0", sp_dir + os.sep, line_no=0)
            self.symbol_table.define("~n0", sp_base, line_no=0)
            self.symbol_table.define("~x0", sp_ext, line_no=0)
            self.symbol_table.define("~nx0", sp_name, line_no=0)
            self.symbol_table.define("~s0", sp_abs, line_no=0)
            self.symbol_table.define("~f0", sp_abs, line_no=0)
            self.symbol_table.define("~p0", sp_dir + os.sep, line_no=0)
        # 预设 BAT 系统环境变量（模拟 cmd.exe 运行时环境）
        if script_type == "bat":
            import datetime
            self.symbol_table.define("CD", os.getcwd(), line_no=0)
            self.symbol_table.define("DATE", datetime.date.today().strftime("%Y/%m/%d"), line_no=0)
            self.symbol_table.define("TIME", datetime.datetime.now().strftime("%H:%M:%S.00"), line_no=0)
            self.symbol_table.define("RANDOM", "0", line_no=0)
            self.symbol_table.define("ERRORLEVEL", "0", line_no=0)
            self.symbol_table.define("COMSPEC", "C:\\Windows\\System32\\cmd.exe", line_no=0)
            self.symbol_table.define("OS", "Windows_NT", line_no=0)
            self.symbol_table.define("PATH", "C:\\Windows\\System32", line_no=0)
        # 预设 SH 脚本路径变量 $0
        if script_type == "sh" and script_path:
            sp_abs = os.path.abspath(script_path)
            self.symbol_table.define("0", sp_abs, line_no=0)

        # 遍历 AST 节点
        for node in ast.nodes:
            self._simulate_node(node)

        return self._result

    # ----------------------------------------------------------
    # 子 shell 简化
    # ----------------------------------------------------------

    @staticmethod
    def _simplify_subshell(text: str) -> str:
        """简化 SH 子 shell $(...) 表达式 — 对简单可推导的模式做静态文本简化"""
        import re
        max_passes = 10
        for _ in range(max_passes):
            if '$(' not in text:
                break
            # $(cd "..." && pwd) — 替代为指定路径
            m = re.search(r'\$\(cd\s+(["\'])([^"\']+)\1\s*&&\s*pwd\s*\)', text)
            if m:
                text = text[:m.start()] + m.group(2) + text[m.end():]
                continue
            # $(echo "string" | sed 's/pattern//')
            m = re.search(r'\$\(echo\s+(["\'])([^"\']+)\1\s*\|\s*sed\s+[\"\']s/[^/]+/([^/]*)/[\"\']\s*\)', text)
            if m:
                original_str = m.group(2)
                replacement = m.group(3)
                if replacement == '':
                    dot_idx = original_str.rfind('.')
                    if dot_idx > 0:
                        text = text[:m.start()] + original_str[:dot_idx] + text[m.end():]
                        continue
                else:
                    text = text[:m.start()] + original_str.replace('.img', replacement) + text[m.end():]
                    continue
            # $(basename "path" .ext) — 去掉路径和后缀
            m = re.search(r'\$\(basename\s+(["\'])([^"\']+)\1(?:\s+\.\w+)?\s*\)', text)
            if m:
                base = os.path.basename(m.group(2))
                # 检查是否有扩展名参数
                full_match = m.group(0)
                rest = full_match[m.end(2)-m.start(0)+3:]  # 匹配后的剩余部分
                ext_m = re.search(r'\.(\w+)\s*\)', full_match)
                if ext_m:
                    ext = '.' + ext_m.group(1)
                    if base.endswith(ext):
                        base = base[:-len(ext)]
                text = text[:m.start()] + base + text[m.end():]
                continue
            # $(dirname "path")
            m = re.search(r'\$\(dirname\s+(["\'])([^"\']+)\1\s*\)', text)
            if m:
                text = text[:m.start()] + os.path.dirname(m.group(2)) + text[m.end():]
                continue
            # 通用: $(echo "xxx")
            m = re.match(r'^\$\(echo\s+(["\'])([^"\']+)\1\s*\)$', text)
            if m:
                return m.group(2)
            break
        return text

    # ----------------------------------------------------------
    # 节点模拟分发
    # ----------------------------------------------------------

    def _simulate_node(self, node: ASTNode):
        """根据节点类型分发到具体模拟方法"""
        dispatch = {
            "command": self._simulate_command,
            "for": self._simulate_for,
            "if": self._simulate_if,
            "if_else": self._simulate_if_else,
            "assignment": self._simulate_assignment,
            "call": self._simulate_call,
            "label": self._simulate_label,
            "goto": self._simulate_goto,
            "directive": self._simulate_directive,
            "while": self._simulate_while,
            "case": self._simulate_case,
            "function": self._simulate_function,
        }
        handler = dispatch.get(node.type)
        if handler:
            handler(node)

    # ----------------------------------------------------------
    # 命令模拟
    # ----------------------------------------------------------

    def _simulate_command(self, node: CommandNode):
        """模拟简单命令 — 变量展开后记录"""
        text = node.text

        # 检查是否从循环展开而来
        skip_resolve = False
        if text.startswith("__LOOP_EXPANDED__"):
            expanded = text[len("__LOOP_EXPANDED__"):]
            # 循环展开后，非循环变量（如 $part）仍需展开
            if self._script_type == "sh":
                expanded = self._resolve_path_modifiers(expanded)
                expanded = self.symbol_table.resolve(expanded, line_no=node.line_no)
            skip_resolve = True
        else:
            expanded = self._resolve_path_modifiers(text)
            expanded = self.symbol_table.resolve(expanded, line_no=node.line_no)

        # BAT 延迟展开：即使来自循环展开，也展开 !VAR!
        if skip_resolve and self._script_type == "bat" and self.symbol_table.has_delayed_expansion():
            expanded = self.symbol_table.resolve(expanded, line_no=node.line_no)

        # SH 函数调用检测（不论是否来自循环展开）
        if self._script_type == "sh" and self._functions:
            first_word = expanded.split()[0] if expanded.split() else ""
            if first_word in self._functions:
                self._expand_function_call(first_word, expanded, node)
                return

        # 记录展开后的命令
        self._result.expanded_bodies.append(expanded)

        # 检查是否包含未展开的变量（动态命令标记）
        if '%' in expanded or '!' in expanded:
            self._result.dynamic_commands += 1

        self._result.expanded_lines.append(expanded)

    def _expand_function_call(self, func_name: str, call_text: str, node: CommandNode):
        """展开 SH 函数调用"""
        func_node = self._functions.get(func_name)
        if not func_node:
            self._result.expanded_lines.append(call_text)
            return

        # 解析参数（引号感知分割，避免 $(...) 子 shell 表达式被拆开）
        try:
            import shlex
            parts = shlex.split(call_text)
        except (ValueError, ImportError):
            parts = call_text.split()
        args = parts[1:] if len(parts) > 1 else []

        self._result.expanded_lines.append(
            f"# 函数调用 {func_name}({', '.join(args)}) — 展开函数体"
        )

        # 设置位置参数 $1, $2, ...
        old_positional = {}
        for i, arg in enumerate(args):
            pname = str(i + 1)
            old_positional[pname] = self.symbol_table.get(pname, None)
            self.symbol_table.define(pname, arg, line_no=node.line_no)

        # 模拟函数体
        for body_node in func_node.body:
            if isinstance(body_node, CommandNode):
                body_text = self._resolve_path_modifiers(body_node.text)
                # 检测函数体内的赋值（local var=val, export var=val, var=val）
                stripped = body_text.strip()
                assign_m = re.match(r'^(?:local|export|readonly)\s+([a-zA-Z_]\w*)=(.*)$', stripped)
                if not assign_m:
                    assign_m = re.match(r'^([a-zA-Z_]\w*)=(.*)$', stripped)
                if assign_m:
                    var_name = assign_m.group(1)
                    var_value = self.symbol_table.resolve(assign_m.group(2), line_no=body_node.line_no)
                    # 简化子 shell
                    if '$(' in var_value:
                        var_value = self._simplify_subshell(var_value)
                    self.symbol_table.define(var_name, var_value, line_no=body_node.line_no)
                    self._result.expanded_lines.append(
                        f"      {stripped[:stripped.find('=')+1]}{var_value}"
                    )
                else:
                    body_text = self.symbol_table.resolve(body_text, line_no=body_node.line_no)
                    inner_node = CommandNode(type="command", text=body_text, line_no=body_node.line_no, raw=body_node.raw)
                    self._simulate_command(inner_node)
            else:
                self._simulate_node(body_node)

        # 恢复位置参数
        for pname, old_val in old_positional.items():
            if old_val is not None:
                self.symbol_table.define(pname, old_val, line_no=node.line_no)
            else:
                self.symbol_table._entries.pop(self.symbol_table._normalize(pname), None)

        self._result.expanded_lines.append(f"# 函数 {func_name} 调用结束")

    def _simulate_assignment(self, node: AssignmentNode):
        """模拟变量赋值"""
        value = self._resolve_path_modifiers(node.value)
        value = self.symbol_table.resolve(value, line_no=node.line_no)
        
        # 简化 SH 子 shell $(...) — 对简单可推导的表达式做静态文本简化
        if self._script_type == "sh" and '$(' in value:
            value = self._simplify_subshell(value)

        # 剥离外层引号（SH 中 "..." 赋值如果简化后是纯路径，不应保留引号）
        if self._script_type == "sh" and value.startswith('"') and value.endswith('"'):
            inner = value[1:-1]
            if ' ' not in inner and '"' not in inner:
                value = inner

        self.symbol_table.define(node.var, value, line_no=node.line_no)

        self._result.expanded_lines.append(f"# set {node.var}={value}")

    def _simulate_directive(self, node: DirectiveNode):
        """模拟指令"""
        if node.directive == "setlocal" and "enabledelayedexpansion" in node.detail.lower():
            self.symbol_table.mark_delayed_expansion(True)
            self._result.has_delayed_expansion = True
            self._result.expanded_lines.append(f"# setlocal enabledelayedexpansion")
        elif node.directive in ("endlocal",):
            # endlocal 在 BAT 中会丢弃变量变更，但我们模拟时保持
            self._result.expanded_lines.append(f"# {node.directive}")
        else:
            self._result.expanded_lines.append(f"# {node.directive} {node.detail}")

    def _simulate_label(self, node: LabelNode):
        """模拟标签 — 仅标记位置，不产生命令"""
        pass

    def _simulate_goto(self, node: GotoNode):
        """模拟 goto — 标记跳转目标（静态分析无法跟踪运行时 goto）"""
        target = node.target
        self._result.warnings.append(
            f"静态分析遇到 goto {target}，跳转可能改变执行路径"
        )
        self._result.dynamic_commands += 1

    def _simulate_call(self, node: CallNode):
        """
        模拟 call :label — 内联展开标签后的命令

        支持：
        - 位置参数 %1, %2, ... %9（从 node.args 解析）
        - 最多内联 3 次防止无限递归
        """
        self._call_depth += 1
        if self._call_depth > 3:
            self._result.warnings.append(
                f"call :{node.target} 递归超限，已跳过"
            )
            return

        self._result.expanded_lines.append(f"# call :{node.target} {node.args}")

        # 解析位置参数（空格分割）
        args_list = shlex.split(node.args) if node.args else []
        old_positional = {}
        for i, arg in enumerate(args_list):
            pname = str(i + 1)
            old_positional[pname] = self.symbol_table.get(pname, None)
            self.symbol_table.define(pname, arg, line_no=node.line_no)

        # 查找标签行号
        label_line = (self._ast.labels or {}).get(node.target)
        if label_line is not None:
            # 从 raw_lines 中提取标签体（从标签下一行到下一个标签/脚本结束）
            label_body_lines = []
            for idx in range(label_line, len(self._ast.raw_lines)):
                line = self._ast.raw_lines[idx]
                stripped = line.strip()
                # 遇到下一个标签（行首:）或 goto 命令时停止
                if re.match(r'^:', stripped) and idx != label_line:
                    break
                if re.match(r'^goto\b', stripped, re.I):
                    break
                label_body_lines.append(self._ast.raw_lines[idx])

            if label_body_lines:
                # 解析标签体内的行并模拟
                body_text = '\n'.join(label_body_lines)
                from core.hydra.ast_parser import ASTParser
                parser = ASTParser()
                body_ast = parser.parse(body_text, script_type=self._script_type)
                for body_node in body_ast.nodes:
                    # 展开标签体中的变量（含 %1, %2 等位置参数）
                    if hasattr(body_node, 'text'):
                        body_node.text = self.symbol_table.resolve(
                            body_node.text, line_no=body_node.line_no
                        )
                    if hasattr(body_node, 'raw'):
                        body_node.raw = self.symbol_table.resolve(
                            body_node.raw, line_no=body_node.line_no
                        )
                    self._simulate_node(body_node)
        else:
            self._result.warnings.append(
                f"call :{node.target} 标签未找到，已跳过"
            )

        # 恢复位置参数
        for pname, old_val in old_positional.items():
            if old_val is not None:
                self.symbol_table.define(pname, old_val, line_no=node.line_no)
            else:
                self.symbol_table._entries.pop(
                    self.symbol_table._normalize(pname), None
                )

    # ----------------------------------------------------------
    # For 循环模拟
    # ----------------------------------------------------------

    def _simulate_for(self, node: ForNode):
        """
        展开 for 循环

        支持：
          BAT: for /L %%i in (1,1,10) do (cmd)
               for %%i in (list) do (cmd)
               for %%i in (*.img *.bin) do (cmd) — 通配符展开
          SH:  for i in list; do cmd; done

        优化: 支持嵌套 if/for 结构中的循环变量替换
        """
        # 展开 items 中的变量（如 %PARTITIONS% → 空格分隔的分区名）
        raw_items = node.items_resolved or node.items
        resolved_items = []
        for item in raw_items:
            expanded = self.symbol_table.resolve(str(item))
            # 通配符展开：如果包含 * 或 ?，尝试 glob 匹配
            if '*' in expanded or '?' in expanded:
                glob_path = self._resolve_path(expanded.strip('"'))
                if not os.path.isabs(glob_path):
                    glob_path = os.path.abspath(glob_path)
                glob_path = glob_path.replace('\\', '/')
                matched = sorted(glob.glob(glob_path))
                if matched:
                    resolved_items.extend(matched)
                else:
                    # glob 无匹配 → 尝试基于 rom_dir 回退查找
                    fallback = self._resolve_path(expanded.strip('"'))
                    if self._rom_dir and not os.path.isabs(fallback):
                        fallback = os.path.join(self._rom_dir, fallback.lstrip('./\\'))
                    fallback = fallback.replace('\\', '/')
                    if fallback != glob_path:
                        matched2 = sorted(glob.glob(fallback))
                        if matched2:
                            resolved_items.extend(matched2)
                            continue
                    # 都找不到时 → 尝试从 rom_dir/script_dir 列出镜像文件，或使用常见文件名
                    pattern_val = expanded.strip('"\' ')
                    pattern_dir = os.path.dirname(pattern_val) if os.path.dirname(pattern_val) else '.'
                    # 尝试从可能的镜像目录中查找文件
                    candidate_dirs = []
                    if self._rom_dir:
                        candidate_dirs.append(self._rom_dir)
                    if self._script_path:
                        candidate_dirs.append(os.path.dirname(os.path.abspath(self._script_path)))
                    # 也尝试直接用 pattern_dir
                    if os.path.isdir(pattern_dir):
                        candidate_dirs.append(pattern_dir)
                    
                    found_images = []
                    for cd in candidate_dirs:
                        img_dir = os.path.join(cd, pattern_dir)
                        if os.path.isdir(img_dir):
                            for f in sorted(os.listdir(img_dir)):
                                if f.lower().endswith('.img'):
                                    found_images.append(os.path.join(img_dir, f).replace('\\', '/'))
                    
                    if found_images:
                        resolved_items.extend(found_images)
                        self._result.warnings.append(
                            f"通配符 '{pattern_val}' 在 {pattern_dir} 目录下找到 {len(found_images)} 个镜像文件"
                            f"（第 {node.line_no} 行）"
                        )
                    else:
                        # 完全找不到时：保留通配符模式本身作为循环值，让步骤显示通配符路径
                        pattern_val = expanded.strip('"\' ')
                        pattern_name = os.path.basename(pattern_val)
                        resolved_items.append(pattern_val)
                        self._result.warnings.append(
                            f"⚠️ 缺少镜像文件: '{pattern_val}' 未匹配到任何文件（第 {node.line_no} 行）"
                            f"，通配符 for 体内的命令将保留为动态步骤"
                        )
            # 如果展开后包含空格，拆分为多个值
            elif ' ' in expanded and '%' not in expanded and '$' not in expanded:
                for part_item in expanded.split():
                    part_item = part_item.strip('"\'')
                    if part_item:
                        resolved_items.append(part_item)
            else:
                resolved_items.append(expanded)

        for val in resolved_items:
            # 替换循环变量（深度遍历，支持嵌套结构）
            for body_node in node.body:
                resolved = self._deep_replace_loop_var(body_node, node.var, val)
                if resolved is not None:
                    # 递归模拟展开后的节点
                    self._simulate_node(resolved)
                else:
                    # 如果替换返回 None，用原节点
                    self._simulate_node(body_node)

        if not node.items_resolved:
            self._result.warnings.append(
                f"for 循环列表为空（第 {node.line_no} 行）: {node.raw}"
            )

    def _deep_replace_loop_var(self, node: ASTNode, var: str, val: str) -> Optional[ASTNode]:
        """
        深度替换循环变量 — 递归遍历嵌套结构

        支持对 CommandNode、IfNode、IfElseNode、ForNode、AssignmentNode 内部进行变量替换
        """
        if node is None:
            return None

        if isinstance(node, CommandNode):
            return self._replace_loop_var_in_text(node, var, val)

        elif isinstance(node, AssignmentNode):
            new_value = self._replace_text_var(node.value, var, val)
            return AssignmentNode(
                type="assignment", var=node.var,
                value=new_value,
                line_no=node.line_no, raw=node.raw,
            )

        elif isinstance(node, IfNode):
            new_condition = self._replace_text_var(node.condition, var, val)
            new_body = []
            for bn in node.body:
                replaced = self._deep_replace_loop_var(bn, var, val)
                new_body.append(replaced if replaced is not None else bn)
            return IfNode(
                type="if", condition=new_condition,
                body=new_body,
                line_no=node.line_no, end_line=node.end_line, raw=node.raw,
            )

        elif isinstance(node, IfElseNode):
            new_condition = self._replace_text_var(node.condition, var, val)
            new_if_body = []
            for bn in node.if_body:
                replaced = self._deep_replace_loop_var(bn, var, val)
                new_if_body.append(replaced if replaced is not None else bn)
            new_else_body = []
            for bn in node.else_body:
                replaced = self._deep_replace_loop_var(bn, var, val)
                new_else_body.append(replaced if replaced is not None else bn)
            return IfElseNode(
                type="if_else", condition=new_condition,
                if_body=new_if_body, else_body=new_else_body,
                line_no=node.line_no, end_line=node.end_line, raw=node.raw,
            )

        elif isinstance(node, ForNode):
            new_body = []
            for bn in node.body:
                replaced = self._deep_replace_loop_var(bn, var, val)
                new_body.append(replaced if replaced is not None else bn)
            return ForNode(
                type="for", var=node.var,
                items=node.items, items_resolved=node.items_resolved,
                body=new_body, is_numeric=node.is_numeric,
                start=node.start, step=node.step, end=node.end,
                line_no=node.line_no, end_line=node.end_line, raw=node.raw,
            )

        return node

    def _replace_text_var(self, text: str, var: str, val: str) -> str:
        """在纯文本中替换循环变量"""
        if self._script_type == "bat":
            var_char = var.replace('%', '')
            base_name = os.path.basename(val)  # 仅文件名
            base_no_ext, ext = os.path.splitext(base_name)  # 文件名无扩展
            item_dir = os.path.dirname(os.path.abspath(val)) + os.sep if val else ''
            # BAT 双百分号修饰符（%%~f、%%~dpf、%%~nf、%%~xf 等）
            # var_char 是循环变量名如 f、i、p 等
            new_text = text.replace(f'%%~{var_char}', val)
            new_text = new_text.replace(f'%%~dp{var_char}', item_dir)
            new_text = new_text.replace(f'%%~n{var_char}', base_no_ext)
            new_text = new_text.replace(f'%%~x{var_char}', ext)
            new_text = new_text.replace(f'%%~nx{var_char}', base_name)
            new_text = new_text.replace(f'%%~p{var_char}', item_dir)
            # 单百分号修饰符
            new_text = new_text.replace(f'%~n{var_char}', base_no_ext)
            new_text = new_text.replace(f'%~x{var_char}', ext)
            new_text = new_text.replace(f'%~nx{var_char}', base_name)
            new_text = new_text.replace(f'%~dp{var_char}', item_dir)
            new_text = new_text.replace(f'%~p{var_char}', item_dir)
            new_text = new_text.replace(f'%~f{var_char}', val)
            # 裸 %%var 和 %var%
            var_bat = f"%{var}"
            new_text = new_text.replace(var_bat, val)
            if new_text == text:
                new_text = new_text.replace(var, val)
            return new_text
        else:
            # SH: $var 和 ${var}
            new_text = text.replace(f'${{{var}}}', val)
            new_text = new_text.replace(f'${var}', val)
            return new_text

    def _replace_loop_var_in_text(self, node: CommandNode, var: str, val: str) -> CommandNode:
        """在 CommandNode 的文本中替换循环变量"""
        text = node.text
        if self._script_type == "bat":
            var_char = var.replace('%', '')
            name_no_ext, ext = os.path.splitext(val)
            item_dir = os.path.dirname(os.path.abspath(val)) + os.sep if val else ''
            # 1. 先处理 %~ 修饰符（%%~f、%%~dpf、%%~nf、%%~xf 等）
            #    BAT 中 %%~f = 完整路径, %%~nf = 文件名无扩展
            #    %%~dpf = 目录路径, %%~xf = 扩展名, %%~nxf = 完整文件名
            base_name = os.path.basename(val)  # 仅文件名
            base_no_ext, ext = os.path.splitext(base_name)  # 文件名无扩展
            item_dir = os.path.dirname(os.path.abspath(val)) + os.sep if val else ''
            text = text.replace(f'%%~{var_char}', val)
            text = text.replace(f'%%~dp{var_char}', item_dir)
            text = text.replace(f'%%~n{var_char}', base_no_ext)
            text = text.replace(f'%%~x{var_char}', ext)
            text = text.replace(f'%%~nx{var_char}', base_name)
            text = text.replace(f'%%~p{var_char}', item_dir)
            # 2. 再处理裸 %%f
            var_bat = f"%{var}"
            new_text = text.replace(var_bat, val)
            if new_text == text:
                new_text = text.replace(var, val)
            # 3. 处理单百分号的 %~ 修饰符（部分 BAT 写法）
            new_text = new_text.replace(f'%~n{var_char}', base_no_ext)
            new_text = new_text.replace(f'%~x{var_char}', ext)
            new_text = new_text.replace(f'%~nx{var_char}', base_name)
            new_text = new_text.replace(f'%~dp{var_char}', item_dir)
            new_text = new_text.replace(f'%~p{var_char}', item_dir)
            new_text = new_text.replace(f'%~f{var_char}', val)
        else:
            # SH: $part 和 ${part} 都替换
            new_text = text.replace(f'${{{var}}}', val)
            new_text = new_text.replace(f'${var}', val)
        return CommandNode(
            type="command",
            text=f"__LOOP_EXPANDED__{new_text}",
            line_no=node.line_no,
            raw=node.raw,
        )

    # ========== 废弃旧方法，保留为别名 ==========
    _replace_loop_var = _replace_loop_var_in_text


    # ----------------------------------------------------------
    # If 条件模拟
    # ----------------------------------------------------------
    def _simulate_if(self, node: IfNode):
        """模拟 if 条件 — 尝试评估条件真假"""
        result = self._eval_condition(node.condition)

        if result is True:
            # 条件为真，执行 if 体
            for body_node in node.body:
                self._simulate_node(body_node)
        elif result is False:
            # 条件为假，跳过
            self._result.expanded_lines.append(
                f"# if {node.condition} → 条件为假，跳过"
            )
        else:
            # 条件未知（运行时才能确定），标记为动态
            if node.condition:
                self._result.dynamic_commands += 1
                self._result.warnings.append(
                    f"if 条件无法静态评估 ({node.condition} at line {node.line_no})"
                )
                # 深度提取嵌套结构中所有可能的 fastboot 命令
                self._extract_commands_deep(node.body)

    def _simulate_if_else(self, node: IfElseNode):
        """模拟 if-else 条件"""
        result = self._eval_condition(node.condition)

        if result is True:
            self._result.expanded_lines.append(
                f"# if {node.condition} → 真，走 if 分支"
            )
            for body_node in node.if_body:
                self._simulate_node(body_node)
        elif result is False:
            self._result.expanded_lines.append(
                f"# if {node.condition} → 假，走 else 分支"
            )
            for body_node in node.else_body:
                self._simulate_node(body_node)
        else:
            self._result.dynamic_commands += 1
            self._result.warnings.append(
                f"if-else 条件无法静态评估 ({node.condition} at line {node.line_no})"
            )
            # 两个分支都深度提取
            self._extract_commands_deep(node.if_body)
            self._extract_commands_deep(node.else_body)

    def _extract_commands_deep(self, body: list):
        """深度提取嵌套结构中的 fastboot 命令"""
        for body_node in body:
            if isinstance(body_node, CommandNode):
                self._simulate_command(body_node)
            elif isinstance(body_node, (IfNode, IfElseNode)):
                # 递归提取 if 体
                inner_body = getattr(body_node, 'body', []) or \
                             getattr(body_node, 'if_body', []) + getattr(body_node, 'else_body', [])
                self._extract_commands_deep(inner_body)
            elif isinstance(body_node, ForNode):
                # 递归提取 for 体
                self._extract_commands_deep(body_node.body)
            elif isinstance(body_node, WhileNode):
                self._extract_commands_deep(body_node.body)
            elif isinstance(body_node, CaseNode):
                for _, branch_body in body_node.branches:
                    self._extract_commands_deep(branch_body)

    # ----------------------------------------------------------
    # While/Case 模拟
    # ----------------------------------------------------------

    def _simulate_while(self, node: WhileNode):
        """模拟 while 循环 — 静态分析无法确定循环次数，标记为动态"""
        condition = self.symbol_table.resolve(node.condition)
        self._result.warnings.append(
            f"while 循环（条件: {condition}）无法完全静态展开"
        )
        self._result.dynamic_commands += 1
        # 深度提取体中的命令
        self._extract_commands_deep(node.body)

    def _simulate_case(self, node: CaseNode):
        """模拟 case 分支 — 尝试匹配已知模式"""
        value = self.symbol_table.resolve(node.value)
        matched = False

        for pattern, body_nodes in node.branches:
            if not matched:
                if pattern == '*':
                    matched = True
                elif value and fnmatch.fnmatch(value, pattern):
                    matched = True

            if matched:
                for body_node in body_nodes:
                    self._simulate_node(body_node)
                break

        if not matched:
            self._result.dynamic_commands += 1
            self._result.warnings.append(
                f"case 分支无法匹配（value={value} at line {node.line_no})"
            )

    def _simulate_function(self, node: FunctionNode):
        """模拟函数定义 — 直接跳过（函数体在执行调用时展开）"""
        self._result.expanded_lines.append(
            f"# function {node.name}() 定义跳过（运行时调用时展开）"
        )
        # 注册函数名到符号表，用于识别调用
        self.symbol_table.define(f"__func__{node.name}", "defined", line_no=node.line_no)

    # ----------------------------------------------------------
    # 条件评估工具
    # ----------------------------------------------------------

    def _eval_condition(self, condition: str) -> Optional[bool]:
        """
        评估条件表达式

        BAT:
          exist <path>      → 文件是否存在
          defined <var>     → 变量是否已定义
          <a> equ/== <b>    → 数值/字符串比较
          <a> neq/lss/leq/gtr/geq <b>
          not <cond>        → 逻辑非

        SH:
          -f <path>         → 文件是否存在
          -d <path>         → 目录是否存在
          -z <str>          → 字符串是否为空
          -n <str>          → 字符串是否非空
          <a> = <b>         → 字符串相等
          <a> != <b>        → 字符串不等
          <a> -eq/-ne/-lt/-le/-gt/-ge <b> → 数值比较

        Returns:
            True / False / None（无法确定）
        """
        if not condition:
            return None

        # 展开变量
        expanded = self.symbol_table.resolve(condition)

        if self._script_type == "bat":
            return self._eval_bat_condition(expanded)
        else:
            return self._eval_sh_condition(expanded)

    def _eval_bat_condition(self, condition: str) -> Optional[bool]:
        """评估 BAT 条件"""
        condition = condition.strip().strip('"\'')

        m = re.match(r'^(not\s+)?exist\s+(.+)$', condition, re.I)
        if m:
            is_not = m.group(1) is not None
            path_str = m.group(2).strip().strip('"\'')
            path_full = self._resolve_path(path_str)
            exists = os.path.exists(path_full)
            if exists:
                return False if is_not else True  # not exist + 文件存在 = 假；exist + 文件存在 = 真
            # 文件不存在也返回 None（未知），让体内命令被提取为动态步骤
            return None

        m = re.match(r'^(not\s+)?defined\s+(\w+)$', condition, re.I)
        if m:
            is_not = m.group(1) is not None
            var_name = m.group(2)
            defined = self.symbol_table.is_defined(var_name)
            return (not defined) if is_not else defined

        # if errorlevel N
        m = re.match(r'^errorlevel\s+(\d+)$', condition, re.I)
        if m:
            return None  # 无法静态评估

        # 比较运算
        m = re.match(r'^(.+?)\s+(equ|==|neq|lss|leq|gtr|geq)\s+(.+)$', condition, re.I)
        if m:
            left = m.group(1).strip().strip('"\'')
            right = m.group(3).strip().strip('"\'')
            op = m.group(2).lower()

            try:
                ln = float(left)
                rn = float(right)
                if op in ('equ', '=='):
                    return ln == rn
                elif op == 'neq':
                    return ln != rn
                elif op == 'lss':
                    return ln < rn
                elif op == 'leq':
                    return ln <= rn
                elif op == 'gtr':
                    return ln > rn
                elif op == 'geq':
                    return ln >= rn
            except ValueError:
                if op in ('equ', '=='):
                    return left.lower() == right.lower()
                elif op == 'neq':
                    return left.lower() != right.lower()
                else:
                    return None

        return None

    def _eval_sh_condition(self, condition: str) -> Optional[bool]:
        """评估 SH 条件"""
        condition = condition.strip()

        # 简单命令（如 command -v fastboot）
        if not condition.startswith('[') and not condition.startswith('test'):
            return None

        # [ -f path ] — 文件存在 → True，不存在/未知 → None（让步骤被提取并标记为动态）
        m = re.match(r'\[\s+-f\s+(.+?)\s*\]', condition)
        if m:
            path_str = m.group(1).strip().strip('"\'')
            path_full = self._resolve_path(path_str)
            if path_full and os.path.isfile(path_full):
                return True
            # 文件不存在也返回 None（未知），让体内命令被提取为动态步骤
            return None

        # [ -d path ] — 目录存在 → True，不存在/未知 → None
        m = re.match(r'\[\s+-d\s+(.+?)\s*\]', condition)
        if m:
            path_str = m.group(1).strip().strip('"\'')
            path_full = self._resolve_path(path_str)
            if path_full and os.path.isdir(path_full):
                return True
            return None

        # [ -z str ]
        m = re.match(r'\[\s+-z\s+(.+?)\s*\]', condition)
        if m:
            val = m.group(1).strip().strip('"\'')
            return len(val) == 0

        # [ -n str ]
        m = re.match(r'\[\s+-n\s+(.+?)\s*\]', condition)
        if m:
            val = m.group(1).strip().strip('"\'')
            return len(val) > 0

        # [ a = b ]
        m = re.match(r'\[\s+(.+?)\s*=\s*(.+?)\s*\]', condition)
        if m:
            left = m.group(1).strip().strip('"\'')
            right = m.group(2).strip().strip('"\'')
            return left == right

        # [ a != b ]
        m = re.match(r'\[\s+(.+?)\s*!=\s*(.+?)\s*\]', condition)
        if m:
            left = m.group(1).strip().strip('"\'')
            right = m.group(2).strip().strip('"\'')
            return left != right

        # [ a -eq/-ne b ]
        m = re.match(r'\[\s+(.+?)\s+-(eq|ne|lt|le|gt|ge)\s+(.+?)\s*\]', condition)
        if m:
            left = m.group(1).strip().strip('"\'')
            right = m.group(3).strip().strip('"\'')
            op = m.group(2)
            try:
                ln, rn = float(left), float(right)
                ops = {
                    'eq': lambda a, b: a == b, 'ne': lambda a, b: a != b,
                    'lt': lambda a, b: a < b, 'le': lambda a, b: a <= b,
                    'gt': lambda a, b: a > b, 'ge': lambda a, b: a >= b,
                }
                return ops[op](ln, rn)
            except ValueError:
                return None

        return None

    # ----------------------------------------------------------
    # 路径工具
    # ----------------------------------------------------------

    def _resolve_path(self, path: str) -> str:
        """解析文件路径（支持相对 ROM_DIR 的路径）"""
        path = path.replace('\\', '/')
        if self._rom_dir and not os.path.isabs(path):
            return os.path.join(self._rom_dir, path.lstrip('./'))
        return path

    def _resolve_path_modifiers(self, text: str) -> str:
        """解析 BAT 路径修饰符（%~dp0 等）"""
        if self._script_type == "bat" and self._script_path:
            sp_abs = os.path.abspath(self._script_path)
            sp_dir = os.path.dirname(sp_abs)
            sp_name = os.path.basename(sp_abs)
            sp_base, sp_ext = os.path.splitext(sp_name)
            for mod, val in [
                ('~dp0', sp_dir + os.sep), ('~n0', sp_base),
                ('~x0', sp_ext), ('~nx0', sp_name), ('~s0', sp_abs),
                ('~p0', sp_dir + os.sep), ('~f0', sp_abs),
            ]:
                text = text.replace('%' + mod, val)
        return text


__all__ = ["Environment", "EnvSimulateResult"]