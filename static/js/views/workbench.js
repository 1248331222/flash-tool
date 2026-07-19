// flash_tool/static/js/views/workbench.js
// ============ 工作台 v4.0.0（重构版） ============
// 配置栏 + 步骤列表（拖拽排序+单独执行）+ 添加步骤弹窗 + Fastboot快捷命令弹窗 + 执行栏

// ===== 状态变量 =====
var _wbSteps = [];            // 步骤列表
var _wbConfigs = [];          // 已导入的配置列表
var _wbCurrentConfig = '';    // 当前选中的配置名
var _wbEditMode = false;      // 是否处于编辑模式（输入框可编辑）
var _wbExecState = 'idle';    // 执行状态：idle/running/paused/done/failed
var _wbCurrentStepType = '';  // 当前选中的步骤类型（添加步骤弹窗）
var _wbDragSrcIdx = -1;       // 拖拽源索引

// ===== 工具函数 =====
function _wbEsc(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function _wbSetStatus(msg, type) {
    var el = document.getElementById('wbStatusText');
    if (el) el.textContent = msg;
    if (typeof writeLog === 'function') writeLog(msg, type || 'info');
}

function _wbShowOutput(text) {
    var el = document.getElementById('wbOutput');
    if (!el) return;
    el.style.display = 'block';
    el.innerHTML += text + '\n';
    el.scrollTop = el.scrollHeight;
}

function _wbClearOutput() {
    var el = document.getElementById('wbOutput');
    if (el) { el.innerHTML = ''; el.style.display = 'none'; }
}

// ===== 配置管理 =====

// 加载配置列表
async function _wbLoadConfigs() {
    try {
        var resp = await fetch('/api/workbench/configs');
        var data = await resp.json();
        if (data.success) {
            _wbConfigs = data.configs || [];
            _wbUpdateConfigList();
            _wbUpdateInputPlaceholder();
            // 如果只有一个配置，自动选中
            if (_wbConfigs.length === 1 && !_wbCurrentConfig) {
                _wbSelectConfig(_wbConfigs[0].name);
            }
        }
    } catch(e) {
        console.error('[workbench] 加载配置列表失败:', e);
    }
}

// 更新配置下拉框（原生 select，点击即可弹出列表）
function _wbUpdateConfigList() {
    var sel = document.getElementById('wbConfigSelect');
    if (!sel) return;
    var html = '';
    if (_wbConfigs.length === 0) {
        html += '<option value="">暂无配置，请点击「修改」创建</option>';
    } else {
        html += '<option value="">-- 请选择配置 --</option>';
        for (var i = 0; i < _wbConfigs.length; i++) {
            var name = _wbConfigs[i].name;
            var stepCount = _wbConfigs[i].step_count || 0;
            html += '<option value="' + _wbEsc(name) + '">' + _wbEsc(name) + '（' + stepCount + ' 步）</option>';
        }
    }
    sel.innerHTML = html;
    // 恢复当前选中
    if (_wbCurrentConfig) sel.value = _wbCurrentConfig;
}

// 更新输入框提示文字
function _wbUpdateInputPlaceholder() {
    var input = document.getElementById('wbConfigInput');
    if (!input) return;
    if (_wbEditMode) {
        input.placeholder = '请输入新配置名称';
    } else {
        input.placeholder = '请输入配置名称';
    }
}

// 选择配置
async function _wbSelectConfig(name) {
    if (!name) return;
    _wbCurrentConfig = name;
    var sel = document.getElementById('wbConfigSelect');
    if (sel) sel.value = name;
    var input = document.getElementById('wbConfigInput');
    if (input) input.value = name;
    // 加载配置详情
    try {
        var resp = await fetch('/api/workbench/configs/' + encodeURIComponent(name));
        var data = await resp.json();
        if (data.success && data.config) {
            _wbSteps = data.config.steps || [];
            _wbRenderSteps();
            _wbSetStatus('工作台状态：已加载配置「' + name + '」（' + _wbSteps.length + ' 步）', 'ok');
        }
    } catch(e) {
        console.error('[workbench] 加载配置详情失败:', e);
    }
}

// 保存配置
async function _wbSaveConfig(name, steps) {
    try {
        var resp = await fetch('/api/workbench/configs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name, steps: steps }),
        });
        var data = await resp.json();
        if (data.success) {
            _wbCurrentConfig = name;
            await _wbLoadConfigs(); // 刷新列表
            _wbSetStatus('工作台状态：配置「' + name + '」已保存（' + steps.length + ' 步）', 'ok');
            return true;
        } else {
            _wbSetStatus('工作台状态：保存失败 - ' + (data.error || '未知错误'), 'err');
            return false;
        }
    } catch(e) {
        _wbSetStatus('工作台状态：保存异常 - ' + e.message, 'err');
        return false;
    }
}

// 删除配置
async function _wbDeleteConfig(name) {
    try {
        var resp = await fetch('/api/workbench/configs/' + encodeURIComponent(name), { method: 'DELETE' });
        var data = await resp.json();
        if (data.success) {
            if (_wbCurrentConfig === name) {
                _wbCurrentConfig = '';
                _wbSteps = [];
                _wbRenderSteps();
                var input = document.getElementById('wbConfigInput');
                if (input) input.value = '';
                var sel = document.getElementById('wbConfigSelect');
                if (sel) sel.value = '';
            }
            await _wbLoadConfigs();
            _wbSetStatus('工作台状态：配置「' + name + '」已删除', 'ok');
        } else {
            _wbSetStatus('工作台状态：删除失败 - ' + (data.error || '未知错误'), 'err');
        }
    } catch(e) {
        _wbSetStatus('工作台状态：删除异常 - ' + e.message, 'err');
    }
}

