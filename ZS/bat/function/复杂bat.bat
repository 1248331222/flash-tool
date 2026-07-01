@echo off
setlocal enabledelayedexpansion

:: ============================================================
:: 复杂刷机脚本 - 基于原变量测试脚本增强
:: 功能：参数化刷机、日志记录、错误处理、交互菜单、分区管理
:: 用法：直接运行进入交互菜单，或带参数：
::   complex_flash.bat -fastboot=.\resources\fastboot.exe -img=.\image -partition="boot system" -wipe -no-reboot
:: ============================================================

:: ---------- 全局配置 ----------
set "SCRIPT_DIR=%~dp0"
set "LOG_FILE=%SCRIPT_DIR%flash_%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%.log"
set "LOG_FILE=%LOG_FILE: =0%"
set "FASTBOOT_DEFAULT=resources\fastboot.exe"
set "IMG_DIR_DEFAULT=image"
set "DEVICE_DEFAULT=ACE竞速版C13c05"
set "MAKER_DEFAULT=酷安@无为真大道"
set "PARTITION_LIST_DEFAULT=preloader_raw lk apusys audio_dsp boot ccu cdt_engineering dpm dtbo gpueb gz mcf_ota mcupm md1img mvpu_algo pi_img scp spmfw sspm tee vcp vendor_boot vbmeta vbmeta_system vbmeta_vendor"
set "PRINT_LOOP=3"

:: 运行时变量
set "FASTBOOT=%FASTBOOT_DEFAULT%"
set "IMG_DIR=%IMG_DIR_DEFAULT%"
set "DEVICE=%DEVICE_DEFAULT%"
set "MAKER=%MAKER_DEFAULT%"
set "PARTITION_LIST=%PARTITION_LIST_DEFAULT%"
set "WIPE_DATA=0"
set "NO_REBOOT=0"
set "SKIP_CHECK=0"
set "AUTO_FLASH=0"
set "STATE=ready"

:: ---------- 日志函数 ----------
:log
echo [%time%] %* >> "%LOG_FILE%"
echo %*
exit /b 0

:log_only
echo [%time%] %* >> "%LOG_FILE%"
exit /b 0

:: ---------- 解析命令行参数 ----------
:parse_args
if "%~1"=="" goto args_done
set "arg=%~1"
if /i "%arg:~0,10%"=="-fastboot=" (
    set "FASTBOOT=%arg:~10%"
    shift
    goto parse_args
)
if /i "%arg:~0,5%"=="-img=" (
    set "IMG_DIR=%arg:~5%"
    shift
    goto parse_args
)
if /i "%arg:~0,11%"=="-partition=" (
    set "PARTITION_LIST=%arg:~11%"
    shift
    goto parse_args
)
if /i "%arg%"=="-wipe" (
    set "WIPE_DATA=1"
    shift
    goto parse_args
)
if /i "%arg%"=="-no-reboot" (
    set "NO_REBOOT=1"
    shift
    goto parse_args
)
if /i "%arg%"=="-skip-check" (
    set "SKIP_CHECK=1"
    shift
    goto parse_args
)
if /i "%arg%"=="-auto" (
    set "AUTO_FLASH=1"
    shift
    goto parse_args
)
if /i "%arg%"=="-h" (
    call :usage
    exit /b 0
)
echo 未知参数: %arg%
shift
goto parse_args
:args_done

:: ---------- 使用说明 ----------
:usage
echo 用法: %~nx0 [选项]
echo   -fastboot=路径     指定 fastboot 可执行文件路径
echo   -img=目录          指定镜像文件所在目录
echo   -partition="列表"  指定要刷写的分区（空格分隔），默认全部
echo   -wipe              刷机后清除用户数据
echo   -no-reboot         刷机完成后不自动重启
echo   -skip-check        跳过设备检测步骤（谨慎使用）
echo   -auto              自动执行全部刷写（不进入菜单）
echo   -h                 显示此帮助
echo 示例:
echo   %~nx0 -img=D:\images -partition="boot recovery" -wipe
exit /b 0

:: ---------- 初始化 ----------
title %DEVICE% By:%MAKER%
call :log "========== 刷机开始 [%date% %time%] =========="
call :log "设备: %DEVICE%"
call :log "制作: %MAKER%"
call :log "Fastboot路径: %FASTBOOT%"
call :log "镜像目录: %IMG_DIR%"

:: 检查 Fastboot 是否存在
if not exist "%FASTBOOT%" (
    call :log "错误: 找不到 fastboot 可执行文件 - %FASTBOOT%"
    exit /b 1
)

:: 检查镜像目录
if not exist "%IMG_DIR%" (
    call :log "警告: 镜像目录不存在 - %IMG_DIR%"
    if "%AUTO_FLASH%"=="1" (
        call :log "自动模式终止，目录不存在。"
        exit /b 1
    )
)

:: ---------- 设备检测 ----------
if "%SKIP_CHECK%"=="0" (
    call :log "检测设备连接..."
    %FASTBOOT% devices > "%TEMP%\fb_devices.txt" 2>&1
    findstr /c:"fastboot" "%TEMP%\fb_devices.txt" >nul
    if errorlevel 1 (
        call :log "错误: 未检测到 Fastboot 设备，请确保手机已进入 Bootloader 模式。"
        del "%TEMP%\fb_devices.txt" 2>nul
        exit /b 1
    )
    call :log "设备已连接。"
    del "%TEMP%\fb_devices.txt" 2>nul
) else (
    call :log "已跳过设备检测。"
)

:: ---------- 交互菜单或自动模式 ----------
if "%AUTO_FLASH%"=="1" (
    call :log "自动模式启动，将执行全部刷写操作。"
    goto auto_flash
)

