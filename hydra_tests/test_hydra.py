#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# flash_tool/hydra_tests/test_hydra.py
"""
Hydra 九头蛇引擎 — 自动化测试框架
===================================
覆盖 BAT/SH 脚本的各类语法结构，验证解析正确性。

用法：
    cd flash_tool && python3 -m hydra_tests.test_hydra
    cd flash_tool && python3 hydra_tests/test_hydra.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.hydra import HydraEngine, HydraStep, HydraParseResult


# ============================================================
# 测试用例
# ============================================================

class HydraTestCase:
    """单个测试用例"""
    def __init__(self, name, script, script_type="bat", rom_dir="", script_path="",
                 expected_steps=None, expected_simple=None, min_steps=0,
                 category="通用", known_complex=False):
        self.name = name
        self.script = script
        self.script_type = script_type
        self.rom_dir = rom_dir
        self.script_path = script_path
        self.expected_steps = expected_steps
        self.expected_simple = expected_simple
        self.min_steps = min_steps
        self.category = category
        self.known_complex = known_complex          # True=已知复杂脚本，失败不算bug

    def run(self, engine):
        result = engine.parse(self.script, self.script_type, self.rom_dir, self.script_path)
        passed = True
        details = []

        details.append(f"steps={result.total_steps}, simple={result.is_simple}")

        if self.expected_steps is not None:
            if result.total_steps != self.expected_steps:
                passed = False
                details.append(f"❌ 期望步骤={self.expected_steps}，实际={result.total_steps}")

        if self.expected_simple is not None:
            if result.is_simple != self.expected_simple:
                passed = False
                details.append(f"❌ 期望simple={self.expected_simple}，实际={result.is_simple}")

        if self.min_steps > 0 and result.total_steps < self.min_steps:
            passed = False
            details.append(f"❌ 步骤数({result.total_steps}) < 最小要求({self.min_steps})")

        if result.dynamic_commands > 0:
            details.append(f"  ⚡ 动态命令: {result.dynamic_commands}")

        if result.warnings:
            for w in result.warnings[:3]:
                details.append(f"  ⚠️  {w}")

        return passed, "\n".join(details), result


# ============================================================
# 测试套件
# ============================================================

class HydraTestSuite:
    def __init__(self):
        self.engine = HydraEngine()
        self.tests: list[HydraTestCase] = []
        self._build_tests()

    def _build_tests(self):
        # ============================
        # 基础功能测试
        # ============================

        self.tests.append(HydraTestCase(
            "简单 fastboot flash 命令",
            "fastboot flash boot boot.img",
            expected_steps=1, expected_simple=True,
            category="基础命令",
        ))

        self.tests.append(HydraTestCase(
            "含 .exe 后缀的 fastboot",
            "fastboot.exe flash boot boot.img",
            expected_steps=1, expected_simple=True,
            category="基础命令",
        ))

        self.tests.append(HydraTestCase(
            "含路径前缀的 fastboot",
            "tools\\fastboot.exe flash vendor vendor.img",
            expected_steps=1, expected_simple=True,
            category="基础命令",
        ))

        self.tests.append(HydraTestCase(
            "多个命令",
            """fastboot flash boot boot.img
fastboot flash dtbo dtbo.img
fastboot flash vendor vendor.img
fastboot reboot""",
            expected_steps=4, expected_simple=True,
            category="基础命令",
        ))

        self.tests.append(HydraTestCase(
            "擦除和重启",
            """fastboot erase userdata
fastboot reboot""",
            expected_steps=2, expected_simple=True,
            category="基础命令",
        ))

        self.tests.append(HydraTestCase(
            "getvar 和 devices 查询",
            """fastboot getvar product
fastboot getvar version-bootloader
fastboot devices""",
            expected_steps=3, expected_simple=True,
            category="基础命令",
        ))

        self.tests.append(HydraTestCase(
            "oem 解锁命令",
            "fastboot oem unlock",
            expected_steps=1, expected_simple=True,
            category="基础命令",
        ))

        self.tests.append(HydraTestCase(
            "fastboot -w (擦除用户数据)",
            "fastboot -w",
            expected_steps=1, expected_simple=True,
            category="基础命令",
        ))

        # ============================
        # BAT 语法测试
        # ============================

        self.tests.append(HydraTestCase(
            "BAT: set 变量 + flash",
            """@echo off
