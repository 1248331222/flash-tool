# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/ast_parser.py
"""
Hydra — AST 解析器
====================
将 BAT/SH 脚本解析为抽象语法树（AST），支持行号追踪和标签映射。

核心职责：
  1. 将脚本拆解为语法单元（行/块/控制结构）
  2. 识别控制结构边界（for 循环体、if 块、函数定义）
  3. 建立标签（:label / function()）到行的映射
  4. 保持 AST 节点的行号信息用于后续调试

BAT 语法结构：
  - 简单命令行          → CommandNode
  - for %%i in (...) do → ForNode (含循环变量、列表、体)
  - if condition (cmd)  → IfNode (含条件、体)
  - if condition (...) else (...) → IfElseNode
  - call :label         → CallNode
  - :label              → LabelNode
  - set VAR=value       → AssignmentNode
  - setlocal/endlocal   → DirectiveNode
  - goto :label         → GotoNode
  - rem / ::            → CommentNode (跳过)

SH 语法结构：
  - 简单命令            → CommandNode
  - for var in ... do ... done       → ForNode
  - if ... then ... fi              → IfNode
  - if ... then ... else ... fi     → IfElseNode
  - function name() { ... }         → FunctionNode
  - name() { ... }                  → FunctionNode
  - var=value                       → AssignmentNode
  - case ... esac                   → CaseNode
  - while/until                    → WhileNode
  - export/readonly                → DirectiveNode
"""

import re
from typing import List, Dict, Optional, Any, Union
from dataclasses import dataclass, field


# ============================================================
# AST 节点定义
# ============================================================

@dataclass
class ASTNode:
    """AST 抽象基节点"""
    type: str               # 节点类型标识
    line_no: int = 0        # 起始行号（从 1 开始）
    end_line: int = 0       # 结束行号
    raw: str = ""           # 原始文本


@dataclass
class CommandNode(ASTNode):
    """简单命令节点（fastboot flash, echo, 等）"""
    text: str = ""          # 展开后的命令文本
    args: list = field(default_factory=list)  # 参数列表


@dataclass
class ForNode(ASTNode):
    """for 循环节点"""
    var: str = ""           # 循环变量名
    items: list = field(default_factory=list)  # 循环列表（展开前）
    items_resolved: list = field(default_factory=list)  # 展开后的值列表
    body: List[ASTNode] = field(default_factory=list)
    is_numeric: bool = False   # /L 数值循环
    start: int = 0
    step: int = 1
    end: int = 0
    is_file: bool = False      # /F 文件循环


@dataclass
class IfNode(ASTNode):
    """if 条件节点"""
    condition: str = ""     # 条件表达式
    body: List[ASTNode] = field(default_factory=list)


@dataclass
class IfElseNode(ASTNode):
    """if-else 条件节点"""
    condition: str = ""
    if_body: List[ASTNode] = field(default_factory=list)
    else_body: List[ASTNode] = field(default_factory=list)


@dataclass
class LabelNode(ASTNode):
    """标签节点（BAT :label / SH label()）"""
    name: str = ""


@dataclass
class CallNode(ASTNode):
    """call 节点（BAT call :label）"""
    target: str = ""
    args: str = ""


@dataclass
class GotoNode(ASTNode):
    """goto 节点"""
    target: str = ""


@dataclass
class AssignmentNode(ASTNode):
    """赋值节点（set VAR=val / var=val）"""
    var: str = ""
    value: str = ""
    is_expression: bool = False  # set /a 算术表达式


@dataclass
class DirectiveNode(ASTNode):
    """指令节点（setlocal/endlocal/export）"""
    directive: str = ""
    detail: str = ""


@dataclass
class FunctionNode(ASTNode):
    """函数定义节点（SH）"""
    name: str = ""
    body: List[ASTNode] = field(default_factory=list)


@dataclass
class WhileNode(ASTNode):
    """while/until 循环节点"""
    condition: str = ""
    body: List[ASTNode] = field(default_factory=list)
    is_until: bool = False


@dataclass
class CaseNode(ASTNode):
    """case 分支节点"""
    value: str = ""
    branches: List[tuple] = field(default_factory=list)  # [(pattern, [nodes])]


