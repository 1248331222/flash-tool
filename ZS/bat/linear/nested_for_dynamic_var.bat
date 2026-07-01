@echo off
REM ============================================================
REM 边界情况: 嵌套 for /L + if exist + 动态变量
REM 测试引擎对深度嵌套和变量追踪的能力
REM ============================================================

setlocal enabledelayedexpansion
set FASTBOOT=fastboot
set IMG_DIR=images

REM 双层 for 循环（嵌套 for）
for /L %%i in (1,1,2) do (
    echo 处理 slot %%i
    for /L %%j in (1,1,2) do (
        if exist !IMG_DIR!\boot_slot%%i_part%%j.img (
            !FASTBOOT! flash boot_%%i_%%j !IMG_DIR!\boot_slot%%i_part%%j.img
        ) else (
            echo 跳过 boot_slot%%i_part%%j.img
        )
    )
)

REM call :label 调用子过程
call :check_device

!FASTBOOT! reboot

goto :eof

:check_device
!FASTBOOT! getvar product 2>nul
!FASTBOOT! devices
goto :eof