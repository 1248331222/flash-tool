@echo off
setlocal enabledelayedexpansion
set FASTBOOT=fastboot
set IMG=images

REM 链式命令测试
%FASTBOOT% flash boot %IMG%/boot.img && %FASTBOOT% flash dtbo %IMG%/dtbo.img
%FASTBOOT% flash vendor %IMG%/vendor.img || echo "刷写失败"
%FASTBOOT% reboot system
