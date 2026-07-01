# flash_tool/core/fastboot_cmd_parser.py
# -*- coding: utf-8 -*-
"""
core/fastboot_cmd_parser.py — fastboot 命令解析与风险定级
从 core/bat_parser.py 拆分而来，函数逻辑保持不变。

split_args / strip_quote 已内联到此文件（原从 bat_parser 导入，bat_parser 已删除）。
DANGEROUS_PARTITIONS / VALID_PARTITIONS 来自 config（分区白名单）。
"""

import re
import shlex
from typing import Dict, Optional, List

from config import DANGEROUS_PARTITIONS, VALID_PARTITIONS


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


def _assess_risk(step: Dict) -> str:
    """
    第四层：风险定级引擎
    基于分区名、命令类型、参数，按规则自动判定 S/A/B/C 四级风险

    S 级（致命）：fastboot flashing lock（上锁）、刷 xbl/abl/pmic 等底层 Bootloader 分区、
                  format 格式化全字库、擦除 frp 以外的安全分区
    A 级（高危）：刷 vbmeta/modem/rpm/tz 分区、关闭 AVB 校验、擦除 userdata（双清）、切换槽位
    B 级（中危）：刷 boot/system/vendor/product 等普通系统分区
    C 级（低危）：getvar 查询、reboot 重启、devices 列表等无害操作
    """
    cmd_type = step.get('type', '')
    part = step.get('part', '')
    params = step.get('params', '') or step.get('prefixParams', '')
    raw = step.get('raw', '')

    # 去除槽位后缀 _a / _b 用于分区名匹配
    part_lower = part.lower()
    for suffix in ('_a', '_b', '_cow'):
        if part_lower.endswith(suffix):
            part_lower = part_lower[:-len(suffix)]

    # S 级（致命）
    if 'flashing lock' in raw.lower():
        return 'S'
    if part_lower in {'xbl', 'abl', 'pmic', 'ufs', 'ufs_misc', 'gpt', 'gpt_backup',
                       'bootloader', 'sbl', 'sbl1', 'rpm', 'tz', 'hyp', 'devcfg',
                       'cmnlib', 'cmnlib64', 'keymaster', 'mdtp', 'aop', 'cpucp',
                       'multiimgoem', 'multiimgqti'}:
        return 'S'
    if cmd_type == 'erase' and part_lower in {'userdata', 'data', 'system', 'vendor',
                                                'product', 'system_ext', 'odm'}:
        return 'S'

    # A 级（高危）
    if part_lower in {'vbmeta', 'vbmeta_system', 'vbmeta_vendor', 'modem', 'modemst1',
                       'modemst2', 'fsg', 'fsghdr', 'dsp', 'bluetooth', 'wifi',
                       'frp', 'persistent', 'misc', 'keystore', 'metadata',
                       'super', 'super_empty', 'recovery', 'dtbo'}:
        return 'A'
    if '--disable-verity' in params or '--disable-verification' in params:
        return 'A'
    if cmd_type == 'set_active':
        return 'A'
    if cmd_type == 'erase' and part_lower not in {'frp'}:
        return 'A'
    if cmd_type == 'oem':
        return 'A'

    # B 级（中危）
    if cmd_type == 'flash' and part_lower in {'boot', 'system', 'vendor', 'product',
                                               'system_ext', 'odm', 'init_boot',
                                               'vendor_boot', 'vendor_kernel_boot',
                                               'system_dlkm', 'vendor_dlkm'}:
        return 'B'

    # C 级（低危）
    if cmd_type in {'getvar', 'devices', 'help'}:
        return 'C'
    if cmd_type == 'reboot':
        return 'C'

    return 'B'


def parse_fastboot_tail(tail: str, raw_line: str) -> Optional[Dict]:
    """从 fastboot 后面的参数中找到真实命令，允许命令前有 -s/--slot 等选项"""
    # 清理 Windows 重定向 (>nul 2>&1, >NUL, >>file 等)
    tail = re.sub(r'\s*>[>]?[^\n]*', '', tail)
    _sq = strip_quote
    _sa = split_args
    tokens = [_sq(x) for x in _sa(tail)]
    if not tokens:
        return None
    known = {'flash', 'erase', 'set_active', '--set-active', 'reboot', 'reboot-bootloader',
             'oem', 'flashing', 'delete-logical-partition', 'update', 'boot',
             'unlock', 'lock', 'continue', 'getvar', 'devices'}
    idx = 0
    prefix_opts = []
    while idx < len(tokens):
        tok = tokens[idx].lower()
        if tok in known or tok.startswith('flash:') or tok.startswith('--set-active'):
            break
        # -w 等独立标志参数（不需要值）
        if tok == '-w':
            return {
                'type': 'erase',
                'part': 'userdata',
                'raw': raw_line,
                'note': 'fastboot -w: 擦除 userdata（清空用户数据）'
            }
        prefix_opts.append(tokens[idx])
        if tok in ('-s', '--slot', '--set-active') and idx + 1 < len(tokens):
            idx += 2
        elif tok.startswith('-'):
            idx += 1
        else:
            idx += 1
    if idx >= len(tokens):
        return None
    cmd = tokens[idx].lower()
    rest = tokens[idx + 1:]
    if cmd == 'flashing' and rest:
        return {
            'type': 'oem',
            'part': ' '.join(rest),
            'raw': raw_line
        }
    if cmd == 'delete-logical-partition' and rest:
        return {
            'type': 'erase',
            'part': rest[0],
            'raw': raw_line
        }
    if cmd.startswith('--set-active'):
        slot = cmd.split('=', 1)[1] if '=' in cmd else (rest[0] if rest else '')
        return {
            'type': 'set_active',
            'part': slot,
            'raw': raw_line
        }
    if cmd.startswith('flash:'):
        # flash:raw 的分区和镜像仍在后续参数中，这里只按 flash 处理
        cmd = 'flash'
    step = parse_fastboot_command(cmd, ' '.join(rest), raw_line)
    if step and prefix_opts:
        step['prefixParams'] = ' '.join(prefix_opts)
    return step


