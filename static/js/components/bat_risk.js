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
    const classInfo = document.getElementById('classInfoRow');
    const toggle = document.getElementById('toggleStepsBtn');
    const counts = stepList.reduce((acc, s) => {
        acc[s.type] = (acc[s.type] || 0) + 1;
        return acc;
    }, {});
    if (stepList.length === 0) {
        text.textContent = '还没有解析刷机脚本。';
        metrics.innerHTML = '';
        if (classInfo) classInfo.innerHTML = '';
        toggle.disabled = true;
        updatePrecheckSummary();
        updateRiskSummary();
        updateResumeCard();
        updateBatchActionState();
        return;
    }
    // 解析方式显示
    const hs = window._hydraSummary;
    const parseMethod = window._parseMethod || (hs && hs.parse_method) || '';
    text.textContent = `刷机任务已准备，共 ${stepList.length} 个步骤。${parseMethod ? ` 🔍 ${parseMethod}` : ""}`;
    metrics.innerHTML = `
        <span class="metric">刷写 ${counts.flash || 0}</span>
        <span class="metric">擦除 ${counts.erase || 0}</span>
        <span class="metric">重启 ${counts.reboot || 0}</span>
        <span class="metric">设槽位 ${counts.set_active || 0}</span>`;
    toggle.disabled = false;

    // === 阶段5：前端展示增强 — 分类/可信度/资源/验收状态 ===
    if (classInfo) {
        const hs = window._hydraSummary;
        // 优先使用 class_id 显示分类名
        const classId = window._classId || '';
        if (classId) {
            const classLabels = {
                'plain': '纯命令', 'simple': '简单脚本', 'conditional': '条件分支',
                'for_loop': '单层循环', 'nested_for': '嵌套循环', 'delayed_expansion': '延迟展开',
                'dynamic_var': '动态变量', 'goto_label': '跳转结构', 'interactive': '交互脚本',
                'native': '原生脚本', 'vendor': '厂商脚本', 'community': '社区脚本',
                'converted': '转换脚本', 'minimal': '精简脚本', 'generic': '通用脚本', 'vip': 'VIP模板',
            };
            const label = classLabels[classId] || classId;
            classInfo.innerHTML = `<span class="class-badge class-${classId}">${escHtml(label)}</span>`;
        } else if (hs && hs.recipe) {
            const recipe = hs.recipe;
            const conf = hs.confidence || {};
            const certain = conf.certain || 0;
            const estimated = conf.estimated || 0;
            const placeholder = conf.placeholder || 0;
            const totalConf = certain + estimated + placeholder;
            const pctCertain = totalConf > 0 ? Math.round(certain / totalConf * 100) : 0;
            // 可信度等级 badge
            let confLabel, confCls;
            if (pctCertain >= 100) { confLabel = '完全确定'; confCls = 'conf-certain'; }
            else if (pctCertain >= 80) { confLabel = '高可信度'; confCls = 'conf-high'; }
            else if (pctCertain >= 50) { confLabel = '中等可信'; confCls = 'conf-mid'; }
            else { confLabel = '低可信度'; confCls = 'conf-low'; }
            // AI验收状态
            const aiAcceptance = hs.ai_acceptance || {};
            const verifyStatus = aiAcceptance.status || 'pending';
            const verifyLabel = aiAcceptance.label || (verifyStatus === 'passed' ? 'AI已验收' : (verifyStatus === 'failed' ? 'AI验收未通过' : '待AI验收'));
            const verifyCls = verifyStatus === 'passed' ? 'verify-pass' : (verifyStatus === 'failed' ? 'verify-fail' : 'verify-pending');
            const verifyTitle = aiAcceptance.reason || '';
            // resource_notes
            const rnotes = hs.resource_notes || [];
            const rnoteText = rnotes.length > 0 ? rnotes.join('；') : '';
            // source
            const src = hs.source || {};
            const srcParts = Object.entries(src).filter(([_,v]) => v > 0).map(([k,v]) => `${k}=${v}`).join(' ');
            classInfo.innerHTML = `
                <span class="class-badge class-${recipe.class}">${escHtml(recipe.class)}</span>
                <span class="class-name-badge">${escHtml(recipe.name || recipe.class)}</span>
                <span class="conf-badge ${confCls}" title="确定${certain}步 / 估计${estimated}步 / 占位${placeholder}步">${confLabel} ${pctCertain}%</span>
                ${srcParts ? `<span class="source-badge" title="步骤来源分布">${escHtml(srcParts)}</span>` : ''}
                <span class="verify-badge ${verifyCls}" title="${escHtml(verifyTitle)}">${escHtml(verifyLabel)}</span>
                ${rnoteText ? `<span class="resource-note-badge" title="${escHtml(rnoteText)}">${escHtml(rnoteText)}</span>` : ''}
            `;
        } else {
            classInfo.innerHTML = `<span class="class-badge class-legacy">未分类</span>`;
        }

    updatePrecheckSummary();
    updateRiskSummary();
    updateBatchActionState();
}
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
        // wipe 类型直接算清数据（fastboot -w）
        if (s.type === 'wipe') wipesData = true;
        // -w 参数（fastboot -w update 或 flash -w）表示清数据
        const wipeParts = raw.split(' -w');
        if (raw.includes(' -w ') || (raw.includes(' -w') && wipeParts.length > 1 && wipeParts[1].trim().startsWith('update'))) hasWipeFlag = true;
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
    // 如果最后一步是重启，且前面没有其它重启步骤，不弹窗（常见刷机脚本结尾）
    const lastStep = stepList[stepList.length - 1];
    if (lastStep && lastStep.type === 'reboot' && reboots.length === 1) return;
    // 简短弹窗提示，不展示完整脚本内容以免遮挡页面
    showConfirm(
        `脚本包含 ${reboots.length} 个重启步骤`,
        `刷机过程中设备会因重启而断联。工具会自动保存断点并持续检测 ADB/Fastboot 重连。\n\n重连时如弹出授权窗口，请点击「允许」；若未自动恢复，请重新插拔 OTG 后点击「检测设备」。`,
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

// ============ 模块初始化 ============
Modules.register('bat-risk', [], function initBatRiskModule() {
    console.log('[bat-risk] 脚本风险模块已初始化');
    return true;
});