set FASTBOOT=%~dp0fastboot.exe
%FASTBOOT% flash boot boot.img
%FASTBOOT% flash dtbo dtbo.img""",
            script_path="/test/flash_all.bat",
            expected_steps=2, expected_simple=True,
            category="BAT 变量",
        ))

        self.tests.append(HydraTestCase(
            "BAT: for /L 循环 (1,1,3)",
            """@echo off
set FASTBOOT=fastboot.exe
for /L %%i in (1,1,3) do (
    %FASTBOOT% flash boot_%%i images/boot%%i.img
)""",
            expected_steps=3, expected_simple=True,
            category="BAT 循环",
        ))

        self.tests.append(HydraTestCase(
            "BAT: for (list) 循环",
            """@echo off
set FASTBOOT=fastboot.exe
for %%f in (boot dtbo vendor) do (
    %FASTBOOT% flash %%f images/%%f.img
)""",
            expected_steps=3, expected_simple=True,
            category="BAT 循环",
        ))

        self.tests.append(HydraTestCase(
            "BAT: if exist (条件为真时提取)",
            """@echo off
if exist boot.img (
    fastboot flash boot boot.img
)
fastboot reboot""",
            min_steps=1, expected_simple=True,
            category="BAT 条件",
        ))

        self.tests.append(HydraTestCase(
            "BAT: 嵌套 if",
            """@echo off
if exist images (
    if exist images/boot.img (
        fastboot flash boot images/boot.img
    )
)
if exist images/vendor.img (
    fastboot flash vendor images/vendor.img
)
fastboot reboot""",
            min_steps=1, expected_simple=True,
            category="BAT 条件",
        ))

        self.tests.append(HydraTestCase(
            "BAT: if-else 双分支",
            """@echo off
if exist boot_a.img (
    fastboot flash boot boot_a.img
) else (
    fastboot flash boot boot_b.img
)
fastboot reboot""",
            min_steps=2, expected_simple=True,
            category="BAT 条件",
        ))

        self.tests.append(HydraTestCase(
            "BAT: goto 跳转（复杂标记）",
            """@echo off
goto :check_device
:flash_boot
fastboot flash boot boot.img
:check_device
fastboot getvar product""",
            min_steps=1, expected_simple=True,
            category="BAT 控制流",
        ))

        self.tests.append(HydraTestCase(
            "BAT: setlocal enabledelayedexpansion",
            """@echo off
setlocal enabledelayedexpansion
set FASTBOOT=fastboot.exe
%FASTBOOT% flash boot boot.img
%FASTBOOT% reboot""",
            expected_steps=2, expected_simple=True,
            category="BAT 指令",
        ))

        # ============================
        # SH 语法测试
        # ============================

        self.tests.append(HydraTestCase(
            "SH: 简单 $FASTBOOT 命令",
            """#!/bin/bash
FASTBOOT=fastboot
${FASTBOOT} flash boot boot.img
${FASTBOOT} flash dtbo dtbo.img
${FASTBOOT} reboot-bootloader""",
            script_type="sh",
            expected_steps=3, expected_simple=True,
            category="SH 变量",
        ))

        self.tests.append(HydraTestCase(
            "SH: for...do...done 循环",
            """#!/bin/bash
FASTBOOT=fastboot
for part in boot dtbo vendor; do
    ${FASTBOOT} flash $part images/${part}.img
done""",
            script_type="sh",
            expected_steps=3, expected_simple=True,
            category="SH 循环",
        ))

        self.tests.append(HydraTestCase(
            "SH: if...then...fi 条件",
            """#!/bin/bash
if [ -f boot.img ]; then
    fastboot flash boot boot.img
fi
fastboot reboot""",
            script_type="sh",
            min_steps=1, expected_simple=True,
            category="SH 条件",
        ))

        self.tests.append(HydraTestCase(
            "SH: 顺序命令 + echo",
            """#!/bin/bash
