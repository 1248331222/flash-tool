// flash_tool/static/js/tools.js
// 版本/工具模块：依赖 changelog.js 提供的 window.renderVersionChangelog

/**
 * 从后端加载当前工具版本号，并触发版本日志渲染和全局状态更新。
 */
async function loadVersion() {
    const verEl = document.getElementById('versionToolVersion');
    if (!verEl) return;
    try {
        const d = await apiGet('/api/version');
        verEl.textContent = 'v' + d.version;
        // 渲染可折叠更新日志（版本页），由 changelog.js 统一处理
        if (typeof renderVersionChangelog === 'function') {
            renderVersionChangelog('versionChangelog', d.version);
        }
        if (App && typeof App.set === 'function') {
            App.set('toolVersion', d.version);
        }
    } catch(e) {
        verEl.textContent = 'v?';
    }
}

/**
 * 检查后端是否有新版本可用。
 * 静默模式下失败不提示用户，避免初始化时弹错；非静默模式会显示检查结果或错误原因。
 * @param {boolean} silent - 是否为静默检查（初始化时传入 true）。
 */
async function checkUpdate(silent) {
    const tip = document.getElementById('versionUpdateTip');
    const btn = document.getElementById('versionUpdateBtn');
    if (!silent) {
        if (tip) tip.textContent = '正在检查更新...';
        if (btn) btn.disabled = true;
    }
    try {
        const ctrl = new AbortController();
        const timer = setTimeout(() => ctrl.abort(), silent ? 5000 : 8000);
        const d = await parseApiResponse(await fetch((App.backendUrl || '') + '/api/update/check', {signal: ctrl.signal}), '/api/update/check');
        clearTimeout(timer);
        if (!d.success) {
            if (silent) return;
            throw new Error(d.error || '检查失败');
        }
        if (d.has_update) {
            if (tip) tip.innerHTML = `发现新版本 v${escHtml(d.remote_version)}（当前 v${escHtml(d.local_version)}）`;
            const doBtn = document.getElementById('versionDoUpdateBtn');
            if (doBtn) { doBtn.style.display = ''; doBtn.disabled = false; }
        } else {
            if (!silent && tip) tip.textContent = `已是最新版本 v${d.local_version}`;
        }
    } catch(e) {
        if (silent) return;
        if (e.name === 'AbortError') {
            if (tip) tip.textContent = '检查更新超时：网络较慢或服务器无响应';
        } else {
            if (tip) tip.textContent = '检查更新失败：' + e.message;
        }
    }
    if (!silent && btn) btn.disabled = false;
}

/**
 * 触发后端更新流程，下载并应用新版本。
 * 完成后提示用户需要重启服务以生效。
 */
async function doUpdate() {
    const tip = document.getElementById('versionUpdateTip');
    const doBtn = document.getElementById('versionDoUpdateBtn');
    showConfirm('确认更新', '确认更新？更新后需要重启服务才能生效。', async () => {
        if (tip) tip.textContent = '正在下载更新...';
        if (doBtn) doBtn.disabled = true;
        try {
            const d = await apiPost('/api/update/do', {});
            if (!d.success) throw new Error(d.error || '更新失败');
            if (tip) tip.textContent = '更新成功！请停止并重新启动刷机工具以生效。';
            if (doBtn) doBtn.style.display = 'none';
        } catch(e) {
            if (tip) tip.textContent = '更新失败：' + e.message;
            if (doBtn) doBtn.disabled = false;
        }
    });
}

// ============ VBmeta（工具页：镜像来源选择与关闭校验） ============

/**
 * 获取当前选择的 vbmeta 镜像路径（从输入框或下拉框联动获取）
 */
function getVbmetaImagePath() {
    const source = document.getElementById('vbmetaSource');
    if (!source) return '';
    if (source.value === 'custom') {
        const input = document.getElementById('vbmetaSelect');
        return input ? input.value.trim() : '';
    }
    const imgSelect = document.getElementById('vbmetaRomImgSelect');
    const romSelect = document.getElementById('vbmetaRomSelect');
    if (!imgSelect || !romSelect) return '';
    const img = imgSelect.value;
    const rom = romSelect.value;
    if (!img || !rom) return '';
    return `/sdcard/123456/${rom}/images/${img}`;
}

/**
 * 刷新按钮状态：根据当前选择的镜像来源和路径决定是否启用。
 */
function updateVbmetaBtnState() {
    const btn = document.getElementById('disableVbmetaBtn');
    if (!btn) return;
    btn.disabled = !getVbmetaImagePath();
}

