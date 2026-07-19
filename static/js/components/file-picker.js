// static/js/components/file-picker.js
// 前端文件管理器 — 后端模式下浏览整个文件系统选择文件或目录

var FilePicker = (function() {
    'use strict';

    var _modal = null;
    var _listEl = null;
    var _pathEl = null;
    var _currentPath = '/';     // 当前绝对路径
    var _history = [];          // 路径历史栈，用于返回上级
    var _options = null;        // 当前选择的配置
    var _resolveFn = null;
    var _rejectFn = null;

    function _init() {
        _modal = document.getElementById('filePickerModal');
        _listEl = document.getElementById('fpFileList');
        _pathEl = document.getElementById('fpCurrentPath');
        if (!_modal || !_listEl || !_pathEl) return false;

        var backBtn = document.getElementById('fpBackBtn');
        if (backBtn) backBtn.onclick = _goUp;

        var refreshBtn = document.getElementById('fpRefreshBtn');
        if (refreshBtn) refreshBtn.onclick = function() { _loadDir(_currentPath); };

        var closeBtn = document.getElementById('fpCloseBtn');
        var cancelBtn = document.getElementById('fpCancelBtn');
        if (closeBtn) closeBtn.onclick = _close;
        if (cancelBtn) cancelBtn.onclick = _close;
        _modal.addEventListener('click', function(e) { if (e.target === _modal) _close(); });

        var selectDirBtn = document.getElementById('fpSelectDirBtn');
        if (selectDirBtn) selectDirBtn.onclick = _selectCurrentDir;

        return true;
    }

    function _close() {
        if (_modal) _modal.style.display = 'none';
        if (_rejectFn) { _rejectFn(new Error('用户取消选择')); _rejectFn = null; }
        _resolveFn = null;
    }

    function _goUp() {
        if (_currentPath === '/' || _currentPath === '') return;
        // 计算父目录
        var parent = _currentPath.replace(/\/+$/, '').replace(/\/[^/]+$/, '');
        if (!parent) parent = '/';
        _history.push(_currentPath);
        _loadDir(parent);
    }

    function _selectCurrentDir() {
        if (!_currentPath) return;
        if (_resolveFn) {
            _resolveFn({
                name: _currentPath.split('/').pop() || _currentPath,
                path: _currentPath,
                type: 'dir',
            });
            _resolveFn = null;
        }
        if (_modal) _modal.style.display = 'none';
    }

    /**
     * 检查文件名是否匹配过滤器
     * filter 格式: '.bat,.cmd,.sh,.txt' 或 '*.js' 或 '.img'
     */
    function _matchFilter(filename, filter) {
        if (!filter) return true;
        var name = filename.toLowerCase();
        // 解析出所有扩展名
        var exts = filter.split(',').map(function(e) {
            return e.trim().replace(/^\*\./, '').replace(/^\./, '').toLowerCase();
        }).filter(function(e) { return e; });
        // 无有效扩展名则不过滤
        if (exts.length === 0) return true;
        return exts.some(function(ext) {
            return name.endsWith('.' + ext);
        });
    }

    async function _loadDir(absPath, fallbackPaths) {
        if (!_listEl) return;
        _listEl.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-muted);font-size:13px;">加载中...</div>';

        try {
            var params = 'path=' + encodeURIComponent(absPath || '/');
            var resp = await fetch('/api/fs/browse?' + params);
            var data = await resp.json();

            if (!data.success) {
                // 如果有回退路径，尝试下一个
                if (fallbackPaths && fallbackPaths.length > 0) {
                    return _loadDir(fallbackPaths.shift(), fallbackPaths);
                }
                _listEl.innerHTML = '<div style="padding:20px;text-align:center;color:var(--accent-red);font-size:13px;">' + _escapeHtml(data.error || '加载失败') + '</div>';
                return;
            }

            _currentPath = data.abs_path || absPath;

            // 更新路径显示
            if (_pathEl) _pathEl.textContent = _currentPath;

            // 渲染文件列表
            var items = data.items || [];
            if (items.length === 0) {
                _listEl.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-muted);font-size:13px;">空目录</div>';
                return;
            }

            var html = '';
            for (var i = 0; i < items.length; i++) {
                var item = items[i];
                var icon = item.type === 'dir' ? '📁' : '📄';
                var sizeText = item.type === 'file' ? _formatSize(item.size) : '';
                var clickable = '';

                if (item.type === 'dir') {
                    clickable = ' data-fp-dir="' + i + '"';
                } else {
                    // 文件：根据 filter 判断是否可选
                    if (_matchFilter(item.name, _options ? _options.filter : '')) {
                        clickable = ' data-fp-file="' + i + '"';
                    }
                }

                html += '<div class="fp-item' + (clickable ? ' fp-clickable' : ' fp-disabled') + '"' + clickable + '>' +
                    '<span class="fp-icon">' + icon + '</span>' +
                    '<span class="fp-name">' + _escapeHtml(item.name) + '</span>' +
                    '<span class="fp-size">' + sizeText + '</span>' +
                    '</div>';
            }
            _listEl.innerHTML = html;

            // 缓存 items 供点击使用
            _listEl._fpItems = items;

            // 绑定点击事件
            var dirEls = _listEl.querySelectorAll('[data-fp-dir]');
            for (var d = 0; d < dirEls.length; d++) {
                dirEls[d].onclick = function() {
                    var idx = parseInt(this.getAttribute('data-fp-dir'));
                    var item = _listEl._fpItems[idx];
                    if (item) {
                        _history.push(_currentPath);
                        _loadDir(item.abs_path);
                    }
                };
            }

            var fileEls = _listEl.querySelectorAll('[data-fp-file]');
            for (var f = 0; f < fileEls.length; f++) {
                fileEls[f].onclick = function() {
                    var idx = parseInt(this.getAttribute('data-fp-file'));
                    var item = _listEl._fpItems[idx];
                    if (item && _resolveFn) {
                        _resolveFn({
                            name: item.name,
                            path: item.abs_path,
                            type: 'file',
                            size: item.size,
                        });
                        _resolveFn = null;
                        if (_modal) _modal.style.display = 'none';
                    }
                };
            }

        } catch(e) {
            _listEl.innerHTML = '<div style="padding:20px;text-align:center;color:var(--accent-red);font-size:13px;">加载失败: ' + _escapeHtml(e.message) + '</div>';
        }
    }

    function _formatSize(bytes) {
        if (!bytes) return '';
        if (bytes < 1024) return bytes + 'B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'K';
        return (bytes / (1024 * 1024)).toFixed(1) + 'M';
    }

    function _escapeHtml(text) {
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * 打开文件管理器弹窗
     * @param {object} opts - { mode: 'file'|'dir', filter: '.bat,.cmd,.sh,.txt' }
     * @returns {Promise<{name, path, type, size?}>}
     */
    function pick(opts) {
        opts = opts || {};
        _options = opts;

        if (!_modal && !_init()) {
            return Promise.reject(new Error('文件管理器未初始化'));
        }

        var selectDirBtn = document.getElementById('fpSelectDirBtn');
        if (selectDirBtn) {
            selectDirBtn.style.display = (opts.mode === 'dir') ? '' : 'none';
        }

        var titleEl = document.getElementById('fpTitle');
        if (titleEl) {
            titleEl.textContent = opts.mode === 'dir' ? '选择目录' : '选择文件';
        }

        _history = [];
        _modal.style.display = 'flex';

        return new Promise(function(resolve, reject) {
            _resolveFn = resolve;
            _rejectFn = reject;
            // 默认显示手机内部存储目录，不存在时依次回退
            var fallbacks = ['/sdcard', '/storage', '/'];
            _loadDir('/storage/emulated/0', fallbacks);
        });
    }

    return {
        pick: pick,
    };
})();