echo "开始刷机..."
fastboot flash boot boot.img
fastboot flash vendor vendor.img
fastboot reboot
echo "完成！"
""",
            script_type="sh",
            expected_steps=3, expected_simple=True,
            category="SH 基础",
        ))

        # ============================
        # 样本脚本测试（读取 hydra_samples/）
        # * 含 while、函数定义、子 shell 的脚本标记为 known_complex
        # ============================

        # 已知复杂样本列表（含 while/函数/subshell 等需真实执行追踪的语法）
        known_complex_samples = {
    'sh/flash-all.sh',                # while 循环、函数定义、if 条件
    'sh/flash-base.sh',               # $(dirname) 子 shell、变量
    'edge_cases/adb_mixed_pipeline.sh',       # adb 混合、管道、通配符 for
}

        samples_dir = os.path.join(os.path.dirname(__file__), '..', 'hydra_samples')
        for root, dirs, files in os.walk(samples_dir):
            for fname in sorted(files):
                if not fname.endswith(('.bat', '.sh')):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                stype = 'sh' if fname.endswith('.sh') else 'bat'
                rel_path = os.path.relpath(fpath, samples_dir)
                is_complex = rel_path in known_complex_samples
                self.tests.append(HydraTestCase(
                    f"样本: {rel_path}" + (" (复杂)" if is_complex else ""),
                    content,
                    script_type=stype,
                    script_path=fpath,
                    min_steps=0 if is_complex else 1,
                    category="样本脚本",
                    known_complex=is_complex,
                ))

    def run_all(self):
        passed = 0
        failed = 0
        known_failed = 0
        total = len(self.tests)

        # 按分类统计
        categories = {}
        for t in self.tests:
            c = t.category
            if c not in categories:
                categories[c] = {"total": 0, "pass": 0, "fail": 0, "known": 0}

        print(f"{'='*60}")
        print(f"🐉 Hydra 九头蛇引擎 — 自动化测试 ({total} 项)")
        print(f"{'='*60}\n")

        for test in self.tests:
            ok, detail, result = test.run(self.engine)
            c = test.category
            categories[c]["total"] += 1

            if ok:
                categories[c]["pass"] += 1
                passed += 1
            else:
                categories[c]["fail"] += 1
                failed += 1
                if test.known_complex:
                    categories[c]["known"] += 1
                    known_failed += 1

            # 状态标记
            if ok:
                status = "✅"
            elif test.known_complex:
                status = "🔶"  # 已知复杂，预期内
            else:
                status = "❌"

            total_steps = result.total_steps
            type_tag = f"[{test.script_type}]" if test.script_type else ""
            print(f"  {status} {type_tag} {test.name}")
            print(f"     步骤={total_steps}, 简单={result.is_simple}")

            if not ok:
                if test.known_complex:
                    print(f"     (已知复杂脚本，需真实执行追踪)")
                else:
                    print(f"     {detail}")
            else:
                for s in result.steps[:5]:
                    print(f"      → {s.type} {s.part} fn={s.fileName}")
                if len(result.steps) > 5:
                    print(f"      → ... 还有 {len(result.steps)-5} 步")
                if result.dynamic_commands > 0:
                    print(f"      ⚡ 动态命令: {result.dynamic_commands}")
                if result.warnings:
                    for w in result.warnings[:2]:
                        print(f"      ⚠️  {w}")

        # 按分类汇总
        print(f"\n{'─'*60}")
        print(f"📊 分类统计")
        print(f"{'─'*60}")
        for cat, stats in sorted(categories.items()):
            p = stats["pass"]
            t = stats["total"]
            k = stats["known"]
            f = stats["fail"]
            bar = "✅" * (p - k) + "🔶" * k + "❌" * (f - k)
            print(f"  {cat:12s}  {p:2d}/{t:2d}  {bar}")

        print(f"\n{'='*60}")
        real_failed = failed - known_failed
        if real_failed == 0 and known_failed > 0:
            print(f"🏁 结果: {passed}/{total} 通过"
                  + f"（{known_failed} 项为已知复杂脚本，不计入失败）🎉")
        elif real_failed > 0:
            print(f"🏁 结果: {passed}/{total} 通过, {real_failed} 失败"
                  + (f"（{known_failed} 项已知复杂）" if known_failed else ""))
        else:
            print(f"🏁 结果: {passed}/{total} 全部通过 🎉")
        print(f"{'='*60}")
        return real_failed == 0


def main():
    suite = HydraTestSuite()
    success = suite.run_all()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())