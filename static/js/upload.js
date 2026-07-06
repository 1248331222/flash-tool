// ============ 脚本上传功能（自包含重写版）============
// v2 - 脱离 _upload_records.json，直接用 WebDAV 文件名列表
var _selectedUploadFile = null;
// ---- 内部常量 ----
var UP = {};
// ---- 配置说明 ----
// wdUrl:   WebDAV 根路径。用于「上传脚本」和「PROPFIND 列表」。
//          AList 后台 → 存储驱动 → 挂载路径（一般就是 /dav）
// wdUser/pass: WebDAV 基础认证凭据。AList 后台 → 用户管理 → 用户名/密码。
//          base64 编码后通过 Authorization 头发送。
// shareBase: OpenList/AList 分享直链。用于「查看脚本内容」。
//          在 AList 后台 → 分享管理 → 创建分享 → 分享链接格式：
//          http://<IP>:<端口>/sd/<分享路径>/
//          需要在 AList 后台开启「分享直链」功能。
// 列表 API: 写死在 loadRecords 函数里，格式：
//          http://<IP>:<端口>/api/fs/list?path=<分享路径>
//          无认证，仅用于读列表，不用于上传。
UP.wdUrl = 'http://81.68.84.205:5244/dav';
UP.wdUser = '123456';
UP.wdPass = '123456';
UP.shareBase = 'http://81.68.84.205:5244/sd/BD/';
// ---- IndexedDB 缓存 ----
var DB_NAME = 'skyflash_script_cache';
var DB_VER = 1;
var DB_STORE = 'scripts';
function openDB() {
    return new Promise(function(resolve, reject) {
        var req = indexedDB.open(DB_NAME, DB_VER);
        req.onupgradeneeded = function(e) {
            var db = e.target.result;
            if (!db.objectStoreNames.contains(DB_STORE)) {
                db.createObjectStore(DB_STORE, { keyPath: 'file_id' });
            }
        };
        req.onsuccess = function(e) { resolve(e.target.result); };
        req.onerror = function(e) { reject(e.target.error); };
    });
}
function getCache(fileId) {
    return openDB().then(function(db) {
        return new Promise(function(resolve, reject) {
            var tx = db.transaction(DB_STORE, 'readonly');
            var req = tx.objectStore(DB_STORE).get(fileId);
            req.onsuccess = function() { resolve(req.result); };
            req.onerror = function() { resolve(null); };
        });
    });
}
function putCache(record) {
    return openDB().then(function(db) {
        record.cached_at = Date.now();
        return new Promise(function(resolve, reject) {
            var tx = db.transaction(DB_STORE, 'readwrite');
            var req = tx.objectStore(DB_STORE).put(record);
            req.onsuccess = function() { resolve(); };
            req.onerror = function() { resolve(); };
        });
    });
}
// ---- 基础 XHR 请求（自包含）----
function _send(method, relPath, body, onOk, onErr) {
    var xhr = new XMLHttpRequest();
    var encodedPath = '';
    for (var i = 0; i < relPath.length; i++) {
        if (relPath.charCodeAt(i) > 127) {
            encodedPath += encodeURIComponent(relPath.charAt(i));
        } else {
            encodedPath += relPath.charAt(i);
        }
    }
    var url = UP.wdUrl + '/' + encodedPath;
    xhr.open(method, url, true);
    xhr.setRequestHeader('Authorization', 'Basic ' + btoa(UP.wdUser + ':' + UP.wdPass));
    if (body != null) {
        xhr.setRequestHeader('Content-Type', 'application/octet-stream');
    }
    xhr.onload = function() {
        if (method === 'PUT') {
            if (xhr.status === 201 || xhr.status === 204) onOk(xhr);
            else onErr(xhr);
        } else {
            if (xhr.status === 200) onOk(xhr);
            else onErr(xhr);
        }
    };
    xhr.onerror = function() { onErr(xhr); };
    xhr.send(body || null);
}
// ---- 解析文件名状态 ----
function parseFileStatus(name) {
    // 去除 yes_ / no_ 前缀，返回 { rawName, displayName, status }
    // status: 'supported' | 'unsupported' | 'pending'
    var rawName = name;
    var displayName = name;
    var status = 'pending';
    if (name.indexOf('yes_') === 0) {
        status = 'supported';
        rawName = name.slice(4);
        displayName = rawName;
    } else if (name.indexOf('no_') === 0) {
        status = 'unsupported';
        rawName = name.slice(3);
        displayName = rawName;
    }
    // displayName 提取原始文件名（去掉时间戳前缀）
    var parts = rawName.split('_');
    // 格式: 时间戳_随机数_原始文件名
    if (parts.length >= 3 && /^\d{14}$/.test(parts[0])) {
        displayName = parts.slice(2).join('_');
    }
    return { rawName: rawName, displayName: displayName, status: status, originName: name };
}
// ---- 通过 OpenList API 获取文件列表（无 CORS 问题）----
function loadRecords(cb) {
    // 用 WebDAV PROPFIND 获取文件列表（与上传同一认证 123456/123456）
    var xhr = new XMLHttpRequest();
    xhr.open('PROPFIND', UP.wdUrl + '/', true);
    xhr.setRequestHeader('Authorization', 'Basic ' + btoa(UP.wdUser + ':' + UP.wdPass));
    xhr.setRequestHeader('Depth', '1');
    xhr.onload = function() {
        if (xhr.status !== 207) { cb([]); return; }
        try {
            var xml = xhr.responseXML;
            if (!xml) { cb([]); return; }
            var hrefs = xml.querySelectorAll('D\\:href, href');
            // 实际元素可能是 d:href 或 D:href 或直接 href，但部分浏览器解析不同
            // 改用字符串解析更可靠
            var text = xhr.responseText;
            var records = [];
            var regex = /<d:href>([^<]+)<\/d:href>|<D:href>([^<]+)<\/D:href>|<href>([^<]+)<\/href>/gi;
            var match;
            var names = [];
            while ((match = regex.exec(text)) !== null) {
                var href = match[1] || match[2] || match[3];
                // 保留原始编码 href，同时解码用于显示
                var rawEncodedName = href.split('/').filter(function(s){return s}).pop() || href;
                href = decodeURIComponent(href);
                // 只取文件名部分（解码后）
                var parts = href.split('/');
                var name = parts[parts.length - 1];
                if (name && name !== '' && name !== 'BD' && !name.endsWith('/')) {
                    names.push({ decoded: name, encoded: rawEncodedName });
                }
            }
            // 去重
            var unique = {};
            for (var i = 0; i < names.length; i++) {
                unique[names[i].decoded] = names[i];
            }
            for (var name in unique) {
                var entry = unique[name];
                var parsed = parseFileStatus(name);
                records.push({
                    file_id: parsed.rawName,
                    origin_name: parsed.originName,
                    original_name: parsed.displayName,
                    raw_href: entry.encoded,
                    status: parsed.status,
                    script_type: name.indexOf('.sh') > 0 ? 'sh' : 'bat',
                    upload_time: ''
                });
            }
            // 按 status 排序：未处理 > 已处理 > 不支持
            records.sort(function(a, b) {
                var order = { pending: 0, supported: 1, unsupported: 2 };
                var oa = order[a.status] || 0;
                var ob = order[b.status] || 0;
                return oa - ob;
            });
            cb(records);
        } catch(e) { cb([]); }
    };
    xhr.onerror = function() { cb([]); };
    xhr.send(null);
}
// ---- 语法高亮（暗色主题，带行号）----
function highlightCode(code, name) {
    var isSh = name && name.indexOf('.sh') > 0;
    var lines = code.split('\n');
    var r = [];
    for (var i = 0; i < lines.length; i++) {
        var line = lines[i], t = line.trimStart();
        r.push('<span style="display:inline-block;width:36px;text-align:right;color:#484f58;user-select:none;margin-right:10px;border-right:1px solid #21262d;padding-right:8px;font-size:11px">' + (i + 1) + '</span>');
        if ((isSh && (t.startsWith('#') || t.startsWith('//'))) || (!isSh && (t.startsWith('::') || t.startsWith('REM ') || t.startsWith('rem ')))) {
            r.push('<span style="color:#8b949e">' + escHtml(line) + '</span>\n');
            continue;
        }
        var p = escHtml(line);
        if (isSh) {
            p = p.replace(/(\$\{?\w+\}?)/g, '<span style="color:#79c0ff">$1</span>');
        } else {
            p = p.replace(/(%[^%]+?%)/g, '<span style="color:#79c0ff">$1</span>');
            p = p.replace(/(!\w+!)/g, '<span style="color:#ffa657">$1</span>');
        }
        p = p.replace(/("(?:[^"\\]|\\.)*")/g, '<span style="color:#a5d6ff">$1</span>');
        p = p.replace(/\b(fastboot|adb)\b/gi, '<span style="color:#3fb950;font-weight:bold">$1</span>');
        r.push(p);
        r.push('\n');
    }
    return r.join('');
}
// ---- 查看弹窗（暗色主题）----
function buildScriptViewer(name, content) {
    var overlay = document.createElement('div');
    overlay.className = 'dialog-overlay show';
    overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.6);z-index:2000;overflow-y:auto;display:flex;align-items:flex-start;justify-content:center;padding:20px 0;';
    var box = document.createElement('div');
    box.style.cssText = 'background:#0d1117;border:1px solid #30363d;border-radius:12px;width:92%;max-width:680px;box-shadow:0 8px 32px rgba(0,0,0,0.4);margin:0 auto;color:#c9d1d9;';
    var header = document.createElement('div');
    header.style.cssText = 'padding:12px 16px;border-bottom:1px solid #30363d;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;background:#161b22;border-radius:12px 12px 0 0;z-index:1;';
    header.innerHTML = '<strong style="font-size:14px;color:#c9d1d9;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:85%;">\uD83D\uDCC4 ' + escHtml(name) + '</strong>' +
        '<button onclick="this.closest(\'.dialog-overlay\').remove()" style="background:none;border:none;font-size:18px;cursor:pointer;color:#8b949e;padding:0 6px;flex-shrink:0;">\u2715</button>';
    var body = document.createElement('pre');
    body.style.cssText = 'margin:0;padding:12px 16px;font-family:\'Cascadia Code\',\'Fira Code\',\'Consolas\',monospace;font-size:12px;line-height:1.6;white-space:pre-wrap;word-break:break-all;color:#c9d1d9;background:#0d1117;max-height:65vh;overflow:auto;';
    body.innerHTML = highlightCode(content, name);
    box.appendChild(header);
    box.appendChild(body);
    overlay.appendChild(box);
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) overlay.remove();
    });
    document.body.appendChild(overlay);
}
// ---- 通过 WebDAV 直连下载（降级用，文件名与服务器一致）----
function fetchScriptViaDirect(fileId, rawHref) {
    rawHref = rawHref || fileId;
    return new Promise(function(resolve, reject) {
        // 纯前端多路径尝试，自动处理 URL 编码
        var auth = btoa(UP.wdUser + ':' + UP.wdPass);
        // rawHref 是 PROPFIND 返回的原始编码文件名，优先级最高
        // encoded 是前端 encodeURIComponent 编码
        // fileId 是解码后的原始中文名
        var encoded = encodeURIComponent(fileId);
        var paths = [
            { url: UP.wdUrl + '/' + rawHref, auth: auth },
            { url: UP.wdUrl + '/BD/' + rawHref, auth: auth },
            { url: 'http://81.68.84.205:5244/sd/flash_tool/' + rawHref, auth: null },
            { url: UP.wdUrl + '/' + encoded, auth: auth },
            { url: UP.wdUrl + '/' + fileId, auth: auth },
            { url: UP.wdUrl + '/BD/' + encoded, auth: auth },
            { url: UP.wdUrl + '/BD/' + fileId, auth: auth },
            { url: 'http://81.68.84.205:5244/sd/flash_tool/' + encoded, auth: null },
            { url: 'http://81.68.84.205:5244/sd/flash_tool/' + fileId, auth: null }
        ];
        function tryNext(idx) {
            if (idx >= paths.length) {
                reject(new Error('所有路径都失败'));
                return;
            }
            var p = paths[idx];
            var xhr = new XMLHttpRequest();
            xhr.open('GET', p.url, true);
            if (p.auth) xhr.setRequestHeader('Authorization', 'Basic ' + auth);
            xhr.onload = function() {
                if (xhr.status === 200 && xhr.responseText && xhr.responseText.trim().length > 0) {
                    resolve(xhr.responseText);
                } else {
                    tryNext(idx + 1);
                }
            };
            xhr.onerror = function() { tryNext(idx + 1); };
            xhr.send();
        }
        tryNext(0);
    });
}
// ---- 查看脚本（IndexedDB 缓存 → WebDAV 直连降级）----
function viewUploadedScript(fileId, rawHref) {
    rawHref = rawHref || fileId;
    // ① 先查 IndexedDB 缓存
    getCache(fileId).then(function(cached) {
        if (cached && cached.content) {
            buildScriptViewer(cached.name || fileId, cached.content);
            return;
        }
        // ② 缓存没有 → 纯前端多路径直连
        showToast('正在加载...');
        fetchScriptViaDirect(fileId, rawHref).then(function(content) {
            putCache({ file_id: fileId, name: fileId, content: content });
            // 显示时提取原始文件名
            var displayName = fileId;
            var parts = fileId.split('_');
            if (parts.length >= 3 && /^\d{14}$/.test(parts[0])) {
                displayName = parts.slice(2).join('_');
            }
            buildScriptViewer(displayName, content);
        }).catch(function() {
            showToast('无法加载脚本内容');
        });
    });
}
// ---- 上传后自动缓存到 IndexedDB ----
function cacheUploadedScript(fileId, name, content) {
    putCache({ file_id: fileId, name: name, content: content });
}
// ---- 刷新上传列表 ----
function refreshUploadList() {
    var listEl = document.getElementById('uploadHistoryList');
    if (!listEl) return;
    loadRecords(function(records) {
        if (!records.length) {
            listEl.innerHTML = '<div style="text-align:center;padding:24px 12px;color:var(--text-muted);font-size:12px">\u6682\u65e0\u4e0a\u4f20\u8bb0\u5f55</div>';
            return;
        }
        listEl.innerHTML = records.map(function(f) {
            var statusText, statusColor, statusLabel;
            if (f.status === 'supported') { statusText = '\u5df2\u5904\u7406'; statusColor = '#30d158'; statusLabel = '\u2705'; }
            else if (f.status === 'unsupported') { statusText = '\u4e0d\u652f\u6301'; statusColor = '#ff453a'; statusLabel = '\u274c'; }
            else { statusText = '\u672a\u5904\u7406'; statusColor = '#8e8e93'; statusLabel = '\u23f3'; }
            return '<div class="upload-history-item" onclick="viewUploadedScript(\'' + escHtml(f.file_id) + '\', \'' + escHtml(f.raw_href || '') + '\')">' +
                '<div class="upload-history-name" style="font-size:13px;font-weight:600;margin-bottom:4px;">' + escHtml(f.original_name) + '</div>' +
                '<div class="upload-history-meta">' +
                '<span style="color:' + statusColor + ';font-weight:600">' + statusLabel + ' ' + statusText + '</span>' +
                '<span class="upload-history-type">' + f.script_type + '</span>' +
                (f.upload_time ? '<span>' + f.upload_time + '</span>' : '') +
                '</div></div>';
        }).join('');
    });
}
// ---- 打开/关闭对话框 ----
function openUploadDialog() {
    var dialog = document.getElementById('uploadDialog');
    if (!dialog) return;
    dialog.classList.add('show');
    document.body.style.overflow = 'hidden';
    // 阻止对话框自身滚动传播
    if (!dialog._scrollLock) {
        dialog._scrollLock = function(e) {
            if (e.target.closest('#uploadHistoryList')) return;
            if (e.target.closest('#uploadPreviewContent')) return;
            e.preventDefault();
        };
        dialog.addEventListener('touchmove', dialog._scrollLock, { passive: false });
    }
    document.getElementById('uploadFileInput').value = '';
    document.getElementById('uploadPreview').style.display = 'none';
    document.getElementById('uploadPreviewContent').textContent = '';
    document.getElementById('uploadHydraResult').style.display = 'none';
    document.getElementById('uploadProgressWrap').style.display = 'none';
    document.getElementById('uploadResult').style.display = 'none';
    document.getElementById('uploadSubmitBtn').disabled = true;
    _selectedUploadFile = null;
    refreshUploadList();
}
function closeUploadDialog() {
    var dialog = document.getElementById('uploadDialog');
    if (dialog) {
        dialog.classList.remove('show');
        if (dialog._scrollLock) {
            dialog.removeEventListener('touchmove', dialog._scrollLock);
            dialog._scrollLock = null;
        }
    }
    document.body.style.overflow = '';
}
// ---- 选文件 ----
function onUploadFileSelect(event) {
    var file = event.target.files[0];
    if (!file) return;
    var ext = '.' + file.name.split('.').pop().toLowerCase();
    if (['.bat','.cmd','.sh','.txt'].indexOf(ext) === -1) {
        showToast('\u4ec5\u652f\u6301 .bat/.cmd/.sh/.txt \u683c\u5f0f');
        event.target.value = '';
        return;
    }
    if (file.size > 1024 * 1024) {
        showToast('\u6587\u4ef6\u8d85\u8fc7 1MB \u9650\u5236');
        event.target.value = '';
        return;
    }
    _selectedUploadFile = file;
    document.getElementById('uploadSubmitBtn').disabled = false;
    document.getElementById('uploadFileInfo').textContent = file.name + ' (' + (file.size / 1024).toFixed(1) + ' KB)';
    var reader = new FileReader();
    reader.onload = function(e) {
        var lines = e.target.result.split('\n');
        var previewEl = document.getElementById('uploadPreview');
        var contentEl = document.getElementById('uploadPreviewContent');
        previewEl.style.display = '';
        contentEl.textContent = lines.slice(0, 20).join('\n') + (lines.length > 20 ? '\n...' : '');
        document.getElementById('uploadTotalLines').textContent = '\u5171 ' + lines.length + ' \u884c';
    };
    reader.readAsText(file);
}
// ---- 上传脚本 ----
function submitUpload() {
    if (!_selectedUploadFile) return;
    var btn = document.getElementById('uploadSubmitBtn');
    var progressWrap = document.getElementById('uploadProgressWrap');
    var progressBar = document.getElementById('uploadProgressBar');
    var result = document.getElementById('uploadResult');
    btn.disabled = true;
    btn.textContent = '\u4e0a\u4f20\u4e2d...';
    progressWrap.style.display = '';
    progressBar.style.width = '10%';
    result.style.display = 'none';
    var file = _selectedUploadFile;
    var reader = new FileReader();
    reader.onload = function(e) {
        var content = e.target.result;
        var ts = new Date().toISOString().replace(/[T:.-]/g,'').slice(0,14);
        var rand = Math.random().toString(36).slice(2,8);
        var safeName = ts + '_' + rand + '_' + file.name;
        // 直接上传到 WebDAV，不写 records.json
        _send('PUT', safeName, content,
            function() {
                progressBar.style.width = '100%';
                // 上传成功后自动缓存到 IndexedDB
                cacheUploadedScript(safeName, file.name, content);
                result.style.display = '';
                result.className = 'upload-result success';
                result.textContent = '\u2705 \u4e0a\u4f20\u6210\u529f';
                btn.disabled = false;
                btn.textContent = '\u786e\u8ba4\u4e0a\u4f20';
                setTimeout(function() { progressWrap.style.display = 'none'; }, 2000);
                refreshUploadList();
            },
            function() {
                result.style.display = '';
                result.className = 'upload-result error';
                result.textContent = '\u274c \u4e0a\u4f20\u5931\u8d25';
                btn.disabled = false;
                btn.textContent = '\u786e\u8ba4\u4e0a\u4f20';
                setTimeout(function() { progressWrap.style.display = 'none'; }, 2000);
            }
        );
    };
    reader.readAsText(file);
}
// ---- HTML 转义 ----
function escHtml(s) {
    return String(s).replace(/[&<>"']/g, function(b) {
        return {'&':'&','<':'<','>':'>','"':'"',"'":'&#039;'}[b];
    });
}
// ---- Toast 提示 ----
function showToast(msg) {
    var el = document.getElementById('uploadToast');
    if (!el) {
        el = document.createElement('div');
        el.id = 'uploadToast';
        el.style.cssText = 'position:fixed;bottom:80px;left:50%;transform:translateX(-50%);background:#1c1c1e;color:#f5f5f7;padding:8px 16px;border-radius:8px;font-size:13px;z-index:9999;max-width:80%;text-align:center;pointer-events:none;opacity:0;transition:opacity 0.3s;';
        document.body.appendChild(el);
    }
    el.textContent = msg;
    el.style.opacity = '1';
    clearTimeout(el._t);
    el._t = setTimeout(function() { el.style.opacity = '0'; }, 2500);
}
// ---- 快速上传 ----
function quickUploadScript() {
    openUploadDialog();
}
// ---- 点击外部关闭 ----
document.addEventListener('click', function(e) {
    var dialog = document.getElementById('uploadDialog');
    if (dialog && dialog.classList.contains('show') && e.target === dialog) {
        closeUploadDialog();
    }
});
