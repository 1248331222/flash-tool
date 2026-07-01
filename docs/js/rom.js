// flash_tool/static/js/rom.js
// ============ 镜像管理 ============
async function loadProjectImages() {
    try {
        const d = await apiGet('/api/images');
        if (d.success) {
            const _cis = document.getElementById('customImgSelect');
            if (_cis) fillSelect(_cis, d.files, '选择镜像文件');
            const _vs = document.getElementById('vbmetaSource');
            const _vsel = document.getElementById('vbmetaSelect');
            if (_vs && _vsel && _vs.value === 'local') {
                fillSelect(_vsel, d.files, '选择vbmeta镜像');
            }
            renderProjectImageList(d.files);
            writeLog(`手机目录镜像：${d.files.length} 个`, 'info');
        }
    } catch(e) { writeLog('加载镜像失败：' + e.message, 'err'); }
}

function renderProjectImageList(files) {
    const el = document.getElementById('projectImageList');
    if (!el) return;
    if (files.length === 0) {
        el.innerHTML = '<div class="empty-state">暂无镜像。请将 .img 文件放入手机目录：<br><b style="color:var(--accent-green)">/storage/emulated/0/123456/image/</b><br>放入后点击刷新即可。</div>';
        return;
    }
    el.innerHTML = '';
    files.forEach(f => {
        const item = document.createElement('div');
        item.className = 'file-item';
        item.innerHTML = `<span>${escHtml(f)}</span><button class="pick-btn" onclick="pickProjectImage('${escHtml(f)}')">选用</button><button class="del-btn" onclick="deleteProjectImage('${escHtml(f)}')">删除</button>`;
        el.appendChild(item);
    });
}

async function deleteProjectImage(fn) {
    showConfirm('删除镜像文件', `确定删除手机目录中的镜像文件？\n\n文件：${fn}\n路径：/storage/emulated/0/123456/image/${fn}\n\n删除后无法恢复，确认删除？`, async () => {
        const d = await apiPost('/api/images/delete', {filename: fn});
        d.success ? writeLog(d.msg, 'ok') : writeLog(d.error, 'err');
        await loadProjectImages();
    });
}

function pickProjectImage(fn) {
    const src = customImgSourceEl ? customImgSourceEl.value : 'local';
    if (src === 'rom') {
        // 刷机包镜像模式：选用的是手机目录的镜像，需切换来源
        if (customImgSourceEl) customImgSourceEl.value = 'local';
        updateSingleImageUI();
        // 重新加载手机目录镜像列表以确保选项存在
        loadProjectImages().then(() => {
            if (customImgSelectEl) customImgSelectEl.value = fn;
            writeLog(`已选用手机目录镜像：${fn}（已从刷机包镜像切换为手机目录镜像）`, 'ok');
        });
        return;
    }
    // 手机目录镜像模式：直接设置
    if (customImgSelectEl) {
        customImgSelectEl.value = fn;
    }
    writeLog(`已选用手机目录镜像：${fn}`, 'ok');
}

// ============ ROM 管理 ============
async function refreshRomList() {
    document.getElementById('romSelect').innerHTML = '<option value="">加载中...</option>';
    try {
        const d = await apiGet('/api/public/roms');
        if (d.success) {
            fillSelect(document.getElementById('romSelect'), d.files, '选择线刷包');
            document.getElementById('extractBtn').disabled = !document.getElementById('romSelect').value;
            writeLog(`扫描到 ${d.files.length} 个刷机包`, 'info');
            // 根据刷机包数量自动展开/收起说明
            const helpRom = document.getElementById('help-rom');
            const helpBat = document.getElementById('help-bat');
            if (d.files.length > 0) {
                // 有刷机包，收起说明
                if (helpRom) helpRom.classList.remove('show');
                if (helpBat) helpBat.classList.remove('show');
            } else {
                // 无刷机包，展开说明
                if (helpRom) helpRom.classList.add('show');
                if (helpBat) helpBat.classList.add('show');
            }
        } else {
            writeLog(d.error, 'err');
            document.getElementById('romSelect').innerHTML = '<option value="">加载失败</option>';
        }
    } catch(e) { writeLog('获取刷机包列表失败', 'err'); }
}