:menu
cls
echo.
echo ========== 刷机主菜单 ==========
echo  1. 刷写所有分区（默认列表）
echo  2. 刷写指定分区
echo  3. 擦除 metadata 并设置活动分区
echo  4. 清除用户数据 (wipe)
echo  5. 重启设备
echo  6. 查看日志
echo  7. 退出
echo ================================
set /p choice="请选择 [1-7]: "
if "%choice%"=="1" goto auto_flash
if "%choice%"=="2" goto select_partition
if "%choice%"=="3" goto do_erase_meta
if "%choice%"=="4" goto do_wipe
if "%choice%"=="5" goto do_reboot
if "%choice%"=="6" goto show_log
if "%choice%"=="7" goto end
goto menu

:select_partition
echo 当前分区列表: %PARTITION_LIST%
set /p custom_part="请输入要刷写的分区（空格分隔，直接回车使用全部）: "
if not "%custom_part%"=="" set "PARTITION_LIST=%custom_part%"
goto auto_flash

:: ---------- 核心刷写流程 ----------
:auto_flash
call :log "进入刷写流程..."
call :log "即将刷写分区: %PARTITION_LIST%"

:: 循环提醒
call :log "----------------刷机前置提醒循环----------------"
for /L %%a in (1,1,%PRINT_LOOP%) do (
    call :log "第%%a遍提醒：刷机期间不要点击鼠标"
    if "%STATE%"=="ready" call :log "检测状态正常，即将进入刷机流程"
)
call :log "------------------------------------------------"

:: 第一步：reboot bootloader 确保处于 bootloader 模式
call :log "执行: %FASTBOOT% reboot bootloader"
%FASTBOOT% reboot bootloader >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    call :log "警告: reboot bootloader 失败，可能已处于 fastboot 模式。"
)

:: 擦除 metadata
call :do_erase_meta

:: 刷写 super 分区（如果存在）
if exist "%IMG_DIR%\super.img" (
    call :log "刷写 super 分区..."
    %FASTBOOT% flash super "%IMG_DIR%\super.img" -S 64M >> "%LOG_FILE%" 2>&1
    if errorlevel 1 (
        call :log "错误: 刷写 super 失败！"
        goto error_exit
    ) else (
        call :log "super 刷写成功。"
    )
) else (
    call :log "未找到 super.img，跳过。"
)

:: 循环刷写分区列表
call :log "开始刷写各个分区（A/B 双槽）..."
for %%p in (%PARTITION_LIST%) do (
    call :log "正在处理分区: %%p"
    if exist "%IMG_DIR%\%%p.img" (
        call :flash_partition %%p
    ) else (
        call :log "警告: 镜像 %IMG_DIR%\%%p.img 不存在，跳过。"
    )
)

:: 擦除 metadata 并设置活动分区
call :do_erase_meta
call :log "设置活动分区为 a"
%FASTBOOT% set_active a >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    call :log "警告: set_active 失败。"
) else (
    call :log "活动分区已设为 a。"
)

:: 清除用户数据（若指定）
if "%WIPE_DATA%"=="1" (
    call :do_wipe
)

:: 刷机完成校验
call :log "----------------刷机完成校验循环----------------"
for /L %%b in (1,1,2) do (
    call :log "流程校验提示 %%b"
    if not "%DEVICE%"=="" call :log "设备名称变量加载成功"
)
call :log "------------------------------------------------"

call :log "刷写流程执行完毕。"

if "%NO_REBOOT%"=="1" (
    call :log "根据参数 -no-reboot，不自动重启。请手动重启。"
) else (
    call :do_reboot
)
goto end

:: ---------- 函数定义 ----------
:flash_partition
:: 参数 %1 = 分区名
set "part=%~1"
call :log "刷写 %part%_a ..."
%FASTBOOT% flash %part%_a "%IMG_DIR%\%part%.img" >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    call :log "错误: 刷写 %part%_a 失败！"
    goto error_exit
)
call :log "刷写 %part%_b ..."
%FASTBOOT% flash %part%_b "%IMG_DIR%\%part%.img" >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    call :log "错误: 刷写 %part%_b 失败！"
    goto error_exit
)
call :log "分区 %part% 刷写完成。"
exit /b 0

:do_erase_meta
call :log "擦除 metadata 分区..."
%FASTBOOT% erase metadata >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    call :log "警告: 擦除 metadata 失败（可能不存在）。"
) else (
    call :log "metadata 已擦除。"
)
exit /b 0

:do_wipe
call :log "开始清除用户数据 (fastboot -w)..."
%FASTBOOT% -w >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    call :log "警告: fastboot -w 失败，尝试单独擦除 userdata 和 cache..."
    %FASTBOOT% erase userdata >> "%LOG_FILE%" 2>&1
    %FASTBOOT% erase cache >> "%LOG_FILE%" 2>&1
)
call :log "数据清除操作完成。"
exit /b 0

:do_reboot
call :log "重启设备..."
%FASTBOOT% reboot >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    call :log "错误: 重启失败，请手动重启。"
) else (
    call :log "设备已重启。"
)
exit /b 0

:show_log
if exist "%LOG_FILE%" (
    type "%LOG_FILE%" | more
) else (
    echo 日志文件不存在。
)
pause
goto menu

:error_exit
call :log "刷机过程中发生错误，流程终止。请检查日志。"
goto end

:end
call :log "========== 刷机结束 [%date% %time%] =========="
echo.
echo 日志已保存至: %LOG_FILE%
echo 按任意键退出...
pause >nul
endlocal
exit /b 0