// 导出配置
async function _wbExportConfig() {
    if (!_wbCurrentConfig) {
        _wbSetStatus('工作台状态：请先选择要导出的配置', 'warn');
        if (typeof showToast === 'function') showToast('请先选择要导出的配置');
        return;
    }
    try {
        // 使用文件选择器选择导出目录
        var dirResult = await FileApi.pickFile({ mode: 'dir' });
        if (!dirResult || !dirResult.path) return;
        var exportPath = dirResult.path.replace(/\/+$/, '') + '/' + _wbCurrentConfig + '.json';
        var resp = await fetch('/api/workbench/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: _wbCurrentConfig, path: exportPath }),
        });
        var data = await resp.json();
        if (data.success) {
            _wbSetStatus('工作台状态：配置已导出到 ' + data.path, 'ok');
            if (typeof showToast === 'function') showToast('配置已导出');
        } else {
            _wbSetStatus('工作台状态：导出失败 - ' + (data.error || '未知错误'), 'err');
        }
    } catch(e) {
        _wbSetStatus('工作台状态：导出异常 - ' + e.message, 'err');
    }
}

// 导入配置
async function _wbImportConfig() {
    try {
        var file = await FileApi.pickFile({ filter: '.json' });
        if (!file || !file.path) return;
        var resp = await fetch('/api/workbench/import', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: file.path }),
        });
        var data = await resp.json();
        if (data.success) {
            await _wbLoadConfigs();
            _wbSelectConfig(data.name);
            _wbSetStatus('工作台状态：配置「' + data.name + '」已导入（' + data.step_count + ' 步）', 'ok');
            if (typeof showToast === 'function') showToast('配置已导入');
        } else {
            _wbSetStatus('工作台状态：导入失败 - ' + (data.error || '未知错误'), 'err');
        }
    } catch(e) {
        _wbSetStatus('工作台状态：导入异常 - ' + e.message, 'err');
    }
}

// 自动保存（步骤修改后自动保存到当前配置）
var _wbAutoSaveTimer = null;
function _wbAutoSave() {
    if (!_wbCurrentConfig || _wbEditMode) return; // 编辑模式下不自动保存
    if (_wbAutoSaveTimer) clearTimeout(_wbAutoSaveTimer);
    _wbAutoSaveTimer = setTimeout(function() {
        _wbSaveConfig(_wbCurrentConfig, _wbSteps);
    }, 1000);
}

// ===== 配置栏交互 =====

// 切换编辑模式：非编辑模式显示 select（点击弹出列表），编辑模式显示 input（输入新名称）
function _wbToggleEdit() {
    var sel = document.getElementById('wbConfigSelect');
    var input = document.getElementById('wbConfigInput');
    var btn = document.getElementById('wbEditBtn');
    if (!sel || !input || !btn) return;

    if (!_wbEditMode) {
        // 进入编辑模式：隐藏 select，显示 input
        _wbEditMode = true;
        sel.style.display = 'none';
        input.style.display = '';
        input.value = _wbCurrentConfig || '';
        input.focus();
        input.select();
        btn.textContent = '确认';
        btn.classList.add('btn-success');
        _wbUpdateInputPlaceholder();
    } else {
        // 确认保存
        var name = input.value.trim();
        if (!name) {
            _wbSetStatus('工作台状态：配置名称不能为空', 'warn');
            return;
        }
        _wbSaveConfig(name, _wbSteps).then(function(ok) {
            if (ok) {
                _wbEditMode = false;
                input.style.display = 'none';
                sel.style.display = '';
                btn.textContent = '修改';
                btn.classList.remove('btn-success');
                _wbUpdateInputPlaceholder();
            }
        });
    }
}

// 配置下拉框 change 事件（非编辑模式下选择配置）
function _wbOnSelectChange() {
    if (_wbEditMode) return;
    var sel = document.getElementById('wbConfigSelect');
    if (!sel) return;
    var name = sel.value.trim();
    if (!name) return; // 选中空选项（提示项）不处理
    if (name === _wbCurrentConfig) return;
    _wbSelectConfig(name);
}

// ===== 步骤列表 =====

// 步骤描述
function _wbStepDescription(s) {
    var p = s.partition || '';
    switch (s.type) {
        case 'flash':
            return '刷写 <b>' + _wbEsc(p || '未知') + '</b> 分区';
        case 'flash-args-front':
            return '刷写 <b>' + _wbEsc(p || '未知') + '</b>（参数在前）';
        case 'flash-args-back':
            return '刷写 <b>' + _wbEsc(p || '未知') + '</b>（参数在后）';
        case 'flash-dir':
            return '遍历目录 <b>' + _wbEsc(s.dir || '') + '</b> 刷写镜像';
        case 'cow':
            return '清理 COW <b>' + _wbEsc(p || '未知') + '</b>';
        case 'erase':
            return '擦除 <b>' + _wbEsc(p || '未知') + '</b> 分区';
        case 'reboot':
            var tm = { bootloader: 'Bootloader', recovery: 'Recovery', system: '系统', fastboot: 'Fastbootd' };
            return '重启到 <b>' + _wbEsc(tm[p] || p || '系统') + '</b>';
        case 'flashing':
            if (/unlock/i.test(s.raw||'')) return '<b>解锁 Bootloader</b>';
            if (/lock/i.test(s.raw||'')) return '<b>上锁 Bootloader</b>';
            return '执行 Flashing 命令';
        case 'getvar':
            return '查询 <b>' + _wbEsc(p || s.raw || '') + '</b>';
        case 'custom':
        case 'quick':
        case 'raw':
        default:
            return '执行 <b>' + _wbEsc(s.label || s.raw || '命令') + '</b>';
    }
}

