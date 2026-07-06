# -*- coding: utf-8 -*-
import os
from .bat_sandbox.engine import BatSandboxEngine
from core.hydra import HydraParseResult, HydraStepCompat
from core.hydra.bat_parser.var_types import CodeBlock, HydraStep

class PlainBatPipeline:
    class_id = "plain"
    class_name = "PlainBatPipeline"

    def __init__(self):
        self._sandbox = BatSandboxEngine()

    def parse(self, content, script_path="", rom_dir="", user_decisions=None):
        steps = self._sandbox.parse(content, rom_dir=rom_dir)
        is_interactive = len(steps) > 0 and "_meta" in str(steps[0])
        if is_interactive:
            meta = steps.pop(0)
            core = {"flash", "erase", "reboot", "reboot-bootloader", "set_active"}
            filtered = [s for s in steps if s.get("type") in core]

            # 非交互管线不会走到这里
            pass

        else:
            compat = []
            for s in steps:
                part = s.get("part","") or s.get("target","") or s.get("slot","") or s.get("action","")
                compat.append(HydraStepCompat(
                    type=s.get("type",""), part=part,
                    fileName=s.get("fileName",""), params=s.get("params",""),
                    raw=content, risk="MEDIUM"
                ))

            bs = []
            for s in steps:
                p = s.get("part","") or s.get("target","") or s.get("slot","") or s.get("action","")
                bs.append(HydraStep(
                    command=f"{s.get("type","")} {p}",
                    subcommand=s.get("type",""), partition=p,
                    path=s.get("fileName",""), risk="MEDIUM"
                ))

            block = CodeBlock("plain", bs, "主流程", "MEDIUM")

            return HydraParseResult(
                steps=compat, total_steps=len(steps),
                missing_files=[], blocks=[block],
                script_type="bat", class_id="plain"
            )
