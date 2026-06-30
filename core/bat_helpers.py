# -*- coding: utf-8 -*-
# flash_tool/core/bat_helpers.py
"""
core/bat_helpers.py — BAT -> Shell 转换器辅助函数
从 core/bat_converter.py 拆分而来，函数逻辑保持不变。
"""

import os
import re
import time
import subprocess
from typing import List, Optional, Tuple

from config import ROM_DIR, PUBLIC_DIR, logger


# ============ 跳过模式（Windows 专属指令过滤） ============
SKIP_PATTERNS = [
    (r'^@?echo\s+(off|on)$', '# @echo off (Bash 默认不回显)'),
    (r'^@?setlocal\b', None),
    (r'^@?endlocal\b', None),
    (r'^@?chcp\b', None),
    (r'^@?color\b', None),
    (r'^@?cls$', None),
    (r'^@?title\b', None),
    (r'^@?pause\b', '# [SKIP] pause（原脚本等待按键，自动跳过）'),
    (r'^@?timeout\s+/t\b', None),
]


# ============ 变量 / 路径 / 条件转换 ============

def pv(s: str) -> str:
    """统一变量替换"""
    s = re.sub(r'%~dp0', '$__SCRIPT_DIR/', s, flags=re.IGNORECASE)
    s = re.sub(r'%~f0', '"$0"', s, flags=re.IGNORECASE)
    s = re.sub(r'%~nx0', '$(basename "$0")', s, flags=re.IGNORECASE)
    s = re.sub(r'%(\d)', r'"$\1"', s)
    s = s.replace('%*', '"$@"')
    s = re.sub(r'%errorlevel%', '$?', s, flags=re.IGNORECASE)
    s = re.sub(r'%cd%', '$PWD', s, flags=re.IGNORECASE)
    s = re.sub(r'%date%', '$(date)', s, flags=re.IGNORECASE)
    s = re.sub(r'%time%', '$(date +%T)', s, flags=re.IGNORECASE)
    s = s.replace('%random%', '$RANDOM')
    s = re.sub(r'%([a-zA-Z0-9_]+)%', r'${\1}', s)
    # %%~nf → ${n%.*}（for 循环变量文件名无扩展名，必须在 %%x 之前）
    s = re.sub(r'%%~n([a-zA-Z])', r'${\1%.*}', s)
    # %%~xf → ${f##*.}（for 循环变量扩展名）
    s = re.sub(r'%%~x([a-zA-Z])', r'${\1##*.}', s)
    # %%~f → $f（for 循环变量完整文件名，必须在 %%x 之前）
    s = re.sub(r'%%~([a-zA-Z])', r'$\1', s)
    # %%x → $x（普通 for 循环变量）
    s = re.sub(r'%%([a-zA-Z])', r'$\1', s)
    # !VAR! → $VAR（延迟扩展）
    s = re.sub(r'!([a-zA-Z0-9_]+)!', r'${\1}', s)
    s = s.replace('\\', '/')
    # 如果是 set VAR=...fastboot... 形式，整个值替换为 $FASTBOOT
    s = re.sub(r'^(set\s+)(\w+)=(.*)fastboot.*$', r'\1\2=$FASTBOOT', s, flags=re.IGNORECASE)
    return s


def pp(p: str) -> str:
    """路径转换"""
    p = p.replace('\\', '/')
    p = re.sub(r'^([A-Za-z]):/', lambda m: f'/storage/{m.group(1).lower()}/', p)
    return p


def cic(cond: str) -> str:
    """if 条件转换"""
    cond = re.sub(r'^/i\s+', '', cond, flags=re.IGNORECASE)
    em = re.match(r'^exist\s+(.+)', cond, re.IGNORECASE)
    if em:
        return f'[ -f "{pv(pp(em.group(1).strip()))}" ]'
    dm = re.match(r'^defined\s+([a-zA-Z0-9_]+)', cond, re.IGNORECASE)
    if dm:
        return f'[ -n "${dm.group(1)}" ]'
    eqm = re.match(r'^(.+?)\s*==\s*(.+)$', cond)
    if eqm:
        return f'[ "{pv(eqm.group(1).strip().strip(chr(34)))}" = "{pv(eqm.group(2).strip().strip(chr(34)))}" ]'
    opm = re.match(r'^(.+?)\s+(equ|neq|geq|leq|gtr|lss)\s+(.+)$', cond, re.IGNORECASE)
    if opm:
        op_map = {'equ': '-eq', 'neq': '-ne', 'geq': '-ge', 'leq': '-le', 'gtr': '-gt', 'lss': '-lt'}
        left = pv(opm.group(1).strip())
        right = pv(opm.group(3).strip())
        return f'[ "{left}" {op_map.get(opm.group(2).lower(), "-eq")} "{right}" ]'
    return f'[ "{pv(cond)}" ]'


