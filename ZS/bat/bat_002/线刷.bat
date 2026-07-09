@echo off
setlocal EnableExtensions EnableDelayedExpansion

:: === 机型校验（codename 替换成你手机代号，如 sagit/alioth/apollo）===
fastboot %* getvar product 2>&1 | findstr /r /c:"^product:.*你的CODENAME" || (
    echo Mismatching image!
    pause
    exit /B 1
)

:: === 清空数据（clean all，保留数据可删掉本行）===
fastboot %* -w

:: === 刷入各分区（按你线刷包 images\ 下实际存在的 img 调整）===
fastboot %* flash vbmeta        %~dp0images\vbmeta.img
fastboot %* flash vbmeta_system %~dp0images\vbmeta_system.img
fastboot %* flash dtbo          %~dp0images\dtbo.img
fastboot %* flash boot          %~dp0images\boot.img
fastboot %* flash super         %~dp0images\super.img
fastboot %* flash recovery      %~dp0images\recovery.img
fastboot %* flash persist       %~dp0images\persist.img
fastboot %* flash misc          %~dp0images\misc.bin
fastboot %* flash cache         %~dp0images\cache.img
:: 如有 vendor_boot / logo / odm 等分区按实际补上

:: ★ 关键：绝对不要加下面这句 → 那就是回锁BL
:: fastboot %* flashing lock
:: fastboot %* oem lock

fastboot %* reboot
echo.
echo ===== Flash completed, Bootloader remains UNLOCKED =====
pause