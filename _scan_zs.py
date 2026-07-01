# -*- coding: utf-8 -*-
"""扫描ZS目录，输出每个脚本的分类结果"""
import sys, os
sys.path.insert(0, "/sdcard/123456/flash_tool")
from core.hydra import Engine

engine = Engine()

for root, dirs, files in os.walk("/sdcard/123456/flash_tool/ZS"):
    for f in sorted(files):
        if not f.endswith(('.sh', '.bat')):
            continue
        path = os.path.join(root, f)
        content = open(path, encoding='utf-8', errors='ignore').read()
        ext = os.path.splitext(f)[1].lstrip('.')
        script_type = 'sh' if ext == 'sh' else 'bat'
        result = engine.parse(content, script_type=script_type, script_path=path)
        print(f"{script_type}/{f:30s} class={result.recipe_match.class_id:12s} steps={result.total_steps}")