/**
 * 切换 VBmeta 镜像来源：自定义路径 ↔ 已解压刷机包
 */
function onVbmetaSourceChange() {
    const source = document.getElementById('vbmetaSource');
    if (!source) return;
    const isRom = source.value === 'rom';
    const romRow = document.getElementById('vbmetaRomRow');
    const customRow = document.getElementById('vbmetaCustomRow');
    if (romRow) romRow.style.display = isRom ? '' : 'none';
    if (customRow) customRow.style.display = isRom ? 'none' : '';
    if (isRom) {
        refreshVbmetaRomList();
    } else {
        updateVbmetaBtnState();
    }
}

/**
 * 刷新已解压刷机包列表到 #vbmetaRomSelect
 */
async function refreshVbmetaRomList() {
    const romSelect = document.getElementById('vbmetaRomSelect');
    if (!romSelect) return;
    const prevVal = romSelect.value;
    romSelect.innerHTML = '<option value="">加载中...</option>';
    romSelect.disabled = true;
    try {
        const data = await apiGet('/api/rom/list');
        const dirs = (data && data.dirs) || [];
        romSelect.innerHTML = '<option value="">选择已解压线刷包</option>';
        dirs.forEach(d => {
            const opt = document.createElement('option');
            opt.value = d.name;
            opt.textContent = d.name + (d.type ? ` (${d.type})` : '');
            if (d.name === prevVal) opt.selected = true;
            romSelect.appendChild(opt);
        });
        romSelect.disabled = false;
        onVbmetaRomSelectChange();
    } catch(e) {
        romSelect.innerHTML = '<option value="">加载失败</option>';
        romSelect.disabled = false;
        console.warn('refreshVbmetaRomList 失败:', e);
    }
}

/**
 * 已解压刷机包选择变化 → 加载该项目的镜像列表到 #vbmetaRomImgSelect
 */
async function onVbmetaRomSelectChange() {
    const romSelect = document.getElementById('vbmetaRomSelect');
    const imgSelect = document.getElementById('vbmetaRomImgSelect');
    if (!romSelect || !imgSelect) return;
    const rom = romSelect.value;
    if (!rom) {
        imgSelect.innerHTML = '<option value="">选择镜像</option>';
        imgSelect.disabled = true;
        updateVbmetaBtnState();
        return;
    }
    imgSelect.innerHTML = '<option value="">加载镜像列表...</option>';
    imgSelect.disabled = true;
    try {
        const data = await apiGet('/api/rom/images?rom_name=' + encodeURIComponent(rom));
        const files = (data && data.files) || [];
        imgSelect.innerHTML = '<option value="">选择镜像</option>';
        files.forEach(f => {
            const opt = document.createElement('option');
            opt.value = f;
            opt.textContent = f;
            imgSelect.appendChild(opt);
        });
        imgSelect.disabled = false;
    } catch(e) {
        imgSelect.innerHTML = '<option value="">加载失败</option>';
        imgSelect.disabled = false;
        console.warn('onVbmetaRomSelectChange 失败:', e);
    }
    updateVbmetaBtnState();
}

/**
 * 加载 VBmeta 镜像来源列表（初始化时调用），自动选中第一个项目并刷新镜像。
 */
async function loadVbmetaRomList() {
    try {
        const data = await apiGet('/api/rom/list');
        const dirs = (data && data.dirs) || [];
        const romSelect = document.getElementById('vbmetaRomSelect');
        if (!romSelect) return;
        romSelect.innerHTML = '<option value="">选择已解压线刷包</option>';
        dirs.forEach(d => {
            const opt = document.createElement('option');
            opt.value = d.name;
            opt.textContent = d.name + (d.type ? ` (${d.type})` : '');
            romSelect.appendChild(opt);
        });
    } catch(e) {
        console.warn('loadVbmetaRomList 获取项目列表失败:', e);
    }
}

// ============ 关闭VBmeta校验 ============
/**
 * 关闭 VBmeta 校验：刷入输入的 vbmeta 镜像并附加 --disable-verity --disable-verification。
 * 支持后端模式和 WebUSB 模式，执行前会弹出二次确认。
 * 镜像使用绝对路径（source=path），后端会校验路径安全性。
 */
