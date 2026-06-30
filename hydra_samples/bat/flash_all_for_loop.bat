@echo off
:: ============================================================
:: 含 for /L 循环的 BAT 脚本 — 动态分区批量刷写
:: 典型特征：for /L 循环 + 变量拼接 + reboot
:: 预期展开：3 条 flash 命令 + 1 条 reboot
:: ============================================================
setlocal enabledelayedexpansion
set FASTBOOT=fastboot.exe

:: 批量刷入 3 个分区
for /L %%i in (1,1,3) do (
    set PART=boot_%%i
    %FASTBOOT% flash !PART! images\boot%%i.img
)

%FASTBOOT% reboot