def parse_fastboot_command(cmd: str, args: str, raw_line: str) -> Optional[Dict]:
    """
    解析单个 fastboot 命令

    Args:
        cmd: 命令类型 (flash/erase/set_active/reboot 等)
        args: 命令参数
        raw_line: 原始行内容

    Returns:
        步骤字典，或 None（如果不是有效命令）
    """
    if cmd == 'flash':
        # flash partition image [params]
        _sq = strip_quote
        _sa = split_args
        parts = [_sq(x) for x in _sa(args)]
        if len(parts) < 2:
            return None
        flash_opts = []
        while parts and parts[0].startswith('-') and not parts[0].lower().endswith('.img'):
            flash_opts.append(parts.pop(0))
        if len(parts) < 2:
            return None
        partition = parts[0]
        image = parts[1].replace('\\', '/')

        # 清理 Windows 批处理变量
        # %~dp0 = 脚本所在目录（最常见）
        # %~d0 = 驱动器号, %~p0 = 路径, %~n0 = 文件名, %~x0 = 扩展名
        # %CD% = 当前目录, %~dp0 = 同 %~dp0
        image = re.sub(r'%~[a-zA-Z]0', '', image, flags=re.IGNORECASE)
        image = re.sub(r'%CD%', '', image, flags=re.IGNORECASE)
        image = re.sub(r'%~dp0', '', image, flags=re.IGNORECASE)
        # 清理其他可能的 %VAR% 环境变量（保留文件名中的合法字符）
        image = re.sub(r'%[\w]+%', '', image)
        # 清理 %%f 等 BAT for 循环变量
        image = re.sub(r'%%[\w]+', '', image)
        # 清理 !var! 延迟扩展变量
        image = re.sub(r'!\w+!', '', image)
        # 清理残留的路径分隔符前缀
        image = re.sub(r'^[\\/]+', '', image)
        # 清理 .\ 前缀（当前目录）
        image = re.sub(r'^\./', '', image)
        # 去掉路径中可能产生的多余斜杠
        image = re.sub(r'/+', '/', image)
        image = image.lstrip('/')

        # 处理 .img / .bin / .mbn / .elf / .fw 等镜像文件
        valid_exts = ('.img', '.bin', '.mbn', '.elf', '.fw', '.xml', '.json')
        if not any(image.lower().endswith(ext) for ext in valid_exts):
            return None

        params = ' '.join(flash_opts + parts[2:]) if (flash_opts or len(parts) > 2) else ''

        return {
            'type': 'flash',
            'part': partition,
            'fileName': image,
            'params': params,
            'raw': raw_line
        }

    elif cmd == 'erase':
        # erase partition
        _sq = strip_quote
        _sa = split_args
        parts = [_sq(x) for x in _sa(args)]
        if not parts:
            return None
        partition = parts[0]
        return {
            'type': 'erase',
            'part': partition,
            'raw': raw_line
        }

    elif cmd == 'set_active':
        # set_active slot
        _sq = strip_quote
        _sa = split_args
        parts = [_sq(x) for x in _sa(args)]
        if not parts:
            return None
        slot = parts[0].replace('--slot=', '').replace('_', '')
        return {
            'type': 'set_active',
            'part': slot,
            'raw': raw_line
        }

    elif cmd == 'reboot':
        # reboot [target]
        _sq = strip_quote
        target = (_sq(args).strip() or 'system')
        return {
            'type': 'reboot',
            'part': target,
            'raw': raw_line,
            'note': f'重启设备到 {target} 模式'
        }

    elif cmd == 'reboot-bootloader':
        return {
            'type': 'reboot',
            'part': 'bootloader',
            'raw': raw_line,
            'note': '重启设备到 Bootloader 模式'
        }


    elif cmd == 'oem':
        # oem command (如 oem unlock)
        oem_cmd = args.strip()
        return {
            'type': 'oem',
            'part': oem_cmd,
            'raw': raw_line
        }

    elif cmd == 'boot':
        _sq = strip_quote
        _sa = split_args
        parts = [_sq(x) for x in _sa(args)]
        image = parts[0] if parts else ''
        return {
            'type': 'boot',
            'part': image,
            'raw': raw_line
        }

    elif cmd in ('unlock', 'lock'):
        return {
            'type': 'oem',
            'part': cmd,
            'raw': raw_line
        }

    elif cmd == 'continue':
        return {
            'type': 'reboot',
            'part': 'continue',
            'raw': raw_line
        }

    elif cmd == 'getvar':
        _sq = strip_quote
        _sa = split_args
        parts = [_sq(x) for x in _sa(args)]
        var_name = parts[0] if parts else ''
        return {
            'type': 'getvar',
            'part': var_name,
            'raw': raw_line,
            'note': '查询设备信息'
        }

    elif cmd == 'devices':
        return {
            'type': 'devices',
            'part': '',
            'raw': raw_line,
            'note': '检测 fastboot 设备连接'
        }

    return None