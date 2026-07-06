# -*- coding: utf-8 -*-
"""ShSimulator v2 — 纯 Python SH 模拟执行器（路径感知版）"""
import json, os, re, shlex, time, tempfile
from typing import Dict, List, Optional, Tuple

RE_CMD_SUBST = re.compile(r'\$\(([^)]*)\)|`([^`]*)`')
RE_VAR = re.compile(r'\$\{([^}]+)\}|\$([a-zA-Z_][a-zA-Z0-9_]*|\*|@|\?|#|0)')
RE_VAR_DEFAULT = re.compile(r'^([^:]*):?-(.*)$')
RE_IF_INLINE = re.compile(r'^\s*if\s+(.+?)\s*;\s*then\s+(.+?)\s*;\s*fi\s*$')
RE_FUNCDEF = re.compile(r'^\s*([a-zA-Z_]\w*)\s*\(\s*\)\s*\{?\s*$')
RE_VAR_ASSIGN = re.compile(r'^\s*(?:export\s+)?([a-zA-Z_]\w*)\s*=\s*(.*?)\s*$')
RE_SET_E = re.compile(r'^\s*set\s+([+-])e\s*$')

class SimResult:
    def __init__(self, steps=None):
        self.steps = steps or []
    def to_jsonl(self, path):
        with open(path, 'w') as f:
            for s in self.steps:
                f.write(json.dumps(s, ensure_ascii=False) + '\n')

def expand_vars(text: str, vars: dict) -> str:
    def repl(m):
        name = m.group(1) or m.group(2)
        if name == '*': return vars.get('*', '')
        if name == '@': return vars.get('@', '')
        if name == '?': return str(vars.get('?', '0'))
        if name == '#': return str(vars.get('#', '0'))
        if name == '0': return vars.get('0', 'script.sh')
        dm = RE_VAR_DEFAULT.match(name)
        if dm:
            base, default = dm.group(1), dm.group(2)
            if base in vars and vars[base]:
                return vars[base]
            return expand_vars(default, vars)
        return vars.get(name, '')
    return RE_VAR.sub(repl, text)

def eval_test(expr: str, vars: dict) -> bool:
    expr = expand_vars(expr.strip(), vars)
    try: parts = shlex.split(expr)
    except: parts = []
    if not parts: return False
    neg = False
    if parts[0] == '!':
        neg, parts = True, parts[1:]
    if not parts: return False ^ neg
    if parts[0] == '-f': r = os.path.isfile(parts[1] if len(parts)>1 else '')
    elif parts[0] == '-e': r = os.path.exists(parts[1] if len(parts)>1 else '')
    elif parts[0] == '-z': r = (parts[1] if len(parts)>1 else '') == ''
    elif parts[0] == '-n': r = (parts[1] if len(parts)>1 else '') != ''
    elif len(parts) >= 3 and parts[1] in ('=', '==', '!='):
        r = parts[0] == parts[2] if parts[1] != '!=' else parts[0] != parts[2]
    elif len(parts) >= 3 and parts[1] in ('-ne','-eq','-gt','-ge','-lt','-le'):
        try:
            a,b = int(parts[0]), int(parts[2])
            ops = {'-ne':a!=b,'-eq':a==b,'-gt':a>b,'-ge':a>=b,'-lt':a<b,'-le':a<=b}
            r = ops.get(parts[1], False)
        except: r = False
    else: r = bool(parts)
    return not r if neg else r

def cmd_subst(cmdline: str, vars: dict) -> tuple:
    parts = shlex.split(cmdline) if cmdline else []
    if not parts: return 0, ''
    cmd = parts[0]
    args = [expand_vars(a, vars) for a in parts[1:]]
    if cmd == 'dirname':
        if args: return 0, os.path.dirname(os.path.normpath(args[0])) + '\n'
        return 0, '.\n'
    if cmd == 'echo': return 0, ' '.join(args) + '\n'
    if cmd == 'cat':
        out = ''
        for a in args:
            if os.path.isfile(a):
                try: out += open(a).read()
                except: pass
        return 0, out
    if cmd == 'fastboot':
        sub = args[0] if args else ''
        if sub == 'getvar':
            vn = args[1] if len(args) > 1 else ''
            if vn == 'product': return 0, 'product: umi\n'
            if vn == 'anti': return 0, 'anti: 0\n'
            return 0, f'{vn}: \n'
        return 0, 'OKAY\n'
    return 0, ''

