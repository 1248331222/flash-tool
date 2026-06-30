@echo off
:: ============================================================
:: 含 if-else 条件判断的 BAT 脚本 — 双槽位刷写
:: 典型特征：if exist ... ( ) else ( )、变量赋值
:: ============================================================
set FASTBOOT=fastboot.exe
set SLOT=_a

:: 检测当前活动槽
%FASTBOOT% getvar current-slot

if exist images\boot_a.img (
    set SLOT=_a
) else (
    set SLOT=_b
)

:: 根据槽位刷写
%FASTBOOT% flash boot%SLOT% images\boot.img
%FASTBOOT% flash dtbo%SLOT% images\dtbo.img
%FASTBOOT% flash vendor%SLOT% images\vendor.img

%FASTBOOT% reboot