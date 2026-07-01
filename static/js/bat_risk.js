// flash_tool/static/js/bat_risk.js

// 禁用步骤编辑功能（复杂脚本模式）
    // v3.0.0: useCustomScript - 用户确认使用手动输入的自定义 .sh 脚本
    async function useCustomScript() {
        const shContent = document.getElementById('customScriptInput').value.trim();
        if (!shContent) {
            writeLog('请先输入转换后的 .sh 脚本内容', 'err');
            document.getElementById('customScriptStatus').textContent = '错误：脚本内容不能为空';
            document.getElementById('customScriptStatus').style.color = 'var(--accent-red)';
            return;
        }
        
        // 基本校验：至少包含 fastboot 或 adb 关键字
        const lowerContent = shContent.toLowerCase();
        if (!lowerContent.includes('fastboot') && !lowerContent.includes('adb') && !lowerContent.includes('reboot')) {
            writeLog('脚本中未检测到 fastboot/adb/reboot 命令，请确认脚本内容是否正确', 'warn');
        }
        
        // 保存到后端
        const statusEl = document.getElementById('customScriptStatus');
        statusEl.textContent = '正在保存脚本...';
        statusEl.style.color = 'var(--accent-blue)';
        
        try {
            const d = await apiPost('/api/rom/save_custom_script', {
                rom_name: getSelectedRomProject(),
                script_content: shContent
            });
            
            if (d.success) {
                window._shContent = shContent;
                window._customScriptPath = d.script_path;
                writeLog('自定义脚本已保存并授权，可以开始刷机', 'ok');
                statusEl.textContent = '脚本已保存：' + (d.script_path || '');
                statusEl.style.color = 'var(--accent-green)';
                
                // 更新按钮状态
                document.getElementById('useCustomScriptBtn').disabled = true;
                document.getElementById('useCustomScriptBtn').textContent = '脚本已就绪';
                document.getElementById('useCustomScriptBtn').style.background = 'var(--accent-green)';
                
                // 启用开始刷机按钮和模拟刷入按钮
                const startBtn = document.getElementById('startBatchBtn');
                if (startBtn) {
                    startBtn.disabled = false;
                    startBtn.title = '直接执行自定义 .sh 脚本';
                }
                document.getElementById('simulateBtn').disabled = false;
                
                setModuleStatus('batch', '自定义脚本已就绪，可以开始刷机。', 'ok');
            } else {
                writeLog('保存脚本失败：' + (d.error || '未知错误'), 'err');
                statusEl.textContent = '保存失败：' + (d.error || '未知错误');
                statusEl.style.color = 'var(--accent-red)';
            }
        } catch(e) {
            writeLog('保存脚本出错：' + e.message, 'err');
            statusEl.textContent = '保存出错：' + e.message;
            statusEl.style.color = 'var(--accent-red)';
        }
    }
    
    // v3.0.0: cancelCustomScript - 取消手动输入，重置状态
    function cancelCustomScript() {
        document.getElementById('scriptProcessArea').style.display = 'none';
        document.getElementById('complexScriptBanner').style.display = 'none';
        document.getElementById('batSourceDetails').style.display = 'none';
        document.getElementById('shNativePreviewArea').style.display = 'none';
        document.getElementById('customScriptArea').style.display = 'none';
        document.getElementById('customScriptInput').value = '';
        document.getElementById('customScriptStatus').textContent = '';
        document.getElementById('nativeShStatus').textContent = '';
        document.getElementById('stepList').style.display = '';
        document.getElementById('toggleStepsBtn').style.display = '';
        document.getElementById('simulateBtn').style.display = '';
        window._isComplexScript = false;
        window._isNativeSh = false;
        window._scriptType = '';
        window._shContent = '';
        window._customScriptPath = '';
        window._batSourceContent = '';
        setModuleStatus('batch', '', '');
    }
    
    // v3.0.0: copyBatSource - 复制原 BAT 脚本源码到剪贴板
    function copyBatSource() {
        const content = window._batSourceContent || '';
        if (!content) return;
        navigator.clipboard.writeText(content).then(() => {
            writeLog('原 BAT 脚本源码已复制到剪贴板', 'ok');
        }).catch(() => {
            const ta = document.createElement('textarea');
            ta.value = content;
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
            writeLog('原 BAT 脚本源码已复制到剪贴板', 'ok');
        });
    }
    
    // v3.0.0: useNativeShScript - 用户确认使用原生 .sh 脚本
    async function useNativeShScript() {
        const shContent = window._batSourceContent || '';
        if (!shContent) {
            writeLog('脚本内容为空', 'err');
            document.getElementById('nativeShStatus').textContent = '错误：脚本内容为空';
            document.getElementById('nativeShStatus').style.color = 'var(--accent-red)';
            return;
        }
        
        window._shContent = shContent;
        writeLog('原生 .sh 脚本已就绪，可以开始刷机', 'ok');
        document.getElementById('nativeShStatus').textContent = '脚本已就绪';
        document.getElementById('nativeShStatus').style.color = 'var(--accent-green)';
        
        // 更新按钮状态
        document.getElementById('useNativeShBtn').disabled = true;
        document.getElementById('useNativeShBtn').textContent = '脚本已就绪';
        document.getElementById('useNativeShBtn').style.background = 'var(--accent-green)';
        
        // 启用开始刷机按钮和模拟刷入按钮
        const startBtn = document.getElementById('batchFlashBtn');
        if (startBtn) {
            startBtn.disabled = false;
            startBtn.title = '直接执行原生 .sh 脚本';
        }
        document.getElementById('simulateBtn').disabled = false;
        
        setModuleStatus('batch', '原生 .sh 脚本已就绪，可以开始刷机。', 'ok');
    }

