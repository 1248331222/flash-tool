# -*- coding: utf-8 -*-
"""
bat_002 -- Pure fastboot command sequence (PLAIN_COMMANDS only).

Covers: all BAT scripts that contain only fastboot commands,
no control flow, no variable expansion, no goto/labels.
"""

import os
from .bat_002_sandbox.engine import BatSandboxEngine
from core.hydra import HydraParseResult, HydraStepCompat
from core.hydra.bat_parser.var_types import CodeBlock, HydraStep

# Feature set that this pipeline covers (exact match required)
COVERS = {"PAUSE", "PLAIN_COMMANDS"}


class Pipeline:
    """bat_002: plain fastboot command sequence pipeline."""

    def __init__(self):
        self._sandbox = BatSandboxEngine()

    def parse(self, content, script_path="", rom_dir="", user_decisions=None, extra_args=""):
        steps = self._sandbox.parse(content, rom_dir=rom_dir, extra_args=extra_args)

        is_interactive = len(steps) > 0 and "_meta" in str(steps[0])
        if is_interactive:
            meta = steps.pop(0)
            core = {"flash", "erase", "reboot", "reboot-bootloader", "set_active"}
            filtered = [s for s in steps if s.get("type") in core]
            # plain scripts should never be interactive; fall through
            pass

        compat = []
        for s in steps:
            part = s.get("part", "") or s.get("target", "") or s.get("slot", "") or s.get("action", "")
            compat.append(HydraStepCompat(
                type=s.get("type", ""), part=part,
                fileName=s.get("fileName", ""), params=s.get("params", ""),
                raw=content, risk="MEDIUM"
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
            script_type="bat", class_id="bat_002"
        )