// 渲染步骤列表
function _wbRenderSteps() {
    var container = document.getElementById('wbStepList');
    if (!container) return;
    if (!_wbSteps.length) {
        container.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-muted)">请先选择或创建配置，然后添加步骤</div>';
        return;
    }
    var html = '';
    for (var i = 0; i < _wbSteps.length; i++) {
        var s = _wbSteps[i];
        var raw = s.raw || '';
        var levelClass = 'step-item';
        if (s.level === 'danger') levelClass += ' step-item-danger';
        if (s.level === 'warn') levelClass += ' step-item-warn';

        html += '<div class="' + levelClass + '" data-step-idx="' + i + '" draggable="true">';
        html += '  <div class="step-item-header">';
        html += '    <div class="step-item-left">';
        html += '      <span class="step-num">' + (i + 1) + '</span>';
        html += '      <span class="step-desc">' + _wbStepDescription(s) + '</span>';
        html += '    </div>';
        html += '    <div class="step-item-right">';
        html += '      <button class="step-run-btn" data-run-idx="' + i + '" title="单独执行">▶</button>';
        html += '      <button class="step-del-btn" data-del-idx="' + i + '">删除</button>';
        html += '    </div>';
        html += '  </div>';
        if (raw) html += '  <div class="step-cmd">' + _wbEsc(raw) + '</div>';
        html += '</div>';
    }
    container.innerHTML = html;

    // 绑定删除按钮
    var delBtns = container.querySelectorAll('[data-del-idx]');
    for (var d = 0; d < delBtns.length; d++) {
        delBtns[d].onclick = function() {
            if (_wbExecState === 'running') return;
            var idx = parseInt(this.getAttribute('data-del-idx'));
            _wbSteps.splice(idx, 1);
            _wbRenderSteps();
            _wbAutoSave();
        };
    }

    // 绑定单独执行按钮
    var runBtns = container.querySelectorAll('[data-run-idx]');
    for (var r = 0; r < runBtns.length; r++) {
        runBtns[r].onclick = function() {
            if (_wbExecState === 'running') return;
            var idx = parseInt(this.getAttribute('data-run-idx'));
            _wbExecSingle(idx);
        };
    }

    // 绑定拖拽事件
    _wbBindDragEvents(container);
}

// 绑定拖拽排序事件
function _wbBindDragEvents(container) {
    var items = container.querySelectorAll('.step-item[draggable="true"]');
    for (var i = 0; i < items.length; i++) {
        items[i].addEventListener('dragstart', function(e) {
            _wbDragSrcIdx = parseInt(this.getAttribute('data-step-idx'));
            this.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
        });
        items[i].addEventListener('dragend', function(e) {
            this.classList.remove('dragging');
            _wbDragSrcIdx = -1;
        });
        items[i].addEventListener('dragover', function(e) {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            this.classList.add('drag-over');
        });
        items[i].addEventListener('dragleave', function(e) {
            this.classList.remove('drag-over');
        });
        items[i].addEventListener('drop', function(e) {
            e.preventDefault();
            this.classList.remove('drag-over');
            var destIdx = parseInt(this.getAttribute('data-step-idx'));
            if (_wbDragSrcIdx >= 0 && _wbDragSrcIdx !== destIdx) {
                // 移动数组元素
                var moved = _wbSteps.splice(_wbDragSrcIdx, 1)[0];
                _wbSteps.splice(destIdx, 0, moved);
                _wbRenderSteps();
                _wbAutoSave();
            }
        });
    }
}

// ===== 命令路由：WebUSB 模式 / 后端模式 =====

/**
 * 执行单个工作台步骤的 fastboot 命令，自动路由到 WebUSB 或后端。
 * @param {Object} step - 步骤对象 { raw, type, partition, image, ... }
 * @returns {Promise<{success: boolean, output: string}>}
 */
async function _wbRunFastbootCommand(step) {
    var args = (step.raw || '').split(/\s+/).filter(Boolean);
    if (!args.length) {
        return { success: false, output: '该步骤没有可执行的命令' };
    }

    // ===== WebUSB 模式 =====
    if (typeof appRunMode !== 'undefined' && appRunMode === 'webusb' &&
        typeof webusbFastbootReady !== 'undefined' && webusbFastbootReady) {
        var cmd = String(args[0] || '').toLowerCase();

        // flash 命令：需要先通过后端 API 读取镜像字节，再通过 WebUSB 刷写
        if (cmd === 'flash') {
            var partition = args[1];
            var imagePath = args[2];
            if (!partition || !imagePath) {
                return { success: false, output: 'flash 命令缺少分区名或镜像路径' };
            }
            // 通过后端 API 读取镜像字节（WebUSB 模式仍需后端提供文件读取）
            var baseUrl = (typeof App !== 'undefined' && App.backendUrl) ? App.backendUrl : '';
            var blobUrl = baseUrl + '/api/image/path_blob?path=' + encodeURIComponent(imagePath);
            var blobResp = await fetch(blobUrl);
            if (!blobResp.ok) {
                var blobErr = '';
                try { blobErr = await blobResp.text(); } catch(e) { blobErr = blobResp.status + ' ' + blobResp.statusText; }
                return { success: false, output: '读取镜像失败(' + imagePath + '): ' + blobErr };
            }
            var bytes = new Uint8Array(await blobResp.arrayBuffer());
            if (typeof runWebUsbFastbootCommand !== 'function') {
                return { success: false, output: 'WebUSB 模块未加载' };
            }
            var flashResult = await runWebUsbFastbootCommand({
                command: 'flash',
                partition: partition,
                payload: bytes
            });
            return { success: true, output: flashResult || ('已刷写 ' + partition) };
        }

        // delete-logical-partition（COW 清理）：WebUSB fastboot.mjs 不支持
        if (cmd === 'delete-logical-partition') {
            return {
                success: false,
                output: 'WebUSB 模式不支持 delete-logical-partition 命令（COW 清理），请切换到后端模式'
            };
        }

        // 其他命令：通过 fastbootArgsToWebUsbCommand 路由
        if (typeof fastbootArgsToWebUsbCommand !== 'function' || typeof runWebUsbFastbootCommand !== 'function') {
            return { success: false, output: 'WebUSB 模块未加载' };
        }
        var cmdObj = fastbootArgsToWebUsbCommand(args);
        if (!cmdObj) {
            return { success: false, output: 'WebUSB 模式不支持该命令: ' + args.join(' ') };
        }
        var result = await runWebUsbFastbootCommand(cmdObj);
        return { success: true, output: result || '完成' };
    }

    // ===== 后端模式 =====
    var backendUrl = (typeof App !== 'undefined' && App.backendUrl) ? App.backendUrl : '';
    var resp = await fetch(backendUrl + '/api/fastboot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ args: args }),
    });
    var data = await resp.json();
    if (data.success) {
        return { success: true, output: (data.output || data.combined || '').trim() };
    } else {
        return { success: false, output: data.error || data.combined || '未知错误' };
    }
}