function updateBatchSummary() {
    const text = document.getElementById('batchSummaryText');
    const metrics = document.getElementById('batchMetrics');
    const toggle = document.getElementById('toggleStepsBtn');
    const counts = stepList.reduce((acc, s) => {
        acc[s.type] = (acc[s.type] || 0) + 1;
        return acc;
    }, {});
    if (stepList.length === 0) {
        text.textContent = '还没有解析刷机脚本。';
        metrics.innerHTML = '';
        toggle.disabled = true;
        updatePrecheckSummary();
        updateRiskSummary();
        updateResumeCard();
        updateBatchActionState();
        return;
    }
    text.textContent = `刷机任务已准备，共 ${stepList.length} 个步骤。`;
    metrics.innerHTML = `
        <span class="metric">刷写 ${counts.flash || 0}</span>
        <span class="metric">擦除 ${counts.erase || 0}</span>
        <span class="metric">重启 ${counts.reboot || 0}</span>
        <span class="metric">设槽位 ${counts.set_active || 0}</span>`;
    toggle.disabled = false;
    updatePrecheckSummary();
    updateRiskSummary();
    updateBatchActionState();
}

function analyzeScriptRisks() {
    const highRiskKeys = ['preloader','bootloader','xbl','abl','tz','modem','persist','nvram','nvdata','vbmeta','super','userdata','lk','efuse','sec','laser'];
    const dataWipeParts = ['userdata','data','metadata','cache','nvram','nvdata','persist'];
    const highRisk = [];
    let wipesData = false, locksBl = false, switchesSlot = false, flashesVbmeta = false, flashesSuper = false;
    let hasWipeFlag = false, flashesBootloader = false, flashesModem = false;
    stepList.forEach(s => {
        const raw = String(s.raw || '').toLowerCase();
        const part = String(s.part || '').toLowerCase();
        const fileName = String(s.fileName || '').toLowerCase();
        const params = String(s.params || '').toLowerCase();
        // 擦除数据分区
        if (s.type === 'erase' && dataWipeParts.some(x => part.includes(x))) wipesData = true;
        // flash userdata 也算清数据
        if (s.type === 'flash' && dataWipeParts.some(x => part.includes(x))) wipesData = true;
        // -w 参数（fastboot -w update 或 flash -w）表示清数据
        if (raw.includes(' -w ') || raw.includes(' -w') && raw.split(' -w')[1].trim().startsWith('update')) hasWipeFlag = true;
        if (params.includes('-w') || (s.prefixParams || '').includes('-w')) hasWipeFlag = true;
        // 上锁 BL
        if (raw.includes('flashing lock') || raw.includes('oem lock')) locksBl = true;
        // 切换槽位
        if (s.type === 'set_active' || raw.includes('set_active') || raw.includes('--set-active')) switchesSlot = true;
        // 刷 vbmeta
        if (part.includes('vbmeta') || fileName.includes('vbmeta')) flashesVbmeta = true;
        // 刷 super
        if (part.includes('super') || fileName.includes('super')) flashesSuper = true;
        // 刷 bootloader
        if (part.includes('bootloader') || part.includes('xbl') || part.includes('abl') || fileName.includes('bootloader')) flashesBootloader = true;
        // 刷 modem
        if (part.includes('modem') || fileName.includes('modem')) flashesModem = true;
        // 高危分区
        if (highRiskKeys.some(k => part.includes(k))) highRisk.push(s.part || part || s.raw);
    });
    // 综合判断
    if (hasWipeFlag) wipesData = true;
    return {highRisk: [...new Set(highRisk)], wipesData, locksBl, switchesSlot, flashesVbmeta, flashesSuper, flashesBootloader, flashesModem};
}

