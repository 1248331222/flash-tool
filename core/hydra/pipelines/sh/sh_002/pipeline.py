# -*- coding: utf-8 -*-
"""
sh_002 -- Shell script with common features (if, $(), backtick, pipe, redirect, grep, dirname, $?).
"""

from .sh_parser import ShEngine
from .sh_parser.types import ShParseMode

COVERS = {
    "SH_PLAIN",
}


class Pipeline:
    """sh_002: shell script with control flow, substitution, and redirects."""

    def __init__(self, mode: str = "full"):
        mode_map = {
            "full": ShParseMode.FULL,
            "dry_run": ShParseMode.DRY_RUN,
            "sketch": ShParseMode.SKETCH,
        }
        self.engine = ShEngine(
            mode=mode_map.get(mode, ShParseMode.FULL),
            profile="sh_002",
            filter_getvar=False,
        )

    def parse(self, content: str, script_path: str = "", rom_dir: str = "",
              user_decisions=None):
        return self.engine.parse(
            content=content,
            script_path=script_path,
            rom_dir=rom_dir,
            user_decisions=user_decisions,
        )