document.getElementById('refreshRomBtn').onclick = refreshRomList;

document.getElementById('romSelect').onchange = () => {
    document.getElementById('extractBtn').disabled = !document.getElementById('romSelect').value;
};

async function refreshExtractedRoms() {
    try {
        const d = await apiGet('/api/rom/list');
        // dirs 现在是 [{name, type}] 格式
        const dirNames = (d.dirs || []).map(item => typeof item === 'object' ? item.name : item);
        const dirTypes = {};
        (d.dirs || []).forEach(item => { if (typeof item === 'object') dirTypes[item.name] = item.type; });
        renderExtractedRomList(dirNames, dirTypes);
        fillSelect(document.getElementById('romProjectSelect'), dirNames, '选择已解压线刷项目');
        fillSelect(document.getElementById('vbmetaRomSelect'), dirNames, '选择已解压刷机包');
    } catch(e) { writeLog('加载列表失败：' + e.message, 'err'); }
}

function getSelectedRomProject() {
    return document.getElementById('romProjectSelect').value || document.getElementById('romSelect').value;
}

function renderExtractedRomList(dirs, dirTypes) {
    const el = document.getElementById('extractedRomList');
    const header = document.getElementById('romListHeader');
    const countEl = document.getElementById('romListCount');

    if (dirs.length === 0) {
        el.innerHTML = '<div style="padding:8px 10px;color:var(--text-muted);font-size:12px">暂无已解压刷机包，请先选择线刷包并解压。</div>';
        header.style.display = 'none';
        return;
    }

    header.style.display = 'flex';
    countEl.textContent = `共 ${dirs.length} 个`;

    // 类型标签样式映射
    const typeLabels = {
        'xiaomi': '小米',
        'qualcomm': '高通',
        'mtk': 'MTK',
        'generic_fastboot': '通用Fastboot',
        'unknown': '未知',
    };
    const typeColors = {
        'xiaomi': '#FF6900',
        'qualcomm': '#3B82F6',
        'mtk': '#8B5CF6',
        'generic_fastboot': '#10B981',
        'unknown': '#6B7280',
    };

    el.innerHTML = '';
    dirs.forEach(d => {
        const item = document.createElement('div');
        item.className = 'file-item';
        item.style.padding = '6px 10px';
        item.style.fontSize = '12px';
        // 当前选中的项目高亮
        const currentProject = document.getElementById('romProjectSelect').value;
        const isActive = d === currentProject;
        item.style.background = isActive ? 'var(--bg-active, rgba(76,175,80,0.08))' : '';
        const romType = (dirTypes && dirTypes[d]) || 'unknown';
        const typeLabel = typeLabels[romType] || romType;
        const typeColor = typeColors[romType] || '#6B7280';
        item.innerHTML = `<span style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escHtml(d)}">${escHtml(d)}<span style="display:inline-block;margin-left:6px;font-size:10px;padding:1px 5px;border-radius:3px;color:#fff;background:${typeColor};vertical-align:middle">${escHtml(typeLabel)}</span></span><button class="btn secondary small" onclick="selectRomProject('${escHtml(d)}')" style="font-size:11px;padding:2px 8px;${isActive ? 'background:var(--accent-green);color:#fff;border-color:var(--accent-green)' : ''}">${isActive ? '当前' : '选用'}</button><button class="del-btn" onclick="deleteExtractedRom('${escHtml(d)}')">删除</button>`;
        el.appendChild(item);
    });
}

function selectRomProject(name) {
    document.getElementById('romProjectSelect').value = name;
    writeLog(`已选择线刷项目：${name}`, 'info');
    refreshBatList();
    // 刷新列表以更新高亮状态
    refreshExtractedRoms();
}

