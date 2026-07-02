# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/bat_execution_tracer.py
"""
Hydra — BAT 轻量动态追踪器
===========================

不是完整 cmd.exe，而是面向刷机脚本的轻量执行追踪器。

目标：
  1. 不依赖 Windows / Wine
  2. 模拟 BAT 刷机脚本的核心控制流
  3. 捕获实际可能执行的 fastboot / adb 命令

支持第一版：
  - set VAR=value
  - %VAR% / !VAR! / %~1
  - call :label args
  - goto label
  - exit /b
  - for %%p in (...) do (...)
  - for /L %%i in (start,step,end) do (...)
  - for /f [options] %%var in (source) do (...) — 文件列表/dir /b/echo
  - if exist / if errorlevel / if "A"=="B"
  - fastboot / adb 捕获
"""

import os
import re
import shlex
import glob
from typing import Dict, List, Tuple, Optional

from .types import HydraStep
from .command_extractor import CommandExtractor


# ============================================================
# 阶段 14：Win CMD 轻量模拟层
# 操作符 / 重定向 / cmd /c / cd / pushd / popd
# ============================================================

_CMD_OPERATOR_PATTERN = re.compile(
    r'^(.*?)\s*(&&|\|\||&)\s*(.*)$', re.IGNORECASE
)

_REDIRECTION_PATTERN = re.compile(
    r'\s*(>>?|2>&1|1>nul|2>nul|>nul)\s*\S*', re.IGNORECASE
)

_CMD_C_PATTERN = re.compile(
    r'^cmd\s*(?:\.exe)?\s*(?:/c|/k)\s+(.+)$', re.IGNORECASE
)

_CMD_C_QUOTED_PATTERN = re.compile(
    r'^cmd\s*(?:\.exe)?\s*(?:/c|/k)\s+"(.+)"$', re.IGNORECASE
)

_CD_PATTERN = re.compile(
    r'^(cd|chdir)\s+(?:/d\s+)?(.+)$', re.IGNORECASE
)

_PUSHD_PATTERN = re.compile(
    r'^pushd\s+(.+)$', re.IGNORECASE
)

_POPD_PATTERN = re.compile(
    r'^popd\s*$', re.IGNORECASE
)