# ============ 头部生成 ============

def generate_header(script_dir: str) -> List[str]:
    """生成 Shell 脚本头部（shebang、环境检测、辅助函数、断点续刷）"""
    lines = []
    lines.append('#!/data/data/com.termux/files/usr/bin/bash')
    lines.append('# 由 Termux 网页刷机工具自动转换（BAT -> Shell）')
    lines.append(f'# 转换时间: {time.strftime("%Y-%m-%d %H:%M:%S")}')
    lines.append('set -o pipefail')
    lines.append(f'__SCRIPT_DIR="{script_dir}"')
    lines.append('FASTBOOT="${FASTBOOT:-fastboot}"')
    lines.append('__TOOL_DIR="${__SCRIPT_DIR}/resources"')
    lines.append('')
    # C1: 断点续刷 + 进度埋点辅助代码（变量加 __ 前缀避免与原厂脚本冲突）
    lines.append('__PROGRESS_FILE="${__SCRIPT_DIR}/.flash_progress"')
    lines.append('')
    lines.append('# 进度上报函数')
    lines.append('__log_step() {')
    lines.append('    local idx=$1 desc=$2')
    lines.append('    echo "[步骤 ${idx}] ${desc}"')
    lines.append('    echo "PROGRESS:${idx}:${desc}" >&2')
    lines.append('}')
    lines.append('')
    lines.append('__mark_progress() {')
    lines.append('    echo "$1" > "${__PROGRESS_FILE}"')
    lines.append('}')
    lines.append('')
    lines.append('# 断点续刷初始化')
    lines.append('__STEP_CURRENT=0')
    lines.append('if [ -f "${__PROGRESS_FILE}" ]; then')
    lines.append('    __STEP_CURRENT=$(cat "${__PROGRESS_FILE}")')
    lines.append('    echo "[断点续刷] 从第 ${__STEP_CURRENT} 步继续" >&2')
    lines.append('fi')
    lines.append('')
    lines.append('# 执行宏：跳过已完成 + 进度上报')
    lines.append('run_step() {')
    lines.append('    local idx=$1 desc=$2; shift 2')
    lines.append('    if [ "${idx}" -le "${__STEP_CURRENT}" ]; then return 0; fi')
    lines.append('    __log_step "${idx}" "${desc}"')
    lines.append('    "$@"')
    lines.append('    local ret=$?')
    lines.append('    if [ ${ret} -eq 0 ]; then __mark_progress "${idx}"; fi')
    lines.append('    return ${ret}')
    lines.append('}')
    lines.append('')
    # 等待设备重连函数（reboot 后自动等待设备重新上线）
    lines.append('__wait_for_device() {')
    lines.append('    local mode="${1:-fastboot}"')
    lines.append('    local max_wait="${2:-180}"')
    lines.append('    local count=0')
    lines.append('    echo "[等待重连] 设备重启中，等待 ${mode} 设备上线（最长 ${max_wait} 秒）..." >&2')
    lines.append('    echo "PROGRESS:wait:等待设备进入 ${mode} 模式" >&2')
    lines.append('    # 先等 3 秒，让设备彻底离线，避免检测到重启前的设备')
    lines.append('    sleep 3')
    lines.append('    while [ ${count} -lt ${max_wait} ]; do')
    lines.append('        if [ "${mode}" = "fastboot" ]; then')
    lines.append('            if "${FASTBOOT}" devices 2>/dev/null | grep -q "fastboot"; then')
    lines.append('                echo "[等待重连] 检测到 Fastboot 设备，继续执行（等待了 ${count} 秒）" >&2')
    lines.append('                return 0')
    lines.append('            fi')
    lines.append('        elif [ "${mode}" = "adb" ]; then')
    lines.append('            if adb devices 2>/dev/null | grep -q "device$"; then')
    lines.append('                echo "[等待重连] 检测到 ADB 设备，继续执行（等待了 ${count} 秒）" >&2')
    lines.append('                return 0')
    lines.append('            fi')
    lines.append('        fi')
    lines.append('        sleep 2')
    lines.append('        count=$((count + 2))')
    lines.append('        if [ $((count % 10)) -eq 0 ]; then')
    lines.append('            echo "[等待重连] 尚未检测到设备，已等待 ${count} 秒..." >&2')
    lines.append('        fi')
    lines.append('    done')
    lines.append('    echo "[错误] 等待 ${mode} 设备超时（${max_wait} 秒），刷机终止" >&2')
    lines.append('    echo "PROGRESS:error:设备重启超时" >&2')
    lines.append('    exit 1')
    lines.append('}')
    lines.append('')
    # 环境前置检测：fastboot 是否可用
    lines.append('# 环境前置检测：fastboot 是否可用')
    lines.append('if ! command -v "${FASTBOOT}" >/dev/null 2>&1; then')
    lines.append('    echo "[错误] 未找到 fastboot 命令，请先执行: pkg install android-tools" >&2')
    lines.append('    exit 1')
    lines.append('fi')
    lines.append('')
    lines.append('# ============================================================')
    lines.append('#                    原厂脚本执行逻辑')
    lines.append('# ============================================================')
    lines.append('')
    return lines


