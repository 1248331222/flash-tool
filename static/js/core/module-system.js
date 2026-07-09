// flash_tool/static/js/module-system.js
// ============ 轻量级模块注册与初始化系统 ============
// 目标：替代按 script 标签顺序加载的脆弱方式，使各功能模块显式声明依赖，
// 并在 DOMReady 后统一、隔离地初始化。单个模块失败不会影响其他模块。

(function(global) {
    'use strict';

    const Modules = {
        _registry: [],
        _states: {},
        _initialized: false,

        /**
         * 注册一个初始化模块。
         * 支持两种重载：register(name, fn) 或 register(name, deps, fn)。
         * @param {string} name - 模块名，需全局唯一。
         * @param {string[]|function} deps - 依赖的模块名数组；若省略则第二参数视为初始化函数。
         * @param {function} fn - 初始化函数，参数为依赖模块的初始化返回值，可返回任意状态对象。
         */
        register(name, deps, fn) {
            if (typeof deps === 'function') {
                fn = deps;
                deps = [];
            }
            if (typeof fn !== 'function') {
                console.error('[Modules] 模块 ' + name + ' 必须提供初始化函数');
                return;
            }
            if (this._initialized) {
                console.warn('[Modules] 系统已初始化完成，模块 ' + name + ' 注册过晚');
            }
            this._registry.push({ name: name, deps: deps || [], fn: fn });
        },

        /**
         * 按拓扑顺序初始化所有已注册模块。
         * 会先对模块进行依赖排序，再逐个异步执行初始化函数；单个模块失败不影响其他模块。
         * 幂等调用：已初始化完成时直接返回状态对象。
         * @returns {Object} 所有模块初始化结果组成的状态对象 _states。
         */
        async init() {
            if (this._initialized) {
                console.warn('[Modules] 已经初始化过，忽略重复调用');
                return this._states;
            }
            this._initialized = true;

            // 拓扑排序：保证依赖先于被依赖模块执行
            const sorted = this._topoSort();
            if (!sorted) {
                console.error('[Modules] 模块依赖存在循环，无法初始化');
                return this._states;
            }

            for (const m of sorted) {
                try {
                    const depArgs = m.deps.map(d => this._states[d]);
                    const result = await m.fn.apply(null, depArgs);
                    this._states[m.name] = (result === undefined) ? true : result;
                    console.log('[Modules] ' + m.name + ' 初始化成功');
                } catch (e) {
                    this._states[m.name] = null;
                    console.error('[Modules] ' + m.name + ' 初始化失败:', e);
                }
            }
            return this._states;
        },

        /**
         * 获取指定模块的初始化结果。
         * @param {string} name - 模块名。
         * @returns {*} 该模块初始化时返回的状态值，未找到返回 undefined。
         */
        get(name) {
            return this._states[name];
        },

        /**
         * 重新初始化指定模块（用于热修复或动态重载）。
         * 依赖仍使用当前 _states 中已保存的状态值，不重新初始化依赖模块。
         * @param {string} name - 要重新初始化的模块名。
         */
        async reinit(name) {
            const m = this._registry.find(x => x.name === name);
            if (!m) {
                console.warn('[Modules] 未找到模块 ' + name);
                return;
            }
            try {
                const depArgs = m.deps.map(d => this._states[d]);
                const result = await m.fn.apply(null, depArgs);
                this._states[name] = (result === undefined) ? true : result;
                console.log('[Modules] ' + name + ' 重新初始化成功');
            } catch (e) {
                this._states[name] = null;
                console.error('[Modules] ' + name + ' 重新初始化失败:', e);
            }
        },

        /**
         * 对注册模块进行拓扑排序，检测循环依赖。
         * 采用 DFS 染色法：temp 集合中再次出现同一节点即判定存在环。
         * @private
         * @returns {Array|null} 排序后的模块数组；若存在循环依赖则返回 null。
         */
        _topoSort() {
            const visited = new Set();
            const temp = new Set();
            const result = [];
            const map = new Map(this._registry.map(m => [m.name, m]));

            function visit(m) {
                if (temp.has(m.name)) return false; // 存在环
                if (visited.has(m.name)) return true;
                temp.add(m.name);
                for (const d of m.deps) {
                    const dep = map.get(d);
                    if (!dep) {
                        console.error('[Modules] 模块 ' + m.name + ' 依赖未注册的 ' + d);
                        return false;
                    }
                    if (!visit(dep)) return false;
                }
                temp.delete(m.name);
                visited.add(m.name);
                result.push(m);
                return true;
            }

            for (const m of this._registry) {
                if (!visit(m)) return null;
            }
            return result;
        }
    };

    global.Modules = Modules;

})(window);