// ===== 单独执行步骤 =====
async function _wbExecSingle(idx) {
    if (idx < 0 || idx >= _wbSteps.length) return;
    var s = _wbSteps[idx];
    var args = (s.raw || '').split(/\s+/).filter(Boolean);
    if (!args.length) {
        _wbSetStatus('工作台状态：该步骤没有可执行的命令', 'warn');
        return;
    }
    _wbSetStatus('工作台状态：正在执行步骤 ' + (idx + 1) + '...', 'info');
    _wbShowOutput('▶ [步骤 ' + (idx + 1) + '] fastboot ' + args.join(' '));
    try {
        var result = await _wbRunFastbootCommand(s);
        if (result.success) {
            if (result.output) _wbShowOutput(result.output);
            _wbShowOutput('✓ 步骤 ' + (idx + 1) + ' 完成');
            _wbSetStatus('工作台状态：步骤 ' + (idx + 1) + ' 执行完成', 'ok');
        } else {
            _wbShowOutput('✗ 步骤 ' + (idx + 1) + ' 失败: ' + result.output);
            _wbSetStatus('工作台状态：步骤 ' + (idx + 1) + ' 失败', 'err');
        }
    } catch(e) {
        _wbShowOutput('✗ 步骤 ' + (idx + 1) + ' 异常: ' + e.message);
        _wbSetStatus('工作台状态：步骤 ' + (idx + 1) + ' 异常', 'err');
    }
}

// ===== 添加步骤弹窗 =====

// 显示添加步骤弹窗
function _wbShowAddStepDialog() {
    var dialog = document.getElementById('wbAddStepDialog');
    if (!dialog) return;
    // 重置到卡片选择页
    document.getElementById('wbStepCards').style.display = '';
    document.getElementById('wbStepForm').style.display = 'none';
    _wbCurrentStepType = '';
    dialog.style.display = 'flex';
}

// 关闭添加步骤弹窗
function _wbCloseAddStepDialog() {
    var dialog = document.getElementById('wbAddStepDialog');
    if (dialog) dialog.style.display = 'none';
}

// 选择步骤类型（卡片点击）
function _wbSelectStepType(type) {
    _wbCurrentStepType = type;
    document.getElementById('wbStepCards').style.display = 'none';
    document.getElementById('wbStepForm').style.display = '';
    var content = document.getElementById('wbStepFormContent');
    var title = document.getElementById('wbAddStepDialogTitle');

    var titles = {
        'flash': '刷写镜像',
        'flash-args-front': '刷写镜像（参数在前）',
        'flash-args-back': '刷写镜像（参数在后）',
        'flash-dir': '遍历目录镜像',
        'cow': 'COW 分区清理',
        'custom': '自定义 Fastboot 命令',
    };
    title.textContent = titles[type] || '添加步骤';

    switch(type) {
        case 'flash':
            content.innerHTML = _wbFormFlash(false);
            break;
        case 'flash-args-front':
            content.innerHTML = _wbFormFlash(true, 'front');
            break;
        case 'flash-args-back':
            content.innerHTML = _wbFormFlash(true, 'back');
            break;
        case 'flash-dir':
            content.innerHTML = _wbFormFlashDir();
            break;
        case 'cow':
            content.innerHTML = _wbFormCow();
            break;
        case 'custom':
            content.innerHTML = _wbFormCustom();
            break;
    }
}

// 返回卡片选择
function _wbBackToCards() {
    document.getElementById('wbStepCards').style.display = '';
    document.getElementById('wbStepForm').style.display = 'none';
    _wbCurrentStepType = '';
    document.getElementById('wbAddStepDialogTitle').textContent = '添加步骤';
}

// 表单：刷写镜像
function _wbFormFlash(hasArgs, argsPos) {
    var argsHtml = '';
    if (hasArgs) {
        argsHtml = '<div class="wb-form-row">';
        argsHtml += '<label>附加参数</label>';
        argsHtml += '<input type="text" id="wbFormArgs" placeholder="如 --disable-verity --disable-verification">';
        argsHtml += '</div>';
    }
    return '<div class="wb-form-row">' +
        '<label>分区名</label>' +
        '<input type="text" id="wbFormPartition" placeholder="如 boot、dtbo、vbmeta">' +
        '</div>' +
        '<div class="wb-form-row">' +
        '<label>镜像路径</label>' +
        '<div class="wb-form-input-group">' +
        '<input type="text" id="wbFormImage" placeholder="镜像绝对路径">' +
        '<button class="btn small secondary" data-action="wb-pick-image">📁</button>' +
        '</div>' +
        '</div>' + argsHtml;
}