def _split_fastboot_args(text: str) -> List[str]:
    """手动拆分 fastboot 命令参数（保留反引号路径）"""
    result = []
    cur = ''
    in_bt = False
    for ch in text:
        if ch == '`':
            in_bt = not in_bt
            cur += ch
        elif ch.isspace() and not in_bt:
            if cur:
                result.append(cur)
                cur = ''
        else:
            cur += ch
    if cur:
        result.append(cur)
    return result

class ShSimulator:
    def __init__(self, extra_env: Optional[dict] = None):
        self.vars = dict(extra_env or {})
        self.steps: List[dict] = []
        self.rom_dir = ''

    def run(self, content: str, rom_dir: str = '', script_path: str = '') -> SimResult:
        self.rom_dir = rom_dir or (os.path.dirname(script_path) if script_path else '')
        self.steps = []
        self.vars.update({'0': script_path or 'script.sh', '*': '', '@': '',
                          '?': '0', '#': '0'})
        self._exec(content.split('\n'), 0)
        return SimResult(self.steps)

    def _exec(self, lines: List[str], idx: int) -> Tuple[int, int]:
        while idx < len(lines):
            s = lines[idx].strip()
            if not s or s.startswith('#') or s == '}':
                idx += 1; continue
            if RE_SET_E.match(s): idx += 1; continue
            # if inline
            if s.startswith('if '):
                im = RE_IF_INLINE.match(s)
                if im:
                    if self._eval_cond(im.group(1)):
                        for c in im.group(2).split('; '):
                            c = c.strip()
                            if c: self._do_cmd(c)
                    self.vars['?'] = '0'; idx += 1; continue
                rc, nxt = self._do_if(lines, idx); idx = nxt; continue
            if s.startswith('for '):
                rc, nxt = self._do_for(lines, idx); idx = nxt; continue
            if s.startswith('while '):
                rc, nxt = self._do_while(lines, idx); idx = nxt; continue
            if s.startswith('case '):
                rc, nxt = self._do_case(lines, idx); idx = nxt; continue
            if RE_FUNCDEF.match(s): idx = self._skip_func(lines, idx); continue
            m = RE_VAR_ASSIGN.match(s)
            if m:
                self.vars[m.group(1)] = self._do_expand(m.group(2))
                idx += 1; continue
            if s.startswith('cd '):
                tp = shlex.split(expand_vars(s[3:], self.vars))
                if tp: self.vars['PWD'] = os.path.normpath(os.path.join(self.rom_dir or '/tmp', tp[0]))
                idx += 1; continue
            if s.startswith('sleep '):
                tp = shlex.split(expand_vars(s[6:], self.vars))
                if tp:
                    try: time.sleep(float(tp[0]))
                    except: pass
                idx += 1; continue
            if s.startswith('exit ') or s.startswith('return '):
                tp = shlex.split(s)
                rc = int(tp[1]) if len(tp) > 1 else 0
                return rc, idx + 1
            self._do_cmd(s)
            idx += 1
        return 0, idx

    def _eval_cond(self, cond: str) -> bool:
        cd = RE_CMD_SUBST.sub(lambda m: cmd_subst(m.group(1) or m.group(2) or '', self.vars)[1].strip(), cond)
        cd = expand_vars(cd, self.vars)
        if cd.startswith('[') and ']' in cd:
            return eval_test(cd[1:].rsplit(']', 1)[0].strip(), self.vars)
        if cd.startswith('! '): return False
        return True

    def _do_expand(self, val: str) -> str:
        val = RE_CMD_SUBST.sub(
            lambda m: cmd_subst(m.group(1) or m.group(2) or '', self.vars)[1].strip(), val)
        return expand_vars(val, self.vars)

    def _do_cmd(self, raw_line: str):
        """执行一条命令——fastboot 命令记录并展开路径"""
        # 从原始行取管道前部分
        fb = raw_line.split('|')[0].strip()
        # 去掉重定向
        fb = re.sub(r'\s*[12]?>&?\d*\s*$', '', fb)
        fb = re.sub(r'\s*&>\s*\S+', '', fb)
        fb = re.sub(r'\s*>\s*\S+', '', fb)
        fb = re.sub(r'\s*>>\s*\S+', '', fb)
        # 展开变量
        fb = expand_vars(fb, self.vars)
        # 手动拆分参数
        args = _split_fastboot_args(fb)
        if not args or args[0] != 'fastboot':
            self.vars['?'] = '0'
            return
        cmd = args[0]
        params = args[1:]
        # 展开 dirname
        rom_dir = self.rom_dir or ''
        clean_params = []
        for p in params:
            cp = p
            if '`dirname' in cp or '$(dirname' in cp:
                cp = re.sub(r'`dirname[^`]+`', rom_dir, cp)
                cp = re.sub(r'\$\(dirname[^)]+\)', rom_dir, cp)
            clean_params.append(cp)
        cmd_text = f'fastboot {" ".join(clean_params)}'
        step = {'cmd': cmd_text, 'parts': ['fastboot'] + clean_params, 'raw': raw_line}
        subcmd = clean_params[0] if clean_params else ''
        if subcmd in ('flash', 'update') and len(clean_params) >= 3:
            clean_path = clean_params[2]
            step['imagePath'] = clean_path
            step['fileName'] = clean_path
        self.steps.append(step)
        self.vars['?'] = '0'

    def _do_if(self, lines: List[str], idx: int) -> Tuple[int, int]:
        raw = lines[idx].strip()
        cond = re.sub(r'\s*;\s*then\s*$', '', raw[3:].strip())
        cond_ok = self._eval_cond(cond)
        then_b = []; else_b = []; cur = then_b
        depth, i = 0, idx + 1
        while i < len(lines):
            l = lines[i].strip()
            if l == 'fi' and depth == 0: break
            if l == 'else' and depth == 0: cur = else_b; i += 1; continue
            if 'if ' in l: depth += 1
            if 'fi' in l and depth > 0: depth -= 1
            cur.append(lines[i]); i += 1
        fi_idx = i
        if cond_ok: self._exec(then_b, 0)
        elif else_b: self._exec(else_b, 0)
        self.vars['?'] = '0'
        return 0, fi_idx + 1

    def _do_for(self, lines, idx):
        m = re.match(r'^\s*for\s+(\w+)\s+in\s+(.+?)\s*(?:;\s*do\s*)?$', lines[idx].strip())
        if not m: return 0, idx+1
        items = shlex.split(expand_vars(m.group(2).strip(), self.vars))
        body, i = [], idx+1
        while i < len(lines) and lines[i].strip() != 'do': i += 1
        i += 1
        while i < len(lines) and lines[i].strip() != 'done': body.append(lines[i]); i += 1
        for item in items:
            self.vars[m.group(1)] = item
            self._exec(body, 0)
        return 0, i+1

    def _do_while(self, lines, idx):
        cond = re.sub(r'\s*;\s*do\s*$', '', re.sub(r'^\s*while\s+', '', lines[idx].strip()))
        body, i = [], idx+1
        while i < len(lines) and lines[i].strip() != 'do': i += 1
        i += 1
        while i < len(lines) and lines[i].strip() != 'done': body.append(lines[i]); i += 1
        if self._eval_cond(cond): self._exec(body, 0)
        return 0, i+1

    def _do_case(self, lines, idx):
        vv = expand_vars(re.sub(r'\s+in\s*$', '', re.sub(r'^\s*case\s+', '', lines[idx].strip())), self.vars)
        i = idx+1
        while i < len(lines):
            l = lines[i].strip()
            if l == 'esac': break
            if ')' in l:
                pat = l.split(')')[0].strip()
                if pat == '*' or pat == vv:
                    i += 1; branch = []
                    while i < len(lines) and not lines[i].strip().endswith(';;') and lines[i].strip() != 'esac':
                        branch.append(lines[i]); i += 1
                    self._exec(branch, 0)
                    if i < len(lines) and lines[i].strip().endswith(';;'): i += 1
                    break
            i += 1
        while i < len(lines) and lines[i].strip() != 'esac': i += 1
        return 0, i+1

    def _skip_func(self, lines, idx):
        i = idx+1
        while i < len(lines) and lines[i].strip() != '}': i += 1
        return i+1

    def run_to_jsonl(self, script_path, rom_dir, sandbox_dir=None):
        content = open(script_path).read()
        result = self.run(content, rom_dir, script_path)
        if sandbox_dir is None: sandbox_dir = tempfile.mkdtemp(prefix='sh_simulator_')
        p = os.path.join(sandbox_dir, 'commands.jsonl')
        result.to_jsonl(p)
        return p
