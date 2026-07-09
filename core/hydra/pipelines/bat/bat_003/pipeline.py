# -*- coding: utf-8 -*-
"""
bat_003 -- Pure fastboot command sequence (PLAIN_COMMANDS only).

Covers: all BAT scripts that contain only fastboot commands,
no control flow, no variable expansion, no goto/labels.
"""

import os
from .bat_003_sandbox.engine import BatSandboxEngine
from core.hydra import HydraParseResult, HydraStepCompat
from core.hydra.bat_parser.var_types import CodeBlock, HydraStep

# Feature set that this pipeline covers (exact match required)
COVERS = {"CHCP", "DELAYED_EXPANSION", "DYNAMIC_VAR", "EXIT", "FOR", "IF", "INDIRECT_TOOL", "PAUSE", "PERCENT_VAR", "PREFIXED_FASTBOOT", "TIMEOUT"}


class Pipeline:
    """bat_003: plain fastboot command sequence pipeline."""

    def __init__(self):
        self._sandbox = BatSandboxEngine()

    def parse(self, content, script_path="", rom_dir="", user_decisions=None, extra_args=""):
        steps = self._sandbox.parse(content, rom_dir=rom_dir, extra_args=extra_args)

        is_interactive = len(steps) > 0 and "_meta" in str(steps[0])
        if is_interactive:
            meta = steps.pop(0)
            core = {"flash", "erase", "reboot", "reboot-bootloader", "set_active"}
            filtered = [s for s in steps if s.get("type") in core]
            steps = filtered

        compat = []
        for s in steps:
            part = s.get("part", "") or s.get("target", "") or s.get("slot", "") or s.get("action", "")
            stype = s.get("type", "")
            if stype == "wipe":
                raw = "fastboot -w"
            elif stype == "reboot":
                raw = f"fastboot reboot {s.get('target', '')}".strip()
            elif stype == "getvar":
                raw = f"fastboot getvar {part}"
            elif stype == "flash":
                raw = f"fastboot flash {part} {s.get('fileName', '')}"
            elif stype == "erase":
                raw = f"fastboot erase {part}"
            else:
                raw = f"fastboot {stype} {part} {s.get('fileName', '')}".strip()
            compat.append(HydraStepCompat(
                type=stype, part=part,
                fileName=s.get("fileName", ""), params=s.get("params", ""),
                raw=raw, risk="MEDIUM"
            ))

        bs = []
        for s in steps:
            p = s.get("part", "") or s.get("target", "") or s.get("slot", "") or s.get("action", "")
            bs.append(HydraStep(
                command="{} {}".format(s.get("type", ""), p),
                subcommand=s.get("type", ""), partition=p,
                path=s.get("fileName", ""), risk="MEDIUM"
            ))

        block = CodeBlock("plain", bs, "主流程", "MEDIUM")

        return HydraParseResult(
            steps=compat, total_steps=len(steps),
            missing_files=[], blocks=[block],
            script_type="bat", class_id="bat_003"
        )