"""
BAT 沙箱引擎 — 基类模板

此文件是公共基类模板，禁止直接实例化。
各子管线(core/hydra/pipelines/bat/*/) 下的 bat_sandbox 私有副本
才是可用的沙箱引擎，子管线的 pipeline.py 从私有副本 import 可正常使用。

如需修改沙箱行为，请修改各子管线私有副本，
或修改此基类模板后重新分发到各子管线。
"""
import os
from typing import Dict, List, Optional
from .normalizer import BatNormalizer
from .executor import BatSandbox


class BatSandboxEngine:
    """BAT 脚本沙箱解析引擎
    
    标记为 is_base=True 的为公共模板，直接实例化会报错。
    各子管线私有副本（位于 pipelines/bat/*/bat_sandbox/）可正常使用。
    """
    is_base = True
    
    def __init__(self):
        # ─────────────────────────────────────────────────────
        # 防调用策略：检测当前文件是否位于公共模板目录
        # 公共模板路径: core/hydra/bat_sandbox/
        # 子管线私有路径: core/hydra/pipelines/bat/*/bat_sandbox/
        # ─────────────────────────────────────────────────────
        caller_dir = os.path.dirname(os.path.abspath(__file__))
        if 'pipelines/bat/' not in caller_dir:
            raise RuntimeError(
                "\n"
                "╔══════════════════════════════════════════════════════════════╗\n"
                "║  BatSandboxEngine 是基类模板，永久禁止直接实例化或调用。  ║\n"
                "║  请使用各 BAT 子管线私有副本:                               ║\n"
                "║  core/hydra/pipelines/bat/*/bat_sandbox/engine.py           ║\n"
                "║  子管线: plain / simple / conditional /                      ║\n"
                "║  for_loop / nested_for / delayed_expansion /                 ║\n"
                "║  dynamic_var / goto_label / interactive                      ║\n"
                "╚══════════════════════════════════════════════════════════════╝"
            )
        self.normalizer = BatNormalizer()
    
    def parse(self, content: str, rom_dir: str = '',
              device_info: Optional[Dict] = None,
              extra_args: str = '') -> List[dict]:
        """
        解析 BAT 脚本，返回步骤 JSON 列表
        
        Args:
            content: BAT 脚本完整文本
            rom_dir: ROM 包路径（用于 %~dp0 解析和 Mock 文件系统）
            device_info: 真机环境变量，如 {'slot': 'a', 'product': 'mars'}
            extra_args: %* 展开值（额外命令行参数）
        
        Returns:
            [
                {'type': 'getvar', 'part': 'product', 'confidence': 'certain'},
                {'type': 'flash', 'part': 'boot', 'fileName': 'boot.img', 'confidence': 'certain'},
                ...
            ]
        """
        cmds = self.normalizer.normalize(content)
        sandbox = BatSandbox(device_info=device_info, rom_dir=rom_dir, extra_args=extra_args)
        return sandbox.run(cmds)