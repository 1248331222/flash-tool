@REM ============================================================
@REM  天树引擎验收报告 — 版本 v3.6.0
@REM  验收时间：2026-07-04 10:40:00
@REM  结论：✅ 通过 — 天树引擎完整支持（legacy 管线）
@REM ============================================================
@REM  class_id       : legacy
@REM  总步数         : 56
@REM  警告/缺失      : 无
@REM  通配符步骤     : 无
@REM  备注           : GBK 编码脚本，引擎预处理已支持路径前缀（resources\fastboot.exe）
@REM  AI 验收        : 56/56 逐行对账通过
@REM ============================================================
@REM  脚本原始内容如下：
@REM ============================================================
@echo off
title ACE竞速版C13c05  By:酷安@无为真大道

resources\fastboot.exe reboot bootloader
resources\fastboot.exe erase metadata
title ACE竞速版C13c05  By:酷安@无为真大道 请勿操作鼠标 刷完会提醒
resources\fastboot.exe flash super image\super.img -S 64M

cls
echo 请勿操作鼠标 刷完会提醒
echo 请勿操作鼠标 刷完会提醒
echo 请勿操作鼠标 刷完会提醒

resources\fastboot.exe reboot fastboot

resources\fastboot.exe flash preloader_raw_a image\preloader_raw.img
resources\fastboot.exe flash preloader_raw_b image\preloader_raw.img
resources\fastboot.exe flash lk_a image\lk.img
resources\fastboot.exe flash lk_b image\lk.img
resources\fastboot.exe flash apusys_a image\apusys.img
resources\fastboot.exe flash apusys_b image\apusys.img
resources\fastboot.exe flash audio_dsp_a image\audio_dsp.img
resources\fastboot.exe flash audio_dsp_b image\audio_dsp.img
resources\fastboot.exe flash boot_a image\boot.img
resources\fastboot.exe flash boot_b image\boot.img
resources\fastboot.exe flash ccu_a image\ccu.img
resources\fastboot.exe flash ccu_b image\ccu.img
resources\fastboot.exe flash cdt_engineering_a image\cdt_engineering.img
resources\fastboot.exe flash cdt_engineering_b image\cdt_engineering.img
resources\fastboot.exe flash dpm_a image\dpm.img
resources\fastboot.exe flash dpm_b image\dpm.img
resources\fastboot.exe flash dtbo_a image\dtbo.img
resources\fastboot.exe flash dtbo_b image\dtbo.img
resources\fastboot.exe flash gpueb_a image\gpueb.img
resources\fastboot.exe flash gpueb_b image\gpueb.img
resources\fastboot.exe flash gz_a image\gz.img
resources\fastboot.exe flash gz_b image\gz.img
resources\fastboot.exe flash mcf_ota_a image\mcf_ota.img
resources\fastboot.exe flash mcf_ota_b image\mcf_ota.img
resources\fastboot.exe flash mcupm_a image\mcupm.img
resources\fastboot.exe flash mcupm_b image\mcupm.img
resources\fastboot.exe flash md1img_a image\md1img.img
resources\fastboot.exe flash md1img_b image\md1img.img
resources\fastboot.exe flash mvpu_algo_a image\mvpu_algo.img
resources\fastboot.exe flash mvpu_algo_b image\mvpu_algo.img
resources\fastboot.exe flash pi_img_a image\pi_img.img
resources\fastboot.exe flash pi_img_b image\pi_img.img
resources\fastboot.exe flash scp_a image\scp.img
resources\fastboot.exe flash scp_b image\scp.img
resources\fastboot.exe flash spmfw_a image\spmfw.img
resources\fastboot.exe flash spmfw_b image\spmfw.img
resources\fastboot.exe flash sspm_a image\sspm.img
resources\fastboot.exe flash sspm_b image\sspm.img
resources\fastboot.exe flash tee_a image\tee.img
resources\fastboot.exe flash tee_b image\tee.img
resources\fastboot.exe flash vcp_a image\vcp.img
resources\fastboot.exe flash vcp_b image\vcp.img
resources\fastboot.exe flash vendor_boot_a image\vendor_boot.img
resources\fastboot.exe flash vendor_boot_b image\vendor_boot.img
resources\fastboot.exe flash vbmeta_a image\vbmeta.img
resources\fastboot.exe flash vbmeta_b image\vbmeta.img
resources\fastboot.exe flash vbmeta_system_a image\vbmeta_system.img
resources\fastboot.exe flash vbmeta_system_b image\vbmeta_system.img
resources\fastboot.exe flash vbmeta_vendor_a image\vbmeta_vendor.img
resources\fastboot.exe flash vbmeta_vendor_b image\vbmeta_vendor.img
resources\fastboot.exe erase metadata
resources\fastboot.exe set_active a

echo 刷完了，跨版本最好手动选择清除一次数据，跨版本忘记双清会无限重启
echo.
pause