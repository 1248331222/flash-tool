// static/js/core/parser-runner.js
// 解析器加载器 + async generator 驱动

var ParserRunner = (function() {
    'use strict';

    var _parsersBaseUrl = '/api/parsers';
    var _parsersCache = {};  // filename -> module

    // ============ 解析器列表管理 ============

    async function listParsers() {
        var resp = await fetch(_parsersBaseUrl + '/list');
        var data = await resp.json();
        if (!data.success) throw new Error(data.error || '获取解析器列表失败');
        return data.parsers || [];
    }

    // ============ 动态加载解析器 ============

    async function loadParser(filename) {
        if (_parsersCache[filename]) return _parsersCache[filename];

        // 通过后端解析器专用 API 读取内容
        var readResp = await fetch(_parsersBaseUrl + '/read/' + encodeURIComponent(filename));
        var readData = await readResp.json();

        if (!readData.success) throw new Error('读取解析器失败: ' + (readData.error || ''));

        var code = readData.content;

        // CommonJS 兼容：检测 module.exports 或 exports.xxx 语法
        // 如果没有 export 关键字，包装为 ES module
        if (!/\bexport\s+(default|function|const|let|var|class)\b/.test(code)) {
            // 可能是 CommonJS，包装转换
            code = 'var module = { exports: {} }; var exports = module.exports;\n' +
                   code + '\n' +
                   'export default module.exports;\n' +
                   'export const __cjs = true;\n';
        }

        // 使用 Blob URL 动态加载为 ES module
        var blob = new Blob([code], { type: 'text/javascript' });
        var url = URL.createObjectURL(blob);
        try {
            var mod = await import(url);
            _parsersCache[filename] = mod;
            return mod;
        } finally {
            URL.revokeObjectURL(url);
        }
    }

    // ============ 根据分类结果匹配解析器 ============

    async function findParser(classifyKey) {
        var parsers = await listParsers();
        // 精确匹配：解析器文件名 == classifyKey + '.js'
        var exact = parsers.find(function(p) {
            return p.filename === classifyKey + '.js';
        });
        if (exact) return exact.filename;

        // 无精确匹配 → 返回 null（不做降级）
        return null;
    }

    // ============ 运行解析器（驱动 async generator） ============

    /**
     * 运行解析器
     * @param {string} parserFilename - 解析器文件名
     * @param {string} content - 脚本内容
     * @param {object} options - { fileApi, extraArgs, onStep, onChoice, romDir }
     * @returns {object} { steps, hasScriptParams, scriptParamHint }
     */
    async function run(parserFilename, content, options) {
        options = options || {};
        var mod = await loadParser(parserFilename);

        // 查找 parse 函数：支持多种导出方式
        var parseFn = mod.parse || (mod.default && typeof mod.default === 'function' ? mod.default : null);
        if (!parseFn && mod.default && typeof mod.default.parse === 'function') {
            parseFn = mod.default.parse;
        }

        if (typeof parseFn !== 'function') {
            throw new Error('解析器 ' + parserFilename + ' 没有导出 parse 函数。请使用 export function parse 或 module.exports = { parse: function... }');
        }

        var steps = [];
        var hasScriptParams = false;
        var scriptParamHint = '';

        // 注入 fileApi
        var fileApi = options.fileApi || FileApi;

        // 调用解析器
        var ctx = {
            fileApi: fileApi,
            extraArgs: options.extraArgs || '',
            romDir: options.romDir || '',
            scriptPath: options.scriptPath || '',
        };

        var result;
        try {
            result = parseFn(content, ctx);
        } catch (e) {
            throw new Error('解析器 ' + parserFilename + ' 内部错误: ' + e.message);
        }

        // 判断是否是 async generator
        if (result && typeof result[Symbol.asyncIterator] === 'function') {
            // async generator 模式：逐步产出步骤，支持交互
            var gen = result;
            while (true) {
                var next = await gen.next();
                if (next.done) break;
                var value = next.value;

                if (!value) continue;

                if (value.type === 'choice' || value.type === 'confirm') {
                    // 交互式：暂停解析，等待用户选择
                    if (typeof options.onChoice === 'function') {
                        var userChoice = await options.onChoice(value);
                        await gen.next(userChoice);
                    } else {
                        throw new Error('解析器需要用户选择，但未提供 onChoice 回调');
                    }
                } else if (value.type === 'step') {
                    var step = value.step || value;
                    steps.push(step);
                    if (typeof options.onStep === 'function') options.onStep(step, steps.length);
                }
            }
        } else if (result && typeof result.then === 'function') {
            // Promise 模式：等待完成
            var resolved = await result;
            if (Array.isArray(resolved)) {
                steps = resolved;
            } else if (resolved && resolved.steps) {
                steps = resolved.steps;
                hasScriptParams = !!resolved.hasScriptParams;
                scriptParamHint = resolved.scriptParamHint || '';
            }
        } else if (Array.isArray(result)) {
            steps = result;
        } else if (result && result.steps) {
            steps = result.steps;
            hasScriptParams = !!result.hasScriptParams;
            scriptParamHint = result.scriptParamHint || '';
        }

        return {
            steps: steps,
            hasScriptParams: hasScriptParams,
            scriptParamHint: scriptParamHint,
        };
    }

    // ============ 解析器安装 API 代理 ============

    async function installParser(formData) {
        var resp = await fetch(_parsersBaseUrl + '/install', { method: 'POST', body: formData });
        return await resp.json();
    }

    async function uninstallParser(filename) {
        var resp = await fetch(_parsersBaseUrl + '/uninstall/' + encodeURIComponent(filename), { method: 'DELETE' });
        return await resp.json();
    }

    async function installFromUrl(url, filename) {
        var resp = await fetch(_parsersBaseUrl + '/install-url', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: url, filename: filename }),
        });
        return await resp.json();
    }

    async function installFromWebdav(filename, webdavConfig) {
        var resp = await fetch(_parsersBaseUrl + '/install-webdav', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(Object.assign({ filename: filename }, webdavConfig || {})),
        });
        return await resp.json();
    }

    async function webdavListParsers(webdavConfig) {
        var resp = await fetch(_parsersBaseUrl + '/webdav-list', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(webdavConfig || {}),
        });
        return await resp.json();
    }

    // 强制刷新解析器缓存
    function clearCache(filename) {
        if (filename) {
            delete _parsersCache[filename];
        } else {
            _parsersCache = {};
        }
    }

    return {
        listParsers: listParsers,
        loadParser: loadParser,
        findParser: findParser,
        run: run,
        installParser: installParser,
        uninstallParser: uninstallParser,
        installFromUrl: installFromUrl,
        installFromWebdav: installFromWebdav,
        webdavListParsers: webdavListParsers,
        clearCache: clearCache,
    };
})();

if (typeof Modules !== 'undefined' && Modules.register) {
    Modules.register('parser-runner', ['file-api'], function() {
        console.log('[parser-runner] 解析器运行器已初始化');
        return true;
    });
}
