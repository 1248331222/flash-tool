# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/sh_parser/sandbox/simulator.py
"""
ShSimulator — 纯 Python 微型 SH 脚本模拟执行器
完全在 Python 生态内执行，代替系统 sh 子进程沙箱。
"""
import json
import os
import re
import shlex
import time
from typing import Dict, List, Optional, Tuple, Any

# ---------- ShSimResult ----------

class ShSimResult:
    """模拟执行结果"""
    def __init__(self, steps: List[Dict] = None, decisions: List[Dict] = None,
                 variables: Dict[str, str] = None):
        self.steps = steps or []
        self.decisions = decisions or []
        self.variables = variables or {}

    def to_jsonl(self, path: str):
        """导出为 JSONL 格式（兼容原沙箱输出）"""
        with open(path, 'w') as f:
            for s in self.steps:
                f.write(json.dumps(s, ensure_ascii=False) + '\n')

# ---------- 变量展开 ----------

_VAR_REF = re.compile(r'\$\{([^}]+)\}|\$([a-zA-Z_][a-zA-Z0-9_]*|\*|@|\?|#|0)')
_VAR_DEFAULT = re.compile(r'^([^:]*):?-(.*)$')

def expand_vars(text: str, vars: Dict[str, str]) -> str:
    """展开 $var / ${var} / ${var:-default}"""
    def repl(m):
        name = m.group(1) or m.group(2)
        if name == '*': return vars.get('*', '')
        if name == '@': return vars.get('@', '')
        if name == '?': return str(vars.get('?', '0'))
        if name == '#': return str(vars.get('#', '0'))
        if name == '0': return vars.get('0', 'script.sh')
        dm = _VAR_DEFAULT.match(name)
        if dm:
            base, default = dm.group(1), dm.group(2)
            if base in vars and vars[base]:
                return vars[base]
            return expand_vars(default, vars)
        return vars.get(name, '')
    return _VAR_REF.sub(repl, text)

def expand_assignment(val: str, vars: Dict[str, str]) -> str:
    """展开赋值右侧（先命令替换再变量展开）"""
    # 命令替换 $(cmd) / `cmd`
    val = re.sub(r'\$\(([^)]*)\)|`([^`]*)`',
                 lambda m: _exec_cmd_subst(m.group(1) or m.group(2) or '', vars), val)
    return expand_vars(val, vars)

def _exec_cmd_subst(cmdline: str, vars: Dict[str, str]) -> str:
    """模拟命令替换"""
    parts = shlex.split(cmdline)
    if not parts:
        return ''
    rc, output = exec_fastboot_mock(parts[0], parts[1:], vars)
    return output.strip()

# ---------- Fastboot Mock ----------

def exec_fastboot_mock(cmd: str, args: List[str],
                       vars: Dict[str, str]) -> Tuple[int, str]:
    """模拟 fastboot 命令（记录并返回假值）"""
    if cmd == 'fastboot':
        subcmd = args[0] if args else ''
        if subcmd == 'getvar':
            var_name = args[1] if len(args) > 1 else ''
            if var_name == 'product': return 0, 'product: umi\n'
            if var_name == 'anti': return 0, 'anti: 0\n'
            return 0, f'{var_name}: \n'
        elif subcmd == 'devices':
            return 0, 'abcdef123456\tfastboot\n'
        elif subcmd in ('flash', 'erase', 'reboot'):
            return 0, 'OKAY\n'
        return 0, 'OKAY\n'
    return 0, ''

# ---------- Builtins ----------

def builtin_echo(args: List[str], vars: Dict[str, str]) -> Tuple[int, str]:
    text = ' '.join(expand_vars(a, vars) for a in args)
    if text.startswith('-e '):
        text = text[3:]
    return 0, text + '\n'

def builtin_dirname(args: List[str]) -> Tuple[int, str]:
    if args:
        return 0, os.path.dirname(os.path.normpath(args[0])) + '\n'
    return 0, '.\n'

def builtin_command(args: List[str]) -> Tuple[int, str]:
    if '-v' in args:
        idx = args.index('-v')
        if idx + 1 < len(args):
            cmd = args[idx + 1]
            if cmd in ('fastboot', 'sh', 'bash', 'cat', 'ls'):
                return 0, f'{cmd}\n'
            return 1, ''
    return 0, ''

def builtin_read(args: List[str], vars: Dict[str, str]) -> str:
    """模拟 read -p prompt var"""
    var_name = ''
    i = 0
    while i < len(args):
        if args[i] == '-p' and i + 1 < len(args):
            i += 2
        else:
            var_name = args[i]
            i += 1
    if var_name:
        vars[var_name] = 'y'
    return var_name

