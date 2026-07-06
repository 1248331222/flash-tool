# -*- coding: utf-8 -*-
# Skytree Flasher / core/step_engine.py
"""
core/step_engine.py — 步骤校验、顺序优化、COW 查询、时间估算、预览命令生成
从单文件版提取，函数逻辑保持不变。
"""

from typing import List, Dict

from config import logger
from core.utils import is_dangerous_partition
from core.device import run_fastboot_command


def validate_steps(steps: List[Dict]) -> Dict:
    """
    校验步骤列表，分析脚本风险

    Args:
        steps: 步骤列表

    Returns:
        校验结果，包含 valid, warnings, errors, flash_count, dangerous_count,
        wipes_data, locks_bl, switches_slot, flashes_bootloader, flashes_modem
    """
    result = {
        'valid': True,
        'warnings': [],
        'errors': [],
        'flash_count': 0,
        'dangerous_count': 0,
        'wipes_data': False,
        'locks_bl': False,
        'switches_slot': False,
        'flashes_bootloader': False,
        'flashes_modem': False
    }

    data_wipe_parts = {'userdata', 'data', 'metadata', 'cache', 'nvram', 'nvdata', 'persist'}
    bootloader_parts = {'bootloader', 'xbl', 'xbl_a', 'xbl_b', 'abl', 'abl_a', 'abl_b', 'lk', 'preloader'}
    modem_parts = {'modem', 'modem_a', 'modem_b', 'dsp'}

    for i, step in enumerate(steps):
        step_num = i + 1
        raw_lower = (step.get('raw', '') or '').lower()
        part_lower = (step.get('part', '') or '').lower()

        if step.get('type', '') == 'flash':
            result['flash_count'] += 1

            # 检查高危分区
            if is_dangerous_partition(step['part']):
                result['dangerous_count'] += 1
                result['warnings'].append(
                    f"步骤 {step_num}: 高危分区 {step['part']}"
                )

            # 检查清数据
            if any(x in part_lower for x in data_wipe_parts):
                result['wipes_data'] = True
                result['warnings'].append(
                    f"步骤 {step_num}: 将刷写 {step['part']} 分区（可能导致数据丢失）"
                )

            # 检查 -w 参数
            params = (step.get('params', '') or '').lower()
            prefix = (step.get('prefixParams', '') or '').lower()
            if '-w' in params or '-w' in prefix or ' -w ' in raw_lower:
                result['wipes_data'] = True

            # 检查刷 bootloader
            if any(x in part_lower for x in bootloader_parts):
                result['flashes_bootloader'] = True

            # 检查刷 modem
            if any(x in part_lower for x in modem_parts):
                result['flashes_modem'] = True

        elif step.get('type', '') == 'erase':
            # 检查擦除分区
            if any(x in part_lower for x in data_wipe_parts):
                result['wipes_data'] = True
                result['warnings'].append(
                    f"步骤 {step_num}: 将擦除 {step['part']} 分区（数据丢失）"
                )

        elif step.get('type', '') == 'set_active':
            result['switches_slot'] = True

        elif step.get('type', '') == 'oem':
            # 检查上锁 BL
            if 'lock' in part_lower or 'flashing lock' in raw_lower:
                result['locks_bl'] = True
                result['warnings'].append(
                    f"步骤 {step_num}: 将上锁 Bootloader（可能导致无法刷机）"
                )

    if result['dangerous_count'] > 0:
        result['warnings'].append(
            f"共 {result['dangerous_count']} 个高危分区操作"
        )

    return result


def optimize_step_order(steps: List[Dict]) -> List[Dict]:
    """
    标记特殊步骤，保持原始顺序不变

    规则：
    1. 保持脚本原始执行顺序（脚本作者的顺序是经过验证的，改变可能导致刷机失败）
    2. COW 清理步骤标记为 cow_cleanup，运行时动态查询分区是否存在
    3. 不做任何重排序

    Returns:
        标记后的步骤列表（顺序不变）
    """
    if not steps:
        return steps

    result = []
    for step in steps:
        s = dict(step)
        # 标记 COW 清理
        p = (s.get('part') or '').lower()
        if s.get('type') == 'erase' and '_cow' in p:
            s['cow_cleanup'] = True
        result.append(s)

    return result


def query_cow_partitions() -> List[str]:
    """
    通过 fastboot 命令查询设备上实际存在的 COW 分区

    Returns:
        存在的 COW 分区名列表
    """
    try:
        # 获取分区列表
        result = run_fastboot_command(["getvar", "all"], timeout=10)
        if not result.get("success"):
            return []

        output = result.get("combined", "") or result.get("stdout", "") or ""
        cow_parts = []
        for line in output.split('\n'):
            line = line.strip()
            # 匹配分区信息
            if '-cow' in line.lower():
                # 提取分区名
                parts = line.split(':')
                if parts:
                    part_name = parts[0].strip()
                    if '_cow' in part_name and part_name not in cow_parts:
                        cow_parts.append(part_name)

        return cow_parts
    except Exception as e:
        logger.warning(f"查询 COW 分区失败: {e}")
        return []


def estimate_execution_time(steps: List[Dict]) -> int:
    """
    估算执行时间（秒）

    Args:
        steps: 步骤列表

    Returns:
        预估时间（秒）
    """
    # 基础时间估算
    time_map = {
        'flash': 15,    # 每次刷写约15秒
        'erase': 5,     # 每次擦除约5秒
        'set_active': 2,
        'reboot': 30,   # 重启需要较长时间
        'oem': 10
    }

    total = 0
    for step in steps:
        total += time_map.get(step.get('type', ''), 5)

    return total


def generate_preview_commands(steps: List[Dict]) -> List[str]:
    """
    生成预览命令列表

    Args:
        steps: 步骤列表

    Returns:
        命令列表（用于模拟运行展示）
    """
    commands = []

    for step in steps:
        if step.get('type', '') == 'flash':
            cmd = f"fastboot flash {step['part']} {step['fileName']}"
            if step.get('params'):
                cmd += f" {step['params']}"
        elif step.get('type', '') == 'erase':
            cmd = f"fastboot erase {step['part']}"
        elif step.get('type', '') == 'set_active':
            cmd = f"fastboot set_active {step['part']}"
        elif step.get('type', '') == 'reboot':
            cmd = f"fastboot reboot {step['part']}"
        elif step.get('type', '') == 'oem':
            cmd = f"fastboot oem {step['part']}"
        else:
            cmd = step.get('raw', '')

        commands.append(cmd)

    return commands