class BatExecutionTracer:
    """BAT 轻量动态追踪器"""

    def __init__(self, timeout_steps: int = 20000):
        self.timeout_steps = timeout_steps
        self.vars: Dict[str, str] = {}
        self.labels: Dict[str, int] = {}
        self.lines: List[str] = []
        self._root_lines: List[str] = []
        self.captured: List[str] = []
        self._steps_executed = 0
        self._call_depth = 0
        self._script_path = ""
        self._script_dir = ""
        self._rom_dir = ""
        self._pending_pc: Optional[int] = None
        self._cwd: str = ""            # 当前工作目录（cd/pushd/popd 可改变）
        self._dir_stack: List[str] = []  # pushd 堆栈

    # ----------------------------------------------------------
    # Public API
    # ----------------------------------------------------------

    def trace(self, script_path: str = "", content: str = "", rom_dir: str = "") -> List[HydraStep]:
        """追踪 BAT 脚本，返回 HydraStep 列表"""
        if script_path and not content:
            try:
                with open(script_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception:
                return []

        if not content:
            return []

        self._script_path = script_path or "script.bat"
        self._script_dir = os.path.dirname(os.path.abspath(self._script_path)) if script_path else os.getcwd()
        self._rom_dir = rom_dir or ""
        self.lines = content.splitlines()
        self._root_lines = list(self.lines)
        self.labels = self._scan_labels(self._root_lines)
        self.captured = []
        self._steps_executed = 0
        self._call_depth = 0
        self._pending_pc = None
        self._cwd = self._script_dir
        self._dir_stack = []

        self._init_vars()
        self._preload_set_vars()
        self._apply_profile()

        # 优先从 :args_done 后的初始化主逻辑执行；否则从开头执行
        start = self.labels.get("args_done", 0)
        if start > 0:
            start += 1
        self._exec_range(start, len(self.lines))

        return self._commands_to_steps(self.captured)

    # ----------------------------------------------------------
    # 初始化
    # ----------------------------------------------------------

    def _init_vars(self):
        self.vars = {
            "ERRORLEVEL": "0",
            "TEMP": "/tmp",
            "CD": self._script_dir,
            "DATE": "2026/07/01",
            "TIME": "00:00:00.00",
        }
        sp_abs = os.path.abspath(self._script_path)
        sp_dir = os.path.dirname(sp_abs)
        sp_name = os.path.basename(sp_abs)
        sp_base, sp_ext = os.path.splitext(sp_name)
        self.vars.update({
            "~dp0": sp_dir + os.sep,
            "~nx0": sp_name,
            "~n0": sp_base,
            "~x0": sp_ext,
            "~f0": sp_abs,
        })

    def _apply_profile(self):
        """刷机分析默认 profile"""
        self.vars["AUTO_FLASH"] = "1"
        self.vars["SKIP_CHECK"] = "0"     # 保留 devices 检测步骤
        self.vars["WIPE_DATA"] = "1"
        self.vars["NO_REBOOT"] = "0"
        self.vars.setdefault("FASTBOOT", "fastboot")
        self.vars.setdefault("ADB", "adb")
        self.vars.setdefault("IMG_DIR", "image")

    def _preload_set_vars(self):
        """预加载 set 变量，主要拿到 PARTITION_LIST_DEFAULT 等"""
        for line in self.lines:
            stripped = line.strip()
            if stripped.startswith(":parse_args"):
                break
            m = re.match(r'^set\s+"?([^=\"]+)=([^\"]*)"?$', stripped, re.I)
            if m:
                key = m.group(1).strip()
                # profile 控制变量不被脚本默认值覆盖
                if key.upper() in {"AUTO_FLASH", "SKIP_CHECK", "WIPE_DATA", "NO_REBOOT"}:
                    continue
                self.vars[key] = m.group(2).strip()
        # 常见默认变量展开
        for k in list(self.vars.keys()):
            self.vars[k] = self._resolve(self.vars[k])

    def _scan_labels(self, lines: List[str]) -> Dict[str, int]:
        labels = {}
        for i, line in enumerate(lines):
            m = re.match(r'^\s*:([A-Za-z0-9_\-]+)', line)
            if m:
                labels[m.group(1).lower()] = i
        return labels

    # ----------------------------------------------------------
    # 执行核心
    # ----------------------------------------------------------

    def _exec_range(self, start: int, end: int):
        i = start
        while i < end:
            if self._pending_pc is not None:
                i = self._pending_pc
                self._pending_pc = None
                if i < 0 or i >= len(self.lines):
                    return
                # 如果跳出了当前执行范围，直接把控制权交给全局主流程
                if i >= end:
                    end = len(self.lines)

            self._steps_executed += 1
            if self._steps_executed > self.timeout_steps:
                return

            raw = self.lines[i]
            line = raw.strip()
            lower = line.lower()

            if not line or line.startswith("::") or lower.startswith("rem "):
                i += 1
                continue

            # 遇到函数标签：主流程中跳过函数体
            if line.startswith(":"):
                label = line[1:].strip().lower()
                if self._is_function_label(label):
                    i = self._find_after_exit_b(i + 1, end)
                    continue
                i += 1
                continue

            # exit /b（函数内退出回到调用点；主流程中退出整个脚本）
            if re.match(r'^exit\s*/b', lower):
                return
            # goto :eof（跳到脚本末尾或函数末尾）
            if re.match(r'^goto\s*:eof', lower):
                return

            # goto
            m = re.match(r'^goto\s+:?([A-Za-z0-9_\-]+)', line, re.I)
            if m:
                target = m.group(1).lower()
                if target in self.labels:
                    # 记录跳转目标；如果在 if/for 子块中，也能带回主循环
                    self._pending_pc = self.labels[target] + 1
                    continue
                return

            # set
            if lower.startswith("set "):
                self._handle_set(line)
                i += 1
                continue

            # call :label args
            m = re.match(r'^call\s+:([A-Za-z0-9_\-]+)(.*)$', line, re.I)
            if m:
                self._call_label(m.group(1).lower(), m.group(2).strip())
                i += 1
                continue

            # if block
            if lower.startswith("if "):
                i = self._handle_if(i, end)
                continue

            # for block
            if lower.startswith("for "):
                i = self._handle_for(i, end)
                continue

            # 捕获命令
            self._exec_single_line(line)
            i += 1

    def _is_function_label(self, label: str) -> bool:
        """有 exit /b 的标签视为函数标签"""
        if label not in self.labels:
            return False
        start = self.labels[label] + 1
        next_label = len(self.lines)
        for name, idx in self.labels.items():
            if idx > self.labels[label]:
                next_label = min(next_label, idx)
        for j in range(start, next_label):
            if j < len(self._root_lines) and re.search(r'exit\s*/b', self._root_lines[j], re.I):
                return True
        return False

    def _find_after_exit_b(self, start: int, end: int) -> int:
        for j in range(start, end):
            if re.search(r'exit\s*/b', self.lines[j], re.I):
                return j + 1
            if self.lines[j].strip().startswith(":"):
                return j
        return end

    # ----------------------------------------------------------
    # 语句处理
    # ----------------------------------------------------------

    def _handle_set(self, line: str):
        m = re.match(r'^set\s+"?([^=\"]+)=([^\"]*)"?$', line, re.I)
        if not m:
            return
        key = m.group(1).strip()
        val = self._resolve(m.group(2).strip())
        # profile 控制变量不被脚本默认值覆盖
        if key.upper() in {"AUTO_FLASH", "SKIP_CHECK", "WIPE_DATA", "NO_REBOOT"}:
            return
        self.vars[key] = val

    def _call_label(self, label: str, args: str):
        if self._call_depth > 20:
            return
        if label not in self.labels:
            return
        # 备份当前位置参数和函数标签内定义的变量
        old_pos = {str(i): self.vars.get(str(i), "") for i in range(1, 10)}
        old_saved = {}
        for k in list(self.vars.keys()):
            if k.startswith("saved_"):
                old_saved[k] = self.vars[k]
        try:
            parts = shlex.split(self._resolve(args), posix=False) if args else []
        except Exception:
            parts = self._resolve(args).split() if args else []
        for idx, arg in enumerate(parts[:9]):
            self.vars[str(idx + 1)] = arg.strip('"')
            # 同时设置带修饰符的版本：%~1, %~dp1, %~n1, %~x1, %~nx1, %~f1
            for mod in ('~dp', '~nx', '~n', '~x', '~f', '~'):
                self.vars[mod + str(idx + 1)] = arg.strip('"')
        self._call_depth += 1
        start = self.labels[label] + 1
        end = self._find_label_end_root(start)
        # 保存函数体内定义的新变量，以便传出
        vars_before = set(self.vars.keys())
        block_lines = self._root_lines[start:end]
        saved = self.lines
        self.lines = block_lines
        self._exec_range(0, len(block_lines))
        self.lines = saved
        self._call_depth -= 1
        # 恢复位置参数
        for k, v in old_pos.items():
            if v:
                self.vars[k] = v
            elif k in self.vars:
                del self.vars[k]
        # 保留函数体内新定义的变量（副作用传递）
        for k in list(self.vars.keys()):
            if k not in vars_before and not k.startswith("saved_"):
                pass  # 保留新变量
        # 清理修饰符变量
        for i in range(1, 10):
            for mod in ('~dp', '~nx', '~n', '~x', '~f', '~'):
                key = mod + str(i)
                if key in self.vars and key not in vars_before:
                    del self.vars[key]

    def _find_label_end(self, start: int) -> int:
        for j in range(start, len(self.lines)):
            if j > start and self.lines[j].strip().startswith(":"):
                return j
        return len(self.lines)

    def _find_label_end_root(self, start: int) -> int:
        for j in range(start, len(self._root_lines)):
            if j > start and self._root_lines[j].strip().startswith(":"):
                return j
        return len(self._root_lines)

    def _handle_if(self, i: int, end: int) -> int:
        line = self.lines[i].strip()
        cond_true = self._eval_if_condition(line)

        # block if：if xxx (
        if line.endswith("("):
            true_start = i + 1
            true_end, else_start, else_end, after = self._find_if_blocks(i, end)
            if cond_true:
                self._exec_range(true_start, true_end)
            elif else_start is not None:
                self._exec_range(else_start, else_end)
            return after

        # 单行 if xxx command — 提取条件后的命令并执行
        if cond_true:
            # 提取 if 条件后的命令：匹配 ) 后或条件末尾后的内容
            m = re.search(r'\)\s*(.+)$', line)
            if not m:
                # 尝试解析无括号单行 if：if cond command
                m = re.match(
                    r'^if\s+(?:/i\s+)?(?:not\s+)?(?:(?:errorlevel|defined|exist)\s+\S+|'
                    r'"[^"]*"\s*==\s*"[^"]*"|'
                    r'\S+\s+(?:equ|neq|gtr|lss|geq|leq)\s+\S+)\s+(.+)$',
                    line, re.I
                )
            if m:
                cmd = m.group(1).strip()
                # 单行命令可能是 set / goto / call / fastboot 等
                if cmd.lower().startswith("set "):
                    self._handle_set(cmd)
                elif re.match(r'^goto\s', cmd, re.I):
                    m_goto = re.match(r'^goto\s+:?([A-Za-z0-9_\-]+)', cmd, re.I)
                    if m_goto and m_goto.group(1).lower() in self.labels:
                        self._pending_pc = self.labels[m_goto.group(1).lower()] + 1
                elif re.match(r'^call\s+:', cmd, re.I):
                    m_call = re.match(r'^call\s+:(\w+)(.*)', cmd, re.I)
                    if m_call:
                        self._call_label(m_call.group(1).lower(), m_call.group(2).strip())
                else:
                    self._capture_if_fastboot(cmd)
        return i + 1

    # ============================================================
# 阶段 10B-2、10B-3、10C 增强（2026-07-01）
# ============================================================

    def _eval_if_condition(self, line: str) -> bool:
        text = self._resolve(line)
        lower = text.lower()
        # if errorlevel 1：假设 fastboot 成功，不进入错误分支
        if re.match(r'^if\s+errorlevel\s+\d+', lower):
            return False
        # if exist / if not exist — 基于真实路径判断
        m_exist = re.match(r'^if\s+(not\s+)?exist\s+(.+?)\s*\(?$', lower)
        if m_exist:
            negate = bool(m_exist.group(1))
            raw_path = m_exist.group(2).strip().strip('"').strip("'")
            raw_path = self._resolve(raw_path)
            # 转换路径分隔符
            raw_path = raw_path.replace("\\\\", "/").replace("\\", "/")
            full_path = raw_path
            if not os.path.isabs(full_path):
                # 优先脚本目录，其次 rom_dir
                if self._script_dir:
                    full_path = os.path.join(self._script_dir, raw_path)
                elif self._rom_dir:
                    full_path = os.path.join(self._rom_dir, raw_path)
                else:
                    full_path = raw_path
            # 如果还不存在，尝试 rom_dir
            if not os.path.exists(full_path) and not ('*' in full_path or '?' in full_path) and self._rom_dir:
                alt = os.path.join(self._rom_dir, os.path.basename(raw_path))
                if os.path.exists(alt):
                    full_path = alt
            # glob 判断（如 *.img 或 *）
            if '*' in full_path or '?' in full_path:
                exists = len(glob.glob(full_path)) > 0
            else:
                exists = os.path.exists(full_path)
            # 兜底：如果路径明显不存在且无法判断（测试环境无真实文件），假设存在
            # 避免因无 rom 目录导致步骤大量丢失
            if not exists and not os.path.isabs(raw_path) and not self._rom_dir:
                # 判断路径是否看起来像真实的脚本内路径（含变量扩展或 ~dp0）
                if '%' in raw_path or '~dp0' in raw_path or '~f0' in raw_path:
                    exists = True
                elif not os.path.exists(full_path) and not os.path.exists(os.path.join(self._script_dir, raw_path)):
                    # 路径看起来像"镜像文件路径"但实际不存在：假设存在（避免丢失步骤）
                    exists = True
            return not exists if negate else exists
        # if defined / if not defined（BAT 变量名大小写不敏感）
        m_def = re.match(r'^if\s+(not\s+)?defined\s+(\S+)\s*\(?$', text, re.I)
        if m_def:
            negate = bool(m_def.group(1))
            var_name = m_def.group(2).strip()
            defined = any(k.lower() == var_name.lower() and v != "" for k, v in self.vars.items())
            return not defined if negate else defined
        # if "A"=="B" (字符串相等)
        m = re.match(r'^if\s+"?([^"=]+)"?=="?([^"(]+)"?', text, re.I)
        if m:
            return m.group(1).strip() == m.group(2).strip()
        # if !var! equ/neq number (数字比较)
        m_num = re.match(r'^if\s+(\S+)\s+(equ|neq|gtr|lss|geq|leq)\s+(\S+)\s*\(?$', lower)
        if m_num:
            lhs = self._resolve(m_num.group(1))
            rhs = self._resolve(m_num.group(3))
            op = m_num.group(2)
            try:
                lhs_val = int(lhs)
                rhs_val = int(rhs)
                if op == 'equ': return lhs_val == rhs_val
                if op == 'neq': return lhs_val != rhs_val
                if op == 'gtr': return lhs_val > rhs_val
                if op == 'lss': return lhs_val < rhs_val
                if op == 'geq': return lhs_val >= rhs_val
                if op == 'leq': return lhs_val <= rhs_val
                return True
            except ValueError:
                return op in ('equ', 'geq', 'leq')  # 无法解析时默认相等类成立
        # if /i "A"=="B" (大小写不敏感)
        m_i = re.match(r'^if\s+/i\s+"([^"]*)"\s*==\s*"([^"]*)"', text, re.I)
        if m_i:
            return m_i.group(1).lower() == m_i.group(2).lower()
        return True

    def _find_if_blocks(self, i: int, end: int) -> Tuple[int, Optional[int], Optional[int], int]:
        """
        查找 BAT if/else 块边界。

        支持：
          if cond (
            ...
          ) else (
            ...
          )

          if cond (
            ...
          )
          else (
            ...
          )

        返回：(true_end, else_start, else_end, after)
        true_end/else_end 都是不包含结束括号行的执行边界。
        """
        true_start = i + 1
        depth = 1
        j = true_start

        while j < end:
            s = self.lines[j].strip()
            sl = s.lower()

            # top-level 的 `) else (` 必须拆成 true 结束 + else 开始，不能用净括号数抵消
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
                    # else (：else 体从下一行开始；else 后单独一行 `(` 也兼容
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
        """从 else 体第一行开始查找结束括号行，返回不包含该括号的 end 索引。"""
        depth = 1
        k = start
        while k < end:
            s = self.lines[k].strip()
            depth += s.count('(') - s.count(')')
            if depth <= 0:
                return k
            k += 1
        return end

    # ============================================================
    # 阶段 14：Win CMD 模拟 — 单行命令执行
    # ============================================================

    def _exec_single_line(self, line: str):
        """
        执行一条普通命令行（非 if/for/goto/call/set 等控制结构）。

        处理顺序：
          1. cd / pushd / popd
          2. cmd /c
          3. 拆分 & / && / || 操作符
          4. 剥离重定向
          5. 捕获 fastboot/adb
        """
        # 1. cd / chdir
        m_cd = _CD_PATTERN.match(line)
        if m_cd:
            self._handle_cd(m_cd.group(2))
            return

        # 2. pushd
        m_pushd = _PUSHD_PATTERN.match(line)
        if m_pushd:
            self._handle_pushd(m_pushd.group(1))
            return

        # 3. popd
        if _POPD_PATTERN.match(line):
            self._handle_popd()
            return

        # 4. cmd /c
        m_cmd = _CMD_C_QUOTED_PATTERN.match(line)
        if m_cmd:
            inner = m_cmd.group(1)
            self._exec_single_line(inner)
            return
        m_cmd2 = _CMD_C_PATTERN.match(line)
        if m_cmd2:
            inner = m_cmd2.group(1)
            self._exec_single_line(inner)
            return

        # 5. 拆分 && / || / &
        parts = self._split_cmd_operators(line)
        for operator, command in parts:
            resolved = self._resolve(command).strip()
            cleaned = self._strip_redirection(resolved)
            if cleaned:
                if operator == '||' and self.vars.get('ERRORLEVEL', '0') == '0':
                    continue  # 上一条成功，|| 不执行
                self._capture_if_fastboot(cleaned)

    def _split_cmd_operators(self, line: str) -> List[Tuple[Optional[str], str]]:
        """
        将包含 & / && / || 的行拆分成 [(operator, command)]。

        返回的 operator 可能是 None（第一个命令）、'&&'、'||'、'&'。
        举例：
          "fastboot devices && fastboot reboot" ->
          [(None, "fastboot devices"), ("&&", "fastboot reboot")]
        """
        result: List[Tuple[Optional[str], str]] = []
        # 按 &&、||、& 分割（注意：&& 和 || 优先级高于 &）
        pattern = re.compile(r'\s*(&&|\|\||&)\s*')
        parts = pattern.split(line)
        first = True
        for i in range(0, len(parts), 2):
            cmd = parts[i].strip()
            op = None
            if not first and i > 0:
                op = parts[i - 1].strip()
            if cmd:
                result.append((op, cmd))
            first = False
        return result

    def _strip_redirection(self, command: str) -> str:
        """移除重定向部分，返回纯命令文本。"""
        result = command
        # 移除 >> file 或 > file（含路径）
        result = re.sub(r'\s*(>>?)\s*\S+', '', result)
        # 移除 2>&1
        result = re.sub(r'\s*2>&1\s*', '', result, flags=re.IGNORECASE)
        # 移除 1>nul、2>nul、>nul
        result = re.sub(r'\s*(?:[12]?>)?nul\s*', '', result, flags=re.IGNORECASE)
        # 清除残留的 > 或 >>（如只剩下的 "2>"）
        result = re.sub(r'\s*[12]?>[>&]?\s*', '', result)
        return result.strip()

    def _handle_cd(self, target: str):
        """模拟 cd / chdir。"""
        target = self._resolve(target).strip().strip('"').strip("'")
        target = target.replace('\\\\', '/').replace('\\', '/')
        # 以 _script_dir 为基准
        if not os.path.isabs(target):
            target = os.path.join(self._script_dir, target)
        if os.path.isdir(target):
            self._cwd = target
            # 更新 %CD%
            self.vars['CD'] = target
            self.vars['__CD__'] = target

    def _handle_pushd(self, target: str):
        """模拟 pushd。"""
        target = self._resolve(target).strip().strip('"').strip("'")
        target = target.replace('\\\\', '/').replace('\\', '/')
        if not os.path.isabs(target):
            target = os.path.join(self._script_dir, target)
        self._dir_stack.append(self._cwd)
        if os.path.isdir(target):
            self._cwd = target
            self.vars['CD'] = target

    def _handle_popd(self):
        """模拟 popd。"""
        if self._dir_stack:
            self._cwd = self._dir_stack.pop()
            self.vars['CD'] = self._cwd

    def _handle_for(self, i: int, end: int) -> int:
        line = self.lines[i].strip()
        # 支持：for %%p in (...) do (
        m = re.match(r'^for\s+%%([A-Za-z])\s+in\s+\((.*?)\)\s+do\s*\($', line, re.I)
        if not m:
            # 支持：for /L %%i in (start,step,end) do (
            mL = re.match(r'^for\s+/L\s+%%([A-Za-z])\s+in\s+\((\d+),(\d+),(\d+)\)\s+do\s*\($', line, re.I)
            if mL:
                var = mL.group(1)
                start = int(mL.group(2))
                step = int(mL.group(3))
                stop = int(mL.group(4))
                items = []
                val = start
                if step > 0:
                    while val <= stop:
                        items.append(str(val))
                        val += step
                else:
                    while val >= stop:
                        items.append(str(val))
                        val += step
                block_start = i + 1
                block_end = self._find_block_end(i, end)
                old = self.vars.get(var, "")
                for item in items:
                    self.vars[var] = item
                    block_lines = [self._replace_for_var(x, var, item) for x in self.lines[block_start:block_end]]
                    saved = self.lines
                    self.lines = block_lines
                    self._exec_range(0, len(block_lines))
                    self.lines = saved
                if old:
                    self.vars[var] = old
                elif var in self.vars:
                    del self.vars[var]
                return block_end + 1

            # 支持：for /f [options] %%var in (source) do (
            # options 可省略，例如：for /f %%p in (parts.txt) do (
            mF = re.match(
                r'^for\s+/f(?:\s+("[^"]*"|\S+))?\s+%%([A-Za-z])\s+in\s+\((.+?)\)\s+do\s*\($',
                line, re.I
            )
            if mF:
                return self._handle_for_f(mF, i, end)

            # 单行 for /f: for /f [options] %%var in (source) do command
            mF2 = re.match(
                r'^for\s+/f(?:\s+("[^"]*"|\S+))?\s+%%([A-Za-z])\s+in\s+\((.+?)\)\s+do\s+(.+)$',
                line, re.I
            )
            if mF2:
                return self._handle_for_f_single(mF2, i, end)

            # 不支持的 for 格式：跳过整个块，不捕获模板命令
            block_end = self._find_block_end(i, end)
            return block_end + 1
        var = m.group(1)
        raw_items = m.group(2).strip()
        items = self._resolve_for_plain_items(raw_items)
        if not items:
            block_end = self._find_block_end(i, end)
            return block_end + 1
        block_start = i + 1
        block_end = self._find_block_end(i, end)
        old = self.vars.get(var, "")
        for item in items:
            self.vars[var] = item
            block_lines = [self._replace_for_var(x, var, item) for x in self.lines[block_start:block_end]]
            # 处理变量修饰符 %%~nvar, %%~fvar 等
            block_lines = [self._replace_for_f_modifiers(x, var, item) for x in block_lines]
            saved = self.lines
            self.lines = block_lines
            self._exec_range(0, len(block_lines))
            self.lines = saved
        if old:
            self.vars[var] = old
        elif var in self.vars:
            del self.vars[var]
        return block_end + 1

    def _resolve_for_plain_items(self, raw: str) -> List[str]:
        """
        解析普通 for %%var in (items) 的数据源，支持 glob 和引号。

        例如：
        ("%%IMG_DIR%%/*.img")  → glob 展开实际文件
        (boot vendor dtbo)   → 原样列表
        """
        raw = raw.strip().strip('"')
        resolved = self._resolve(raw)
        # 转换路径分隔符
        resolved = resolved.replace("\\\\", "/").replace("\\", "/")
        # 尝试 glob 展开
        full_glob = resolved
        if not os.path.isabs(full_glob):
            full_glob = os.path.join(self._script_dir, resolved)
        matched = glob.glob(full_glob)
        if matched:
            return sorted(matched)
        # glob 未匹配时 fallback 到 split，但限制最大展开数量避免爆炸
        items = resolved.split() if resolved else []
        MAX_FOR_ITEMS = 200
        if len(items) > MAX_FOR_ITEMS:
            items = items[:MAX_FOR_ITEMS]
        return items

    def _handle_for_f(self, m, i: int, end: int) -> int:
        """处理 for /f block: for /f "options" %%var in (source) do (...)"""
        options = m.group(1).strip('"') if m.group(1) else ""
        var = m.group(2)
        source = m.group(3).strip()

        items = self._resolve_for_f_source(source, options, var)

        if not items:
            # 无法展开：安全跳过块体，不捕获模板命令
            block_end = self._find_block_end(i, end)
            return block_end + 1

        block_start = i + 1
        block_end = self._find_block_end(i, end)
        old = self.vars.get(var, "")
        for item in items:
            self.vars[var] = item
            block_lines = [self._replace_for_var(x, var, item) for x in self.lines[block_start:block_end]]
            # 同时处理 %%~nvar 形式（取文件名部分）
            block_lines = [self._replace_for_f_modifiers(x, var, item) for x in block_lines]
            saved = self.lines
            self.lines = block_lines
            self._exec_range(0, len(block_lines))
            self.lines = saved
        if old:
            self.vars[var] = old
        elif var in self.vars:
            del self.vars[var]
        return block_end + 1

    def _handle_for_f_single(self, m, i: int, end: int) -> int:
        """处理单行 for /f: for /f "options" %%var in (source) do command"""
        options = m.group(1).strip('"') if m.group(1) else ""
        var = m.group(2)
        source = m.group(3).strip()
        command = m.group(4).strip()

        items = self._resolve_for_f_source(source, options, var)
        if not items:
            return i + 1

        old = self.vars.get(var, "")
        for item in items:
            self.vars[var] = item
            cmd = self._replace_for_var(command, var, item)
            cmd = self._replace_for_f_modifiers(cmd, var, item)
            self._capture_if_fastboot(cmd)
        if old:
            self.vars[var] = old
        elif var in self.vars:
            del self.vars[var]
        return i + 1

    def _resolve_for_f_source(self, source: str, options: str, var: str) -> List[str]:
        """
        解析 for /f 的数据源，返回值列表。

        支持的数据源：
        - 文件列表: (file1 file2 ...) 或 (file.txt)
        - 命令输出: ('command') — 仅支持 dir /b 和简单 echo
        - 字符串: ("str")
        """
        source = source.strip().strip('"')

        # 命令输出: 'command'
        if source.startswith("'") and source.endswith("'"):
            cmd = source[1:-1].strip()
            return self._exec_for_f_command(cmd, options, var)

        # 字符串字面量: "str"
        if source.startswith('"') and source.endswith('"'):
            text = source[1:-1]
            return text.split() if text else []

        # 括号包裹的文件列表: file1 file2
        # 或单个文件名: parts.txt
        files = source.split()
        items: List[str] = []

        for f in files:
            f = self._resolve(f).strip().strip('"')
            # 尝试作为文件路径读取
            full_path = f
            if not os.path.isabs(full_path):
                full_path = os.path.join(self._script_dir, f)

            if os.path.isfile(full_path):
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as fh:
                        for file_line in fh:
                            file_line = file_line.strip()
                            if file_line and not file_line.startswith("#") and not file_line.startswith("::"):
                                # for /f 默认按空格分 token，取第一个 token
                                tokens = file_line.split()
                                if tokens:
                                    items.append(tokens[0])
                except Exception:
                    pass
            else:
                # 文件不存在时，如果看起来像文件名（含扩展名），不添加为值
                # 如果不像文件名（比如纯词），可能就是值列表
                if "." not in os.path.basename(f):
                    items.append(f)

        return items

    def _exec_for_f_command(self, cmd: str, options: str, var: str) -> List[str]:
        """
        模拟 for /f 中命令的输出。

        仅支持:
        - dir /b pattern
        - echo text
        """
        cmd = self._resolve(cmd).strip()
        lower = cmd.lower()

        # dir /b <pattern>
        m_dir = re.match(r'^dir\s+/b\s+(.+)$', lower)
        if m_dir:
            pattern = self._resolve(m_dir.group(1)).strip().strip('"')
            # 转换 Windows 路径分隔符
            pattern = pattern.replace("\\\\", "/").replace("\\", "/")
            full_pattern = pattern
            if not os.path.isabs(full_pattern):
                full_pattern = os.path.join(self._script_dir, pattern)
            try:
                matched = glob.glob(full_pattern)
                result = []
                for f in sorted(matched):
                    result.append(os.path.basename(f))
                return result
            except Exception:
                return []

        # 简单 echo
        m_echo = re.match(r'^echo\s+(.+)$', lower)
        if m_echo:
            return m_echo.group(1).split()

        # 不支持的命令（powershell, cmd /c 等）：返回空列表，安全跳过
        return []

    def _replace_for_f_modifiers(self, line: str, var: str, val: str) -> str:
        """
        替换 for /f 的变量修饰符: %%~nvar, %%~xvar, %%~fvar, %%~nxvar 等。

        仅处理常见修饰符:
        - %%~nVAR → 文件名部分（不含扩展名）
        - %%~xVAR → 扩展名
        - %%~nxVAR → 文件名.扩展名
        - %%~fVAR → 完整路径
        - %%~pVAR → 路径
        - %%~dVAR → 驱动器
        """
        def repl(m):
            modifiers = m.group(1).lower()
            raw_var = m.group(2)
            if raw_var.lower() != var.lower():
                return m.group(0)

            base = val
            if 'f' in modifiers:
                full_path = base
                if not os.path.isabs(full_path):
                    full_path = os.path.join(self._script_dir, base)
                base = os.path.abspath(full_path)
            if 'd' in modifiers:
                drive = os.path.splitdrive(base)
                base = drive[0] if drive[0] else ""
            if 'p' in modifiers:
                base = os.path.dirname(base) + os.sep
            if 'n' in modifiers and 'x' not in modifiers:
                base = os.path.splitext(os.path.basename(base))[0]
            if 'x' in modifiers and 'n' not in modifiers:
                base = os.path.splitext(base)[1]
            if 'n' in modifiers and 'x' in modifiers:
                base = os.path.basename(base)
            return base

        # 匹配 %%~modifiersVAR
        return re.sub(r'%%(~[a-zA-Z]*)([A-Za-z])', repl, line)

    def _find_block_end(self, i: int, end: int) -> int:
        depth = 0
        for j in range(i, end):
            s = self.lines[j].strip()
            depth += s.count('(') - s.count(')')
            if depth <= 0 and j > i:
                return j
        return end - 1

    def _replace_for_var(self, line: str, var: str, val: str) -> str:
        return re.sub(rf'%%{re.escape(var)}(?=[^%]|$)', val, line, flags=re.I)

    # ----------------------------------------------------------
    # 变量与捕获
    # ----------------------------------------------------------

    def _resolve(self, text: str) -> str:
        if text is None:
            return ""
        result = text
        # %~1 等位置参数
        def pos_repl(m):
            key = m.group(1)
            if key.startswith('~'):
                key = key[1:]
            return self.vars.get(key, m.group(0)).strip('"')
        result = re.sub(r'%((?:~)?[1-9])', pos_repl, result)
        # %~dp0, %~nx0, %~n0, %~x0, %~f0 等路径修饰符（单百分号前缀，非 %VAR% 形式）
        # 使用 vars 中预存的 "~dp0"、 "~nx0" 等键值展开
        result = re.sub(r'%~dp0', lambda m: self.vars.get('~dp0', ''), result, flags=re.I)
        result = re.sub(r'%~nx0', lambda m: self.vars.get('~nx0', ''), result, flags=re.I)
        result = re.sub(r'%~n0', lambda m: self.vars.get('~n0', ''), result, flags=re.I)
        result = re.sub(r'%~x0', lambda m: self.vars.get('~x0', ''), result, flags=re.I)
        result = re.sub(r'%~f0', lambda m: self.vars.get('~f0', ''), result, flags=re.I)
        # %CD% 等特殊变量展开
        for _ in range(10):
            prev = result
            result = re.sub(r'%([^%]+)%', lambda m: self.vars.get(m.group(1), m.group(0)), result)
            result = re.sub(r'!([^!]+)!', lambda m: self.vars.get(m.group(1), m.group(0)), result)
            if result == prev:
                break
        return result

    def _capture_if_fastboot(self, line: str):
        resolved = self._resolve(line).strip()
        if not resolved:
            return
        lower = resolved.lower()
        if 'fastboot' in lower or re.search(r'\badb\b', lower):
            self.captured.append(resolved)
            self.vars['ERRORLEVEL'] = '0'

    def _commands_to_steps(self, commands: List[str]) -> List[HydraStep]:
        extractor = CommandExtractor()
        steps = extractor.extract_from_lines(commands)
        for s in steps:
            s.dynamic = True
        return steps


__all__ = ["BatExecutionTracer"]