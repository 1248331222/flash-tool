@echo off
fastboot flash boot boot.img
fastboot flash dtbo dtbo.img
fastboot reboot
