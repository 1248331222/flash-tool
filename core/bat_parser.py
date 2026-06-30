# -*- coding: utf-8 -*-
# flash_tool/core/bat_parser.py
"""
core/bat_parser.py — BAT 脚本解析引擎
从单文件版提取，函数逻辑保持不变。

fastboot 命令解析与风险定级（parse_fastboot_tail / parse_fastboot_command /
_assess_risk）已拆分至 core/fastboot_cmd_parser.py，此处通过 import 重新导出，
parse_bat_script 运行时仍可正常调用。
"""

import os
import re
import glob
import fnmatch
import shlex
from typing import List, Dict, Optional, Tuple

from config import DANGEROUS_PARTITIONS, logger


# ======================================================================
# 模块: utils/bat_parser.py
# ======================================================================


def parse_bat_script(content: str, rom_dir: str = '', script_path: str = '') -> Tuple[List[Dict], List[str]]:
    """
    v3.0.7: BAT 脚本解析引擎 v3 — 基于变量展开后语义判断
    先做完整变量展开，再判断语法复杂度，支持更多 BAT 语法：
    - for /L 数值循环、for /F 文件读取、for 列表/通配符
    - if exist、if 比较（equ/==/neq等）、if 恒真/恒假
    - call :label 同文件子程序内联
    - %~dp0 等路径修饰符、%var:old=new% 字符串替换、%var:~start,len% 切片
    返回 (steps, missing_files)
    """
    steps = []
    missing_files = []

    # ===== 预处理 =====
    lines = content.replace('^\n', ' ').replace('^\r\n', ' ').splitlines()
    lines = [line.strip() for line in lines if line.strip() and not line.strip().startswith('::')]
    lines = [line for line in lines if not re.match(r'^@?echo\s+(on|off)\b', line, re.IGNORECASE)]

    # 变量预扫描
    variables = {}
    for line in lines:
        m = re.match(r'^set\s+"?(\w+)=(.*?)"?$', line, re.IGNORECASE)
        if m:
            variables[m.group(1).upper()] = m.group(2)

    def resolve(text: str) -> str:
        """高级变量展开：%var%、!var!、%var:old=new%、%var:~s,l%、%~dp0"""
        # 1. 路径修饰符 %~dp0 等
        if script_path:
            sp_abs = os.path.abspath(script_path)
            sp_dir = os.path.dirname(sp_abs)
            sp_name = os.path.basename(sp_abs)
            sp_base, sp_ext = os.path.splitext(sp_name)
            for mod, val in [('~dp0', sp_dir + os.sep), ('~n0', sp_base),
                             ('~x0', sp_ext), ('~nx0', sp_name), ('~s0', sp_abs),
                             ('~p0', sp_dir + os.sep), ('~f0', sp_name)]:
                text = text.replace('%' + mod, val)
        # 2. 多轮基础展开 %var% 和 !var!
        for _ in range(10):
            prev = text
            text = re.sub(r'!(\w+)!', lambda m: variables.get(m.group(1).upper(), m.group(0)), text)
            text = re.sub(r'%(\w+)%', lambda m: variables.get(m.group(1).upper(), m.group(0)), text)
            if text == prev:
                break
        # 3. 字符串替换 %var:old=new%
        def _repl_sub(m):
            vn = m.group(1).upper()
            old = m.group(2)
            new = m.group(3)
            val = variables.get(vn, m.group(0))
            return val.replace(old, new)
        text = re.sub(r'%(\w+):([^=]+)=(.+?)%', _repl_sub, text)
        # 4. 字符串切片 %var:~start,length%
        def _slice_sub(m):
            vn = m.group(1).upper()
            s = int(m.group(2))
            l = m.group(3)
            val = variables.get(vn, m.group(0))
            return val[s:s + int(l)] if l else val[s:]
        text = re.sub(r'%(\w+):~(\d+),(\d+)?%', _slice_sub, text)
        return text

    def _parse_fastboot_line(line: str, raw_line: str) -> Optional[Dict]:
        resolved = resolve(line)
        return parse_fastboot_tail(resolved, raw_line)

    def collect_block_v2(lines_list: list, start_idx: int) -> tuple:
        """引号-aware 的括号块收集"""
        depth = 1
        j = start_idx
        block = []
        while j < len(lines_list) and depth > 0:
            bline = lines_list[j]
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
                if close_pos > 0:
                    prefix = bline[:close_pos].strip()
                    if prefix:
                        block.append(prefix)
                break
            block.append(bline)
            j += 1
        return block, j

    def expand_for_loop(line: str, idx: int) -> tuple:
        """展开 for 循环（/L、/F 文件、普通列表/通配符）"""
        mf = []
        block, end_i = collect_block_v2(lines, idx + 1)
        expanded = []
        # for /L 数值循环
        ml = re.match(r'^for\s+/L\s+%%(\w+)\s+in\s*\((\d+),(\d+),(\d+)\)\s*do\s*\(', line, re.I)
        if ml:
            lv = '%%' + ml.group(1)
            start, step, end = int(ml.group(2)), int(ml.group(3)), int(ml.group(4))
            if step == 0:
                vals = [start]
            elif step > 0:
                vals = list(range(start, end + 1, step))
            else:
                vals = list(range(start, end - 1, step))
            for val in vals:
                for bline in block:
                    expanded.append(bline.replace(lv, str(val)))
            return expanded, end_i, mf
        # for /F 读取文件（非命令输出）
        mf2 = re.match(r'^for\s+/F\s+(?:["\'][^"\']*["\']\s+)?%%(\w+)\s+in\s*\(([^)]+)\)\s*do\s*\(', line, re.I)
        if mf2:
            lv = '%%' + mf2.group(1)
            file_path = resolve(mf2.group(2).strip().strip('"').strip("'")).replace('\\', '/')
            full_path = os.path.join(rom_dir, file_path.lstrip('./')) if rom_dir else file_path
            if os.path.isfile(full_path):
                with open(full_path, 'r', errors='ignore') as f:
                    file_items = [ln.strip() for ln in f if ln.strip()]
            else:
                file_items = []
                mf.append(file_path)
            for item in file_items:
                for bline in block:
                    expanded.append(bline.replace(lv, item))
            return expanded, end_i, mf
        # 普通 for 列表/通配符
        m0 = re.match(r'^for\s+%%(\w+)\s+in\s*\(([^)]+)\)\s*do\s*\(', line, re.I)
        if m0:
            lv = '%%' + m0.group(1)
            items_str_r = resolve(m0.group(2).strip())
            items_list = []
            if '*' in items_str_r or '?' in items_str_r:
                pattern = os.path.join(rom_dir, items_str_r.replace('\\', '/')) if rom_dir else items_str_r.replace('\\', '/')
                matches = sorted(glob.glob(pattern))
                if not matches:
                    # v3.0.8: 大小写不敏感回退（Windows ROM 包在 Linux 下目录名大小写可能不匹配）
                    dir_part, file_pattern = os.path.split(pattern)
                    if os.path.isdir(dir_part):
                        try:
                            ci_re = re.compile(fnmatch.translate(file_pattern.lower()))
                            matches = sorted([
                                os.path.join(dir_part, e)
                                for e in os.listdir(dir_part)
                                if ci_re.match(e.lower())
                            ])
                        except OSError:
                            pass
                if matches:
                    items_list = matches
                else:
                    mf.append(items_str_r)
            else:
                items_list = [x.strip().strip('"\'') for x in items_str_r.split() if x.strip()]
            for item in items_list:
                item_base = os.path.basename(item) if os.path.isfile(item) else item
                name_no_ext, ext = os.path.splitext(item_base)
                item_dir = os.path.dirname(item) + os.sep
                for bline in block:
                    eline = bline.replace(lv, item)
                    # 循环变量修饰符
                    sv_name = m0.group(1)
                    eline = eline.replace('%%~n' + sv_name, name_no_ext)
                    eline = eline.replace('%%~x' + sv_name, ext)
                    eline = eline.replace('%%~nx' + sv_name, item_base)
                    eline = eline.replace('%%~dp' + sv_name, item_dir)
                    eline = eline.replace('%%~p' + sv_name, item_dir)
                    eline = eline.replace('%%~f' + sv_name, item)
                    expanded.append(eline)
            return expanded, end_i, mf
        return [], idx, mf

    def eval_if(line: str, idx: int) -> tuple:
        """if 条件判断，返回 (result, block, end_idx)。result: True/False/None"""
        m = re.match(r'^if\s+(not\s+)?(.+?)\s*\(', line, re.I)
        if not m:
            return None, [], idx
        is_not = m.group(1) is not None
        condition = resolve(m.group(2).strip())
        block, end_i = collect_block_v2(lines, idx + 1)
        # if exist
        em = re.match(r'^(not\s+)?exist\s+(.+)', condition, re.I)
        if em:
            fp = em.group(2).strip().strip('"').strip("'").replace('\\', '/')
            full = os.path.join(rom_dir, fp.lstrip('./')) if rom_dir else fp
            exists = os.path.exists(full)
            return ((not exists) if is_not else exists), block, end_i
        # if 比较 (equ, ==, neq, lss, leq, gtr, geq)
        cm = re.match(r'^(.+?)\s+(equ|==|neq|lss|leq|gtr|geq)\s+(.+)', condition, re.I)
        if cm:
            left = cm.group(1).strip().strip('"\'')
            right = cm.group(3).strip().strip('"\'')
            op = cm.group(2).lower()
            try:
                ln, rn = float(left), float(right)
                if op in ('equ', '=='): r = ln == rn
                elif op == 'neq': r = ln != rn
                elif op == 'lss': r = ln < rn
                elif op == 'leq': r = ln <= rn
                elif op == 'gtr': r = ln > rn
                elif op == 'geq': r = ln >= rn
                else: r = None
            except ValueError:
                if op in ('equ', '=='): r = left == right
                elif op == 'neq': r = left != right
                else: r = None
            return r, block, end_i
        return None, block, end_i

    # 收集子程序标签
    labels = {}
    current_label = None
    for line in lines:
        if re.match(r'^:\w', line):
            current_label = line[1:].strip()
            labels[current_label] = []
        elif current_label is not None:
            labels[current_label].append(line)

    # ===== 主解析循环 =====
    _call_count = {}  # v3.0.8: call :label 递归保护（计数器，每个 label 最多内联 3 次）
    skip_patterns = [r'^echo\b', r'^pause\b', r'^cls\b', r'^title\b', r'^color\b',
                     r'^chcp\b', r'^timeout\b', r'^sleep\b', r'^export\b',
                     r'^set\b', r'^setlocal\b', r'^endlocal\b', r'^shift\b',
                     r'^:\w', r'^goto\b', r'^exit\b', r'^#', r'^::']
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        lower = stripped.lower()
        if not stripped or any(re.match(p, lower) for p in skip_patterns):
            i += 1
            continue

        # for 循环
        if re.match(r'^for\s+', lower) and '(' in stripped:
            expanded, end_i, mf = expand_for_loop(stripped, i)
            missing_files.extend(mf)
            for eline in expanded:
                step = _parse_fastboot_line(eline, eline)
                if step:
                    step['loop'] = stripped
                    steps.append(step)
            i = end_i + 1
            continue

        # if 条件块
        if re.match(r'^if\s+', lower) and '(' in stripped:
            result, block, end_i = eval_if(stripped, i)
            if result is True:
                for bline in block:
                    step = _parse_fastboot_line(bline, bline)
                    if step:
                        steps.append(step)
            elif result is None:
                for bline in block:
                    step = _parse_fastboot_line(bline, bline)
                    if step:
                        step['condition'] = stripped.split('(')[0].strip()
                        steps.append(step)
            i = end_i + 1
            continue

        # call :label 子程序内联（v3.0.8: 递归保护）
        cm = re.match(r'^call\s+:(\w+)(.*)', stripped, re.I)
        if cm:
            label_name = cm.group(1)
            args_str = cm.group(2).strip()
            if label_name in labels and _call_count.get(label_name, 0) < 3:
                _call_count[label_name] = _call_count.get(label_name, 0) + 1
                arg_list = split_args(args_str)
                for bline in labels[label_name]:
                    inlined = resolve(bline)
                    for ai, arg in enumerate(arg_list, 1):
                        inlined = inlined.replace('%' + str(ai), arg)
                        inlined = re.sub(r'%~n' + str(ai), os.path.splitext(arg)[0], inlined)
                        inlined = re.sub(r'%~x' + str(ai), os.path.splitext(arg)[1], inlined)
                    step = _parse_fastboot_line(inlined, inlined)
                    if step:
                        step['call'] = stripped
                        steps.append(step)
            i += 1
            continue

        # 普通行
        step = _parse_fastboot_line(stripped, stripped)
        if step:
            steps.append(step)
        i += 1

    for step in steps:
        step['risk'] = _assess_risk(step)

    return steps, missing_files

def split_args(text: str) -> List[str]:
    """兼容 BAT/SH 的简单参数切分，保留 Windows 反斜杠路径"""
    try:
        return shlex.split(text, posix=False)
    except Exception:
        return re.findall(r'"[^"]*"|\'[^\']*\'|\S+', text)


def strip_quote(v: str) -> str:
    v = (v or '').strip()
    if len(v) >= 2 and ((v[0] == '"' and v[-1] == '"') or (v[0] == "'" and v[-1] == "'")):
        return v[1:-1]
    return v


# ----------------------------------------------------------------------
# 重新导出 fastboot 命令解析接口（已拆分至 core/fastboot_cmd_parser.py）
# 放在文件末尾，确保 split_args / strip_quote 先定义，避免循环导入。
# parse_bat_script 运行时调用 parse_fastboot_tail / _assess_risk，导入后即可解析。
# ----------------------------------------------------------------------
from core.fastboot_cmd_parser import (  # noqa: E402
    parse_fastboot_tail,
    parse_fastboot_command,
    _assess_risk,
)
