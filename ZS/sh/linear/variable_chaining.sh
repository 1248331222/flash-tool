#!/bin/bash
# ============================================================
# 边界情况: 变量链式引用 + 路径拼凑 + 默认值嵌套
# 测试引擎对多层变量替换的处理
# ============================================================

FASTBOOT=${FASTBOOT:-fastboot}
IMAGES_DIR=${IMAGES_DIR:-images}
SLOT=${SLOT:-_a}

# 基于其他变量定义新变量
BOOT_IMG=${IMAGES_DIR}/boot.img
DTBO_IMG=${IMAGES_DIR}/dtbo.img
VENDOR_IMG=${IMAGES_DIR}/vendor.img

# 组合变量
PART_PREFIX=boot
TARGET_PART=${PART_PREFIX}${SLOT}

# 使用组合后的变量
${FASTBOOT} flash ${TARGET_PART} ${BOOT_IMG}

# 另一个组合
TARGET2=dtbo${SLOT}
${FASTBOOT} flash ${TARGET2} ${DTBO_IMG}

# 多级变量引用
VENDOR_SLOT=vendor${SLOT}
${FASTBOOT} flash ${VENDOR_SLOT} ${VENDOR_IMG}

# reboot
${FASTBOOT} reboot