# ============================================================
# AST 解析结果
# ============================================================

@dataclass
class ASTParseResult:
    """AST 解析器的输出"""
    nodes: List[ASTNode] = field(default_factory=list)
    labels: Dict[str, int] = field(default_factory=dict)       # label_name -> line_no
    functions: Dict[str, FunctionNode] = field(default_factory=dict)  # function_name -> node
    script_type: str = "bat"
    raw_lines: List[str] = field(default_factory=list)


# ============================================================
# ASTParser — AST 解析器
# ============================================================

class ASTParser:
    """
    AST 解析器 — 将 BAT/SH 脚本解析为结构化语法树

    用法:
        parser = ASTParser()
        result = parser.parse(content, script_type="bat")
        for node in result.nodes:
            print(node.type, node.raw)
    """

    def __init__(self):
        self._lines: List[str] = []
        self._i: int = 0
        self._script_type: str = "bat"
        self._script_path: str = ""

    def parse(
        self,
        content: str,
        script_type: str = "bat",
        script_path: str = "",
    ) -> Optional[ASTParseResult]:
        """
        主解析入口

        Args:
            content: 脚本内容字符串
            script_type: "bat" 或 "sh"
            script_path: 脚本文件路径（可选）

        Returns:
            ASTParseResult 或 None（解析失败时）
        """
        self._script_type = script_type.lower()
        self._script_path = script_path

        # 预处理：合并续行符，按行拆分
        raw = content.replace('^\n', ' ').replace('^\r\n', ' ')
        self._lines = raw.splitlines()
        self._i = 0

        # 词法分析：第一次扫描收集所有标签/函数
        labels: Dict[str, int] = {}
        functions: Dict[str, FunctionNode] = {}

        if self._script_type == "bat":
            self._scan_bat_labels(labels)
        elif self._script_type == "sh":
            self._scan_sh_functions(functions)

        # 语法分析：逐行解析构建 AST
        self._i = 0
        nodes = self._parse_block()

        result = ASTParseResult(
            nodes=nodes,
            labels=labels,
            functions=functions,
            script_type=self._script_type,
            raw_lines=self._lines,
        )

        return result

    # ----------------------------------------------------------
    # 词法扫描
    # ----------------------------------------------------------

    def _scan_bat_labels(self, labels: Dict[str, int]):
        """第一遍扫描 BAT 脚本，收集所有 :label"""
        for idx, line in enumerate(self._lines):
            stripped = line.strip()
            m = re.match(r'^:([a-zA-Z0-9_\-]+)', stripped)
            if m:
                labels[m.group(1)] = idx + 1  # 1-based

    def _scan_sh_functions(self, functions: Dict[str, FunctionNode]):
        """第一遍扫描 SH 脚本，收集函数定义边界"""
        idx = 0
        while idx < len(self._lines):
            line = self._lines[idx]
            stripped = line.strip()
            # 匹配 name() { 或 function name() {
            m = re.match(
                r'^(?:function\s+)?([a-zA-Z_]\w*)\s*\(\s*\)\s*(\{|{)',
                stripped
            )
            if m:
                name = m.group(1)
                start = idx
                # 找到匹配的 }，简单处理：数大括号
                brace_depth = stripped.count('{') - stripped.count('}')
                body_start = idx + 1
                body_lines = []
                idx += 1
                while idx < len(self._lines) and brace_depth > 0:
                    l = self._lines[idx]
                    brace_depth += l.count('{') - l.count('}')
                    if brace_depth > 0:
                        body_lines.append(l)
                    idx += 1
                functions[name] = FunctionNode(
                    type="function",
                    name=name,
                    body=[CommandNode(type="command", text=l) for l in body_lines],
                    line_no=start + 1,
                    end_line=idx + 1,
                    raw='\n'.join(body_lines),  # 存储原始代码体，供后续重解析
                )
                continue
            idx += 1

    # ----------------------------------------------------------
    # 语法分析
    # ----------------------------------------------------------

    def _parse_block(self) -> List[ASTNode]:
        """解析连续的命令行序列"""
        nodes = []
        while self._i < len(self._lines):
            line = self._lines[self._i].strip()
            if not line:
                self._i += 1
                continue
            # 尝试识别各类控制结构
            before_i = self._i
            node = self._try_parse_control_structure()
            if node is not None:
                nodes.append(node)
                continue
            # 如果 _try_parse_control_structure 已经移动了 _i（例如跳过注释），
            # 则重新开始循环，不要用 _parse_simple_line 处理新的 _i 位置
            if self._i != before_i:
                continue

            # 普通行
            node = self._parse_simple_line()
            if node is not None:
                nodes.append(node)
            else:
                self._i += 1

        return nodes

    def _try_parse_control_structure(self) -> Optional[ASTNode]:
        """尝试解析控制结构（for/if/else/label/call/goto）"""
        if self._script_type == "bat":
            return self._try_parse_bat_control()
        elif self._script_type == "sh":
            return self._try_parse_sh_control()
        print(f"WARNING: unknown script_type={self._script_type}")
        return None

    # ===================== BAT 解析 =====================

    def _try_parse_bat_control(self) -> Optional[ASTNode]:
        line = self._lines[self._i].strip()
        lower = line.lower()
        line_no = self._i + 1

        # 跳过注释和 echo off — 返回None但不加索引，由 _parse_simple_line 处理
        if line.startswith('::') or lower.startswith('rem '):
            return None

        if re.match(r'^@?echo\s+', lower) or lower in ('echo', 'echo.'):
            return None

        # 忽略指令（setlocal/endlocal 必须返回 DirectiveNode）
        if lower.startswith('setlocal ') or lower == 'setlocal' or lower.startswith('endlocal'):
            is_setlocal = lower.startswith('setlocal')
            detail = line[len('setlocal' if is_setlocal else 'endlocal'):].strip()
            cmd = 'setlocal' if is_setlocal else 'endlocal'
            self._i += 1
            return DirectiveNode(type="directive", directive=cmd, detail=detail, line_no=line_no, raw=line)

        if re.match(r'^(title|color|chcp|pause|cls)\b', lower):
            return None

        # :label
        m = re.match(r'^:([a-zA-Z0-9_\-]+)', line)
        if m:
            self._i += 1
            return LabelNode(type="label", name=m.group(1), line_no=line_no, raw=line)

        # goto
        m = re.match(r'^goto\s+:?([a-zA-Z0-9_\-]+)', lower)
        if m:
            self._i += 1
            return GotoNode(type="goto", target=m.group(1), line_no=line_no, raw=line)

        # call :label
        m = re.match(r'^call\s+:(\w+)(.*)', line, re.I)
        if m:
            self._i += 1
            return CallNode(type="call", target=m.group(1), args=m.group(2).strip(), line_no=line_no, raw=line)

        # for 循环
        if re.match(r'^for\s+', lower) and '(' in line:
            node = self._parse_bat_for(line, line_no)
            if node:
                return node

        # if 条件
        if re.match(r'^if\s+', lower):
            node = self._parse_bat_if(line, line_no)
            if node:
                return node

        # ) 闭合（属于上层控制结构，不应在此处理）
        if line == ')':
            self._i += 1
            return None

        return None

    def _parse_bat_for(self, line: str, line_no: int) -> Optional[ForNode]:
        """解析 BAT for 循环"""
        # for /L %%i in (start,step,end) do (
        m = re.match(r'^for\s+/L\s+%%(\w+)\s+in\s*\((\d+),(\d+),(\d+)\)\s*do\s*\(?', line, re.I)
        if m:
            var = '%' + m.group(1)
            start, step, end = int(m.group(2)), int(m.group(3)), int(m.group(4))
            body, end_i = self._collect_bat_block(self._i + 1)
            end_line = end_i + 1
            self._i = end_i + 1
            # 展开数值
            if step == 0:
                vals = [start]
            elif step > 0:
                vals = list(range(start, end + 1, step))
            else:
                vals = list(range(start, end - 1, step))
            body_nodes = self._parse_block_lines(body)
            return ForNode(
                type="for", var=var,
                items=[str(v) for v in vals],
                items_resolved=[str(v) for v in vals],
                body=body_nodes,
                is_numeric=True, start=start, step=step, end=end,
                line_no=line_no, end_line=end_line, raw=line,
            )

        # for /F "tokens=* delims=" %%i in (...) do (
        m = re.match(r'^for\s+/F\s+(?:"[^"]*"\s+)?%%(\w+)\s+in\s*\(([^)]+)\)\s*do\s*\(?', line, re.I)
        if m:
            var = '%' + m.group(1)
            raw_items_str = m.group(2).strip()
            # 处理不同来源：
            # 1. 'command' → 标记为动态（无法静态执行命令）
            # 2. "text" → 单字面量
            # 3. file1 file2 ... → 静态文件列表
            # 4. %VAR% → 变量引用（等展开后处理）
            if raw_items_str.startswith("'") or raw_items_str.startswith('"'):
                # 命令输出或字面量 → 标记为动态
                items = [raw_items_str]
                items_resolved = [raw_items_str]
            else:
                # 文件列表或变量引用 → 提取为 items
                items = [x.strip().strip('"\'') for x in raw_items_str.split() if x.strip()]
                items_resolved = list(items)
            
            body, end_i = self._collect_bat_block(self._i + 1)
            end_line = end_i + 1
            self._i = end_i + 1
            body_nodes = self._parse_block_lines(body)
            return ForNode(
                type="for", var=var,
                items=items, items_resolved=items_resolved,
                body=body_nodes,
                is_numeric=False,
                is_file=True,
                line_no=line_no, end_line=end_line, raw=line,
            )

        # for %%i in (list) do (
        m = re.match(r'^for\s+%%(\w+)\s+in\s*\(([^)]+)\)\s*do\s*\(?', line, re.I)
        if m:
            var = '%' + m.group(1)
            items = [x.strip().strip('"\'') for x in m.group(2).split() if x.strip()]
            body, end_i = self._collect_bat_block(self._i + 1)
            end_line = end_i + 1
            self._i = end_i + 1
            body_nodes = self._parse_block_lines(body)
            return ForNode(
                type="for", var=var,
                items=items, items_resolved=list(items),
                body=body_nodes,
                is_numeric=False,
                line_no=line_no, end_line=end_line, raw=line,
            )

        self._i += 1
        return None

    def _parse_bat_if(self, line: str, line_no: int) -> Optional[Union[IfNode, IfElseNode]]:
        """解析 BAT if 条件"""
        # 检查是否带括号块
        has_block = '(' in line
        if not has_block:
            # 单行 if
            m = re.match(r'^if\s+(.+?)\s+(.+)$', line, re.I)
            if m:
                self._i += 1
                return IfNode(
                    type="if",
                    condition=m.group(1).strip(),
                    body=[CommandNode(type="command", text=m.group(2), line_no=line_no, raw=line)],
                    line_no=line_no, end_line=line_no, raw=line,
                )
            self._i += 1
            return None

        # 带括号块形式
        m = re.match(r'^if\s+(.+?)\s*\(', line, re.I)
        if m:
            condition = m.group(1).strip()
            body, end_i = self._collect_bat_block(self._i + 1)
            body_nodes = self._parse_block_lines(body)
            next_i = end_i + 1

            # 检查 else
            if next_i < len(self._lines):
                else_line = self._lines[next_i].strip()
                if re.match(r'^\)\s*else\s*\(', else_line.lower()):
                    else_body, else_end_i = self._collect_bat_block(next_i + 1)
                    else_body_nodes = self._parse_block_lines(else_body)
                    self._i = else_end_i + 1
                    end_line = else_end_i + 1
                    return IfElseNode(
                        type="if_else",
                        condition=condition,
                        if_body=body_nodes,
                        else_body=else_body_nodes,
                        line_no=line_no, end_line=end_line, raw=line,
                    )

            self._i = next_i
            end_line = end_i + 1
            return IfNode(
                type="if",
                condition=condition,
                body=body_nodes,
                line_no=line_no, end_line=end_line, raw=line,
            )

        self._i += 1
        return None

    def _collect_bat_block(self, start_idx: int) -> tuple:
        """收集 BAT 括号块 (...) 的内容，返回 (lines, end_idx)"""
        depth = 1
        j = start_idx
        block = []
        while j < len(self._lines):
            bline = self._lines[j]
            in_quote = False
            quote_char = None
            close_pos = -1
            for ci, ch in enumerate(bline):
                if ch in '"\'':
                    if not in_quote:
                        in_quote = True
                        quote_char = ch
                    elif quote_char == ch:
                        in_quote = False
                elif not in_quote:
                    if ch == '(':
                        depth += 1
                    elif ch == ')':
                        depth -= 1
                        if depth <= 0:
                            close_pos = ci
                            break
            if depth <= 0:
                # 排除闭合括号后的内容
                if close_pos > 0:
                    prefix = bline[:close_pos].strip()
                    if prefix:
                        block.append(prefix)
                break
            block.append(bline)
            j += 1
            if j >= len(self._lines):
                break
        return block, j

    # ===================== SH 解析 =====================

    def _try_parse_sh_control(self) -> Optional[ASTNode]:
        line = self._lines[self._i].strip()
        lower = line.strip()
        line_no = self._i + 1

        # 跳过注释
        if line.startswith('#') and not line.startswith('#!'):
            self._i += 1
            return None

        # for ... do ... done
        if re.match(r'^for\s+', lower):
            return self._parse_sh_for(line, line_no)

        # if ... then ... fi / elif / else
        if re.match(r'^if\s+', lower):
            return self._parse_sh_if(line, line_no)

        # while/until
        if re.match(r'^(while|until)\s+', lower):
            m = re.match(r'^(while|until)\s+(.+?)\s*;?\s*do', lower)
            if m:
                is_until = m.group(1) == 'until'
                body, end_i = self._collect_sh_block('done')
                body_nodes = self._parse_block_lines(body)
                self._i = end_i + 1
                end_line = end_i + 1
                return WhileNode(
                    type="while",
                    condition=m.group(2).strip(),
                    body=body_nodes,
                    is_until=is_until,
                    line_no=line_no, end_line=end_line, raw=line,
                )
            self._i += 1
            return None

        # case ... esac
        if re.match(r'^case\s+', lower):
            return self._parse_sh_case(line, line_no)

        # function name() { / name() {
        if re.match(r'^(?:function\s+)?[a-zA-Z_]\w*\s*\(\s*\)', lower):
            # 已由第一遍扫描处理，跳过
            brace_depth = line.count('{') - line.count('}')
            self._i += 1
            while self._i < len(self._lines) and brace_depth > 0:
                l = self._lines[self._i]
                brace_depth += l.count('{') - l.count('}')
                self._i += 1
            return None

        # export/readonly/local
        if re.match(r'^(export|readonly|local)\s+', lower):
            m = re.match(r'^(export|readonly|local)\s+([a-zA-Z_]\w*)=(.*)', lower)
            if m:
                # local var=val 形式 → 作为赋值处理
                self._i += 1
                return AssignmentNode(type="assignment", var=m.group(2), value=m.group(3), line_no=line_no, raw=line)
            m = re.match(r'^(export|readonly|local)\s+(.+)', lower)
            if m:
                self._i += 1
                return DirectiveNode(type="directive", directive=m.group(1), detail=m.group(2), line_no=line_no, raw=line)
            self._i += 1
            return None

        # var=value (赋值)
        m = re.match(r'^([a-zA-Z_]\w*)=(.+)', lower)
        if m and not lower.startswith('for') and not lower.startswith('if'):
            self._i += 1
            return AssignmentNode(type="assignment", var=m.group(1), value=m.group(2), line_no=line_no, raw=line)

        return None

    def _parse_sh_for(self, line: str, line_no: int) -> Optional[ForNode]:
        """解析 SH for 循环"""
        m = re.match(r'^for\s+(\w+)\s+in\s+(.+?)\s*;?\s+do\b', line)
        if m:
            var = m.group(1)
            items_raw = m.group(2).strip()
            # 更精确的 item 拆分：保持引号组为整体，但剥离包裹引号
            # SH 中 "$IMG_DIR"/*.img 是一个整体（glob pattern），不能拆分
            items = []
            for token in re.findall(r'\S+', items_raw):
                # 剥离外层引号
                cleaned = token
                if cleaned.startswith('"') or cleaned.startswith("'"):
                    cleaned = cleaned[1:]
                if cleaned.endswith('"') or cleaned.endswith("'"):
                    cleaned = cleaned[:-1]
                # 清理内部的残留引号
                cleaned = cleaned.replace('"', '').replace("'", '')
                if cleaned:
                    items.append(cleaned)
            body, end_i = self._collect_sh_block('done')
            body_nodes = self._parse_block_lines(body)
            self._i = end_i + 1
            end_line = end_i + 1
            return ForNode(
                type="for", var=var,
                items=items, items_resolved=list(items),
                body=body_nodes,
                is_numeric=False,
                line_no=line_no, end_line=end_line, raw=line,
            )

        # for ((expr; expr; expr)) 风格
        m = re.match(r'^for\s*\(\((.*?);(.*?);(.*?)\)\)\s*;?\s*do', line)
        if m:
            self._i += 1
            return None  # 太复杂，暂不支持

        self._i += 1
        return None

    def _parse_sh_if(self, line: str, line_no: int) -> Optional[Union[IfNode, IfElseNode]]:
        """解析 SH if 条件"""
        m = re.match(r'^if\s+(.+?)\s*;?\s*then', line)
        if not m:
            self._i += 1
            return None

        condition = m.group(1).strip()
        if_body, end_i = self._collect_sh_block('fi', allow_else=True)

        # 检查 else / elif
        if_body_nodes = []
        else_body_nodes = []
        has_else = False

        # 看看是否在 body 中遇到了 else 分割
        else_idx = -1
        for idx, bline in enumerate(if_body):
            if bline.strip().lower() == 'else':
                else_idx = idx
                break
            if re.match(r'^elif\s+', bline.strip().lower()):
                else_idx = idx
                break

        if else_idx >= 0:
            has_else = True
            if_body_nodes = self._parse_block_lines(if_body[:else_idx])
            else_body_nodes = self._parse_block_lines(if_body[else_idx + 1:])
        else:
            if_body_nodes = self._parse_block_lines(if_body)

        self._i = end_i + 1
        end_line = end_i + 1

        if has_else:
            return IfElseNode(
                type="if_else",
                condition=condition,
                if_body=if_body_nodes,
                else_body=else_body_nodes,
                line_no=line_no, end_line=end_line, raw=line,
            )

        return IfNode(
            type="if",
            condition=condition,
            body=if_body_nodes,
            line_no=line_no, end_line=end_line, raw=line,
        )

    def _parse_sh_case(self, line: str, line_no: int) -> Optional[CaseNode]:
        """解析 SH case 分支"""
        m = re.match(r'^case\s+(.+?)\s+in', line)
        if not m:
            self._i += 1
            return None

        value = m.group(1).strip()
        branches = []
        current_pattern = None
        current_body = []

        self._i += 1
        while self._i < len(self._lines):
            l = self._lines[self._i].strip()
            if l == 'esac':
                if current_pattern is not None:
                    branches.append((current_pattern, self._parse_block_lines(current_body)))
                self._i += 1
                break
            # pattern)
            pm = re.match(r'^([^(]+)\)', l)
            if pm:
                if current_pattern is not None:
                    branches.append((current_pattern, self._parse_block_lines(current_body)))
                current_pattern = pm.group(1).strip()
                current_body = []
                # 单行 case（;; 在同一行）
                if ';;' in l:
                    cmd = l.split(';;')[0].split(')')[-1].strip()
                    if cmd:
                        current_body.append(cmd)
                    branches.append((current_pattern, self._parse_block_lines(current_body)))
                    current_pattern = None
                    current_body = []
            elif l == ';;':
                if current_pattern is not None:
                    branches.append((current_pattern, self._parse_block_lines(current_body)))
                    current_pattern = None
                    current_body = []
            elif current_pattern is not None:
                current_body.append(l)
            self._i += 1

        end_line = self._i
        return CaseNode(
            type="case",
            value=value,
            branches=branches,
            line_no=line_no, end_line=end_line, raw=line,
        )

    def _collect_sh_block(self, end_keyword: str, allow_else: bool = False) -> tuple:
        """
        收集 SH 块内容直到遇到 end_keyword
        返回 (lines, end_idx)
        """
        body = []
        depth = 0
        # 跟踪 for...done 嵌套深度（不依赖 if...fi 深度）
        for_depth = 0
        self._i += 1
        while self._i < len(self._lines):
            l = self._lines[self._i]
            stripped = l.strip().lower()

            # 处理嵌套 if 的 fi 计数
            if stripped == 'fi':
                if depth == 0:
                    break
                depth -= 1
                body.append(l)
                self._i += 1
                continue

            # 跟踪 if...then 嵌套深度
            if stripped == 'then':
                depth += 1
            if stripped.startswith('if ') and stripped.endswith('; then'):
                depth += 1

            # 跟踪 for...do...done 嵌套深度
            if re.match(r'^for\s+', stripped) and ('do' in stripped or ';' in stripped):
                for_depth += 1
            if stripped == 'done':
                if for_depth > 0:
                    for_depth -= 1
                    body.append(l)
                    self._i += 1
                    continue
                # for_depth == 0 时，才是真正的 done
                if depth == 0:
                    break

            if stripped == end_keyword and depth == 0 and for_depth == 0:
                break

            if allow_else and stripped in ('else',) and depth == 0:
                break
            if allow_else and stripped.startswith('elif ') and depth == 0:
                break

            body.append(l)
            self._i += 1

        return body, self._i

    # ===================== 通用工具 =====================

    def _parse_block_lines(self, lines: List[str]) -> List[ASTNode]:
        """将行列表解析为 AST 节点列表（子解析器）"""
        saved_lines = self._lines
        saved_i = self._i

        self._lines = lines
        self._i = 0
        nodes = self._parse_block()

        self._lines = saved_lines
        self._i = saved_i
        return nodes

    def _parse_simple_line(self) -> Optional[ASTNode]:
        """解析简单命令/赋值行"""
        if self._i >= len(self._lines):
            return None

        line = self._lines[self._i]
        stripped = line.strip()
        line_no = self._i + 1

        if not stripped:
            self._i += 1
            return None

        self._i += 1

        # BAT set 赋值（含 set /p 用户输入、set /a 算术）
        m = re.match(r'^set\s+(/a\s+)?(/p\s+)?("?)([a-zA-Z0-9_]+)=("?)(.*?)("?)$', stripped, re.I)
        if m and self._script_type == "bat":
            is_expr = bool(m.group(1))  # set /a
            is_prompt = bool(m.group(2))  # set /p
            # set /p 用空字符串模拟用户输入
            value = m.group(6) if not is_prompt else ''
            return AssignmentNode(
                type="assignment", var=m.group(4), value=value,
                is_expression=is_expr,
                line_no=line_no, raw=stripped
            )

        # SH 赋值（已在控制结构中处理过，这里只处理遗漏的）
        m = re.match(r'^([a-zA-Z_]\w*)=(.+)', stripped)
        if m and self._script_type == "sh" and not stripped.startswith('#'):
            return AssignmentNode(type="assignment", var=m.group(1), value=m.group(2), line_no=line_no, raw=stripped)

        # SH local/export/readonly 赋值
        m = re.match(r'^(local|export|readonly)\s+([a-zA-Z_]\w*)=(.+)', stripped)
        if m and self._script_type == "sh":
            return AssignmentNode(type="assignment", var=m.group(2), value=m.group(3), line_no=line_no, raw=stripped)

        return CommandNode(type="command", text=stripped, line_no=line_no, raw=stripped)


__all__ = [
    "ASTParser", "ASTParseResult",
    "ASTNode", "CommandNode", "ForNode", "IfNode", "IfElseNode",
    "LabelNode", "CallNode", "GotoNode", "AssignmentNode",
    "DirectiveNode", "FunctionNode", "WhileNode", "CaseNode",
]