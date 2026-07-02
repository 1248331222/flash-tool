# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/cmd_sandbox/sandbox.py
"""
Hydra — Win CMD 沙箱主入口

WinCmdSandbox 是沙箱的核心调度器：
  1. 加载脚本
  2. 扫描标签
  3. 逐行执行（if/for/goto/call/set 控制流 + 内置命令 + 外部命令）
  4. 输出捕获到的 fastboot/adb 命令
"""

import os
import re
from typing import Dict, List, Optional, Tuple

from .runtime import WinCmdRuntime
from .vfs import VirtualFileSystem
from .result import CommandResult
from .parser import (
    split_operators, strip_redirection, is_cmd_c,
    is_set_line, is_echo_line, is_cd_line,
    is_pushd_line, is_popd_line,
    parse_redirection, split_pipe,
)
from .handlers import dispatch_builtin, handle_external


class WinCmdSandbox:
    """Win CMD 沙箱——模拟 BAT 脚本在 cmd.exe 中的执行"""

    def __init__(self, script_path: str = "", rom_dir: str = "",
                 max_steps: int = 20000):
        self.script_path = script_path
        self.script_dir = os.path.dirname(os.path.abspath(script_path)) if script_path else os.getcwd()
        self.rom_dir = rom_dir or ""
        self._max_steps = max_steps

        # 运行时组件
        self.runtime: Optional[WinCmdRuntime] = None
        self.vfs: Optional[VirtualFileSystem] = None

        # 脚本行
        self.lines: List[str] = []
        self.labels: Dict[str, int] = {}

        # call 栈
        self._call_stack: List[Tuple[int, int]] = []

    def _apply_redirection(self, result: CommandResult, redirect):
        """根据重定向配置，将 stdout/stderr 写入 VFS 文件。"""
        from .parser import ParsedRedirection
        if not isinstance(redirect, ParsedRedirection):
            return
        # stdout > file
        if redirect.stdout_redirect and result.stdout:
            content = '\n'.join(result.stdout)
            if redirect.stdout_append:
                existing = self.vfs.read_text(redirect.stdout_redirect) or ''
                self.vfs.write_text(redirect.stdout_redirect, existing + '\n' + content + '\n')
            else:
                self.vfs.write_text(redirect.stdout_redirect, content + '\n')
        # stderr > file
        if redirect.stderr_redirect and result.stderr:
            content = '\n'.join(result.stderr)
            self.vfs.write_text(redirect.stderr_redirect, content + '\n')



    def run(self, script_path: str = "", content: str = "",
            rom_dir: str = "") -> List[str]:
        """
        运行 BAT 脚本，返回捕获到的 fastboot/adb 命令列表。

        参数：
          script_path: 脚本文件路径
          content: 脚本内容（优先于文件读取）
          rom_dir: ROM 目录路径
        """
        if script_path:
            self.script_path = script_path
            self.script_dir = os.path.dirname(os.path.abspath(script_path))
        if content:
            pass
        elif script_path:
            try:
                with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                return []
        else:
            return []

        if not content:
            return []

        self.rom_dir = rom_dir or self.rom_dir
        self.lines = content.splitlines()
        self.runtime = WinCmdRuntime(script_path=self.script_path, rom_dir=self.rom_dir)
        self.runtime.max_steps = self._max_steps
        self.vfs = VirtualFileSystem(script_dir=self.script_dir, rom_dir=self.rom_dir,
                                      cwd=self.runtime.cwd)
        self.labels = self._scan_labels()
        self._call_stack = []

        # 执行
        start = self.labels.get("args_done", 0)
        if start > 0:
            start += 1
        self._exec_range(start, len(self.lines))

        return self.runtime.captured_commands

    def _scan_labels(self) -> Dict[str, int]:
        labels = {}
        for i, line in enumerate(self.lines):
            m = re.match(r'^\s*:([A-Za-z0-9_\-]+)', line)
            if m:
                labels[m.group(1).lower()] = i
        return labels

    # ----------------------------------------------------------
    # 执行核心
    # ----------------------------------------------------------

    def _exec_range(self, start: int, end: int, depth: int = 0):
        """执行行范围 [start, end)。"""
        if depth > 50:
            return  # 防止无限递归
        i = start
        while i < end:
            if not self.runtime.step():
                return

            raw = self.lines[i]
            line = raw.strip()
            lower = line.lower()

            if not line or line.startswith("::") or lower.startswith("rem "):
                i += 1
                continue

            # 标签：跳过函数体
            if line.startswith(":"):
                label = line[1:].strip().lower()
                if self._is_function_label(label):
                    i = self._find_after_exit_b(i + 1, end)
                    continue
                i += 1
                continue

            # exit /b
            if re.match(r'^exit\s*/b', lower):
                return
            # goto :eof
            if re.match(r'^goto\s*:eof', lower):
                return

            # goto
            m = re.match(r'^goto\s+:?([A-Za-z0-9_\-]+)', line, re.I)
            if m:
                target = m.group(1).lower()
                if target in self.labels:
                    i = self.labels[target] + 1
                    continue
                return

            # if block
            if lower.startswith("if "):
                i = self._handle_if(i, end)
                continue

            # for block
            if lower.startswith("for "):
                i = self._handle_for(i, end)
                continue

            # set（独立行，不在 if 内）
            if lower.startswith("set "):
                self._exec_line(line)
                i += 1
                continue

            # call :label args
            m = re.match(r'^call\s+:([A-Za-z0-9_\-]+)(.*)$', line, re.I)
            if m:
                self._call_label(m.group(1).lower(), m.group(2).strip(), i, end, depth)
                i += 1
                continue

            # 普通命令执行
            self._exec_line(line)
            i += 1

    def _exec_line(self, line: str):
        """执行单行 BAT 命令（非控制结构）。"""
        # 1. 变量展开
        resolved = self.runtime.resolve(line)

        # 2. cmd /c
        inner = is_cmd_c(resolved)
        if inner:
            self._exec_line(inner)
            return

        # 3. 检查管道
        left_cmd, right_cmd = split_pipe(resolved)
        if right_cmd:
            # 有管道：执行左命令，捕获 stdout，作为右命令的 stdin
            left_clean, left_redirect = parse_redirection(left_cmd)
            left_result = self._execute_command(left_clean)
            self.runtime.last_stdout = left_result.stdout
            self.runtime.set_errorlevel(left_result.errorlevel)
            self._apply_redirection(left_result, left_redirect)
            if left_result.is_fastboot:
                pass

            # 执行右命令（findstr 会从 last_stdout 读取）
            right_clean, right_redirect = parse_redirection(right_cmd)
            if right_clean:
                # 右命令也可能包含 &&/||/& 操作符
                right_parts = split_operators(right_clean)
                for right_op, right_subcmd in right_parts:
                    if right_op == '&&' and self.runtime.errorlevel != 0:
                        continue
                    if right_op == '||' and self.runtime.errorlevel == 0:
                        continue
                    if not right_subcmd:
                        continue
                    right_result = self._execute_command(right_subcmd)
                    self.runtime.last_stdout = right_result.stdout
                    self.runtime.set_errorlevel(right_result.errorlevel)
                    self._apply_redirection(right_result, right_redirect)
                    if right_result.is_fastboot:
                        pass
            return

        # 4. 解析重定向（先于操作符拆分，避免 2>&1 中的 & 被误分割）
        clean_cmd, redirect = parse_redirection(resolved)
        if not clean_cmd:
            return

        # 5. 操作符拆分（此时已无重定向符号）
        parts = split_operators(clean_cmd)
        for operator, command in parts:
            # 操作符条件判断
            if operator == '&&' and self.runtime.errorlevel != 0:
                continue
            if operator == '||' and self.runtime.errorlevel == 0:
                continue

            if not command:
                continue

            # 6. 执行命令
            result = self._execute_command(command)
            self.runtime.last_stdout = result.stdout
            self.runtime.set_errorlevel(result.errorlevel)
            self._apply_redirection(result, redirect)
            if result.is_fastboot:
                pass

    def _execute_command(self, command: str) -> CommandResult:
        """执行单条命令（内置或外部）。"""
        result = dispatch_builtin(self.runtime, self.vfs, command)
        if result is not None:
            return result
        return handle_external(self.runtime, self.vfs, command)

    # ----------------------------------------------------------
    # if / for / call / goto 控制结构（轻量版，复用旧 tracer 逻辑）
    # ----------------------------------------------------------

    def _handle_if(self, i: int, end: int) -> int:
        """处理 if 块。"""
        line = self.lines[i].strip()
        condition_true = self._eval_if_condition(line)
        true_end, else_start, else_end, after = self._find_if_blocks(i, end)

        if condition_true:
            if 'else' not in line and '(' not in line:
                # 单行 if (无括号无 else)：从条件行提取命令部分执行
                # 格式：if cond command
                cmd = self._extract_single_if_command(line)
                if cmd:
                    self._exec_line(cmd)
                return i + 1
            # 块级 if：执行 true 分支范围
            self._exec_range(i + 1, true_end, depth=self._call_depth())
            return else_end + 1 if else_end is not None else after
        else:
            if else_start is not None:
                self._exec_range(else_start, else_end, depth=self._call_depth())
            return after

    def _extract_single_if_command(self, line: str) -> str:
        """从单行 if cond command 中提取 command 部分。"""
        # 先展开变量
        resolved = self.runtime.resolve(line)
        lower = resolved.strip().lower()
        # 去掉 if [not] cond 前缀
        if lower.startswith('if not '):
            rest = resolved.strip()[7:]  # 去掉 "if not "
        else:
            rest = resolved.strip()[3:]  # 去掉 "if "

        # 跳过 cond 部分：支持常见的 if cond 格式
        # defined var / errorlevel code / exist path / "str"=="str" / /i "str"=="str" / !var! equ num
        cond_patterns = [
            r'^defined\s+(\S+)',        # defined var
            r'^errorlevel\s+(\d+)',      # errorlevel num
            r'^exist\s+(\S+)',           # exist path
            r'^/i\s+"[^"]*"\s*==\s*"[^"]*"',  # /i "str"=="str"
            r'^"[^"]*"\s*==\s*"[^"]*"',       # "str"=="str"
            r'^!?\w+!?\s+(equ|neq|gtr|lss|geq|leq)\s+\d+',  # !var! equ num
        ]
        for pat in cond_patterns:
            m = __import__('re').match(pat, rest, __import__('re').I)
            if m:
                cmd_start = m.end()
                cmd = rest[cmd_start:].strip()
                if cmd:
                    return cmd
                return ""
        # 兜底：如果 rest 包含多个空格分割的词，跳过第一个词（cond 关键词）和可能的路径
        parts = rest.split(None, 1)
        if len(parts) >= 2:
            return parts[1]
        return ""

    def _eval_if_condition(self, line: str) -> bool:
        """判断 if 条件是否成立。"""
        # 先展开变量（%VAR% / !VAR!）
        resolved = self.runtime.resolve(line)
        line = resolved
        lower = line.lower()

        # if not
        not_flag = lower.startswith("if not ")
        cond_part = line[3:].strip()  # 去掉 "if "
        if not_flag:
            cond_part = cond_part[4:].strip()  # 去掉 "not "

        cond_lower = cond_part.lower()

        # if defined var
        m = re.match(r'^defined\s+([A-Za-z0-9_]+)', cond_lower)
        if m:
            var = m.group(1)
            defined = var in self.runtime.env
            return not defined if not_flag else defined

        # if errorlevel code
        m = re.match(r'^errorlevel\s+(\d+)', cond_lower)
        if m:
            code = int(m.group(1))
            match = self.runtime.errorlevel >= code
            return not match if not_flag else match

        # if exist path
        m = re.match(r'^exist\s+(.+)', cond_lower)
        if m:
            path = m.group(1).strip()
            # 截断在 ( / ) / 空格之前（存在路径后的命令部分）
            for sep in ['(', ')']:
                if sep in path:
                    path = path.split(sep)[0]
            # 路径允许包含空格（带引号的路径），但不包含命令
            # 用正则提取第一个 token 或引号路径
            import re as _re
            qm = _re.match(r'^"([^"]+)"', path)
            if qm:
                path = qm.group(1)
            else:
                path = path.split(None, 1)[0] if ' ' in path else path
            path = path.strip().strip('"').strip("'")
            path = self.runtime.resolve(path)
            exists = self.vfs.exists(path)
            return not exists if not_flag else exists

        # if /i "str1"=="str2"
        m = re.match(r'^/i\s+"([^"]*)"\s*==\s*"([^"]*)"', cond_lower)
        if m:
            a = m.group(1).lower()
            b = m.group(2).lower()
            eq = (a == b)
            return not eq if not_flag else eq

        # if "str1"=="str2"
        m = re.match(r'^"([^"]*)"\s*==\s*"([^"]*)"', cond_lower)
        if m:
            a = m.group(1)
            b = m.group(2)
            eq = (a == b)
            return not eq if not_flag else eq

        # if var oper number (equ / neq / gtr / lss / geq / leq)
        m = re.match(
            r'^(!?[A-Za-z0-9_]+!?)\s+(equ|neq|gtr|lss|geq|leq)\s+(\d+)',
            cond_lower
        )
        if m:
            var_expr = m.group(1)
            op = m.group(2)
            num = int(m.group(3))
            var_val = self.runtime.resolve(var_expr)
            try:
                val = int(var_val)
            except ValueError:
                val = 0
            op_map = {
                'equ': val == num, 'neq': val != num,
                'gtr': val > num, 'lss': val < num,
                'geq': val >= num, 'leq': val <= num,
            }
            result = op_map.get(op, False)
            return not result if not_flag else result

        return not_flag  # 未知条件视为不成立

    def _find_if_blocks(self, i: int, end: int) -> Tuple[int, Optional[int], Optional[int], int]:
        """
        查找 BAT if/else 块边界（同 bat_execution_tracer 逻辑，已修复 else 误执行）。
        返回：(true_end, else_start, else_end, after)
        """
        true_start = i + 1
        depth = 1
        j = true_start

        while j < end:
            s = self.lines[j].strip()
            sl = s.lower()

            # top-level 的 `) else (` 必须拆成 true 结束 + else 开始
            if depth == 1 and re.match(r'^\)\s*else\b', sl):
                true_end = j
                else_start = j + 1
                else_end = self._find_block_end_from_else(else_start, end)
                return true_end, else_start, else_end, min(else_end + 1, end)

            depth += s.count('(') - s.count(')')
            if depth <= 0:
                true_end = j
                # 独立 else 行：下一行为 else 或 else (
                next_idx = j + 1
                if next_idx < end and self.lines[next_idx].strip().lower().startswith('else'):
                    else_line = self.lines[next_idx].strip().lower()
                    if '(' in else_line:
                        else_start = next_idx + 1
                    elif next_idx + 1 < end and self.lines[next_idx + 1].strip() == '(':
                        else_start = next_idx + 2
                    else:
                        else_start = next_idx + 1
                    else_end = self._find_block_end_from_else(else_start, end)
                    return true_end, else_start, else_end, min(else_end + 1, end)
                return true_end, None, None, j + 1
            j += 1

        return end, None, None, end

    def _find_block_end_from_else(self, start: int, end: int) -> int:
        depth = 1
        k = start
        while k < end:
            s = self.lines[k].strip()
            depth += s.count('(') - s.count(')')
            if depth <= 0:
                return k
            k += 1
        return end

    def _handle_for(self, i: int, end: int) -> int:
        """处理 for 块（简化版，只追踪循环体）。"""
        line = self.lines[i].strip()
        m = re.match(r'^for\s+%%([A-Za-z])\s+in\s+\((.*?)\)\s+do\s*\($', line, re.I)
        if not m:
            return i + 1
        var = m.group(1)
        source = m.group(2).strip()
        resolved = self.runtime.resolve(source)
        items = [x.strip().strip('"') for x in resolved.split() if x.strip()]

        # 找到循环体
        body_start = i + 1
        depth = 1
        k = body_start
        while k < end:
            s = self.lines[k].strip()
            depth += s.count('(') - s.count(')')
            if depth <= 0:
                body_end = k  # 不包含 k
                break
            k += 1
        else:
            return end

        # 对每个 item 执行循环体
        for item in items:
            if not self.runtime.step():
                break
            # 设置循环变量
            self.runtime.set_var(var, item)
            self._exec_range(body_start, body_end, depth=self._call_depth())

        return k + 1

    def _is_function_label(self, label: str) -> bool:
        if label not in self.labels:
            return False
        start = self.labels[label] + 1
        next_label = len(self.lines)
        for name, idx in self.labels.items():
            if idx > self.labels[label] and idx < next_label:
                next_label = idx
        # 检查该标签到下一个标签之间是否有 exit /b
        for j in range(start, next_label):
            if re.match(r'^\s*exit\s+/b', self.lines[j], re.I):
                return True
        return False

    def _find_after_exit_b(self, start: int, end: int) -> int:
        for j in range(start, end):
            if re.match(r'^\s*exit\s+/b', self.lines[j], re.I):
                return j
        return end

    def _call_label(self, label: str, args: str, return_i: int, end: int, depth: int):
        """模拟 call :label。"""
        if label not in self.labels:
            return
        # 保存 %1 %2 等位置参数
        old_pos = {}
        for k, v in list(self.runtime.env.items()):
            if re.match(r'^\d+$', k):
                old_pos[k] = v
        # 设置新位置参数
        arg_list = args.split()
        for idx, arg in enumerate(arg_list, 1):
            self.runtime.set_var(str(idx), arg)
        # 执行函数体
        func_start = self.labels[label] + 1
        func_end = self._find_after_exit_b(func_start, end)
        # 扩展执行范围到下一个标签或文件末尾
        next_label = end
        for name, idx in self.labels.items():
            if idx > self.labels[label] and idx < next_label:
                next_label = idx
        self._exec_range(func_start, next_label, depth=depth + 1)
        # 恢复位置参数
        for k in list(self.runtime.env.keys()):
            if re.match(r'^\d+$', k):
                if k in old_pos:
                    self.runtime.set_var(k, old_pos[k])
                else:
                    self.runtime.env.pop(k, None)

    def _call_depth(self) -> int:
        return len(self._call_stack)

    def cleanup(self):
        if self.vfs:
            self.vfs.cleanup()


__all__ = ["WinCmdSandbox"]