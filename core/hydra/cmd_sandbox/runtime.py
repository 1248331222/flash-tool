# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/cmd_sandbox/runtime.py
"""
Hydra — Win CMD 沙箱：运行时环境（变量、目录、errorlevel 等）
"""

import os
import re
from typing import Dict, List, Optional


class WinCmdRuntime:
    """CMD 运行时状态"""

    def __init__(self, script_path: str = "", rom_dir: str = ""):
        self.script_path = script_path or "script.bat"
        self.script_dir = os.path.dirname(os.path.abspath(self.script_path))
        self.rom_dir = rom_dir or ""

        # 当前目录
        self.cwd: str = self.script_dir

        # pushd 堆栈
        self.dir_stack: List[str] = []

        # 环境变量
        self.env: Dict[str, str] = {}
        self._init_env()

        # errorlevel
        self.errorlevel: int = 0

        # 命令计数器，防死循环
        self.step_counter: int = 0
        self.max_steps: int = 20000

        # 捕获到的外部命令（fastboot / adb）
        self.captured_commands: List[str] = []

        # 输出缓冲区
        self.stdout: List[str] = []
        self.stderr: List[str] = []
        self.last_stdout: List[str] = []  # 上一条命令的 stdout（供管道/findstr）

    def _init_env(self):
        sp_abs = os.path.abspath(self.script_path)
        sp_dir = os.path.dirname(sp_abs)
        sp_name = os.path.basename(sp_abs)
        sp_base, sp_ext = os.path.splitext(sp_name)
        self.env.update({
            "CD": self.script_dir,
            "ERRORLEVEL": "0",
            "TEMP": "/tmp",
            "DATE": "2026/07/01",
            "TIME": "00:00:00.00",
            "AUTO_FLASH": "1",
            "SKIP_CHECK": "0",
            "WIPE_DATA": "1",
            "NO_REBOOT": "0",
            "FASTBOOT": "fastboot",
            "ADB": "adb",
            "IMG_DIR": "image",
            "~DP0": sp_dir + os.sep,
            "~NX0": sp_name,
            "~N0": sp_base,
            "~X0": sp_ext,
            "~F0": sp_abs,
        })

    def resolve(self, text: str) -> str:
        """展开 %VAR% 和 !VAR!（不区分大小写）。"""
        result = text
        # %VAR% 展开
        result = re.sub(
            r'%([A-Za-z0-9_~]+)%',
            lambda m: self.env.get(m.group(1).upper(), m.group(0)),
            result
        )
        # !VAR! 展开（延迟变量）
        result = re.sub(
            r'!([A-Za-z0-9_~]+)!',
            lambda m: self.env.get(m.group(1).upper(), m.group(0)),
            result
        )
        return result

    def set_var(self, key: str, value: str):
        self.env[key.upper()] = value

    def get_var(self, key: str, default: str = "") -> str:
        return self.env.get(key.upper(), default)

    def set_errorlevel(self, code: int):
        self.errorlevel = code
        self.env["ERRORLEVEL"] = str(code)

    def step(self) -> bool:
        """步进计数器，返回 False 表示超限。"""
        self.step_counter += 1
        return self.step_counter <= self.max_steps

    def is_fastboot_command(self, cmd: str) -> bool:
        cmd_lower = cmd.strip().lower()
        return cmd_lower.startswith("fastboot") or cmd_lower.startswith("adb")

    def capture(self, cmd: str):
        self.captured_commands.append(cmd)

    def reset(self):
        self.cwd = self.script_dir
        self.dir_stack.clear()
        self.errorlevel = 0
        self.step_counter = 0
        self.captured_commands.clear()
        self.stdout.clear()
        self.stderr.clear()


__all__ = ["WinCmdRuntime"]