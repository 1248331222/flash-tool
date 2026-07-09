@echo off
chcp 65001 >nul
title 抉择线路测试脚本
setlocal enabledelayedexpansion

echo ==============================================
echo          抉择线路测试脚本
echo ==============================================

:: ==============================================
:: 步骤1：检测设备（普通命令，自动执行）
:: ==============================================
:check_device
echo [步骤1] 检测设备连接...
set TOOL_PATH=fastboot
%TOOL_PATH% devices >nul 2>&1
for /f "tokens=1" %%i in ('%TOOL_PATH% devices 2^>nul') do set device=%%i
if "!device!"=="" (
    echo   等待设备...
    timeout /t 1 >nul
    goto check_device
)
echo [OK] 设备已连接

:: ==============================================
:: 步骤2：抉择 - 刷boot方式（弹窗选2或3）
:: ==============================================
:step2
echo.
echo ==============================================
echo   ★ 步骤2/5：选择boot刷写方式
echo ==============================================
echo   2. 刷写 boot_a 分区
echo   3. 刷写 boot_b 分区
echo ==============================================
echo.
set /p boot_choice=请选择 [2/3]：

if "%boot_choice%"=="2" goto boot_a
if "%boot_choice%"=="3" goto boot_b
echo 无效输入
goto step2

:boot_a
echo --- 刷入 boot_a ---
%TOOL_PATH% flash boot_a boot.img
echo [OK] boot_a 刷写完成
goto step3

:boot_b
echo --- 刷入 boot_b ---
%TOOL_PATH% flash boot_b boot.img
echo [OK] boot_b 刷写完成
goto step3

:: ==============================================
:: 步骤3：抉择 - 选择额外刷写分区（弹窗选4/5/6）
:: ==============================================
:step3
echo.
echo ==============================================
echo   ★ 步骤3/5：选择额外刷写分区
echo ==============================================
echo   4. 刷写 dtbo 分区
echo   5. 刷写 vbmeta 分区
echo   6. 刷写 recovery 分区
echo ==============================================
echo.
set /p extra_choice=请选择 [4/5/6]：

if "%extra_choice%"=="4" goto flash_dtbo
if "%extra_choice%"=="5" goto flash_vbmeta
if "%extra_choice%"=="6" goto flash_recovery
echo 无效输入
goto step3

:flash_dtbo
echo --- 刷入 dtbo ---
%TOOL_PATH% flash dtbo dtbo.img
echo [OK] dtbo 刷写完成
goto step4

:flash_vbmeta
echo --- 刷入 vbmeta ---
%TOOL_PATH% flash vbmeta vbmeta.img
echo [OK] vbmeta 刷写完成
goto step4

:flash_recovery
echo --- 刷入 recovery ---
%TOOL_PATH% flash recovery recovery.img
echo [OK] recovery 刷写完成
goto step4

:: ==============================================
:: 步骤4：擦除操作（普通命令，自动执行）
:: ==============================================
:step4
echo.
echo [步骤4] 执行擦除操作...
%TOOL_PATH% erase data
echo [OK] data 已擦除
:: 这里不停留，直接到步骤5

:: ==============================================
:: 步骤5：抉择 - 选择重启方式（弹窗选9或10）
:: ==============================================
:step5
echo.
echo ==============================================
echo   ★ 步骤5/5：选择重启方式
echo ==============================================
echo   9. 重启到系统
echo   10. 重启到 Bootloader
echo ==============================================
echo.
set /p reboot_choice=请选择 [9/10]：

if "%reboot_choice%"=="9" goto reboot_system
if "%reboot_choice%"=="10" goto reboot_bootloader
echo 无效输入
goto step5

:reboot_system
echo --- 重启到系统 ---
%TOOL_PATH% reboot
echo [OK] 设备重启中
goto end

:reboot_bootloader
echo --- 重启到 Bootloader ---
%TOOL_PATH% reboot bootloader
echo [OK] 设备已进入 Bootloader
goto end

:: ==============================================
:: 结束
:: ==============================================
:end
echo.
echo ==============================================
echo          脚本执行完毕
echo ==============================================
echo 感谢使用！
pause
exit /b 0