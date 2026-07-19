// static/js/core/file-api.js
// 文件系统 API — 封装后端 /api/fs/* + 浏览器原生回退

var FileApi = (function() {
    'use strict';

    var _backendReady = false;

    function setBackendReady(ready) {
        _backendReady = !!ready;
    }

    // --- 后端 API 调用 ---

    async function _fetch(path, options) {
        var resp = await fetch(path, options);
        var data = await resp.json();
        if (!data.success && data.error !== 'overwrite_confirm') {
            throw new Error(data.error || '文件操作失败');
        }
        return data;
    }

    // --- 公共接口 ---

    async function list(dirPath, pattern) {
        if (!_backendReady) return _nativeList();
        var params = 'path=' + encodeURIComponent(dirPath || '/');
        if (pattern) params += '&pattern=' + encodeURIComponent(pattern);
        var data = await _fetch('/api/fs/list?' + params);
        return data.items || [];
    }

    async function exists(filePath) {
        if (!_backendReady) return false;
        var data = await _fetch('/api/fs/exists?path=' + encodeURIComponent(filePath));
        return data.exists;
    }

    async function glob(pattern, basePath) {
        if (!_backendReady) return [];
        var data = await _fetch('/api/fs/glob', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pattern: pattern, base_path: basePath || '/' }),
        });
        return data.files || [];
    }

    async function read(filePath, encoding) {
        if (!_backendReady) return '';
        var params = 'path=' + encodeURIComponent(filePath);
        if (encoding) params += '&encoding=' + encodeURIComponent(encoding);
        var data = await _fetch('/api/fs/read?' + params);
        return data.content;
    }

    async function readWithMeta(filePath, encoding) {
        if (!_backendReady) return { content: '', abs_path: '' };
        var params = 'path=' + encodeURIComponent(filePath);
        if (encoding) params += '&encoding=' + encodeURIComponent(encoding);
        var data = await _fetch('/api/fs/read?' + params);
        return { content: data.content, abs_path: data.abs_path || '' };
    }

    async function readBinary(filePath) {
        if (!_backendReady) return new Uint8Array(0);
        var data = await _fetch('/api/fs/read?path=' + encodeURIComponent(filePath) + '&encoding=base64');
        var bin = atob(data.content);
        var arr = new Uint8Array(bin.length);
        for (var i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
        return arr;
    }

    async function mkdir(dirPath) {
        if (!_backendReady) return;
        await _fetch('/api/fs/mkdir', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: dirPath }),
        });
    }

    async function remove(filePath) {
        if (!_backendReady) return;
        await _fetch('/api/fs/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: filePath }),
        });
    }

    async function copy(src, dst) {
        if (!_backendReady) return;
        await _fetch('/api/fs/copy', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ src: src, dst: dst }),
        });
    }

    async function move(src, dst) {
        if (!_backendReady) return;
        await _fetch('/api/fs/move', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ src: src, dst: dst }),
        });
    }

    // --- 浏览器原生回退（WebUSB 模式） ---

    function _nativeList() {
        return Promise.resolve([]);
    }

    // --- 统一文件选择入口 ---

    async function pickFile(opts) {
        opts = opts || {};
        // WebUSB 模式：强制使用浏览器原生文件选择器
        // 后端模式：使用内部文件管理器弹窗
        var useBackend = _backendReady && typeof FilePicker !== 'undefined' && FilePicker.pick;
        if (typeof appRunMode !== 'undefined' && appRunMode === 'webusb') {
            useBackend = false;
        }
        if (useBackend) {
            // 后端模式：使用文件管理器弹窗
            var result = await FilePicker.pick({
                mode: opts.mode || 'file',
                filter: opts.filter || '',
            });
            // 如果选择了文件，通过绝对路径读取内容
            if (result && result.type === 'file') {
                var readResp = await fetch('/api/fs/read-abs?path=' + encodeURIComponent(result.path));
                var readData = await readResp.json();
                if (!readData.success) throw new Error('读取文件失败: ' + (readData.error || ''));
                return {
                    name: result.name,
                    content: readData.content,
                    size: readData.size || result.size || 0,
                    path: readData.abs_path || result.path,
                };
            }
            // 选择了目录
            return result;
        }
        return _nativePickFile(opts);
    }

    function _nativePickFile(opts) {
        opts = opts || {};
        return new Promise(function(resolve, reject) {
            var input = document.createElement('input');
            input.type = 'file';
            if (opts.filter) input.accept = opts.filter;
            if (opts.multiple) input.multiple = true;
            // 目录选择模式：使用浏览器原生目录选择
            if (opts.mode === 'dir') {
                input.webkitdirectory = true;
                input.directory = true;
                input.onchange = function() {
                    if (!input.files.length) return reject(new Error('未选择目录'));
                    // 浏览器安全限制：无法获取目录绝对路径，使用 webkitRelativePath 的第一级目录名
                    var firstFile = input.files[0];
                    var relPath = firstFile.webkitRelativePath || firstFile.name;
                    var dirName = relPath.split('/')[0] || '';
                    // 收集目录内所有文件
                    var files = Array.from(input.files).map(function(f) {
                        return {
                            name: f.name,
                            size: f.size,
                            file: f,
                            path: '',  // 浏览器安全限制：无法获取绝对路径
                            relativePath: f.webkitRelativePath || f.name
                        };
                    });
                    resolve({
                        type: 'dir',
                        name: dirName,
                        path: '',  // 浏览器安全限制
                        files: files
                    });
                };
                input.click();
                return;
            }
            input.onchange = function() {
                if (!input.files.length) return reject(new Error('未选择文件'));
                var files = Array.from(input.files);
                if (files.length === 1) {
                    var reader = new FileReader();
                    reader.onload = function() {
                        resolve({
                            name: files[0].name,
                            content: reader.result,
                            size: files[0].size,
                            path: ''  // 浏览器安全限制：无法获取本地路径
                        });
                    };
                    reader.onerror = function() { reject(new Error('读取文件失败')); };
                    reader.readAsText(files[0]);
                } else {
                    resolve(files.map(function(f) {
                        return { name: f.name, size: f.size, file: f, path: '' };
                    }));
                }
            };
            input.click();
        });
    }

    /**
     * 通过后端路径读取文件（后端模式专用）
     * 返回 { name, content, size, path }
     */
    async function pickByPath(filePath) {
        if (!_backendReady) throw new Error('后端未连接');
        var params = 'path=' + encodeURIComponent(filePath);
        var data = await _fetch('/api/fs/read?' + params);
        var name = filePath.split('/').pop() || filePath;
        return {
            name: name,
            content: data.content,
            size: data.size || 0,
            path: data.abs_path || filePath
        };
    }

    return {
        setBackendReady: setBackendReady,
        list: list,
        exists: exists,
        glob: glob,
        read: read,
        readWithMeta: readWithMeta,
        readBinary: readBinary,
        mkdir: mkdir,
        remove: remove,
        copy: copy,
        move: move,
        pickFile: pickFile,
        pickByPath: pickByPath,
    };
})();

// 注册模块
if (typeof Modules !== 'undefined' && Modules.register) {
    Modules.register('file-api', [], function() {
        console.log('[file-api] 文件系统 API 已初始化');
        return true;
    });
}