// 清空全部已解压线刷包
document.getElementById('clearAllRomsBtn').onclick = async () => {
    showConfirm('清空线刷包', '确定清空全部已解压线刷包？此操作不可恢复。', async () => {
        const d = await apiPost('/api/rom/delete', {rom_dir: '__ALL__'});
        if (d.success) {
            writeLog('已清空全部线刷包', 'ok');
        } else {
            writeLog(d.error || '清空失败', 'err');
        }
        await refreshExtractedRoms();
    });
};

async function deleteExtractedRom(dn) {
    showConfirm('删除线刷包', `确定删除 ${dn}？`, async () => {
        const d = await apiPost('/api/rom/delete', {rom_dir: dn});
        d.success ? writeLog(d.msg, 'ok') : writeLog(d.error, 'err');
        await refreshExtractedRoms();
    });
}

// ============ 解压 ============
document.getElementById('extractBtn').onclick = async () => {
    const rn = document.getElementById('romSelect').value;
    if (!rn) return;
    
    document.getElementById('extractBtn').disabled = true;
    writeLog(`启动解压：${rn}`);
    showProgress('解压进度');
    
    try {
        const d = await apiPost('/api/rom/copy_extract', {rom_name: rn});
        if (!d.success) {
            writeLog('启动解压失败：' + d.error, 'err');
            document.getElementById('extractBtn').disabled = false;
            hideProgress();
            return;
        }
        
        // WebSocket 会推送进度，这里只等待完成
        // 或者用传统轮询作为后备
        pollTaskFallback(d.task_id, (ok, err) => {
            document.getElementById('extractBtn').disabled = false;
            hideProgress();
            if (ok) {
                writeLog('解压完成', 'ok');
                refreshExtractedRoms().then(() => {
                    const base = rn.replace(/\.(tar\.gz|tar\.bz2|tar\.md5|tgz|tbz2|zip|7z|rar|gz)$/i, '').replace(/\.[^.]+$/,'');
                    // 如果只有一个已解压包，自动选中它
                    const sel = document.getElementById('romProjectSelect');
                    const options = [...sel.options].filter(o => o.value);
                    if (options.length === 1) {
                        selectRomProject(options[0].value);
                    } else if ([...sel.options].some(o => o.value === base)) {
                        sel.value = base;
                        refreshBatList();
                    } else {
                        refreshBatList();
                    }
                });
                loadVbmetaRomList();
            } else {
                writeLog('解压失败：' + err, 'err');
            }
        });
    } catch(e) {
        writeLog('解压异常：' + e.message, 'err');
        document.getElementById('extractBtn').disabled = false;
        hideProgress();
    }
};

// 传统轮询后备
function pollTaskFallback(taskId, onFinish, options = {}) {
    let lastLogLen = 0;
    const moduleName = options.module || '';
    const progressPrefix = options.progressPrefix || '';
    const timer = setInterval(async () => {
        const res = await apiGet(`/api/task/status?task_id=${taskId}`);
        if (!res.success) {
            clearInterval(timer);
            if (moduleName) setModuleStatus(moduleName, `${progressPrefix}失败：${res.error}`, 'err');
            onFinish && onFinish(false, res.error);
            return;
        }
        
        const newLogs = res.logs.slice(lastLogLen);
        newLogs.forEach(line => {
            if (line.includes('解决办法')) writeLog(line, 'tip');
            else if (line.includes('失败')) writeLog(line, 'err');
            else writeLog(line);
        });
        lastLogLen = res.logs.length;
        
        // 更新进度
        if (res.progress) {
            updateProgress(res.progress, '');
            if (moduleName) updateModuleProgress(moduleName, res.progress, progressPrefix || '执行中');
        }
        
        if (res.status === 'success') {
            clearInterval(timer);
            if (moduleName) updateModuleProgress(moduleName, 100, '完成');
            onFinish && onFinish(true, '');
        } else if (res.status === 'error') {
            clearInterval(timer);
            if (moduleName) setModuleStatus(moduleName, `${progressPrefix}失败：${res.error}`, 'err');
            onFinish && onFinish(false, res.error);
        }
    }, 500);
    return timer;
}