# ---------- test 表达式 ----------

def eval_test(expr: str, vars: Dict[str, str]) -> bool:
    """解析 [ expr ] 表达式"""
    expr = expand_vars(expr.strip(), vars)
    parts = shlex.split(expr)
    if not parts:
        return False
    negate = False
    if parts[0] == '!':
        negate = True
        parts = parts[1:]
    if not parts:
        result = False
    elif parts[0] == '-f':
        result = os.path.isfile(parts[1] if len(parts) > 1 else '')
    elif parts[0] == '-e':
        result = os.path.exists(parts[1] if len(parts) > 1 else '')
    elif parts[0] == '-d':
        result = os.path.isdir(parts[1] if len(parts) > 1 else '')
    elif parts[0] == '-z':
        result = (parts[1] if len(parts) > 1 else '') == ''
    elif parts[0] == '-n':
        result = (parts[1] if len(parts) > 1 else '') != ''
    elif len(parts) >= 3 and parts[1] in ('=', '==', '!='):
        result = parts[0] != parts[2] if parts[1] == '!=' else parts[0] == parts[2]
    elif len(parts) >= 3 and parts[1] in ('-ne', '-eq', '-gt', '-ge', '-lt', '-le'):
        try:
            a, b = int(parts[0]), int(parts[2])
            ops = {'-ne': a!=b, '-eq': a==b, '-gt': a>b, '-ge': a>=b, '-lt': a<b, '-le': a<=b}
            result = ops.get(parts[1], False)
        except: result = False
    else:
        result = bool(parts)
    return not result if negate else result


# ---------- ShSimulator ----------

