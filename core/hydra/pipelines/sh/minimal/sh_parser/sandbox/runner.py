# -*- coding: utf-8 -*-
# Skytree Flasher / core/hydra/sh_parser/sandbox/runner.py
"""
ShSandboxRunner — 阶段 1 沙箱执行器（纯 Python 实现）
内部使用 ShSimulator 替代系统 sh 子进程。
"""
import os
import tempfile
from typing import Dict, Optional
from .simulator2 import ShSimulator

class ShSandboxRunner:
    """沙箱执行器（纯 Python 模拟实现）"""

    def __init__(self, getvar_defs: Optional[Dict[str, str]] = None,
                 extra_env: Optional[Dict[str, str]] = None,
                 timeout: int = 30):
        self.simulator = ShSimulator(extra_env=extra_env)
        self.getvar_defs = getvar_defs or {}

    def run(self, script_path: str, rom_dir: str,
            sandbox_dir: Optional[str] = None) -> str:
        if sandbox_dir is None:
            sandbox_dir = tempfile.mkdtemp(prefix="sh_simulator_")
        jsonl_path = os.path.join(sandbox_dir, "commands.jsonl")
        try:
            with open(script_path, 'r') as f:
                content = f.read()
        except FileNotFoundError:
            return jsonl_path
        result = self.simulator.run(content, rom_dir=rom_dir, script_path=script_path)
        result.to_jsonl(jsonl_path)
        return jsonl_path

    def _load_default_getvars(self) -> Dict[str, str]:
        return {}
