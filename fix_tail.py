#!/usr/bin/env python3
"""修复 bat_risk.js 缺失的尾部函数"""
import os

path = 'static/js/bat_risk.js'
# 读取现有文件
with open(path, 'r') as f:
    lines = f.readlines()

# 删除 322 行之后的内容（可能被 bash 搞乱的）
del lines[321:]

# 追加完整尾部
tail = """}

function updateResumeCard() {
    const box = document.getElementById('resumeSummary');
    const text = document.getElementById('resumeText');
    if (!box || !text) return;
    const saved = localStorage.getItem('batch_progress');
    if (!saved) { box.style.display = 'none'; return; }
    try {
        const data = JSON.parse(saved);
        pendingResumeIndex = Number(data.step_index || 0);
        if (!data.steps || pendingResumeIndex <= 0) { box.style.display = 'none'; return; }
        box.style.display = 'block';
        const total = data.steps.length;
        const last = data.steps[Math.min(pendingResumeIndex, total - 1)] || {};
        text.textContent = `上次进度：第 ${pendingResumeIndex + 1} / ${total} 步，当前步骤：${last.raw || last.part || last.type || '未知'}。`;
    } catch(e) {
        box.style.display = 'none';
    }
}

function updatePrecheckSummary() {
    const text = document.getElementById('precheckText');
    const metrics = document.getElementById('precheckMetrics');
    if (!text || !metrics) return;
    const fastbootReady = canFastboot || webusbFastbootReady;
    const scriptReady = stepList.length > 0;
    const slot = currentSlot ? `槽位：${currentSlot.toUpperCase()}` : '槽位：未知';
    const deviceLabel = fastbootReady ? '设备：Fastboot已连接' : (canAdb || webusbAdbReady ? '设备：ADB已连接' : '设备：未就绪');
    const blLabel = blStatusText.replace('Bootloader状态：', 'Bootloader：').replace('。', '');
    metrics.innerHTML = `
        <span class="metric">${deviceLabel}</span>
        <span class="metric">${blLabel}</span>
        <span class="metric">${slot}</span>
        <span class="metric">脚本：${scriptReady ? stepList.length + '步' : '未解析'}</span>`;
    if (!fastbootReady) {
        text.textContent = '不能线刷：请先连接 Fastboot/Bootloader 设备。';
    } else if (blUnlocked === false) {
        text.textContent = '不建议线刷：Bootloader 未解锁，大多数分区刷写会失败。';
    } else if (!scriptReady) {
        text.textContent = '等待解析刷机脚本。';
    } else {
        text.textContent = '检查通过：设备和脚本已就绪，可以执行线刷。';
    }
    updateSafetySummaryLine();
}
"""

lines.append(tail)

with open(path, 'w') as f:
    f.writelines(lines)

print(f"完成！总行数: {len(lines)}")
print(f"尾部函数: updateResumeCard, updatePrecheckSummary")