# ============ 文件操作命令处理 ============

def try_file_ops(stripped: str, lower: str, indent: str) -> Optional[List[str]]:
    """
    尝试匹配 Windows 文件操作命令（cd/dir/del/rd/md/copy/move/ren/type/findstr/start/exit）。
    匹配则返回输出行列表，不匹配返回 None。
    """
    # cd
    cm = re.match(r'^cd\s+(?:/d\s+)?(.+)$', stripped, re.IGNORECASE)
    if cm:
        return [indent + f'cd "{pp(pv(cm.group(1).strip()))}" || exit 1']
    # dir
    if re.match(r'^dir\b', lower):
        rest = re.sub(r'^dir\s*', '', stripped, flags=re.IGNORECASE)
        rest = rest.replace('/s', '-R').replace('/b', '-1').replace('/w', '-C')
        return [indent + f'ls {pv(rest)}'.strip()]
    # del / erase
    if re.match(r'^(del|erase)\b', lower):
        rest = re.sub(r'^(del|erase)\s*', '', stripped, flags=re.IGNORECASE)
        rest = rest.replace('/f', '-f').replace('/s', '-r').replace('/q', '')
        return [indent + f'rm -f "{pp(pv(rest.strip()))}"']
    # rd / rmdir
    if re.match(r'^(rd|rmdir)\b', lower):
        rest = re.sub(r'^(rd|rmdir)\s*', '', stripped, flags=re.IGNORECASE)
        rest = rest.replace('/s', '').replace('/q', '')
        return [indent + f'rm -rf "{pp(pv(rest.strip()))}"']
    # md / mkdir
    if re.match(r'^(md|mkdir)\b', lower):
        rest = re.sub(r'^(md|mkdir)\s*', '', stripped, flags=re.IGNORECASE)
        return [indent + f'mkdir -p "{pp(pv(rest.strip()))}"']
    # copy
    if re.match(r'^copy\b', lower):
        rest = re.sub(r'^copy\s*', '', stripped, flags=re.IGNORECASE)
        parts = rest.split(None, 1)
        if len(parts) >= 2:
            return [indent + f'cp -f "{pp(pv(parts[0]))}" "{pp(pv(parts[1]))}"']
        return []
    # move
    if re.match(r'^move\b', lower):
        rest = re.sub(r'^move\s*', '', stripped, flags=re.IGNORECASE)
        parts = rest.split(None, 1)
        if len(parts) >= 2:
            return [indent + f'mv -f "{pp(pv(parts[0]))}" "{pp(pv(parts[1]))}"']
        return []
    # ren / rename
    if re.match(r'^(ren|rename)\b', lower):
        rest = re.sub(r'^(ren|rename)\s*', '', stripped, flags=re.IGNORECASE)
        parts = rest.split(None, 1)
        if len(parts) >= 2:
            return [indent + f'mv -f "{pp(pv(parts[0]))}" "{pp(pv(parts[1]))}"']
        return []
    # type
    if re.match(r'^type\b', lower):
        rest = re.sub(r'^type\s*', '', stripped, flags=re.IGNORECASE)
        return [indent + f'cat "{pp(pv(rest.strip()))}"']
    # findstr
    if re.match(r'^findstr\b', lower):
        rest = re.sub(r'^findstr\s*', '', stripped, flags=re.IGNORECASE)
        rest = rest.replace('/i', '-i').replace('/n', '-n')
        return [indent + f'grep {pv(rest)}'.strip()]
    # start
    stm = re.match(r'^start\s+(.+)$', stripped, re.IGNORECASE)
    if stm:
        return [indent + f'termux-open "{pv(stm.group(1).strip())}"']
    # exit
    if re.match(r'^exit\b', lower):
        cm = re.search(r'exit\s+(?:/b\s+)?(\d+)', stripped, re.IGNORECASE)
        return [indent + f'exit {cm.group(1) if cm else 0}']
    return None


