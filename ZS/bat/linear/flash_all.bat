@echo off
:: ============================================================
:: 小米线刷脚本 — flash_all.bat（简化版）
:: 典型特征：set FASTBOOT 变量、for /L 循环、if exist 条件
:: ============================================================
setlocal enabledelayedexpansion

set FASTBOOT=%~dp0tools\fastboot.exe

:: 刷入 boot 分区
%FASTBOOT% flash boot images\boot.img
if !errorlevel! neq 0 (
    echo 刷入 boot 失败，请检查
    pause
    exit /b 1
)

:: 刷入 dtbo 分区
%FASTBOOT% flash dtbo images\dtbo.img

:: 刷入 vendor_boot
if exist images\vendor_boot.img (
    %FASTBOOT% flash vendor_boot images\vendor_boot.img
)

:: 刷入 vendor 分区
%FASTBOOT% flash vendor images\vendor.img

:: 刷入 system 分区
%FASTBOOT% flash system images\system.img

:: 清除用户数据
%FASTBOOT% -w

:: 重启
%FASTBOOT% reboot

pause
