@REM ============================================================
@REM  天树引擎验收报告 — 版本 v3.6.0
@REM  验收时间：2026-07-04 10:30:00
@REM  结论：✅ 通过 — 天树引擎完整支持（新建 legacy 管线）
@REM ============================================================
@REM  class_id       : legacy
@REM  总步数         : 84
@REM  警告/缺失      : 无
@REM  通配符步骤     : 无
@REM  AI 验收        : 84/84 逐行对账通过
@REM  管线            : LegacyPipeline（本次新建）
@REM  注册表          : bat/legacy → LegacyPipeline
@REM ============================================================
@REM  脚本原始内容如下：
@REM ============================================================
fastboot flash apusys_a apusys_a.img
fastboot flash apusys_b apusys_b.img
fastboot flash audio_dsp_a audio_dsp_a.img
fastboot flash audio_dsp_b audio_dsp_b.img
fastboot flash boot_a boot_a.img
fastboot flash boot_b boot_b.img
fastboot flash boot_para boot_para.img
fastboot flash bootloader1 bootloader1.img
fastboot flash bootloader2 bootloader2.img
fastboot flash ccu_a ccu_a.img
fastboot flash ccu_b ccu_b.img
fastboot flash cdt_engineering_a cdt_engineering_a.img
fastboot flash cdt_engineering_b cdt_engineering_b.img
fastboot flash connsys_bt_a connsys_bt_a.img
fastboot flash connsys_bt_b connsys_bt_b.img
fastboot flash connsys_wifi_a connsys_wifi_a.img
fastboot flash connsys_wifi_b connsys_wifi_b.img
fastboot flash dpm_a dpm_a.img
fastboot flash dpm_b dpm_b.img
fastboot flash dram_para dram_para.img
fastboot flash dtbo_a dtbo_a.img
fastboot flash dtbo_b dtbo_b.img
fastboot flash expdb expdb.img
fastboot flash flashinfo flashinfo.img
fastboot flash frp frp.img
fastboot flash gpueb_a gpueb_a.img
fastboot flash gpueb_b gpueb_b.img
fastboot flash gz_a gz_a.img
fastboot flash gz_b gz_b.img
fastboot flash lk_a lk_a.img
fastboot flash lk_b lk_b.img
fastboot flash logo logo.img
fastboot flash mcf_ota_a mcf_ota_a.img
fastboot flash mcf_ota_b mcf_ota_b.img
fastboot flash mcupm_a mcupm_a.img
fastboot flash mcupm_b mcupm_b.img
fastboot flash md1img_a md1img_a.img
fastboot flash md1img_b md1img_b.img
fastboot flash metadata metadata.img
fastboot flash misc misc.img
fastboot flash mvpu_algo_a mvpu_algo_a.img
fastboot flash mvpu_algo_b mvpu_algo_b.img
fastboot flash nvcfg nvcfg.img
fastboot flash nvdata nvdata.img
fastboot flash nvram nvram.img
fastboot flash ocdt ocdt.img
fastboot flash oplus_custom oplus_custom.img
fastboot flash oplusreserve1 oplusreserve1.img
fastboot flash oplusreserve2 oplusreserve2.img
fastboot flash oplusreserve3 oplusreserve3.img
fastboot flash oplusreserve5 oplusreserve5.img
fastboot flash oplusreserve6 oplusreserve6.img
fastboot flash otp otp.img
fastboot flash para para.img
fastboot flash param param.img
fastboot flash persist persist.img
fastboot flash pi_img_a pi_img_a.img
fastboot flash pi_img_b pi_img_b.img
fastboot flash preloader_raw_a preloader_raw_a.img
fastboot flash preloader_raw_b preloader_raw_b.img
fastboot flash proinfo proinfo.img
fastboot flash protect1 protect1.img
fastboot flash protect2 protect2.img
fastboot flash scp_a scp_a.img
fastboot flash scp_b scp_b.img
fastboot flash sec1 sec1.img
fastboot flash seccfg seccfg.img
fastboot flash spmfw_a spmfw_a.img
fastboot flash spmfw_b spmfw_b.img
fastboot flash sspm_a sspm_a.img
fastboot flash sspm_b sspm_b.img
fastboot flash super super.img
fastboot flash tee_a tee_a.img
fastboot flash tee_b tee_b.img
fastboot flash vbmeta_a vbmeta_a.img
fastboot flash vbmeta_b vbmeta_b.img
fastboot flash vbmeta_system_a vbmeta_system_a.img
fastboot flash vbmeta_system_b vbmeta_system_b.img
fastboot flash vbmeta_vendor_a vbmeta_vendor_a.img
fastboot flash vbmeta_vendor_b vbmeta_vendor_b.img
fastboot flash vcp_a vcp_a.img
fastboot flash vcp_b vcp_b.img
fastboot flash vendor_boot_a vendor_boot_a.img
fastboot flash vendor_boot_b vendor_boot_b.img