# ============ 全局后处理 ============

def post_process(sh_content: str) -> Tuple[str, List[str]]:
    """
    全局后处理：修复所有 handler 无法覆盖的问题 + 最终自检。
    返回 (处理后的 sh_content, warnings 列表)。
    """
    warnings = []

    # 1. TOOL_PATH/...fastboot.exe → $FASTBOOT（变量值中含 fastboot 的 set 语句）
    sh_content = re.sub(r'^(\s*)TOOL_PATH="[^"]*fastboot[^"]*"',
                        r'\1TOOL_PATH="$FASTBOOT"', sh_content, flags=re.MULTILINE | re.IGNORECASE)
    # 2. ${TOOL_PATH} → $FASTBOOT（引用 fastboot 变量的地方）
    sh_content = re.sub(r'\$\{?TOOL_PATH\}?', '$FASTBOOT', sh_content)
    # 3. ${CURRENT_DIR}tools/fastboot.exe → $FASTBOOT
    sh_content = re.sub(r'\$\{?CURRENT_DIR\}?(/tools/fastboot(\.exe)?)\b', '$FASTBOOT', sh_content)
    # 4. if [ ! -f "$FASTBOOT" ] → command -v fastboot（只替换条件部分，保留外层 if/then）
    sh_content = re.sub(r'\[ ! -f "\$\{?FASTBOOT\}?" \]', '! command -v fastboot >/dev/null 2>&1', sh_content)
    sh_content = re.sub(r'\[ -f "\$\{?FASTBOOT\}?" \]', 'command -v fastboot >/dev/null 2>&1', sh_content)
    # 5. if [ $? -ge 1 ] → grep 判断（fastboot devices 退出码永远为 0）
    sh_content = re.sub(r'if \[ \$\? -ge 1 \]', 'if ! "${FASTBOOT}" devices 2>/dev/null | grep -q "fastboot"', sh_content)
    sh_content = re.sub(r'if \[ \$\? -ne 0 \]', 'if ! "${FASTBOOT}" devices 2>/dev/null | grep -q "fastboot"', sh_content)
    # 6. ${p}_a-cow → ${p}_a_cow（变量拼接修复）
    sh_content = re.sub(r'\$\{?p\}?_a-cow', '${p}_a_cow', sh_content)
    sh_content = re.sub(r'\$\{?p\}?_b-cow', '${p}_b_cow', sh_content)
    # 7. >/dev/null 2 → 2>/dev/null || true（错误重定向修复）
    sh_content = re.sub(r'>/dev/null 2\s*$', '2>/dev/null || true', sh_content, flags=re.MULTILINE)
    # 8. name="${f%.*}" → name=$(basename "$f" .img)（路径提取修复）
    sh_content = re.sub(r'name="\$\{f%\.\*\}"', 'name=$(basename "$f" .img)', sh_content)
    # 9. run_step N "fastboot fastboot" → 自动生成描述
    def _fix_step_desc(m):
        step_num = m.group(1)
        rest = m.group(2)
        # 从命令中提取操作类型和分区名（跳过 --flag 参数，$FASTBOOT 可能被引号包裹）
        # 先去掉末尾的重定向部分
        clean_rest = re.sub(r'\s*2>/dev/null\s*\|\|\s*true\s*$', '', rest).strip()
        clean_rest = re.sub(r'\s*>\s*/dev/null\s*$', '', clean_rest).strip()
        # 找到 $FASTBOOT 后面的第一个非 -- 开头的词作为子命令
        fb_m = re.search(r'\$FASTBOOT["\s]+(?:(?:--?\S+\s+)*)(\w[\w-]*)(?:\s+(.+?))?$', clean_rest)
        if fb_m:
            cmd = fb_m.group(1)
            # target：取最后一个非引号包裹的参数（排除重定向和 flag）
            raw_target = fb_m.group(2) or ''
            target = re.sub(r'2>/dev/null.*$', '', raw_target).strip().strip('"').split()[0] if raw_target.strip() else ''
            if target.startswith('--'):
                target = ''
            desc_map = {
                'devices': '检测设备连接',
                'flash': f'刷写 {target} 分区',
                'erase': f'擦除 {target} 分区',
                'delete-logical-partition': f'擦除 {target} 逻辑分区',
                'reboot': '重启设备',
                'set_active': f'切换激活 {target} 槽位',
            }
            desc = desc_map.get(cmd, f'fastboot {cmd}')
            if cmd == 'reboot' and target:
                desc = f'重启进入 {target} 模式'
            # 检测 AVB 禁用标志，在描述中标注（不去除校验可能导致无法开机）
            if '--disable-verity' in rest or '--disable-verification' in rest:
                desc = f'禁用AVB校验并{desc}'
            return f'run_step {step_num} "{desc}" {rest}'
        return m.group(0)
    sh_content = re.sub(r'run_step\s+(\d+)\s+"fastboot fastboot"\s+(.+)', _fix_step_desc, sh_content)
    # 10. reboot 后注入 __wait_for_device（如果还没有的话）
    # 匹配 run_step 包裹的 reboot 命令（从命令部分判断，不依赖描述）
    def _inject_wait_after_reboot(m):
        prefix = m.group(1)
        step_num = m.group(2)
        reboot_target = m.group(3).strip()
        if reboot_target in ('fastboot', 'bootloader', 'fastbootd'):
            return f'{prefix}\n__wait_for_device "fastboot" 180\n__mark_progress {step_num}'
        elif reboot_target == 'edl':
            return f'{prefix}\n__wait_for_device "edl" 180\n__mark_progress {step_num}'
        else:
            return f'{prefix}\n__mark_progress {step_num}'
    sh_content = re.sub(
        r'(run_step\s+(\d+)\s+"[^"]*"\s+"\$FASTBOOT"\s+reboot\s+(\S+))\n(?!\s*__wait_for_device)',
        _inject_wait_after_reboot, sh_content
    )
    # 也匹配 $FASTBOOT 不带引号的情况
    sh_content = re.sub(
        r'(run_step\s+(\d+)\s+"[^"]*"\s+\$FASTBOOT\s+reboot\s+(\S+))\n(?!\s*__wait_for_device)',
        _inject_wait_after_reboot, sh_content
    )
    # 11. 循环内固定步骤号 → 动态自增（检测 run_step 在 for 循环体内的情况）
    # 这个较复杂，暂不自动处理，保持当前行为

    # 最终自检：检查残留的 Windows 语法
    if re.search(r'%[^%]+%', sh_content):
        warnings.append('脚本中存在未替换的 %变量%')
    if re.search(r'\.exe\b', sh_content):
        warnings.append('脚本中残留 .exe 后缀')
    if re.search(r'\\(?![nt"])', sh_content):
        warnings.append('脚本中残留 Windows 反斜杠路径')
    if re.search(r'2>nul', sh_content, re.IGNORECASE):
        warnings.append('脚本中残留 2>nul（未转换为 2>/dev/null）')
    if re.search(r'>nul', sh_content, re.IGNORECASE):
        warnings.append('脚本中残留 >nul（未转换为 >/dev/null）')

    return sh_content, warnings