function warnIfScriptHasRebootSteps() {
    const reboots = stepList.filter(s => s.type === 'reboot');
    if (!reboots.length) return;
    // 如果最后一步是重启，且前面没有其它重启步骤，不弹窗提示（这是常见刷机脚本结尾）
    const lastStep = stepList[stepList.length - 1];
    if (lastStep && lastStep.type === 'reboot' && reboots.length === 1) return;
    const names = reboots.slice(0, 5).map(s => s.raw || `reboot ${s.part || ''}`.trim()).join('\n');
    showConfirm(
        '脚本包含重启步骤',
        `检测到 ${reboots.length} 个重启步骤：\n${names}${reboots.length > 5 ? '\n...' : ''}\n\n刷机过程中设备会断联。工具会先保存断点，然后持续检测 ADB/Fastboot 重连。\n\n重连期间系统可能重新弹出授权窗口，例如"允许 Termux:API 访问 Android 吗？"、"允许 USB 调试？"或 OTG/USB 授权，请点击"允许/确定"。如果没有自动恢复，请重新插拔/授权 OTG 后点击"检测ADB/Fastboot设备"，检测到 Fastboot 后会自动从断点继续。`,
        null,
        false
    );
}

function updateRiskSummary() {
    const text = document.getElementById('riskSummaryText');
    const metrics = document.getElementById('riskMetrics');
    if (!text || !metrics) return;
    if (stepList.length === 0) {
        text.textContent = '解析脚本后自动分析高危分区、清空数据、切槽和上锁风险。';
        metrics.innerHTML = '';
        updateSafetySummaryLine();
        return;
    }
    const r = analyzeScriptRisks();
    metrics.innerHTML = `
        <span class="metric">高危分区：${r.highRisk.length}</span>
        <span class="metric">清空数据：${r.wipesData ? '是' : '否'}</span>
        <span class="metric">切换槽位：${r.switchesSlot ? '是' : '否'}</span>
        <span class="metric">刷vbmeta：${r.flashesVbmeta ? '是' : '否'}</span>
        <span class="metric">刷super：${r.flashesSuper ? '是' : '否'}</span>
        <span class="metric">刷Bootloader：${r.flashesBootloader ? '是' : '否'}</span>
        <span class="metric">刷Modem：${r.flashesModem ? '是' : '否'}</span>
        <span class="metric">上锁Bootloader：${r.locksBl ? '是' : '否'}</span>`;
    const details = r.highRisk.length ? `高危分区：${r.highRisk.slice(0, 8).join('、')}${r.highRisk.length > 8 ? ' 等' : ''}。` : '未识别到典型高危分区。';
    let warnings = '';
    if (r.wipesData) warnings += ' 脚本包含清空数据操作（-w 或刷 userdata/cache/metadata）。';
    if (r.flashesBootloader) warnings += ' 脚本包含刷入 Bootloader 操作。';
    if (r.locksBl) warnings += ' 警告：脚本包含上锁Bootloader命令。';
    text.textContent = `${details}${warnings}`;
    updateSafetySummaryLine();
}

function updateBatchActionState(state = {}) {
const fastbootUsable = state.fastbootUsable ?? (backendReady && (canFastboot || webusbFastbootReady));
const backendMode = state.backendMode ?? (appRunMode === 'backend');
const flashModeUsable = state.flashModeUsable ?? (backendMode && fastbootUsable);
if (!backendMode) {
setModuleStatus('batch', '线刷状态：WebUSB 模式不执行完整线刷，请切换到后端模式。', 'warn');
} else if (stepList.length === 0 && !fastbootUsable) {
setModuleStatus('batch', '线刷状态：等待解析脚本并检测设备。', 'info');
} else if (stepList.length === 0) {
setModuleStatus('batch', '线刷状态：已连接设备，等待解析刷机脚本。', 'info');
} else if (!fastbootUsable) {
setModuleStatus('batch', `线刷状态：已解析 ${stepList.length} 步，等待检测 Fastboot/Bootloader 设备。`, 'warn');
} else if (flashModeUsable) {
setModuleStatus('batch', `线刷状态：已解析 ${stepList.length} 步，Fastboot 设备已连接，可以执行线刷。`, 'ok');
}
}