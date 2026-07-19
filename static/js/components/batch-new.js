// static/js/components/batch-new.js
// 新线刷页面 — 脚本选择 → 分类 → 解析 → 步骤列表 → 分段执行（含等待重连/暂停继续）

(function() {
    'use strict';

    var _selectedFile = null;
    var _parsedSteps = [];
    var _hasParams = false;
    var _scriptContent = '';
    var _scriptPath = '';
    var _romDir = '';
    var _stepTemplates = [];     // 原始步骤模板（含 %* 占位符的 raw）
    var _hasParamSteps = false;  // 是否有步骤包含 %* / %1-%9 占位符

    // 执行状态机
    var _execState = 'idle';   // idle | running | paused | done | failed
    var _pauseIndex = 0;       // 暂停时的步骤索引
    var _currentTaskId = null; // 当前后端任务ID
    var _wsListeners = [];     // WebSocket监听器引用（用于清理）

    function init() {
        var selectBtn = document.getElementById('selectScriptBtn');
        var parseBtn = document.getElementById('parseScriptBtn');
        var executeBtn = document.getElementById('newExecuteBtn');
        var clearBtn = document.getElementById('newClearStepsBtn');
        if (!selectBtn) return;

        // === 订阅设备状态变化，动态更新状态栏 ===
        if (typeof App !== 'undefined' && App.subscribe) {
            App.subscribe('backendReady', function() { _updateStatusFromDevice(); });
            App.subscribe('deviceConnected', function() { _updateStatusFromDevice(); });
            App.subscribe('canFastboot', function() { _updateStatusFromDevice(); });
        }
        // 初始更新一次状态栏
        _updateStatusFromDevice();

        // === 选择脚本 ===
        selectBtn.addEventListener('click', async function() {
            try {
                var file = await FileApi.pickFile({ filter: '.bat,.cmd,.sh,.txt' });
                if (!file) return;
                _selectedFile = file;
                _scriptContent = file.content;
                _scriptPath = file.path || '';
                _romDir = _scriptPath ? _scriptPath.substring(0, _scriptPath.lastIndexOf('/')) : '';
                selectBtn.textContent = '📄 ' + file.name;
                parseBtn.disabled = false;
                var cls = ScriptClassifier.classify(_scriptContent, file.name);
                var paramsRow = document.getElementById('scriptParamsRow');
                if (cls.hasParams) { _hasParams = true; paramsRow.style.display = 'block'; }
                else { _hasParams = false; paramsRow.style.display = 'none'; }
            } catch (e) {
                if (e.message !== '用户取消选择' && typeof showToast === 'function') showToast('选择文件失败: ' + e.message);
            }
        });

        // === 解析 ===
        parseBtn.addEventListener('click', async function() {
            if (!_scriptContent) return;
            parseBtn.disabled = true;
            parseBtn.textContent = '解析中...';
            try {
                var cls = ScriptClassifier.classify(_scriptContent, _selectedFile ? _selectedFile.name : '');
                if (typeof writeLog === 'function') writeLog('脚本分类: ' + cls.key, 'info');
                var parserFile = await ParserRunner.findParser(cls.key);
                if (!parserFile) {
                    _showNeedParser(cls);
                    parseBtn.disabled = false;
                    parseBtn.textContent = '解析';
                    return;
                }
                if (typeof writeLog === 'function') writeLog('匹配到解析器: ' + parserFile, 'ok');
                var extraArgs = '';
                if (_hasParams) {
                    var paramsInput = document.getElementById('scriptParamsInput');
                    extraArgs = paramsInput ? paramsInput.value.trim() : '';
                }
                var result = await ParserRunner.run(parserFile, _scriptContent, {
                    fileApi: FileApi, extraArgs: extraArgs, romDir: _romDir, scriptPath: _scriptPath,
                    onStep: function() { renderStepList(); },
                    onChoice: function(choice) {
                        return _showChoiceDialog(choice);
                    },
                });
                _parsedSteps = result.steps || [];

                // 检测步骤中是否包含 %* / %1-%9 占位符，存储模板并首次同步
                _processParamSteps();

                // 检测reboot到bt/fa，插入等待重连步骤
                var hasRebootBtFa = _insertReconnectSteps();

                // 如果检测到reboot到bt/fa，弹窗提示
                if (hasRebootBtFa) _showRebootWarning();

                renderStepList();
                _updateStatusFromDevice();
                if (typeof writeLog === 'function') writeLog('解析完成，共 ' + _parsedSteps.length + ' 步', 'ok');
            } catch (e) {
                if (typeof writeLog === 'function') writeLog('解析失败: ' + e.message, 'err');
            } finally {
                parseBtn.disabled = false;
                parseBtn.textContent = '解析';
            }
        });

        // === 执行/暂停/继续 ===
        if (executeBtn) {
            executeBtn.addEventListener('click', function() {
                if (_execState === 'idle' || _execState === 'done' || _execState === 'failed') {
                    if (!_preCheck()) return;
                    _execState = 'running';
                    executeBtn.textContent = '暂停刷写';
                    clearBtn.textContent = '重置';
                    _executeFromIndex(0);
                } else if (_execState === 'running') {
                    _requestPause();
                } else if (_execState === 'paused') {
                    if (!_preCheck()) return;
                    _execState = 'running';
                    executeBtn.textContent = '暂停刷写';
                    _executeFromIndex(_pauseIndex);
                }
            });
        }

        // === 重置/清空 ===
        if (clearBtn) {
            clearBtn.addEventListener('click', function() {
                if (_execState === 'running') return; // 执行中不可重置
                if (_execState === 'idle') {
                    // idle时清空步骤列表
                    _parsedSteps = [];
                    _stepTemplates = [];
                    _hasParamSteps = false;
                    renderStepList();
                    document.getElementById('newBatchOutput').style.display = 'none';
                    document.getElementById('newBatchProgress').style.display = 'none';
                    _updateStatusFromDevice();
                } else {
                    // 重置执行状态
                    _execState = 'idle';
                    _pauseIndex = 0;
                    _currentTaskId = null;
                    _cleanupWsListeners();
                    executeBtn.textContent = '执行线刷';
                    clearBtn.textContent = '清空';
                    _updateStatusFromDevice();
                    document.getElementById('newBatchProgress').style.display = 'none';
                    var pb = document.querySelector('#newBatchProgress .module-progress-bar');
                    if (pb) pb.style.width = '0%';
                    document.getElementById('newBatchOutput').style.display = 'none';
                    if (typeof writeLog === 'function') writeLog('执行状态已重置', 'info');
                }
            });
        }

        // === 参数输入框实时同步 ===
        var paramsInput = document.getElementById('scriptParamsInput');
        if (paramsInput) {
            paramsInput.addEventListener('input', function() {
                if (_hasParamSteps && _execState === 'idle') _syncStepParams();
            });
        }
    }

    // ============ 重连步骤插入 ============
    function _insertReconnectSteps() {
        var hasRebootBtFa = false;
        var newSteps = [];
        for (var i = 0; i < _parsedSteps.length; i++) {
            newSteps.push(_parsedSteps[i]);
            if (_parsedSteps[i].type === 'reboot') {
                var target = (_parsedSteps[i].target || 'system').toLowerCase();
                if (target === 'bootloader' || target === 'fastboot') {
                    hasRebootBtFa = true;
                    // 检查下一步是否已经是 wait_reconnect（避免重复插入）
                    var nextStep = _parsedSteps[i + 1];
                    if (!nextStep || nextStep.type !== 'wait_reconnect') {
                        newSteps.push({
                            type: 'wait_reconnect',
                            target: target,
                            raw: '等待设备重连到 ' + (target === 'bootloader' ? 'Bootloader' : 'Fastboot') + ' 模式',
                            risk: 'LOW',
                        });
                    }
                }
            }
        }
        // 合并连续的 wait_reconnect 步骤（多个 reboot 连续时只需等待一次重连）
        var merged = [];
        for (var j = 0; j < newSteps.length; j++) {
            if (newSteps[j].type === 'wait_reconnect' && merged.length > 0 && merged[merged.length - 1].type === 'wait_reconnect') {
                // 跳过连续的 wait_reconnect，只保留第一个
                continue;
            }
            merged.push(newSteps[j]);
        }
        _parsedSteps = merged;
        return hasRebootBtFa;
    }

    function _showRebootWarning() {
        var modal = document.getElementById('rebootWarnModal');
        if (!modal) { alert('检测到脚本包含重启到 Bootloader/Fastboot 模式的操作。\n重启后需要重新给 Termux:API 授权 OTG 权限。\n系统已自动插入"等待重连"步骤。'); return; }
        modal.style.display = 'flex';
        var okBtn = document.getElementById('rebootWarnOkBtn');
        if (okBtn) okBtn.onclick = function() { modal.style.display = 'none'; };
        modal.onclick = function(e) { if (e.target === modal) modal.style.display = 'none'; };
    }

    function _showNeedParser(cls) {
        var parserName = cls.key + '.js';
        var modal = document.getElementById('needParserModal');
        var featureEl = document.getElementById('needParserFeature');
        var nameEl = document.getElementById('needParserName');
        if (modal && featureEl && nameEl) {
            var fl = ['当前脚本特征: <b style="color:var(--accent-blue);">' + cls.key + '</b>'];
            if (cls.features) {
                var fp = [];
                for (var cat in cls.features) { if (cls.features[cat] && cls.features[cat] !== 'none') fp.push(cat + '=' + cls.features[cat]); }
                if (fp.length) fl.push('<span style="color:var(--text-muted);font-size:12px;">' + fp.join(' · ') + '</span>');
            }
            featureEl.innerHTML = fl.join('<br>');
            nameEl.textContent = parserName;
            modal.style.display = 'flex';
            var copyBtn = document.getElementById('needParserCopyBtn');
            if (copyBtn) copyBtn.onclick = function() { navigator.clipboard.writeText(parserName).then(function(){copyBtn.textContent='已复制';setTimeout(function(){copyBtn.textContent='复制';},1500);}); };
            var closeH = function() { modal.style.display = 'none'; };
            var closeBtn = document.getElementById('needParserCloseBtn');
            var cancelBtn = document.getElementById('needParserCancelBtn');
            if (closeBtn) closeBtn.onclick = closeH;
            if (cancelBtn) cancelBtn.onclick = closeH;
            modal.onclick = function(e) { if (e.target === modal) modal.style.display = 'none'; };
            var installBtn = document.getElementById('needParserInstallBtn');
            if (installBtn) installBtn.onclick = function() { modal.style.display = 'none'; var m = document.getElementById('parserMgrBtn'); if (m) m.click(); };
        } else {
            alert('需要安装解析器: ' + parserName);
        }
    }

    // ============ 设备状态检查 + 状态栏更新 ============

    /**
     * 根据 App 全局状态更新线刷状态栏文字
     */
    function _updateStatusFromDevice() {
        if (_execState === 'running' || _execState === 'paused') return; // 执行中不覆盖
        var statusEl = document.getElementById('newBatchStatus');
        if (!statusEl) return;

        var brReady = (typeof backendReady !== 'undefined') ? backendReady : false;
        var devConn = (typeof deviceConnected !== 'undefined') ? deviceConnected : false;
        var fbReady = (typeof canFastboot !== 'undefined') ? canFastboot : false;

        if (!brReady) {
            statusEl.textContent = '线刷状态：后端未连接';
        } else if (!devConn) {
            statusEl.textContent = '线刷状态：未检测到设备';
        } else if (!fbReady) {
            statusEl.textContent = '线刷状态：设备不在 Fastboot 模式';
        } else if (_parsedSteps.length === 0) {
            statusEl.textContent = '线刷状态：设备就绪，请选择脚本解析';
        } else {
            statusEl.textContent = '线刷状态：就绪，共 ' + _parsedSteps.length + ' 步';
        }
    }

    /**
     * 设备检查，失败时更新状态栏并提示
     */
    function _preCheck() {
        var statusEl = document.getElementById('newBatchStatus');
        var brReady = (typeof backendReady !== 'undefined') ? backendReady : false;
        var devConn = (typeof deviceConnected !== 'undefined') ? deviceConnected : false;
        var fbReady = (typeof canFastboot !== 'undefined') ? canFastboot : false;

        if (!brReady) {
            var msg1 = '后端未连接，请先连接后端服务';
            if (statusEl) statusEl.textContent = '线刷状态：' + msg1;
            if (typeof showToast === 'function') showToast(msg1); else alert(msg1);
            return false;
        }
        if (!devConn) {
            var msg2 = '未检测到设备，请先在设备页检测并连接设备';
            if (statusEl) statusEl.textContent = '线刷状态：' + msg2;
            if (typeof showToast === 'function') showToast(msg2); else alert(msg2);
            return false;
        }
        if (!fbReady) {
            var msg3 = '设备不在 Fastboot 模式，无法线刷';
            if (statusEl) statusEl.textContent = '线刷状态：' + msg3;
            if (typeof showToast === 'function') showToast(msg3); else alert(msg3);
            return false;
        }
        if (!_parsedSteps.length) {
            var msg4 = '请先选择刷机脚本并解析';
            if (statusEl) statusEl.textContent = '线刷状态：' + msg4;
            if (typeof showToast === 'function') showToast(msg4); else alert(msg4);
            return false;
        }
        return true;
    }

    // ============ 分段执行引擎 ============
    async function _executeFromIndex(startIndex) {
        var executeBtn = document.getElementById('newExecuteBtn');
        var statusEl = document.getElementById('newBatchStatus');
        var progressEl = document.getElementById('newBatchProgress');
        var outputEl = document.getElementById('newBatchOutput');
        progressEl.style.display = 'flex';
        outputEl.style.display = 'block';
        outputEl.innerHTML = '';

        var i = startIndex;
        while (i < _parsedSteps.length) {
            if (_execState !== 'running') { _pauseIndex = i; return; }

            // 收集普通步骤段（非wait_reconnect）
            var segment = [];
            var segStart = i;
            while (i < _parsedSteps.length && _parsedSteps[i].type !== 'wait_reconnect') {
                segment.push(_parsedSteps[i]);
                i++;
            }

            // 提交普通步骤段到后端
            if (segment.length > 0) {
                statusEl.textContent = '线刷状态：执行步骤 ' + (segStart + 1) + '-' + (segStart + segment.length) + '/' + _parsedSteps.length;
                var segResult = await _submitSegment(segment, segStart);
                if (!segResult.success) {
                    _execState = 'failed';
                    executeBtn.textContent = '执行线刷';
                    _showError(segResult.error, segResult.category, segResult.diagnosis);
                    return;
                }
                if (_execState !== 'running') {
                    // 使用后端返回的next_index精确定位暂停位置
                    _pauseIndex = (segResult.nextIndex != null) ? segStart + segResult.nextIndex : i;
                    return;
                }
            }

            // 处理wait_reconnect步骤
            if (i < _parsedSteps.length && _parsedSteps[i].type === 'wait_reconnect') {
                var reconnectResult = await _handleReconnect(_parsedSteps[i]);
                if (_execState !== 'running') { _pauseIndex = i; return; }
                if (!reconnectResult.success) {
                    _execState = 'paused';
                    executeBtn.textContent = '继续刷写';
                    _pauseIndex = i;
                    return;
                }
                i++; // 重连成功，继续下一步
            }
        }

        // 全部完成
        _execState = 'done';
        executeBtn.textContent = '执行线刷';
        var clearBtn = document.getElementById('newClearStepsBtn');
        if (clearBtn) clearBtn.textContent = '清空';
        statusEl.textContent = '线刷状态：已完成 ✓';
        var pb = progressEl.querySelector('.module-progress-bar');
        if (pb) pb.style.width = '100%';
        var pt = progressEl.querySelector('.module-progress-text');
        if (pt) pt.textContent = '100%';
        if (typeof writeLog === 'function') writeLog('线刷全部完成', 'ok');
    }

    // ============ 提交步骤段 ============
    async function _submitSegment(segment, segStart) {
        var statusEl = document.getElementById('newBatchStatus');
        var progressEl = document.getElementById('newBatchProgress');
        var outputEl = document.getElementById('newBatchOutput');
        var executeBtn = document.getElementById('newExecuteBtn');

        var extraArgs = '';
        if (_hasParams) { var pi = document.getElementById('scriptParamsInput'); extraArgs = pi ? pi.value.trim() : ''; }

        _updateOverallProgress(segStart, _parsedSteps.length, 0);
        statusEl.textContent = '线刷状态：正在提交任务...';

        try {
            var resp = await fetch('/api/flash/execute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    steps: segment,
                    extra_args: extraArgs,
                    step_offset: segStart,           // 本段在全局步骤列表中的偏移
                    step_total: _parsedSteps.length, // 全局步骤总数
                }),
            });
            var data = await resp.json();
            if (!data.success) return { success: false, error: data.error || '提交失败' };

            _currentTaskId = data.task_id;
            if (typeof writeLog === 'function') writeLog('提交步骤段 ' + (segStart + 1) + '-' + (segStart + segment.length) + '，共 ' + segment.length + ' 步', 'info');

            // 等待段完成（WebSocket + 轮询降级）
            return await _waitSegmentComplete(data.task_id, segStart, segment.length);
        } catch (e) {
            return { success: false, error: e.message };
        }
    }

    // ============ 等待段完成 ============
    function _waitSegmentComplete(taskId, segStart, segLen) {
        return new Promise(function(resolve) {
            var resolved = false;
            var segTotalSteps = _parsedSteps.length;

            // WebSocket监听
            function onProgress(data) {
                if (data.task_id !== taskId || resolved) return;
                _updateOverallProgress(segStart, segTotalSteps, data.progress || 0);
                var pt = document.querySelector('#newBatchProgress .module-progress-text');
                if (pt) pt.textContent = (data.progress || 0) + '%';
                var statusEl = document.getElementById('newBatchStatus');
                if (statusEl && data.message) statusEl.textContent = '线刷状态：' + data.message;
                if (data.message) _appendOutput(data.message);
            }
            function onComplete(data) {
                if (data.task_id !== taskId || resolved) return;
                resolved = true;
                _cleanupWsListeners();
                clearInterval(poll);
                if (data.success) {
                    _updateOverallProgress(segStart + segLen, segTotalSteps, 100);
                    resolve({ success: true });
                } else {
                    resolve({ success: false, error: data.message || data.error || '执行失败', category: data.category || 'unknown', diagnosis: data.diagnosis || '' });
                }
            }

            if (typeof socket !== 'undefined' && socket) {
                socket.on('task_progress', onProgress);
                socket.on('task_complete', onComplete);
                _wsListeners.push(function() { socket.off('task_progress', onProgress); socket.off('task_complete', onComplete); });
            }

            // 轮询降级（3秒一次）
            var poll = setInterval(async function() {
                if (resolved) { clearInterval(poll); return; }
                try {
                    var resp = await fetch('/api/batch-task/status/' + taskId);
                    var data = await resp.json();
                    if (!data.success || !data.task) { clearInterval(poll); if (!resolved) { resolved = true; _cleanupWsListeners(); resolve({ success: false, error: '任务状态查询失败' }); } return; }
                    var task = data.task;
                    _updateOverallProgress(segStart, segTotalSteps, task.progress || 0);
                    var pt = document.querySelector('#newBatchProgress .module-progress-text');
                    if (pt) pt.textContent = (task.progress || 0) + '%';
                    var statusEl = document.getElementById('newBatchStatus');
                    if (statusEl) statusEl.textContent = '线刷状态：' + (task.phase || task.status || '');
                    var logs = task.logs || [];
                    var outputEl = document.getElementById('newBatchOutput');
                    outputEl.innerHTML = logs.map(function(l) { return '<div>' + escHtml(l) + '</div>'; }).join('');
                    outputEl.scrollTop = outputEl.scrollHeight;

                    // 检查暂停
                    if (task.status === 'paused') {
                        resolved = true; _cleanupWsListeners(); clearInterval(poll);
                        resolve({ success: true, paused: true, nextIndex: task.next_index != null ? task.next_index : 0 });
                        return;
                    }
                    if (task.status === 'completed' || task.status === 'success') {
                        resolved = true; _cleanupWsListeners(); clearInterval(poll);
                        _updateOverallProgress(segStart + segLen, segTotalSteps, 100);
                        resolve({ success: true });
                        return;
                    }
                    if (task.status === 'error' || task.status === 'failed') {
                        resolved = true; _cleanupWsListeners(); clearInterval(poll);
                        resolve({ success: false, error: task.error || '执行失败', category: task.category || 'unknown', diagnosis: task.diagnosis || '' });
                        return;
                    }
                    if (task.status === 'cancelled') {
                        resolved = true; _cleanupWsListeners(); clearInterval(poll);
                        resolve({ success: true }); // 取消（暂停）视为段完成
                        return;
                    }
                } catch (e) { /* 网络错误继续轮询 */ }
            }, 3000);
        });
    }

    function _updateOverallProgress(completedSteps, totalSteps, segmentProgress) {
        var basePct = totalSteps > 0 ? Math.round((completedSteps / totalSteps) * 100) : 0;
        var segSpan = totalSteps > 0 ? Math.round((1 / totalSteps) * 100) : 0;
        var pct = Math.min(99, basePct + Math.round(segSpan * (segmentProgress / 100)));
        var pb = document.querySelector('#newBatchProgress .module-progress-bar');
        if (pb) pb.style.width = pct + '%';
    }

    function _appendOutput(msg) {
        var outputEl = document.getElementById('newBatchOutput');
        if (!outputEl) return;
        var div = document.createElement('div');
        div.textContent = msg;
        outputEl.appendChild(div);
        outputEl.scrollTop = outputEl.scrollHeight;
    }

    function _cleanupWsListeners() {
        _wsListeners.forEach(function(fn) { try { fn(); } catch(e) {} });
        _wsListeners = [];
    }

    // ============ 等待重连处理 ============
    async function _handleReconnect(step) {
        var modal = document.getElementById('reconnectModal');
        var statusText = document.getElementById('reconnectStatus');
        var attemptText = document.getElementById('reconnectAttempt');
        var retryBtn = document.getElementById('reconnectRetryBtn');
        var skipBtn = document.getElementById('reconnectSkipBtn');
        var target = step.target || 'fastboot';
        var targetLabel = target === 'bootloader' ? 'Bootloader' : 'Fastboot';

        // 用户操作结果：'continue' | 'skip' | 'paused'
        var userAction = null;
        var manualRetryTrigger = null;

        if (modal) modal.style.display = 'flex';
        if (statusText) statusText.textContent = '正在等待设备重连到 ' + targetLabel + ' 模式...';
        if (typeof writeLog === 'function') writeLog('开始等待设备重连到 ' + targetLabel, 'info');

        // 绑定按钮事件
        if (retryBtn) {
            retryBtn.onclick = function() {
                if (manualRetryTrigger) manualRetryTrigger();
            };
        }
        if (skipBtn) {
            skipBtn.onclick = function() {
                userAction = 'skip';
                if (manualRetryTrigger) manualRetryTrigger();
            };
        }

        // 等待2秒让设备离线
        if (statusText) statusText.textContent = '等待设备离线（2秒）...';
        await _sleep(2000);

        // 检测设备是否已连接（最多 60 次，每次 2 秒 = 2 分钟）
        var maxAttempts = 60;
        for (var attempt = 0; attempt < maxAttempts; attempt++) {
            if (_execState !== 'running') {
                _cleanupReconnect(modal, retryBtn, skipBtn);
                return { success: false, reason: 'paused' };
            }
            if (userAction === 'skip') break;

            if (statusText) statusText.textContent = '正在检测设备是否已进入 ' + targetLabel + ' 模式...';
            if (attemptText) attemptText.textContent = '第 ' + (attempt + 1) + ' / ' + maxAttempts + ' 次检测';

            // 创建一个可被手动触发的 Promise
            var detectPromise = _detectReconnect(target);
            var manualPromise = new Promise(function(resolve) {
                manualRetryTrigger = function() { resolve(null); };
            });

            // 等待检测结果或手动触发
            var result = await Promise.race([detectPromise, manualPromise]);

            // 如果是手动触发（result === null），立即再检测一次
            if (result === null) {
                if (userAction === 'skip') break;
                result = await _detectReconnect(target);
            }

            if (result && result.connected) {
                if (statusText) statusText.textContent = '✅ 设备已连接到 ' + targetLabel + '，继续执行...';
                if (attemptText) attemptText.textContent = '';
                if (typeof writeLog === 'function') writeLog('设备已重连到 ' + targetLabel, 'ok');
                await _sleep(1000);
                _cleanupReconnect(modal, retryBtn, skipBtn);
                return { success: true };
            }

            // 非最后一次检测时等待 2 秒
            if (attempt < maxAttempts - 1) {
                await _sleep(2000);
            }
        }

        // 用户跳过
        if (userAction === 'skip') {
            if (statusText) statusText.textContent = '已跳过等待重连，继续执行...';
            if (typeof writeLog === 'function') writeLog('用户跳过等待重连', 'warn');
            _cleanupReconnect(modal, retryBtn, skipBtn);
            return { success: true, skipped: true };
        }

        // 超时
        if (statusText) statusText.textContent = '⚠️ 重连超时：' + maxAttempts + ' 次检测未发现设备';
        if (attemptText) attemptText.textContent = '可点击"立即检测"手动重试，或"跳过"继续';
        if (typeof writeLog === 'function') writeLog('设备重连超时，等待用户操作', 'err');
        // 不自动关闭弹窗，等待用户手动操作（检测或跳过）
        // 等待用户点击"立即检测"成功或"跳过"
        while (true) {
            var finalResult = await new Promise(function(resolve) {
                manualRetryTrigger = function() {
                    if (userAction === 'skip') { resolve('skip'); return; }
                    _detectReconnect(target).then(function(r) { resolve(r); });
                };
            });
            if (finalResult === 'skip') {
                _cleanupReconnect(modal, retryBtn, skipBtn);
                return { success: true, skipped: true };
            }
            if (finalResult && finalResult.connected) {
                if (statusText) statusText.textContent = '✅ 设备已连接到 ' + targetLabel + '，继续执行...';
                if (typeof writeLog === 'function') writeLog('设备已重连到 ' + targetLabel, 'ok');
                await _sleep(1000);
                _cleanupReconnect(modal, retryBtn, skipBtn);
                return { success: true };
            }
            if (statusText) statusText.textContent = '⚠️ 仍未检测到设备，请检查 OTG 授权';
            if (attemptText) attemptText.textContent = '可点击"立即检测"重试，或"跳过"继续';
        }
    }

    // 清理重连弹窗事件
    function _cleanupReconnect(modal, retryBtn, skipBtn) {
        if (modal) modal.style.display = 'none';
        if (retryBtn) retryBtn.onclick = null;
        if (skipBtn) skipBtn.onclick = null;
    }

    // 检测设备是否已重连
    async function _detectReconnect(target) {
        try {
            var resp = await fetch('/api/device/state');
            var data = await resp.json();
            // 后端返回 mode='fastboot'（bootloader 模式也归为 fastboot）
            // can_fastboot=true 表示 fastboot 设备已连接
            if (data.mode === 'fastboot' && data.can_fastboot) {
                return { connected: true, mode: 'fastboot' };
            }
            return { connected: false };
        } catch (e) {
            return { connected: false, error: e.message };
        }
    }

    // ============ 暂停 ============
    function _requestPause() {
        var modal = document.getElementById('pauseConfirmModal');
        if (!modal) { if (confirm('确认暂停刷写？')) _doPause(); return; }
        modal.style.display = 'flex';
        var confirmBtn = document.getElementById('pauseConfirmBtn');
        var cancelBtn = document.getElementById('pauseCancelBtn');
        var handler = function() {
            modal.style.display = 'none';
            confirmBtn.onclick = null;
            cancelBtn.onclick = null;
        };
        if (confirmBtn) confirmBtn.onclick = function() { handler(); _doPause(); };
        if (cancelBtn) cancelBtn.onclick = handler;
        modal.onclick = function(e) { if (e.target === modal) handler(); };
    }

    function _doPause() {
        _execState = 'paused';
        // 如果有后端任务在跑，发暂停请求
        if (_currentTaskId) {
            fetch('/api/batch-task/pause/' + _currentTaskId, { method: 'POST' }).catch(function() {});
        }
        var executeBtn = document.getElementById('newExecuteBtn');
        if (executeBtn) executeBtn.textContent = '继续刷写';
        var statusEl = document.getElementById('newBatchStatus');
        if (statusEl) statusEl.textContent = '线刷状态：已暂停';
        if (typeof writeLog === 'function') writeLog('线刷已暂停', 'info');
    }

    // ============ 错误显示 ============
    function _showError(error, category, diagnosis) {
        var statusEl = document.getElementById('newBatchStatus');
        var errorMap = {
            'device_not_found': '设备未连接或已断开，请重新检测设备',
            'fastboot_timeout': 'Fastboot 命令超时，设备可能未响应',
            'file_not_found': '镜像文件不存在：' + error,
            'permission_denied': '权限不足，请检查 USB 调试授权',
            'command_failed': '命令执行失败：' + error,
            'reboot_disconnect': '重启时设备断开（正常现象）',
            'unknown': '错误：' + error,
        };
        var msg = errorMap[category] || errorMap['unknown'];
        if (diagnosis) msg += '\n诊断建议：' + diagnosis;
        if (statusEl) statusEl.textContent = '线刷状态：失败 - ' + msg;
        if (typeof writeLog === 'function') writeLog('线刷失败：' + msg, 'err');
        if (typeof showToast === 'function') showToast(msg);
    }

    // ============ %* 参数占位符同步 ============

    /**
     * 检测步骤 raw 中是否包含 %* / %1-%9 占位符，存储原始模板。
     * 检测到时立即同步一次（空参数则移除占位符）。
     */
    function _processParamSteps() {
        _stepTemplates = _parsedSteps.map(function(s) { return s.raw || ''; });
        _hasParamSteps = _stepTemplates.some(function(raw) {
            return /%\*|%[1-9]/.test(raw);
        });
        if (_hasParamSteps) {
            var paramsRow = document.getElementById('scriptParamsRow');
            if (paramsRow) paramsRow.style.display = 'block';
            _hasParams = true;
            _syncStepParams();
        }
    }

    /**
     * 将参数输入框的值同步到所有包含占位符的步骤。
     * 空参数时移除 %* 和 %1-%9，非空时替换为对应值。
     */
    function _syncStepParams() {
        var paramsInput = document.getElementById('scriptParamsInput');
        var extraArgs = paramsInput ? paramsInput.value.trim() : '';
        var argParts = extraArgs ? extraArgs.split(/\s+/) : [];

        _parsedSteps.forEach(function(step, i) {
            var template = _stepTemplates[i] || step.raw || '';
            if (!/%\*|%[1-9]/.test(template)) return; // 无占位符跳过

            var raw = template;
            raw = raw.replace(/%\*/g, extraArgs);
            raw = raw.replace(/%([1-9])/g, function(m, n) {
                var idx = parseInt(n) - 1;
                return (argParts[idx] !== undefined) ? argParts[idx] : '';
            });
            raw = raw.replace(/\s+/g, ' ').trim();
            step.raw = raw;

            // 同步 prefixParams / params 字段
            if (step.prefixParams && /%\*|%[1-9]/.test(step.prefixParams)) {
                step.prefixParams = step.prefixParams
                    .replace(/%\*/g, extraArgs)
                    .replace(/%([1-9])/g, function(m, n) {
                        var idx = parseInt(n) - 1;
                        return (argParts[idx] !== undefined) ? argParts[idx] : '';
                    })
                    .replace(/\s+/g, ' ').trim() || undefined;
            }
            if (step.params && /%\*|%[1-9]/.test(step.params)) {
                step.params = step.params
                    .replace(/%\*/g, extraArgs)
                    .replace(/%([1-9])/g, function(m, n) {
                        var idx = parseInt(n) - 1;
                        return (argParts[idx] !== undefined) ? argParts[idx] : '';
                    })
                    .replace(/\s+/g, ' ').trim() || undefined;
            }
        });

        renderStepList();
    }

    // ============ 交互式选择对话框 ============

    /**
     * 弹出选择框，返回用户选择的索引（0-based）。
     * choice 对象格式：{ prompt: string, options: string[] }
     */
    function _showChoiceDialog(choice) {
        return new Promise(function(resolve) {
            var prompt = choice.prompt || '请选择';
            var options = choice.options || ['确定', '取消'];

            // 动态创建模态框
            var overlay = document.createElement('div');
            overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.6);z-index:9999;display:flex;align-items:center;justify-content:center;';

            var box = document.createElement('div');
            box.style.cssText = 'background:var(--bg-card,#1e1e2e);border:1px solid var(--rule,#333);border-radius:12px;padding:24px;max-width:400px;width:90%;box-shadow:0 8px 32px rgba(0,0,0,0.4);';

            var titleEl = document.createElement('div');
            titleEl.style.cssText = 'font-size:15px;font-weight:600;margin-bottom:16px;color:var(--text-primary,#e0e0e0);line-height:1.5;';
            titleEl.textContent = prompt;
            box.appendChild(titleEl);

            var btnRow = document.createElement('div');
            btnRow.style.cssText = 'display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap;';

            options.forEach(function(opt, idx) {
                var btn = document.createElement('button');
                btn.textContent = opt;
                btn.style.cssText = 'padding:8px 18px;border:1px solid var(--rule,#444);border-radius:8px;background:var(--bg-input,#2a2a3e);color:var(--text-primary,#e0e0e0);font-size:13px;cursor:pointer;transition:all 0.15s;' +
                    (idx === 0 ? ';border-color:var(--accent-blue,#4a9eff);color:var(--accent-blue,#4a9eff);' : '');
                btn.onmouseenter = function() { btn.style.opacity = '0.8'; };
                btn.onmouseleave = function() { btn.style.opacity = '1'; };
                btn.onclick = function() {
                    document.body.removeChild(overlay);
                    resolve(idx);
                };
                btnRow.appendChild(btn);
            });

            box.appendChild(btnRow);
            overlay.appendChild(box);
            document.body.appendChild(overlay);

            // 点击遮罩不关闭（强制选择）
        });
    }

    // ============ 步骤列表渲染 ============
    function _stepDescription(s) {
        var p = s.partition || s.target || '';
        switch (s.type) {
            case 'flash': return '刷写 <b>' + escHtml(p || '未知') + '</b> 分区';
            case 'erase': return '擦除 <b>' + escHtml(p || '未知') + '</b> 分区';
            case 'reboot':
                var target = p || '系统';
                var tm = { bootloader: 'Bootloader', recovery: 'Recovery', system: '系统', fastboot: 'Fastboot' };
                return '重启到 <b>' + escHtml(tm[target] || target) + '</b>';
            case 'set_active': return '切换到 <b>' + escHtml(p || 'A') + '</b> 槽位';
            case 'wait_reconnect': return '等待设备重连到 <b>' + escHtml(p === 'bootloader' ? 'Bootloader' : 'Fastboot') + '</b>';
            case 'oem':
                if (s.raw && /vbmeta|disable.*verity/i.test(s.raw)) return '去除 <b>VB 校验</b>';
                return '执行 OEM 命令 <b>' + escHtml(p || s.raw || '') + '</b>';
            case 'flashing':
                if (s.raw && /unlock/i.test(s.raw)) return '<b>解锁 Bootloader</b>';
                if (s.raw && /lock/i.test(s.raw)) return '<b>锁定 Bootloader</b>';
                return '执行 Flashing 命令';
            case 'getvar': return '查询设备信息 <b>' + escHtml(p || s.raw || '') + '</b>';
            case 'decompress':
                var fmtLabel = s.format === 'zstd' ? 'Zstandard' : (s.format || '压缩包');
                var inName = s.inputFile ? s.inputFile.split('/').pop() : '';
                var outName = s.outputFile ? s.outputFile.split('/').pop() : '';
                return '解压 <b>' + escHtml(inName) + '</b> → <b>' + escHtml(outName || '同目录') + '</b>';
            case 'shell': return '执行 Shell 命令';
            case 'raw':
            default: return '执行命令';
        }
    }

    function renderStepList() {
        var container = document.getElementById('newStepList');
        if (!container) return;
        if (!_parsedSteps.length) {
            container.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-muted)">选择刷机脚本 → 解析 → 确认步骤 → 执行线刷</div>';
            return;
        }
        var html = '';
        for (var i = 0; i < _parsedSteps.length; i++) {
            var s = _parsedSteps[i];
            var raw = s.raw || '';
            var isReconnect = s.type === 'wait_reconnect';
            var itemClass = isReconnect ? 'step-item step-item-reconnect' : 'step-item';

            html += '<div class="' + itemClass + '" data-step-idx="' + i + '">';
            html += '  <div class="step-item-header">';
            html += '    <div class="step-item-left">';
            html += '      <span class="step-num">' + (i + 1) + '</span>';
            if (isReconnect) html += '      <span class="step-reconnect-icon">🔄</span>';
            html += '      <span class="step-desc">' + _stepDescription(s) + '</span>';
            html += '    </div>';
            html += '    <div class="step-item-right">';
            html += '      <button class="step-del-btn" data-del-idx="' + i + '">删除</button>';
            html += '    </div>';
            html += '  </div>';
            if (raw) html += '  <div class="step-cmd">' + escHtml(raw) + '</div>';
            html += '</div>';
        }
        container.innerHTML = html;

        var delBtns = container.querySelectorAll('[data-del-idx]');
        for (var d = 0; d < delBtns.length; d++) {
            delBtns[d].onclick = function() {
                if (_execState === 'running') return;
                var idx = parseInt(this.getAttribute('data-del-idx'));
                _parsedSteps.splice(idx, 1);
                renderStepList();
            };
        }
    }

    // ============ 工具函数 ============
    function _sleep(ms) { return new Promise(function(r) { setTimeout(r, ms); }); }
    function escHtml(t) { var d = document.createElement('div'); d.textContent = t; return d.innerHTML; }

    if (typeof Modules !== 'undefined' && Modules.register) {
        Modules.register('batch-new', ['file-api', 'classifier', 'parser-runner'], init);
    }
})();