# ============ 语法检查 ============

def syntax_check(sh_content: str, output: List[str]) -> Tuple[str, List[str]]:
    """
    B1: bash -n 语法检查。
    返回 (可能修改后的 sh_content, syntax_errors 列表)。
    """
    syntax_errors = []
    try:
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write('#!/bin/bash\n' + sh_content)
            tmp_sh_path = f.name
        try:
            result = subprocess.run(
                ['bash', '-n', tmp_sh_path],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0:
                logger.warning(f"转换后脚本语法检查失败: {result.stderr}")
                # 收集错误行
                for err_line in result.stderr.strip().split('\n'):
                    if err_line.strip():
                        syntax_errors.append(err_line.strip())
                # 如果错误超过阈值，在脚本顶部添加注释警告
                if len(syntax_errors) >= 5:
                    sh_content = (
                        f"# WARNING: 转换后脚本可能存在语法错误，建议检查\n"
                        f"# 错误数量: {len(syntax_errors)}\n"
                        f"# 错误详情:\n"
                    )
                    for err in syntax_errors[:10]:
                        sh_content += f"#   {err}\n"
                    sh_content += "\n" + '\n'.join(output)
        except Exception as e:
            logger.warning(f"bash -n 检查异常: {e}")
        finally:
            try:
                os.unlink(tmp_sh_path)
            except:
                pass
    except Exception as e:
        logger.warning(f"语法检查创建临时文件失败: {e}")

    return sh_content, syntax_errors
