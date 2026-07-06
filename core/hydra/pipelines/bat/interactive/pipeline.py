# -*- coding: utf-8 -*-
import os
from .bat_sandbox.engine import BatSandboxEngine
from core.hydra import HydraParseResult, HydraStepCompat
from core.hydra.bat_parser.var_types import CodeBlock, HydraStep

class InteractiveBatPipeline:
    class_id = "interactive"
    class_name = "InteractiveBatPipeline"

    def __init__(self):
        self._sandbox = BatSandboxEngine()

    def parse(self, content, script_path="", rom_dir="", user_decisions=None):
        steps = self._sandbox.parse(content, rom_dir=rom_dir)
        is_interactive = len(steps) > 0 and "_meta" in str(steps[0])
        if is_interactive:
            meta = steps.pop(0)
            core = {"flash", "erase", "reboot", "reboot-bootloader", "set_active"}
            filtered = [s for s in steps if s.get("type") in core]

            # 交互式管线：构建带 pending_choices 的返回结果
            compat = []
            for s in filtered:
                compat.append(HydraStepCompat(
                    type=s.get("type",""), part=s.get("part",""),
                    fileName=s.get("fileName",""), params=s.get("params",""),
                    raw=content, risk="MEDIUM",
                    dynamic=bool(s.get("_branch_source"))
                ))

            bs = []
            for s in filtered:
                bs.append(HydraStep(
                    command=f"{s.get('type','')} {s.get('part','')}",
                    subcommand=s.get("type",""), partition=s.get("part",""),
                    path=s.get("fileName",""), risk="MEDIUM",
                    is_conditional=bool(s.get("_branch_source"))
                ))

            branches = meta.get("branches", [])
            import json
            from core.hydra import _build_choice_tree
            script_name = os.path.basename(script_path) if script_path else ""
            branch_options = _build_choice_tree(branches, script_name)
            summary = " | ".join(f'{b["choice"]}={b["step_count"]}步' for b in branches)
            choices_json = json.dumps(branch_options, ensure_ascii=False)
            block = CodeBlock("interactive", bs,
                f"{summary}\n||CHOICES||{choices_json}", "MEDIUM")

            return HydraParseResult(
                steps=compat, total_steps=len(filtered),
                missing_files=[], blocks=[block],
                script_type="bat", class_id="interactive",
                pending_choices=branch_options,
            )
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
                script_type="bat", class_id="interactive"
            )