async function disableVbmeta() {
    const img = getVbmetaImagePath();
    if (!img) return;

    showConfirm('操作确认', '刷入 vbmeta 并关闭校验（--disable-verity --disable-verification），确认继续？', async () => {
        setModuleStatus('toolbox', '工具箱状态：准备刷入 vbmeta 并关闭校验。', 'warn');
        showModuleProgress('toolbox', '准备刷入 vbmeta');
        const reqData = {
            extra: '--disable-verity --disable-verification',
            source: 'path',
            image: img
        };
        if (appRunMode === 'webusb') {
            if (!webusbFastbootReady || !webusbFastboot) {
                setModuleStatus('toolbox', 'WebUSB Fastboot 未连接，无法刷写 vbmeta。', 'err');
                return;
            }
            try {
                writeLog('WebUSB模式：刷入 vbmeta 并关闭 verity/verification。', 'tip');
                const bytes = await fetchImageBytes('path', img);
                await webusbFastboot.flash('vbmeta', bytes, p => updateModuleProgress('toolbox', p, 'WebUSB刷写 vbmeta'));
                updateModuleProgress('toolbox', 100, 'vbmeta 已刷入');
                setModuleStatus('toolbox', 'WebUSB已刷入 vbmeta，校验关闭完成。', 'ok');
                showToast('WebUSB vbmeta 关闭校验完成');
            } catch(e) {
                hideModuleProgress('toolbox');
                setModuleStatus('toolbox', 'WebUSB vbmeta刷写失败：' + e.message, 'err');
            }
            return;
        }

        showProgress('刷写 vbmeta');
        setModuleStatus('toolbox', '工具箱状态：正在刷写分区 vbmeta。', 'info');
        writeLog('刷写 vbmeta...');

        const res = await apiPost('/api/flash', {...reqData, partition: 'vbmeta'});
        if (!res.success) {
            hideProgress();
            hideModuleProgress('toolbox');
            setModuleStatus('toolbox', `工具箱状态：vbmeta 启动刷写失败：${res.error}`, 'err');
            writeLog('vbmeta 刷写失败：' + res.error, 'err');
            return;
        }

        await new Promise(resolve => {
            pollTaskFallback(res.task_id, (ok, err) => {
                hideProgress();
                if (ok) {
                    updateModuleProgress('toolbox', 100, 'vbmeta 已刷入');
                    setModuleStatus('toolbox', '工具箱状态：已刷入 vbmeta，校验关闭完成。', 'ok');
                    writeLog('VBmeta校验关闭完成', 'ok');
                    if ('vibrate' in navigator) navigator.vibrate([200, 100, 200]);
                    showToast('关闭校验完成');
                } else {
                    hideModuleProgress('toolbox');
                    setModuleStatus('toolbox', `工具箱状态：vbmeta 刷写失败：${err}`, 'err');
                    writeLog('vbmeta 刷写失败：' + err, 'err');
                    showToast('关闭校验失败：' + err);
                }
                resolve();
            }, {module: 'toolbox', progressPrefix: '正在刷写 vbmeta'});
        });
    }, false);
}

// ============ 版本/工具模块事件委托 ============
function handleVersionAction(e) {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;
    const action = btn.dataset.action;
    if (action === 'check-update') {
        e.preventDefault();
        checkUpdate(false);
    } else if (action === 'do-update') {
        e.preventDefault();
        doUpdate();
    }
}

// ============ 模块初始化 ============
Modules.register('tools', ['api','utils','device-info'], function initToolsModule() {
    // VBmeta 镜像来源切换
    const vbmetaSource = document.getElementById('vbmetaSource');
    if (vbmetaSource) vbmetaSource.onchange = onVbmetaSourceChange;

    // VBmeta 自定义路径输入
    const vbmetaInput = document.getElementById('vbmetaSelect');
    if (vbmetaInput) {
        vbmetaInput.oninput = updateVbmetaBtnState;
        vbmetaInput.onchange = updateVbmetaBtnState;
    }

    // VBmeta 刷机包选择
    const vbmetaRomSelect = document.getElementById('vbmetaRomSelect');
    if (vbmetaRomSelect) vbmetaRomSelect.onchange = onVbmetaRomSelectChange;

    // VBmeta 镜像选择
    const vbmetaRomImgSelect = document.getElementById('vbmetaRomImgSelect');
    if (vbmetaRomImgSelect) vbmetaRomImgSelect.onchange = updateVbmetaBtnState;

    // VBmeta 执行关闭校验
    const disableVbmetaBtn = document.getElementById('disableVbmetaBtn');
    if (disableVbmetaBtn) disableVbmetaBtn.onclick = disableVbmeta;

    loadVersion();
    loadVbmetaRomList();

    console.log('[tools] 版本/工具模块已初始化');
    return true;
});