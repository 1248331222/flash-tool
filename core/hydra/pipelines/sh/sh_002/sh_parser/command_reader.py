# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/sh_parser/command_reader.py
"""
ShCommandReader — 阶段 4b 命令结构化解析器

将纯 fastboot 命令字符串解析为结构化的 ShStep。
包含 sparsechunk 分片合并、getvar 区分、参数提取。
完全独立实现，不依赖 BAT 的任何代码。
"""

import re
from typing import Dict, List, Optional

from .types import ShStep


# fastboot 前缀正则（移除前缀以提取参数）
_RE_FASTBOOT_PREFIX = re.compile(
    r'^"?'
    r'(?:.*[/\\])?'           # 任意路径前缀
    r'fastboot(?:\.exe)?'     # fastboot 二进制名
    r'"?'
    r'(?:\s+(?:'
        r'--\S+(?:\s+\S+)?'  # --slot _a, --disable-verity
        r'|\$\*|\$\@|\$\{?\w+\}?'   # $*, $@, $SLOT
    r'))*'
    r'\s+',
    re.IGNORECASE,
)

# sparsechunk 分片检测
_RE_SPARSECHUNK = re.compile(r'sparsechunk\.(\d+)', re.IGNORECASE)

# reboot 相关子命令
_REBOOT_COMMANDS = {
    "reboot", "reboot-bootloader", "reboot-fastboot",
    "reboot-edl", "reboot-recovery",
}


class ShCommandReader:
    """命令结构化解析器"""

    def parse(self, commands: List[str]) -> List[ShStep]:
        """
        将纯命令列表解析为结构化步骤。

        Args:
            commands: 纯 fastboot 命令字符串列表

        Returns:
            List[ShStep]: 结构化步骤
        """
        # 第一步：逐条解析
        steps = []
        for raw_cmd in commands:
            step = self._parse_single(raw_cmd)
            if step:
                steps.append(step)

        # 第二步：sparsechunk 合并
        steps = self._merge_sparsechunks(steps)

        return steps

    def parse_single(self, command: str) -> Optional[ShStep]:
        """解析单条命令（公开接口，供外部调用）"""
        return self._parse_single(command)

    def _parse_single(self, command: str) -> Optional[ShStep]:
        """解析单条命令"""
        subcommand = self._extract_subcommand(command)
        partition = self._extract_partition(command, subcommand)
        file_path = self._extract_file_path(command, subcommand)
        params = self._extract_params(command)

        is_reboot = subcommand in _REBOOT_COMMANDS
        is_getvar = subcommand == "getvar"
        is_skippable = is_reboot  # 重启类默认标为可跳过

        return ShStep(
            command=command,
            subcommand=subcommand,
            partition=partition,
            file_path=file_path,
            params=params,
            is_reboot=is_reboot,
            is_getvar=is_getvar,
            is_skippable=is_skippable,
        )

    def _extract_subcommand(self, command: str) -> str:
        """提取子命令"""
        match = _RE_FASTBOOT_PREFIX.match(command)
        if not match:
            # 没有 fastboot 前缀 → 直接取第一个词
            parts = command.strip().split()
            return parts[0].lower() if parts else "unknown"

        after_prefix = command[match.end():]
        parts = after_prefix.strip().split()
        for p in parts:
            if not p.startswith('--'):
                return p.lower()
        return "unknown"

    def _extract_partition(self, command: str,
                           subcommand: str) -> Optional[str]:
        """提取分区名"""
        if subcommand not in ("flash", "erase", "format",
                              "delete-logical-partition", "set_active"):
            return None

        parts = self._split_after_fastboot(command)
        # 找到子命令后的第一个非选项参数
        found_cmd = False
        for p in parts:
            if p.lower() == subcommand:
                found_cmd = True
                continue
            if found_cmd and not p.startswith('-'):
                return p.lower()
        return None

    def _extract_file_path(self, command: str,
                           subcommand: str) -> Optional[str]:
        """提取 flash 命令的镜像文件路径"""
        if subcommand != "flash":
            return None

        parts = self._split_after_fastboot(command)
        # 去掉子命令和选项，取最后一个非选项参数
        valid = []
        skip_next = False
        for p in parts:
            if skip_next:
                skip_next = False
                continue
            if p.lower() == subcommand:
                continue
            if p.startswith('-') and not p.startswith('--'):
                skip_next = True  # -S 64M 跳过值和选项
                continue
            if not p.startswith('--'):
                valid.append(p)
        return valid[-1] if valid else None

    def _extract_params(self, command: str) -> str:
        """提取 --xxx 选项参数"""
        parts = self._split_after_fastboot(command)
        opts = [p for p in parts if p.startswith('--')]
        return " ".join(opts)

    def _split_after_fastboot(self, command: str) -> List[str]:
        """去掉 fastboot 前缀后分割参数"""
        match = _RE_FASTBOOT_PREFIX.match(command)
        if not match:
            return command.strip().split()
        after_prefix = command[match.end():]
        return after_prefix.strip().split()

    def _merge_sparsechunks(self, steps: List[ShStep]) -> List[ShStep]:
        """合并连续的 sparsechunk 分片"""
        if not steps:
            return []

        merged = []
        i = 0
        while i < len(steps):
            # 检查是否以 sparsechunk.N 开头
            match = _RE_SPARSECHUNK.search(steps[i].command)
            if match and steps[i].partition:
                partition = steps[i].partition
                # 收集同一分区的连续 sparsechunk
                chunk_steps = [steps[i]]
                chunk_count = 1
                j = i + 1
                while j < len(steps):
                    m = _RE_SPARSECHUNK.search(steps[j].command)
                    if m and steps[j].partition == partition:
                        chunk_steps.append(steps[j])
                        chunk_count += 1
                        j += 1
                    else:
                        break

                if chunk_count > 1:
                    # 合为一条
                    first = chunk_steps[0]
                    step = ShStep(
                        command=first.command,
                        subcommand=first.subcommand,
                        partition=partition,
                        file_path=f"sparsechunk ({chunk_count} 分片)",
                        params=first.params,
                        risk=first.risk,
                        is_reboot=first.is_reboot,
                        is_getvar=first.is_getvar,
                        sparse_chunk_of=partition,
                        sparse_chunk_count=chunk_count,
                        notes=[f"包含 {chunk_count} 个 sparsechunk 分片"],
                    )
                    merged.append(step)
                    i = j
                    continue

            # 非 sparsechunk 或仅 1 个分片
            merged.append(steps[i])
            i += 1

        return merged

    def re_parse_single(self, command: str) -> ShStep:
        """重新解析单条命令（供 risk_analyzer 调试用）"""
        result = self._parse_single(command)
        return result if result else ShStep(command=command)

    def update_partition(self, steps: List[ShStep],
                         old_partition: str,
                         new_partition: str) -> List[ShStep]:
        """批量更新步骤中的分区名（供前端编辑后使用）"""
        for step in steps:
            if step.partition == old_partition:
                step.partition = new_partition
        return steps


__all__ = ["ShCommandReader"]
