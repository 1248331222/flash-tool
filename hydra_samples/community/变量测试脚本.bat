@echo off
setlocal enabledelayedexpansion
:: 自定义全局变量
set "fastboot=resources\fastboot.exe"
set "img_dir=image"
set "device=ACE竞速版C13c05"
set "maker=酷安@无为真大道"
set "print_loop=3"
set "state=ready"

:: 开头简易数字循环 + 单if条件（无else）
echo ----------------刷机前置提示循环----------------
for /L %%a in (1,1,%print_loop%) do (
    echo 第%%a遍提醒：刷机期间不要点击鼠标
    if "%state%"=="ready" echo 检测状态正常，即将进入刷机流程
)
echo ------------------------------------------------

title %device%  By:%maker%
%fastboot% reboot bootloader
%fastboot% erase metadata
title %device%  By:%maker% 请勿操作鼠标 刷完会提醒
%fastboot% flash super %img_dir%\super.img -S 64M

cls
:: 简单单条件判断，仅成立分支
if exist "%img_dir%\super.img" (
    echo super镜像文件存在，继续执行下一步
)
echo 请勿操作鼠标 刷完会提醒
echo 请勿操作鼠标 刷完会提醒
echo 请勿操作鼠标 刷完会提醒

%fastboot% reboot fastboot

:: 分区列表变量
set partition=preloader_raw lk apusys audio_dsp boot ccu cdt_engineering dpm dtbo gpueb gz mcf_ota mcupm md1img mvpu_algo pi_img scp spmfw sspm tee vcp vendor_boot vbmeta vbmeta_system vbmeta_vendor
:: 分区循环，内置无意义单if条件
for %%p in (%partition%) do (
    echo 正在刷写分区 %%p
    if 1 equ 1 (
        %fastboot% flash %%p_a %img_dir%\%%p.img
        %fastboot% flash %%p_b %img_dir%\%%p.img
    )
)

%fastboot% erase metadata
%fastboot% set_active a

:: 尾部收尾小循环
echo ----------------刷机完成校验循环----------------
for /L %%b in (1,1,2) do (
    echo 流程校验提示 %%b
    if not "%device%"=="" echo 设备名称变量加载成功
)
echo ------------------------------------------------

echo 刷完了，跨版本最好手动选择清除一次数据，跨版本忘记双清会无限重启
echo.
pause
endlocal