// 表单：遍历目录镜像
function _wbFormFlashDir() {
    return '<div class="wb-form-row">' +
        '<label>镜像目录</label>' +
        '<div class="wb-form-input-group">' +
        '<input type="text" id="wbFormDir" placeholder="选择包含镜像的目录">' +
        '<button class="btn small secondary" data-action="wb-pick-dir">📁</button>' +
        '</div>' +
        '</div>' +
        '<div class="wb-form-row">' +
        '<label>文件后缀</label>' +
        '<input type="text" id="wbFormSuffix" value=".img" placeholder="如 .img">' +
        '</div>' +
        '<div class="wb-form-row wb-form-checkbox">' +
        '<label><input type="checkbox" id="wbFormAB"> AB 机型</label>' +
        '<div class="wb-form-hint" id="wbABHint" style="display:none;">勾选后：如果目录中任何一个镜像带 _a/_b 则全部以默认方式刷写（不补全）；如果所有镜像都不带 _a/_b 则每个镜像补全为同文件刷到 _a 和 _b 两个分区</div>' +
        '</div>';
}

// 表单：COW 分区清理
function _wbFormCow() {
    return '<div class="wb-form-row">' +
        '<label>分区名</label>' +
        '<input type="text" id="wbFormPartition" placeholder="如 boot（将清理 boot-cow）">' +
        '</div>' +
        '<div class="wb-form-row wb-form-checkbox">' +
        '<label><input type="checkbox" id="wbFormAB"> AB 机型</label>' +
        '<div class="wb-form-hint" id="wbABHint" style="display:none;">勾选后：输入 boot 将自动补全 boot_a-cow 和 boot_b-cow 两条步骤</div>' +
        '</div>';
}

// 表单：自定义 Fastboot 命令
function _wbFormCustom() {
    return '<div class="wb-form-row">' +
        '<label>fastboot 命令参数</label>' +
        '<input type="text" id="wbFormCmd" placeholder="如 flash boot /sdcard/boot.img 或 reboot bootloader">' +
        '</div>' +
        '<div class="wb-form-row">' +
        '<label>步骤描述（可选）</label>' +
        '<input type="text" id="wbFormLabel" placeholder="如 刷写 boot 分区">' +
        '</div>';
}

// 选择镜像文件
async function _wbPickImage() {
    try {
        var file = await FileApi.pickFile({ filter: '.img,.bin,.elf' });
        if (file && file.path) {
            var input = document.getElementById('wbFormImage');
            if (input) input.value = file.path;
        } else if (file && file.name) {
            // WebUSB 模式：浏览器无法获取绝对路径
            _wbSetStatus('工作台状态：浏览器安全限制无法获取文件绝对路径，请手动输入路径或切换到后端模式', 'warn');
        }
    } catch(e) { console.error(e); }
}

// 选择目录
async function _wbPickDir() {
    try {
        var result = await FileApi.pickFile({ mode: 'dir' });
        if (result && result.path) {
            var input = document.getElementById('wbFormDir');
            if (input) input.value = result.path;
        } else if (result && result.name) {
            // WebUSB 模式：浏览器无法获取目录绝对路径
            _wbSetStatus('工作台状态：浏览器安全限制无法获取目录绝对路径，遍历目录镜像功能需要后端模式', 'warn');
        }
    } catch(e) { console.error(e); }
}