class ShSimulator:
    """纯 Python SH 脚本模拟执行器"""

    def __init__(self, getvar_defs: Optional[Dict[str, str]] = None,
                 extra_env: Optional[Dict[str, str]] = None):
        self.vars: Dict[str, str] = dict(extra_env or {})
        self.steps: List[Dict] = []
        self.decisions: List[Dict] = []
        self.set_e: bool = False
        self.rom_dir: str = ''

    def run(self, content: str, rom_dir: str = '',
            script_path: str = '') -> 'ShSimResult':
        """执行脚本内容"""
        self.rom_dir = rom_dir
        self.steps = []
        self.decisions = []
        self.vars['0'] = script_path or 'script.sh'
        self.vars['*'] = ''
        self.vars['@'] = ''
        self.vars['?'] = '0'
        self.vars['#'] = '0'

        lines = content.split('\n')
        self._exec_block(lines, 0)

        return ShSimResult(steps=self.steps, decisions=self.decisions,
                           variables=dict(self.vars))

    # -------- 语句块执行 --------

    def _exec_block(self, lines: List[str], start: int,
                    stop_pat: Optional[re.Pattern] = None) -> Tuple[int, int]:
        """执行语句块，返回 (rc, next_line)"""
        idx = start
        rc = 0

        while idx < len(lines):
            raw = lines[idx]
            stripped = raw.strip()

            # 停止条件
            if stop_pat and stop_pat.search(stripped):
                break

            # 空行 / 注释 / 纯括号
            if not stripped or stripped.startswith('#') or stripped == '}':
                idx += 1
                continue

            # set -e / set +e
            m = re.match(r'^\s*set\s+([+-])e\s*$', stripped)
            if m:
                self.set_e = (m.group(1) == '-')
                idx += 1
                continue

            # if
            if stripped.startswith('if '):
                rc, idx = self._handle_if(lines, idx)
                if self.set_e and rc != 0:
                    return rc, idx
                continue

            # for
            if stripped.startswith('for '):
                rc, idx = self._handle_for(lines, idx)
                continue

            # while
            if stripped.startswith('while '):
                rc, idx = self._handle_while(lines, idx)
                continue

            # case
            if stripped.startswith('case '):
                rc, idx = self._handle_case(lines, idx)
                continue

            # function name()
            m = re.match(r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\s*\)\s*', stripped)
            if m:
                idx = self._skip_function_body(lines, idx)
                continue

            # cd
            if stripped.startswith('cd '):
                parts = shlex.split(expand_vars(stripped[3:].strip(), self.vars))
                if parts:
                    target = os.path.normpath(os.path.join(self.rom_dir or '/tmp', parts[0]))
                    self.vars['PWD'] = target
                idx += 1
                continue

            # sleep
            if stripped.startswith('sleep '):
                parts = shlex.split(expand_vars(stripped[6:].strip(), self.vars))
                if parts:
                    try:
                        time.sleep(float(parts[0]))
                    except: pass
                idx += 1
                continue

            # exit / return
            if stripped.startswith('exit ') or stripped.startswith('return '):
                parts = shlex.split(stripped)
                try:
                    rc = int(parts[1]) if len(parts) > 1 else 0
                except: rc = 0
                self.vars['?'] = str(rc)
                return rc, idx + 1

            # 变量赋值
            m = re.match(r'^\s*(?:export\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.*?)\s*$', stripped)
            if m and not stripped.lstrip().startswith('#'):
                var_name, val = m.group(1), expand_assignment(m.group(2), self.vars)
                self.vars[var_name] = val
                idx += 1
                continue

            # { 复合命令
            if stripped.startswith('{'):
                end = self._find_matching_brace(lines, idx)
                block = lines[idx+1:end]
                self._exec_block(block, 0)
                idx = end + 1
                continue

            # 普通命令（含 && / || 链）
            rc, idx = self._exec_cmd_line(stripped, idx)
            if self.set_e and rc != 0:
                return rc, idx
            idx += 1

        return rc, idx

    # -------- 命令执行 --------

    def _exec_cmd_line(self, line: str, line_no: int) -> Tuple[int, int]:
        """执行单条命令（含 && / || 链、管道、重定向）"""
        expanded = expand_vars(line, self.vars)

        # 拆解 && / || 链
        if ' && ' in expanded or ' || ' in expanded:
            return self._exec_chain(expanded, line_no)

        # 提取管道前的部分（仅第一个命令）
        pipe_parts = expanded.split('|')
        first_cmd = pipe_parts[0].strip()

        # 去除重定向符号及后面的参数: 2>&1, > file, &> file
        first_cmd = re.sub(r'\s*[12]?>&?\d*\s*$', '', first_cmd)
        first_cmd = re.sub(r'\s*&>\s*\S+', '', first_cmd)
        first_cmd = re.sub(r'\s*>\s*\S+', '', first_cmd)
        first_cmd = re.sub(r'\s*>>\s*\S+', '', first_cmd)

        parts = shlex.split(first_cmd)
        if not parts:
            return 0, line_no

        cmd = parts[0]
        args = parts[1:]

        # fastboot
        if cmd == 'fastboot':
            return self._record_fastboot(cmd, args, line)

        # 内置命令
        if cmd == 'echo':
            rc, out = builtin_echo(args, self.vars)
            self.vars['?'] = str(rc)
            return rc, line_no
        elif cmd == 'dirname':
            rc, out = builtin_dirname(args)
            self.vars['?'] = str(rc)
            return rc, line_no
        elif cmd == 'command':
            rc, out = builtin_command(args)
            self.vars['?'] = str(rc)
            return rc, line_no
        elif cmd == 'read':
            builtin_read(args, self.vars)
            return 0, line_no
        elif cmd == 'cat':
            out = ''
            for a in args:
                ap = expand_vars(a, self.vars)
                if os.path.isfile(ap):
                    try: out += open(ap).read()
                    except: pass
            self.vars['?'] = '0'
            if out:
                return 0, line_no
            return 0, line_no
        elif cmd == 'true':
            self.vars['?'] = '0'
            return 0, line_no
        elif cmd == 'false':
            self.vars['?'] = '1'
            return 1, line_no

        # 其他命令 — 假设成功
        self.vars['?'] = '0'
        return 0, line_no

    def _exec_chain(self, expanded: str, line_no: int) -> Tuple[int, int]:
        """执行 && / || 链"""
        # 拆分
        tokens = re.split(r'(\s*&&\s*|\s*\|\|\s*)', expanded)
        rc = 0
        i = 0
        while i < len(tokens):
            tok = tokens[i].strip()
            if not tok:
                i += 1
                continue
            if tok == '&&':
                i += 1
                if rc != 0:
                    i += 1
                    continue
                tok = tokens[i].strip() if i < len(tokens) else ''
                i += 1
            elif tok == '||':
                i += 1
                if rc == 0:
                    i += 1
                    continue
                tok = tokens[i].strip() if i < len(tokens) else ''
                i += 1

            parts = shlex.split(tok)
            if not parts:
                continue

            if parts[0] == 'fastboot':
                rc, _ = self._record_fastboot(parts[0], parts[1:], tok)
            else:
                # 处理 echo / dirname 等
                if parts[0] == 'echo':
                    rc, _ = builtin_echo(parts[1:], self.vars)
                else:
                    rc = 0

            self.vars['?'] = str(rc)
            i += 1

        return rc, line_no

    def _record_fastboot(self, cmd: str, args: List[str],
                         raw_line: str) -> Tuple[int, int]:
        """记录 fastboot 命令到步骤列表"""
        cmd_text = f'fastboot {' '.join(args)}'
        self.steps.append({
            'cmd': cmd_text,
            'parts': ['fastboot'] + args,
            'raw': raw_line,
        })
        return 0, 0

    # -------- if / elif / else / fi --------

    def _handle_if_inline(self, lines, idx):
        """处理单行 if: if cond; then cmd1; cmd2; fi"""
        raw = lines[idx].strip()
        body = raw
        # if [ cond ]; then cmd1; cmd2; fi
        cond_match = re.match(r'^\s*if\s+(.*?)\s*;\s*then\s+(.*?)\s*;\s*fi\s*$', body)
        if cond_match:
            cond_raw = cond_match.group(1)
            then_body = cond_match.group(2)
            cond_ok = self._eval_cond(cond_raw)
            if cond_ok:
                for cmd in then_body.split('; '):
                    cmd = cmd.strip()
                    if cmd:
                        self._exec_cmd_line(cmd, idx)
        elif '; then' in body and body.rstrip().endswith('fi'):
            parts = body.replace('; fi', '').split('; then ', 1)
            if len(parts) == 2:
                cond_raw = parts[0].replace('if ', '', 1).strip()
                then_body = parts[1]
                cond_ok = self._eval_cond(cond_raw)
                if cond_ok:
                    for cmd in then_body.split('; '):
                        cmd = cmd.strip()
                        if cmd:
                            self._exec_cmd_line(cmd, idx)
        self.vars['?'] = '0'
        return 0, idx + 1


    def _handle_if(self, lines: List[str], idx: int) -> Tuple[int, int]:
        """处理 if ... fi（支持单行和多行）"""
        raw = lines[idx].strip()
        
        # 单行 if: if cond; then cmd1; cmd2; fi
        if '; then' in raw and '; fi' in raw:
            rc, nxt = self._handle_if_inline(lines, idx)
            return rc, nxt
        
        # 提取条件
        cond_raw = re.sub(r'^\s*if\s+', '', raw)
        cond_raw = re.sub(r'\s*;\s*then\s*$', '', cond_raw)
        cond_ok = self._eval_cond(cond_raw)

        # 定位分支
        body_then = []
        body_elif = None
        body_else = []
        current = body_then
        depth = 0
        i = idx + 1

        while i < len(lines):
            l = lines[i].strip()
            if re.match(r'^\s*fi\s*$', l) and depth == 0:
                break
            if re.match(r'^\s*elif\s+', l) and depth == 0:
                if cond_ok:
                    break
                body_elif = []
                current = body_elif
                # 提取 elif 条件
                elif_cond = re.sub(r'^\s*elif\s+', '', l)
                elif_cond = re.sub(r'\s*;\s*then\s*$', '', elif_cond)
                i += 1
                continue
            if re.match(r'^\s*else\s*$', l) and depth == 0:
                if cond_ok:
                    break
                current = body_else
                i += 1
                continue

            # 追踪 if/for 嵌套
            if 'if ' in l: depth += 1
            if 'fi' in l: depth -= 1
            if 'for ' in l: depth += 1
            if 'done' in l: depth -= 1

            current.append(lines[i])
            i += 1

        # 执行分支
        if cond_ok:
            self._exec_block(body_then, 0)
        elif body_elif is not None:
            # elif 再判断
            elif_cond_raw = re.sub(r'^\s*elif\s+', '', lines[idx].strip()) if idx < len(lines) else ''
            elif_cond_raw = re.sub(r'\s*;\s*then\s*$', '', elif_cond_raw)
            if self._eval_cond(elif_cond_raw):
                self._exec_block(body_elif, 0)
            else:
                self._exec_block(body_else, 0)
        else:
            self._exec_block(body_else, 0)

        # 跳到 fi
        while i < len(lines) and not re.match(r'^\s*fi\s*$', lines[i].strip()):
            i += 1
        if i < len(lines) and re.match(r'^\s*fi\s*$', lines[i].strip()):
            i += 1

        self.vars['?'] = '0'
        return 0, i

    def _eval_cond(self, cond: str) -> bool:
        """评估条件表达式（支持命令替换）"""
        # 先展开命令替换 $(cmd) / `cmd`
        cond_expanded = re.sub(r'\$\(([^)]*)\)|`([^`]*)`',
                               lambda m: _exec_cmd_subst(m.group(1) or m.group(2) or '', self.vars),
                               cond)
        # 再展开变量
        cond_expanded = expand_vars(cond_expanded, self.vars)
        
        if cond_expanded.startswith('[') and ']' in cond_expanded:
            expr = cond_expanded[1:].rsplit(']', 1)[0].strip()
            return eval_test(expr, self.vars)
        if cond_expanded.startswith('! '):
            return False  # ! command -v 一般成功，取反
        if cond_expanded.startswith('command '):
            return True
        if cond_expanded.startswith('fastboot '):
            parts = shlex.split(cond_expanded)
            return True
        return True

    # -------- for/do/done --------

    def _handle_for(self, lines: List[str], idx: int) -> Tuple[int, int]:
        """处理 for var in list; do ... done"""
        stripped = lines[idx].strip()
        m = re.match(r'^\s*for\s+(\w+)\s+in\s+(.*?)\s*(?:;\s*do\s*)?$', stripped)
        if not m:
            return 0, idx
        var_name = m.group(1)
        list_str = expand_vars(m.group(2).strip(), self.vars)
        items = shlex.split(list_str)

        # 收集 body
        body = []
        i = idx + 1
        depth = 0
        found_do = False
        while i < len(lines):
            l = lines[i].strip()
            if l == 'do' and depth == 0:
                found_do = True
                i += 1
                continue
            if re.match(r'^\s*done\s*$', l) and depth == 0:
                break
            if not found_do:
                i += 1
                continue
            body.append(lines[i])
            i += 1

        for item in items:
            self.vars[var_name] = item
            self._exec_block(body, 0)

        return 0, i + 1

    # -------- while/do/done --------

    def _handle_while(self, lines: List[str], idx: int) -> Tuple[int, int]:
        """处理 while cond; do ... done（模拟执行 1 次）"""
        stripped = lines[idx].strip()
        cond_raw = re.sub(r'^\s*while\s+', '', stripped)
        cond_raw = re.sub(r'\s*;\s*do\s*$', '', cond_raw)

        body = []
        i = idx + 1
        while i < len(lines):
            l = lines[i].strip()
            if re.match(r'^\s*done\s*$', l):
                break
            if l == 'do':
                i += 1
                continue
            body.append(lines[i])
            i += 1

        # 只执行一次（避免死循环）
        if self._eval_cond(cond_raw):
            self._exec_block(body, 0)

        return 0, i + 1

    # -------- case/esac --------

    def _handle_case(self, lines: List[str], idx: int) -> Tuple[int, int]:
        """处理 case var in pattern) ... ;; esac"""
        stripped = lines[idx].strip()
        var_part = re.sub(r'^\s*case\s+', '', stripped)
        var_part = re.sub(r'\s+in\s*$', '', var_part)
        var_value = expand_vars(var_part, self.vars)

        i = idx + 1
        matched = False
        while i < len(lines):
            l = lines[i].strip()
            if re.match(r'^\s*esac\s*$', l):
                break
            if not matched and ')' in l:
                pattern = l.split(')')[0].strip()
                # 匹配模式
                if pattern == '*' or pattern == var_value or pattern == expand_vars(pattern, self.vars):
                    matched = True
                    # 执行分支体
                    branch = []
                    i += 1
                    while i < len(lines):
                        ll = lines[i].strip()
                        if ll.endswith(';;'):
                            break
                        if re.match(r'^\s*esac\s*$', ll):
                            break
                        branch.append(lines[i])
                        i += 1
                    self._exec_block(branch, 0)
                    i += 1  # 跳过 ;;
                    break
            i += 1

        # 跳到 esac
        while i < len(lines) and not re.match(r'^\s*esac\s*$', lines[i].strip()):
            i += 1
        return 0, i + 1

    # -------- 辅助 --------

    def _skip_function_body(self, lines: List[str], idx: int) -> int:
        """跳过函数定义 { ... }"""
        i = idx + 1
        while i < len(lines) and lines[i].strip() != '}':
            i += 1
        return i + 1

    def _find_matching_brace(self, lines: List[str], idx: int) -> int:
        """找到匹配的 }"""
        depth = 0
        for i in range(idx, len(lines)):
            l = lines[i].strip()
            if '{' in l: depth += 1
            if '}' in l:
                depth -= 1
                if depth == 0:
                    return i
        return idx

    # -------- 兼容 ShSandboxRunner 接口 --------

    def run_to_jsonl(self, script_path: str, rom_dir: str,
                     sandbox_dir: Optional[str] = None) -> str:
        """兼容 ShSandboxRunner.run() 接口"""
        content = open(script_path, 'r').read()
        result = self.run(content, rom_dir, script_path)

        if sandbox_dir is None:
            sandbox_dir = tempfile.mkdtemp(prefix='sh_simulator_')

        jsonl_path = os.path.join(sandbox_dir, 'commands.jsonl')
        result.to_jsonl(jsonl_path)
        return jsonl_path
