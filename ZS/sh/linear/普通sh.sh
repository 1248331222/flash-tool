#!/bin/bash
# 简化刷机脚本 - 仅保留核心流程

# 核心变量（可根据需要修改）
FASTBOOT="fastboot"          # 若 fastboot 不在 PATH，请改为绝对路径
IMG_DIR="image"              # 镜像文件存放目录

# 进入 bootloader
"$FASTBOOT" reboot bootloader

# 擦除 metadata
"$FASTBOOT" erase metadata

# 刷写 super（如果存在）
if [ -f "$IMG_DIR/super.img" ]; then
    "$FASTBOOT" flash super "$IMG_DIR/super.img" -S 64M
fi

# 重启到 fastbootd（动态分区模式）
"$FASTBOOT" reboot fastboot

# 刷写所有分区（A/B 双槽）
for part in preloader_raw lk apusys audio_dsp boot ccu cdt_engineering dpm dtbo gpueb gz mcf_ota mcupm md1img mvpu_algo pi_img scp spmfw sspm tee vcp vendor_boot vbmeta vbmeta_system vbmeta_vendor; do
    "$FASTBOOT" flash "${part}_a" "$IMG_DIR/$part.img"
    "$FASTBOOT" flash "${part}_b" "$IMG_DIR/$part.img"
done

# 再次擦除 metadata 并设置活动分区为 a
"$FASTBOOT" erase metadata
"$FASTBOOT" set_active a

# 完成提示
echo "刷机完成！建议手动双清数据（若跨版本）。"