// 确认添加步骤
async function _wbAddStepConfirm() {
    var type = _wbCurrentStepType;
    var newSteps = [];

    switch(type) {
        case 'flash':
        case 'flash-args-front':
        case 'flash-args-back': {
            var partition = (document.getElementById('wbFormPartition').value || '').trim();
            var image = (document.getElementById('wbFormImage').value || '').trim();
            var args = '';
            if (type === 'flash-args-front' || type === 'flash-args-back') {
                args = (document.getElementById('wbFormArgs').value || '').trim();
            }
            if (!partition || !image) {
                _wbSetStatus('工作台状态：分区名和镜像路径不能为空', 'warn');
                return;
            }
            var raw;
            if (type === 'flash-args-front' && args) {
                raw = args + ' flash ' + partition + ' ' + image;
            } else if (type === 'flash-args-back' && args) {
                raw = 'flash ' + partition + ' ' + image + ' ' + args;
            } else {
                raw = 'flash ' + partition + ' ' + image;
            }
            newSteps.push({
                type: type,
                partition: partition,
                image: image,
                args: args,
                raw: raw,
                label: '刷写 ' + partition,
                level: 'danger',
            });
            break;
        }
        case 'flash-dir': {
            var dir = (document.getElementById('wbFormDir').value || '').trim();
            var suffix = (document.getElementById('wbFormSuffix').value || '.img').trim();
            var isAB = document.getElementById('wbFormAB').checked;
            if (!dir) {
                _wbSetStatus('工作台状态：镜像目录不能为空', 'warn');
                return;
            }
            // 获取目录中的镜像文件
            try {
                var resp = await fetch('/api/fs/browse?path=' + encodeURIComponent(dir));
                var data = await resp.json();
                if (!data.success) {
                    _wbSetStatus('工作台状态：读取目录失败 - ' + (data.error || ''), 'err');
                    return;
                }
                var items = data.items || [];
                var images = [];
                for (var i = 0; i < items.length; i++) {
                    if (items[i].type === 'file' && items[i].name.endsWith(suffix)) {
                        images.push(items[i]);
                    }
                }
                if (!images.length) {
                    _wbSetStatus('工作台状态：目录中没有找到 ' + suffix + ' 文件', 'warn');
                    return;
                }
                // 检查是否有 _a/_b 镜像（使用动态后缀）
                var abPattern = new RegExp('_a' + suffix.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '$|_b' + suffix.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '$', 'i');
                var hasAB = false;
                for (var j = 0; j < images.length; j++) {
                    if (abPattern.test(images[j].name)) {
                        hasAB = true;
                        break;
                    }
                }
                for (var k = 0; k < images.length; k++) {
                    var img = images[k];
                    var partitionName = img.name.replace(suffix, '');
                    if (isAB && hasAB) {
                        // AB 机型且目录已有 _a/_b：直接刷写
                        newSteps.push({
                            type: 'flash-dir',
                            partition: partitionName,
                            image: img.abs_path,
                            raw: 'flash ' + partitionName + ' ' + img.abs_path,
                            label: '刷写 ' + partitionName,
                            dir: dir,
                            level: 'danger',
                        });
                    } else if (isAB && !hasAB) {
                        // AB 机型但目录无 _a/_b：同一文件刷到 _a 和 _b
                        newSteps.push({
                            type: 'flash-dir',
                            partition: partitionName + '_a',
                            image: img.abs_path,
                            raw: 'flash ' + partitionName + '_a ' + img.abs_path,
                            label: '刷写 ' + partitionName + '_a',
                            dir: dir,
                            level: 'danger',
                        });
                        newSteps.push({
                            type: 'flash-dir',
                            partition: partitionName + '_b',
                            image: img.abs_path,
                            raw: 'flash ' + partitionName + '_b ' + img.abs_path,
                            label: '刷写 ' + partitionName + '_b',
                            dir: dir,
                            level: 'danger',
                        });
                    } else {
                        // 非 AB：直接刷写
                        newSteps.push({
                            type: 'flash-dir',
                            partition: partitionName,
                            image: img.abs_path,
                            raw: 'flash ' + partitionName + ' ' + img.abs_path,
                            label: '刷写 ' + partitionName,
                            dir: dir,
                            level: 'danger',
                        });
                    }
                }
            } catch(e) {
                _wbSetStatus('工作台状态：读取目录异常 - ' + e.message, 'err');
                return;
            }
            break;
        }
        case 'cow': {
            var cowPartition = (document.getElementById('wbFormPartition').value || '').trim();
            var cowAB = document.getElementById('wbFormAB').checked;
            if (!cowPartition) {
                _wbSetStatus('工作台状态：分区名不能为空', 'warn');
                return;
            }
            if (cowAB) {
                newSteps.push({
                    type: 'cow',
                    partition: cowPartition + '_a',
                    raw: 'delete-logical-partition ' + cowPartition + '_a-cow',
                    label: '清理 ' + cowPartition + '_a-cow',
                    level: 'warn',
                });
                newSteps.push({
                    type: 'cow',
                    partition: cowPartition + '_b',
                    raw: 'delete-logical-partition ' + cowPartition + '_b-cow',
                    label: '清理 ' + cowPartition + '_b-cow',
                    level: 'warn',
                });
            } else {
                newSteps.push({
                    type: 'cow',
                    partition: cowPartition,
                    raw: 'delete-logical-partition ' + cowPartition + '-cow',
                    label: '清理 ' + cowPartition + '-cow',
                    level: 'warn',
                });
            }
            break;
        }
        case 'custom': {
            var cmd = (document.getElementById('wbFormCmd').value || '').trim();
            var label = (document.getElementById('wbFormLabel').value || '').trim();
            if (!cmd) {
                _wbSetStatus('工作台状态：命令不能为空', 'warn');
                return;
            }
            newSteps.push({
                type: 'custom',
                raw: cmd,
                label: label || '自定义命令',
                level: 'warn',
            });
            break;
        }
    }

    // 添加步骤到列表
    for (var m = 0; m < newSteps.length; m++) {
        _wbSteps.push(newSteps[m]);
    }
    _wbRenderSteps();
    _wbAutoSave();
    _wbCloseAddStepDialog();
    _wbSetStatus('工作台状态：已添加 ' + newSteps.length + ' 个步骤', 'ok');
}

// ===== Fastboot 快捷命令弹窗 =====

function _wbShowFastbootDialog() {
    var dialog = document.getElementById('wbFastbootDialog');
    if (dialog) dialog.style.display = 'flex';
}

function _wbCloseFastbootDialog() {
    var dialog = document.getElementById('wbFastbootDialog');
    if (dialog) dialog.style.display = 'none';
}

// 添加快捷命令到步骤列表
function _wbAddQuickStep(cmd, label) {
    var level = 'safe';
    if (/erase|format|-w|unlock|lock|flash/i.test(cmd)) level = 'danger';
    else if (/reboot/i.test(cmd)) level = 'warn';

    // 判断类型
    var type = 'quick';
    var partition = '';
    if (/^flash\s+(\S+)/.test(cmd)) {
        type = 'flash';
        partition = cmd.match(/^flash\s+(\S+)/)[1];
    } else if (/^erase\s+(\S+)/.test(cmd)) {
        type = 'erase';
        partition = cmd.match(/^erase\s+(\S+)/)[1];
    } else if (/^reboot\s*(\S*)/.test(cmd)) {
        type = 'reboot';
        partition = cmd.match(/^reboot\s*(\S*)/)[1] || 'system';
    } else if (/^flashing\s+(\S+)/.test(cmd)) {
        type = 'flashing';
    } else if (/^getvar\s+(\S+)/.test(cmd)) {
        type = 'getvar';
        partition = cmd.match(/^getvar\s+(\S+)/)[1];
    }

    _wbSteps.push({
        type: type,
        partition: partition,
        raw: cmd,
        label: label,
        level: level,
    });
    _wbRenderSteps();
    _wbAutoSave();
    _wbSetStatus('工作台状态：已添加「' + label + '」', 'ok');
}

// ===== 执行栏 =====

