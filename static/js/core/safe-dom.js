// flash_tool/static/js/safe-dom.js
// ============ 安全 DOM 访问层 ============
// 目标：解决前端「稍微改动就崩溃」的核心问题。
// 1. 提供 $(id) 安全获取元素；元素不存在时返回空代理，避免 null 抛错。
// 2. 可选全局补丁 document.getElementById，使现有代码自动获得保护（过渡方案）。
// 3. 所有缺失元素都会在控制台输出警告，便于开发者定位。

(function(global) {
    'use strict';

    const noop = function(){};

    function createStyleProxy() {
        return new Proxy({}, {
            get(t, p) {
                if (p === 'cssText') return '';
                if (p === 'length') return 0;
                if (p === 'item') return function(){ return ''; };
                if (p === 'getPropertyValue') return function(){ return ''; };
                return '';
            },
            set(t, p, v) { return true; },
            deleteProperty(t, p) { return true; }
        });
    }

    function createClassList() {
        return {
            add: noop,
            remove: noop,
            toggle: function(){ return false; },
            contains: function(){ return false; },
            replace: noop,
            removeAll: noop,
            length: 0,
            item: function(){ return null; },
            value: ''
        };
    }

    /**
     * 为缺失的 DOM 元素创建安全空代理。
     * 读取任意属性时返回空字符串/空数组/noop 等安全默认值，写入操作静默成功，避免空引用抛错。
     * @param {string} id - 缺失的元素 id（仅用于调试，不实际查询 DOM）。
     * @returns {Proxy} 可安全用于链式 DOM 操作的空代理对象。
     */
    function createNullProxy(id) {
        const styleProxy = createStyleProxy();
        const classListObj = createClassList();
        return new Proxy({}, {
            get(t, p) {
                if (p === 'style') return styleProxy;
                if (p === 'classList') return classListObj;
                if (p === 'dataset') return {};
                if (p === 'children') return [];
                if (p === 'childNodes') return [];
                if (p === 'options') return [];
                if (p === 'selectedOptions') return [];
                if (['addEventListener','removeEventListener','setAttribute','removeAttribute','focus','blur','click','scrollIntoView','insertAdjacentHTML','insertAdjacentElement','insertAdjacentText','setSelectionRange','reset','submit','scrollTo','scrollBy'].indexOf(p) !== -1) return noop;
                if (['querySelector','closest','firstElementChild','lastElementChild','nextElementSibling','previousElementSibling'].indexOf(p) !== -1) return function(){ return null; };
                if (['querySelectorAll','getElementsByTagName','getElementsByClassName'].indexOf(p) !== -1) return function(){ return []; };
                if (['appendChild','insertBefore','removeChild','replaceChild','append','prepend','before','after','replaceWith'].indexOf(p) !== -1) return function(){ return null; };
                // 对 value / textContent / innerHTML / checked / disabled 等返回安全默认值
                return t[p] !== undefined ? t[p] : '';
            },
            set(t, p, v) { return true; },
            deleteProperty(t, p) { return true; }
        });
    }

    const originalGetElementById = document.getElementById.bind(document);

    /**
     * 安全 DOM 访问管理器。
     * 提供带缓存的元素查询，元素不存在时返回空代理；支持对 document.getElementById 打全局补丁。
     * @namespace SafeDOM
     */
    const SafeDOM = {
        _cache: new Map(),
        _patched: false,

        /**
         * 安全获取 DOM 元素（自动去掉 # 前缀）。
         * 元素存在时缓存并返回真实元素；不存在时输出警告并返回空代理，避免调用链抛错。
         * @param {string} id - 元素 id，可带或不带 # 前缀。
         * @returns {HTMLElement|Proxy} 真实元素或空代理对象。
         */
        get(id) {
            // 兼容调用者传入 #id 或 id
            const cleanId = String(id).replace(/^#/, '');
            if (this._cache.has(cleanId)) return this._cache.get(cleanId);
            const el = originalGetElementById(cleanId);
            if (!el) {
                console.warn('[SafeDOM] 元素 #' + cleanId + ' 不存在');
                return createNullProxy(cleanId);
            }
            this._cache.set(cleanId, el);
            return el;
        },

        /**
         * 直接获取原始 DOM 元素，不做安全代理和缓存。
         * 用于必须区分元素是否真实存在的场景。
         * @param {string} id - 元素 id。
         * @returns {HTMLElement|null} 真实元素或 null。
         */
        getRaw(id) {
            return originalGetElementById(id);
        },

        /**
         * 判断指定 id 的元素是否真实存在于 DOM 中。
         * @param {string} id - 元素 id，可带或不带 # 前缀。
         * @returns {boolean} 存在返回 true，否则返回 false。
         */
        exists(id) {
            return !!originalGetElementById(String(id).replace(/^#/, ''));
        },

        clearCache() {
            this._cache.clear();
        },

        /**
         * 安全执行：元素存在时才调用回调函数。
         * 常用于对可选 DOM 元素执行一次性初始化或副作用操作。
         * @param {string} id - 元素 id，可带或不带 # 前缀。
         * @param {function(HTMLElement): void} fn - 元素存在时执行的回调。
         * @returns {HTMLElement|null} 真实元素或 null。
         */
        ifExists(id, fn) {
            const el = originalGetElementById(String(id).replace(/^#/, ''));
            if (el && typeof fn === 'function') fn(el);
            return el;
        },

        /**
         * 全局补丁：重写 document.getElementById，使其在元素缺失时也返回空代理。
         * 幂等调用：已打补丁时直接返回，避免重复包装。
         */
        enableGlobalPatch() {
            if (this._patched) return;
            this._patched = true;
            const self = this;
            document.getElementById = function(id) {
                const cleanId = String(id).replace(/^#/, '');
                const el = originalGetElementById(cleanId);
                if (!el) {
                    console.warn('[SafeDOM] 元素 #' + cleanId + ' 不存在（全局补丁）');
                    return createNullProxy(cleanId);
                }
                return el;
            };
            console.log('[SafeDOM] document.getElementById 已启用安全补丁');
        },

        // 禁用全局补丁（调试用）
        disableGlobalPatch() {
            if (!this._patched) return;
            document.getElementById = originalGetElementById;
            this._patched = false;
        }
    };

    global.SafeDOM = SafeDOM;
    global.$ = SafeDOM.get.bind(SafeDOM);

    // 默认启用全局补丁，保护现有 355+ 处 document.getElementById 调用
    SafeDOM.enableGlobalPatch();
    console.log('[safe-dom.js] 加载完成，全局补丁已启用');

})(window);
