@echo off
setlocal

:: 核心变量
set "fastboot=resources\fastboot.exe"
set "img_dir=image"

:: 进入 bootloader
%fastboot% reboot bootloader

:: 擦除 metadata
%fastboot% erase metadata

:: 刷写 super（如果存在）
if exist "%img_dir%\super.img" (
    %fastboot% flash super "%img_dir%\super.img" -S 64M
)

:: 重启到 fastbootd（动态分区模式）
%fastboot% reboot fastboot

:: 刷写所有分区（A/B 双槽）
for %%p in (preloader_raw lk apusys audio_dsp boot ccu cdt_engineering dpm dtbo gpueb gz mcf_ota mcupm md1img mvpu_algo pi_img scp spmfw sspm tee vcp vendor_boot vbmeta vbmeta_system vbmeta_vendor) do (
    %fastboot% flash %%p_a "%img_dir%\%%p.img"
    %fastboot% flash %%p_b "%img_dir%\%%p.img"
)

:: 再次擦除 metadata 并设置活动分区为 a
%fastboot% erase metadata
%fastboot% set_active a

:: 完成提示
echo 刷机完成！建议手动双清数据（若跨版本）。
pause
endlocal