// 全部执行
async function _wbExecuteAll() {
    var btn = document.getElementById('wbExecuteBtn');
    if (_wbExecState === 'idle' || _wbExecState === 'done' || _wbExecState === 'failed') {
        if (!_wbSteps.length) {
            _wbSetStatus('工作台状态：步骤列表为空', 'warn');
            return;
        }
        if (!canFastboot && !webusbFastbootReady) {
            _wbSetStatus('工作台状态：请先检测到 Fastboot 设备', 'warn');
            if (typeof showToast === 'function') showToast('请先检测到 Fastboot 设备');
            return;
        }
        _wbExecState = 'running';
        if (btn) { btn.textContent = '暂停'; btn.classList.remove('warn'); btn.classList.add('secondary'); }
        _wbClearOutput();
        _wbShowOutput('开始执行全部步骤（共 ' + _wbSteps.length + ' 步）');
        await _wbExecuteFromIndex(0);
    } else if (_wbExecState === 'running') {
        // 暂停
        _wbExecState = 'paused';
        if (btn) { btn.textContent = '继续'; }
        _wbSetStatus('工作台状态：已暂停', 'warn');
    } else if (_wbExecState === 'paused') {
        // 继续
        _wbExecState = 'running';
        if (btn) { btn.textContent = '暂停'; }
        _wbSetStatus('工作台状态：继续执行...', 'info');
        // 注意：实际继续需要保存暂停位置，这里简化处理
    }
}

// 从指定索引执行
async function _wbExecuteFromIndex(startIdx) {
    var progressEl = document.getElementById('wbProgress');
    var btn = document.getElementById('wbExecuteBtn');
    if (progressEl) progressEl.style.display = 'flex';

    for (var i = startIdx; i < _wbSteps.length; i++) {
        if (_wbExecState !== 'running') return; // 暂停或停止

        var s = _wbSteps[i];
        var args = (s.raw || '').split(/\s+/).filter(Boolean);
        if (!args.length) continue;

        // 更新进度
        var pct = parseInt((i / _wbSteps.length) * 100);
        if (progressEl) {
            var pb = progressEl.querySelector('.module-progress-bar');
            var pt = progressEl.querySelector('.module-progress-text');
            if (pb) pb.style.width = pct + '%';
            if (pt) pt.textContent = pct + '%';
        }
        _wbSetStatus('工作台状态：执行步骤 ' + (i + 1) + '/' + _wbSteps.length + '...', 'info');
        _wbShowOutput('▶ [步骤 ' + (i + 1) + '/' + _wbSteps.length + '] fastboot ' + args.join(' '));

        try {
            var result = await _wbRunFastbootCommand(s);
            if (result.success) {
                if (result.output) _wbShowOutput(result.output);
            } else {
                _wbShowOutput('✗ 步骤 ' + (i + 1) + ' 失败: ' + result.output);
                _wbExecState = 'failed';
                if (btn) { btn.textContent = '全部执行'; btn.classList.add('warn'); btn.classList.remove('secondary'); }
                _wbSetStatus('工作台状态：步骤 ' + (i + 1) + ' 失败 - ' + result.output, 'err');
                return;
            }
        } catch(e) {
            _wbShowOutput('✗ 步骤 ' + (i + 1) + ' 异常: ' + e.message);
            _wbExecState = 'failed';
            if (btn) { btn.textContent = '全部执行'; btn.classList.add('warn'); btn.classList.remove('secondary'); }
            _wbSetStatus('工作台状态：步骤 ' + (i + 1) + ' 异常 - ' + e.message, 'err');
            return;
        }
    }

    // 全部完成
    _wbExecState = 'done';
    var doneBtn = document.getElementById('wbExecuteBtn');
    if (doneBtn) { doneBtn.textContent = '全部执行'; doneBtn.classList.add('warn'); doneBtn.classList.remove('secondary'); }
    if (progressEl) {
        var pb2 = progressEl.querySelector('.module-progress-bar');
        var pt2 = progressEl.querySelector('.module-progress-text');
        if (pb2) pb2.style.width = '100%';
        if (pt2) pt2.textContent = '100%';
    }
    _wbShowOutput('✓ 全部完成（共 ' + _wbSteps.length + ' 步）');
    _wbSetStatus('工作台状态：全部完成 ✓', 'ok');
}

// 模拟执行
async function _wbSimulate() {
    if (!_wbSteps.length) {
        _wbSetStatus('工作台状态：步骤列表为空', 'warn');
        return;
    }
    _wbClearOutput();
    _wbShowOutput('===== 模拟执行（不实际调用 fastboot）=====');
    _wbShowOutput('共 ' + _wbSteps.length + ' 步');
    _wbSetStatus('工作台状态：模拟执行中...', 'info');

    for (var i = 0; i < _wbSteps.length; i++) {
        var s = _wbSteps[i];
        var args = (s.raw || '').split(/\s+/).filter(Boolean);
        _wbShowOutput('▶ [步骤 ' + (i + 1) + '/' + _wbSteps.length + '] fastboot ' + args.join(' '));

        // 检查步骤是否有效
        var issues = [];
        if (s.type === 'flash' || s.type === 'flash-args-front' || s.type === 'flash-args-back' || s.type === 'flash-dir') {
            if (!s.partition) issues.push('分区名缺失');
            if (!s.image) issues.push('镜像路径缺失');
        }
        if (s.type === 'cow' && !s.partition) issues.push('分区名缺失');
        if (s.type === 'custom' && !s.raw) issues.push('命令为空');

        if (issues.length) {
            _wbShowOutput('  ⚠ 检查发现问题: ' + issues.join(', '));
        } else {
            _wbShowOutput('  ✓ 检查通过');
        }

        // 模拟延迟
        await new Promise(function(r) { setTimeout(r, 200); });
    }

    _wbShowOutput('===== 模拟执行完成 =====');
    _wbSetStatus('工作台状态：模拟执行完成（检查通过 ' + _wbSteps.length + ' 步）', 'ok');
}

