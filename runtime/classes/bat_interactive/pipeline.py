# -*- coding: utf-8 -*-
"""
运行时覆写示例 — 交互式 BAT 管线

此文件演示 runtime/classes/ 热更新覆写机制。
继承包内 InteractiveBatPipeline，保留分支合并逻辑，
可在此基础上覆写 parse() 做自定义处理。

修改此文件后调用 POST /api/hydra/reload 即可生效。
"""

from core.hydra.pipelines.bat.interactive import InteractiveBatPipeline


class Pipeline(InteractiveBatPipeline):
    """交互式 BAT 管线覆写 — 继承包内 InteractiveBatPipeline"""

    class_id = "bat:interactive"
    class_name = "InteractiveBatOverride"

    def __init__(self):
        super().__init__()

    def parse(self, content, script_path="", rom_dir="", user_decisions=None):
        # 默认委托包内 InteractiveBatPipeline.parse()
        # 如需自定义交互式分支合并逻辑，在此覆写
        return super().parse(content, script_path=script_path, rom_dir=rom_dir)
