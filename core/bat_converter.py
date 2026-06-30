# flash_tool/core/bat_converter.py
# -*- coding: utf-8 -*-
"""
core/bat_converter.py — BAT -> Shell 转换器主函数
辅助函数（pv/pp/cic/generate_header/try_file_ops/post_process/syntax_check）
已拆分至 core/bat_helpers.py。
"""

import os
import re
import time
import subprocess
from typing import Tuple, List

from config import ROM_DIR, PUBLIC_DIR, logger
from core.bat_helpers import (
    pv as _pv,
    pp as _pp,
    cic as _cic,
    SKIP_PATTERNS,
    generate_header,
    try_file_ops,
    post_process,
    syntax_check,
)


def convert_bat_to_sh(content: str, script_dir: str = '', _depth: int = 0) -> Tuple[str, List[str], List[str], dict]:
    """
    BAT -> Shell 转换器（参考豆包转换器优化版）
    两遍扫描 + 缩进追踪 + 完整语法支持

    Returns:
        (sh_content, syntax_errors, warnings, stats)
    """
    if _depth >= 5:
        return ('# [WARN] 子脚本递归深度超限，已跳过\n', [], ['递归深度超限'], {})
    lines = re.split(r'\r?\n', content)
    output = []
    stats = {'total_lines': 0, 'flash_commands': 0, 'erase_commands': 0,
             'reboot_commands': 0, 'condition_blocks': 0, 'loop_blocks': 0}

    # 第一遍：收集变量名和标签
    var_names = set()
    labels = {}  # label_name -> line_index
    gotos = []    # list of (line_index, label_name)
    for idx, line in enumerate(lines):
        s = line.strip().lstrip('@').strip()
        lm = re.match(r'^:([a-zA-Z0-9_\-]+)', s)
        if lm:
            labels[lm.group(1)] = idx
        sm = re.match(r'^set\s+"?([a-zA-Z0-9_]+)\s*=', s, re.IGNORECASE)
        if sm: var_names.add(sm.group(1))
        gm = re.match(r'^goto\s+:?([a-zA-Z0-9_\-]+)', s, re.IGNORECASE)
        if gm:
            gotos.append((idx, gm.group(1)))

    # 头部（shebang、环境检测、辅助函数、断点续刷）
    output.extend(generate_header(script_dir))

    # 第二遍：逐行转换
    if_depth = 0
    for_depth = 0
    if_stack = []
    block_stack = []  # 追踪块类型: 'if' 或 'for'
    fastboot_step_counter = 0  # C2: fastboot 步骤计数器

    def _indent():
        return '    ' * (if_depth + for_depth)

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        i += 1
        if not stripped:
            output.append('')
            continue
        if stripped.startswith('@'):
            stripped = stripped[1:].strip()
        lower = stripped.lower()

        # 统一过滤 Windows 专属指令
        skip_matched = False
        for pat, replacement in SKIP_PATTERNS:
            if re.match(pat, lower):
                if replacement:
                    output.append(_indent() + replacement)
                skip_matched = True
                break
        if skip_matched:
            continue

        # 注释
        if stripped.startswith('::') or lower.startswith('rem '):
            c = stripped[2:].strip() if stripped.startswith('::') else stripped[4:].strip()
            output.append(_indent() + f'# {c}')
            continue

        # set /a
        sm = re.match(r'^set\s+/a\s+([a-zA-Z0-9_]+)\s*=\s*(.+)$', stripped, re.IGNORECASE)
        if sm:
            output.append(_indent() + f'{sm.group(1)}=$(( {_pv(sm.group(2))} ))')
            continue

        # set /p
        sm = re.match(r'^set\s+/p\s+([a-zA-Z0-9_]+)\s*=?\s*"?([^"]*)"?$', stripped, re.IGNORECASE)
        if sm:
            output.append(_indent() + f'read -p "{_pv(sm.group(2) or chr(35821)+chr(36755)+chr(20837))}" {sm.group(1)}')
            continue

        # set VAR=value
        sm = re.match(r'^set\s+"?([a-zA-Z0-9_]+)=([^"]*(?:"[^"]*"[^"]*)*)"?$', stripped, re.IGNORECASE)
        if sm:
            output.append(_indent() + f'{sm.group(1)}="{_pv(sm.group(2).strip().strip(chr(34)))}"')
            continue

        # echo
        if re.match(r'^echo\s', lower) or lower == 'echo':
            if lower in ('echo', 'echo.'):
                output.append(_indent() + 'echo ""')
            else:
                msg = _pv(re.sub(r'^echo\s+', '', stripped, flags=re.IGNORECASE))
                if (msg.startswith('"') and msg.endswith('"')) or (msg.startswith("'") and msg.endswith("'")):
                    output.append(_indent() + f'echo {msg}')
                else:
                    output.append(_indent() + f'echo "{msg}"')
            continue
        if re.match(r'^echo\.', lower):
            output.append(_indent() + 'echo ""')
            continue

        # Windows 文件操作命令（cd/dir/del/rd/md/copy/move/ren/type/findstr/start/exit）
        file_ops_result = try_file_ops(stripped, lower, _indent())
        if file_ops_result is not None:
            output.extend(file_ops_result)
            continue

        # goto
        gm = re.match(r'^goto\s+:?([a-zA-Z0-9_\-]+)', stripped, re.IGNORECASE)
        if gm:
            label_name = gm.group(1)
            goto_line_idx = i - 1
            target_idx = labels.get(label_name, -1)
            if target_idx >= 0 and target_idx < goto_line_idx:
                output.append(_indent() + f'while true; do')
                output.append(_indent() + f'    {label_name}_func')
                output.append(_indent() + f'    break')
                output.append(_indent() + f'done')
            else:
                output.append(_indent() + f'{label_name}_func')
            continue

        # :label
        lm = re.match(r'^:([a-zA-Z0-9_\-]+)', stripped)
        if lm:
            if lm.group(1).lower() == 'eof':
                output.append(_indent() + 'return 0 2>/dev/null || exit 0')
            else:
                label_name = lm.group(1)
                has_forward_goto = any(
                    g_label == label_name and g_idx < i - 1
                    for g_idx, g_label in gotos
                )
                output.append('')
                output.append(f'{label_name}_func() {{')
                if has_forward_goto:
                    output.append('    :')
            continue

        # call
        clm = re.match(r'^call\s+:?([a-zA-Z0-9_\-\.]+)(.*)$', stripped, re.IGNORECASE)
        if clm:
            target = clm.group(1)
            args = _pv(clm.group(2).strip())
            if target.lower().endswith(('.bat', '.cmd')):
                sub_script_path = None
                for search_dir in [script_dir, ROM_DIR, PUBLIC_DIR, '.']:
                    if not search_dir:
                        continue
                    candidate = os.path.join(search_dir, target)
                    if os.path.exists(candidate):
                        sub_script_path = candidate
                        break
                if sub_script_path:
                    try:
                        with open(sub_script_path, 'r', encoding='utf-8', errors='ignore') as sf:
                            sub_content = sf.read()
                        sub_sh, _, _, _ = convert_bat_to_sh(sub_content, os.path.dirname(sub_script_path), _depth=_depth+1)
                        output.append(_indent() + f'# --- 内联子脚本: {target} ---')
                        for sub_line in sub_sh.split('\n'):
                            if sub_line.startswith('#!') or sub_line.startswith('SCRIPT_DIR=') or sub_line.startswith('FASTBOOT='):
                                continue
                            if sub_line.strip():
                                output.append(_indent() + sub_line)
                        output.append(_indent() + f'# --- 子脚本结束: {target} ---')
                    except Exception as e:
                        output.append(_indent() + f'# [WARN] 子脚本读取失败: {e}')
                        sh_name = re.sub(r'\.(bat|cmd)$', '.sh', target, flags=re.IGNORECASE)
                        output.append(_indent() + f'bash "{sh_name}" {args}'.strip())
                else:
                    sh_name = re.sub(r'\.(bat|cmd)$', '.sh', target, flags=re.IGNORECASE)
                    output.append(_indent() + f'# [WARN] 子脚本不存在，尝试 source: {target}')
                    output.append(_indent() + f'source "{sh_name}" {args}'.strip())
            else:
                output.append(_indent() + f'{target} {args}'.strip())
            continue

        # if errorlevel
        em = re.match(r'^if\s+errorlevel\s+(\d+)', stripped, re.IGNORECASE)
        if em:
            output.append(_indent() + f'if [ $? -ge {em.group(1)} ]; then')
            if_depth += 1; if_stack.append({'hasElse': False}); block_stack.append('if'); stats['condition_blocks'] += 1
            continue

        # if not exist
        nem = re.match(r'^if\s+not\s+exist\s+"?([^"]+)"?\s*\(', stripped, re.IGNORECASE)
        if nem:
            output.append(_indent() + f'if [ ! -f "{_pp(_pv(nem.group(1).strip().strip(chr(34))))}" ]; then')
            if_depth += 1; if_stack.append({'hasElse': False}); block_stack.append('if'); stats['condition_blocks'] += 1
            continue

        # if exist
        em = re.match(r'^if\s+exist\s+"?([^"]+)"?\s*\(', stripped, re.IGNORECASE)
        if em:
            output.append(_indent() + f'if [ -f "{_pp(_pv(em.group(1).strip().strip(chr(34))))}" ]; then')
            if_depth += 1; if_stack.append({'hasElse': False}); block_stack.append('if'); stats['condition_blocks'] += 1
            continue

        # if not <cond> (块形式)
        nm = re.match(r'^if\s+not\s+(.+?)\s+\(', stripped, re.IGNORECASE)
        if nm:
            output.append(_indent() + f'if ! {_cic(nm.group(1))}; then')
            if_depth += 1; if_stack.append({'hasElse': False}); block_stack.append('if'); stats['condition_blocks'] += 1
            continue

        # if ... <单行命令>（无括号单行 if）
        slm = re.match(r'^if\s+(?:not\s+)?(?:/i\s+)?(.+?)(==|equ|neq|geq|leq|gtr|lss)\s*(.+?)\s+(.+)$', stripped, re.IGNORECASE)
        if slm and not stripped.rstrip().endswith('('):
            cond_str = f'{slm.group(1)} {slm.group(2)} {slm.group(3)}'
            cmd_part = slm.group(4).strip()
            scm = re.match(r'^set\s+"?([a-zA-Z0-9_]+)=([^"]*(?:"[^"]*"[^"]*)*)"?$', cmd_part, re.IGNORECASE)
            if scm:
                cmd_part = f'{scm.group(1)}="{_pv(scm.group(2).strip().strip(chr(34)))}"'
            else:
                cmd_part = _pv(cmd_part)
            output.append(_indent() + f'if {_cic(cond_str)}; then {cmd_part}; fi')
            continue

        # if <cond> (块形式)
        im = re.match(r'^if\s+(.+?)\s+\(', stripped, re.IGNORECASE)
        if im:
            output.append(_indent() + f'if {_cic(im.group(1))}; then')
            if_depth += 1; if_stack.append({'hasElse': False}); block_stack.append('if'); stats['condition_blocks'] += 1
            continue

        # else
        if re.match(r'^\)\s*else\s*\(', lower) or lower == 'else':
            if if_stack:
                if_stack[-1]['hasElse'] = True
                if_depth -= 1
                output.append(_indent() + 'else')
                if_depth += 1
            continue

        # ) 闭合——根据 block_stack 判断闭合类型
        if stripped == ')':
            if block_stack:
                bt = block_stack.pop()
                if bt == 'if':
                    has_else = if_stack.pop()['hasElse'] if if_stack else False
                    if_depth -= 1
                    output.append(_indent() + 'fi')
                else:
                    for_depth -= 1
                    output.append(_indent() + 'done')
            continue

        # for %%i in (...) do (
        fm = re.match(r'^for\s+%%([a-zA-Z])\s+in\s*\((.+?)\)\s+do\s*\(', stripped, re.IGNORECASE)
        if fm:
            output.append(_indent() + f'for {fm.group(1)} in {_pv(fm.group(2))}; do')
            for_depth += 1; block_stack.append('for'); stats['loop_blocks'] += 1
            continue

        # for %%i in (...) do <单行>
        fsm = re.match(r'^for\s+%%([a-zA-Z])\s+in\s*\((.+?)\)\s+do\s+(.+)$', stripped, re.IGNORECASE)
        if fsm:
            output.append(_indent() + f'for {fsm.group(1)} in {_pv(fsm.group(2))}; do')
            output.append(_indent() + f'    {_pv(fsm.group(3))}')
            output.append(_indent() + 'done')
            continue

        # for /f
        ffm = re.match(r"^for\s+/f\s+\"?([^\"]*)\"?\s+%%([a-zA-Z])\s+in\s*\('([^']+)'\)\s+do\s*\(", stripped, re.IGNORECASE)
        if not ffm:
            ffm = re.match(r'^for\s+/f\s+"?([^"]*)"?\s+%%([a-zA-Z])\s+in\s*\(([^)]+)\)\s+do\s*\(', stripped, re.IGNORECASE)
        if ffm:
            options = ffm.group(1)
            loop_var = ffm.group(2)
            source = ffm.group(3)
            is_command = re.match(r"^for\s+/f\s+\"?[^\"]*\"?\s+%%[a-zA-Z]\s+in\s*\('([^']+)'\)", stripped, re.IGNORECASE)

            tokens_m = re.search(r'tokens=(\d+)', options, re.IGNORECASE)
            delims_m = re.search(r'delims=([^"\s]*)', options, re.IGNORECASE)
            token_num = int(tokens_m.group(1)) if tokens_m else 1
            delims = delims_m.group(1) if delims_m else ' '

            if is_command:
                if token_num == 1 and delims != ' ':
                    output.append(_indent() + f'while IFS=\'{delims}\' read -r {loop_var} rest; do')
                else:
                    output.append(_indent() + f'while read -r {loop_var}; do')
                output.append(_indent() + f'    # source: < <({_pv(source.strip())})')
                for_depth += 1; block_stack.append('for'); stats['loop_blocks'] += 1
            else:
                file_path = _pp(_pv(source.strip()))
                if token_num == 1 and delims != ' ':
                    output.append(_indent() + f'while IFS=\'{delims}\' read -r {loop_var} rest; do')
                else:
                    output.append(_indent() + f'while read -r {loop_var}; do')
                output.append(_indent() + f'    # source: < {file_path}')
                for_depth += 1; block_stack.append('for'); stats['loop_blocks'] += 1
            continue

        # timeout / chcp
        if re.match(r'^(timeout|chcp)\b', lower):
            output.append(_indent() + f'# [BAT] {stripped}')
            continue

        # 普通命令
        p = _pv(stripped)
        p = re.sub(r'[a-zA-Z_0-9/\\]*[/\\]fastboot(?:\.exe)?', '$FASTBOOT', p, flags=re.IGNORECASE)
        p = re.sub(r'\s*>nul\s*', ' >/dev/null ', p, flags=re.IGNORECASE)
        p = re.sub(r'\s*2>nul\s*', ' 2>/dev/null ', p, flags=re.IGNORECASE)
        p = re.sub(r'\s*>[>]?((?!/?dev/null)[^\n])*$', '', p)
        p = p.replace('2>&1', '2>/dev/null')
        p = re.sub(r'%%([a-zA-Z])', r'$\1', p)
        p = re.sub(r'\$\{?TOOL_PATH\}?', '$FASTBOOT', p)
        p = re.sub(r'\$\{?CURRENT_DIR\}?(/tools/fastboot(\.exe)?)\b', '$FASTBOOT', p)
        p = re.sub(r'\$([a-zA-Z_]\w*)(_[a-zA-Z0-9_])', r'${\1}\2', p)
        p = re.sub(r'\$\{f%\.?\w*\}', '$(basename "$f" .img)', p)
        def _quote_fb_args(m):
            cmd = m.group(0)
            parts = cmd.split(None, 1)
            if len(parts) == 2:
                args = parts[1]
                args = re.sub(r'(?<!")(\$ [{]?[a-zA-Z_][a-zA-Z0-9_]*[}]?(?:_[a-zA-Z0-9_]*)*)', r'"\1"', args)
                return parts[0] + ' ' + args
            return cmd
        p = re.sub(r'\$FASTBOOT\s+.+', _quote_fb_args, p)

        # 修复：fastboot devices 的退出码判断
        p = re.sub(r'if \[ \$\? -ge 1 \]', 'if ! "${FASTBOOT}" devices 2>/dev/null | grep -q "fastboot"', p)
        p = re.sub(r'if \[ \$\? -ne 0 \]', 'if ! "${FASTBOOT}" devices 2>/dev/null | grep -q "fastboot"', p)

        # 修复：if [ ! -f "$FASTBOOT" ] → command -v fastboot
        p = re.sub(r'\[ ! -f "\$\{?FASTBOOT\}?" \]', 'if ! command -v fastboot >/dev/null 2>&1; then', p)
        p = re.sub(r'\[ -f "\$\{?FASTBOOT\}?" \]', 'if command -v fastboot >/dev/null 2>&1; then', p)

        # C2: fastboot 命令包装为 run_step
        is_fastboot_cmd = '$FASTBOOT' in p or re.search(r'fastboot(?:\.exe)?\s+', p, re.IGNORECASE)
        if is_fastboot_cmd:
            fastboot_step_counter += 1
            fb_cmd_match = re.search(r'\$FASTBOOT\s+(\w+)', p)
            fb_cmd_desc = fb_cmd_match.group(1) if fb_cmd_match else 'fastboot'
            if 'flash' in fb_cmd_desc:
                stats['flash_commands'] += 1
            elif 'erase' in fb_cmd_desc or 'delete' in fb_cmd_desc:
                stats['erase_commands'] += 1
            if fb_cmd_desc == 'reboot':
                stats['reboot_commands'] += 1
            fb_part_match = re.search(r'\$FASTBOOT\s+\w+\s+(\S+)', p)
            fb_part = fb_part_match.group(1).strip('"') if fb_part_match else ''
            step_desc = f"fastboot {fb_cmd_desc}"
            if fb_part:
                step_desc += f" {fb_part}"
            if fb_cmd_desc == 'reboot':
                reboot_target = fb_part.strip('"') if fb_part else ''
                output.append(_indent() + f'__log_step {fastboot_step_counter} "{step_desc}"')
                output.append(_indent() + p)
                if reboot_target in ('fastboot', 'bootloader', 'fastbootd'):
                    output.append(_indent() + '__wait_for_device "fastboot" 180')
                elif reboot_target == 'edl':
                    output.append(_indent() + '__wait_for_device "edl" 180')
                output.append(_indent() + f'__mark_progress {fastboot_step_counter}')
            else:
                output.append(_indent() + f'run_step {fastboot_step_counter} "{step_desc}" {p}')
        else:
            output.append(_indent() + p)

    # 闭合未闭合块
    while if_depth > 0:
        output.append('fi'); if_depth -= 1
    while for_depth > 0:
        output.append('done'); for_depth -= 1

    output.append('')
    output.append('# C3: 脚本末尾清理')
    output.append('rm -f "${__PROGRESS_FILE}"')
    output.append('echo "PROGRESS:done:刷机脚本执行完成" >&2')
    output.append('')
    output.append('# ========================================')
    output.append('# 转换完成，Termux 中执行:')
    output.append('#   chmod +x script.sh && ./script.sh')
    output.append('# ========================================')

    sh_content = '\n'.join(output)

    # 全局后处理 + 最终自检
    sh_content, warnings = post_process(sh_content)

    # B1: bash -n 语法检查
    sh_content, syntax_errors = syntax_check(sh_content, output)

    return sh_content, syntax_errors, warnings, stats