// 清空步骤
function _wbClearSteps() {
    if (!_wbSteps.length) return;
    if (typeof showConfirm === 'function') {
        showConfirm('确认', '确认清空所有步骤？此操作不可撤销。', function() {
            _wbSteps = [];
            _wbRenderSteps();
            _wbAutoSave();
            _wbClearOutput();
            _wbSetStatus('工作台状态：步骤已清空', 'ok');
        }, true);
    } else {
        if (confirm('确认清空所有步骤？')) {
            _wbSteps = [];
            _wbRenderSteps();
            _wbAutoSave();
            _wbClearOutput();
            _wbSetStatus('工作台状态：步骤已清空', 'ok');
        }
    }
}

// ===== 事件处理 =====

function _wbHandleClick(e) {
    var btn = e.target.closest('[data-action]');
    if (!btn) return;
    var action = btn.dataset.action;
    switch(action) {
        case 'wb-toggle-edit':
            e.preventDefault();
            _wbToggleEdit();
            break;
        case 'wb-import-config':
            e.preventDefault();
            _wbImportConfig();
            break;
        case 'wb-export-config':
            e.preventDefault();
            _wbExportConfig();
            break;
        case 'wb-delete-config':
            e.preventDefault();
            if (!_wbCurrentConfig) {
                _wbSetStatus('工作台状态：请先选择要删除的配置', 'warn');
                return;
            }
            if (typeof showConfirm === 'function') {
                showConfirm('确认删除', '确认删除配置「' + _wbCurrentConfig + '」？此操作不可撤销。', function() {
                    _wbDeleteConfig(_wbCurrentConfig);
                }, true);
            } else if (confirm('确认删除配置「' + _wbCurrentConfig + '」？')) {
                _wbDeleteConfig(_wbCurrentConfig);
            }
            break;
        case 'wb-show-add-step-dialog':
            e.preventDefault();
            _wbShowAddStepDialog();
            break;
        case 'wb-close-add-step-dialog':
            e.preventDefault();
            _wbCloseAddStepDialog();
            break;
        case 'wb-back-to-cards':
            e.preventDefault();
            _wbBackToCards();
            break;
        case 'wb-add-step-confirm':
            e.preventDefault();
            _wbAddStepConfirm();
            break;
        case 'wb-pick-image':
            e.preventDefault();
            _wbPickImage();
            break;
        case 'wb-pick-dir':
            e.preventDefault();
            _wbPickDir();
            break;
        case 'wb-show-fastboot-dialog':
            e.preventDefault();
            _wbShowFastbootDialog();
            break;
        case 'wb-close-fastboot-dialog':
            e.preventDefault();
            _wbCloseFastbootDialog();
            break;
        case 'wb-add-quick-step':
            e.preventDefault();
            _wbAddQuickStep(btn.dataset.cmd, btn.dataset.label);
            break;
        case 'wb-execute-all':
            e.preventDefault();
            _wbExecuteAll();
            break;
        case 'wb-simulate':
            e.preventDefault();
            _wbSimulate();
            break;
        case 'wb-clear-steps':
            e.preventDefault();
            _wbClearSteps();
            break;
    }
}

// 处理步骤卡片点击
function _wbHandleStepCardClick(e) {
    var card = e.target.closest('.wb-step-card');
    if (!card) return;
    var type = card.dataset.stepType;
    if (type) _wbSelectStepType(type);
}

// 处理 AB 勾选提示
function _wbHandleABChange(e) {
    if (e.target.id === 'wbFormAB') {
        var hint = document.getElementById('wbABHint');
        if (hint) hint.style.display = e.target.checked ? 'block' : 'none';
    }
}

// ===== 模块初始化 =====
Modules.register('workbench', ['api','utils','file-api'], function initWorkbenchModule() {
    // 主事件委托（工作台视图内）
    var workbenchView = document.querySelector('.app-view[data-view="workbench"]');
    if (workbenchView) workbenchView.addEventListener('click', _wbHandleClick);

    // 添加步骤弹窗事件（弹窗在 view 外，需单独绑定 data-action 委托）
    var addStepDialog = document.getElementById('wbAddStepDialog');
    if (addStepDialog) {
        addStepDialog.addEventListener('click', function(e) {
            // 先处理 data-action 按钮（返回/确认/取消/关闭/选文件）
            var actionBtn = e.target.closest('[data-action]');
            if (actionBtn) {
                _wbHandleClick(e);
                return;
            }
            // 点击遮罩关闭
            if (e.target === addStepDialog) _wbCloseAddStepDialog();
            // 卡片选择
            var card = e.target.closest('.wb-step-card');
            if (card) _wbSelectStepType(card.dataset.stepType);
        });
        addStepDialog.addEventListener('change', _wbHandleABChange);
    }

    // Fastboot 弹窗事件（弹窗在 view 外，需单独绑定 data-action 委托）
    var fastbootDialog = document.getElementById('wbFastbootDialog');
    if (fastbootDialog) {
        fastbootDialog.addEventListener('click', function(e) {
            // 先处理 data-action 按钮（关闭/添加快捷命令）
            var actionBtn = e.target.closest('[data-action]');
            if (actionBtn) {
                _wbHandleClick(e);
                return;
            }
            // 点击遮罩关闭
            if (e.target === fastbootDialog) _wbCloseFastbootDialog();
        });
    }

    // 配置下拉框事件（非编辑模式下选择配置）
    var configSelect = document.getElementById('wbConfigSelect');
    if (configSelect) {
        configSelect.addEventListener('change', _wbOnSelectChange);
    }
    // 编辑模式下 input 的 Enter 键确认
    var configInput = document.getElementById('wbConfigInput');
    if (configInput) {
        configInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && _wbEditMode) {
                e.preventDefault();
                _wbToggleEdit(); // 触发确认保存
            }
        });
    }

    // 加载配置列表
    _wbLoadConfigs();

    console.log('[workbench] 工作台模块已初始化（v4.0.0 重构版）');
    return true;
});
