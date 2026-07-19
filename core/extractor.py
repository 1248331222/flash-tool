// 文件名：按分类器特征键命名，如 bat_rule_based.js
module.exports = {
    parse: async function(content, ctx) {
        var steps = [];
        var vars = {};
        var romDir = ctx.romDir || '';
        var fileApi = ctx.fileApi;
        var delayedExpansion = false;

        // ========== 工具函数 ==========
        function resolveVars(text) {
            text = text.replace(/%~dp0/gi, romDir + '/');
            text = text.replace(/%(\w+)%/g, function(_, name) {
                if (name === '*' || /^[1-9]$/.test(name)) return _; // 保留命令行占位符
                return vars[name] !== undefined ? vars[name] : _;
            });
            if (delayedExpansion) {
                text = text.replace(/!(\w+)!/g, function(_, name) {
                    return vars[name] !== undefined ? vars[name] : _;
                });
            }
            return text;
        }

        function normalizePath(p) {
            p = p.replace(/\\/g, '/').replace(/^["']|["']$/g, '');
            if (p.indexOf('/') === 0) return p;
            return romDir ? romDir.replace(/\/+$/, '') + '/' + p : p;
        }

        // 展开 for 变量（预留，本脚本未使用）
        function expandAllForVars(str, forStack) {
            if (!forStack.length) return str;
            var varNames = forStack.map(function(ctx) { return ctx.var; });
            var pattern = '%%(~[a-zA-Z]*)?(' + varNames.join('|') + ')';
            var re = new RegExp(pattern, 'g');
            return str.replace(re, function(match, modifier, varName) {
                var ctx = null;
                for (var i = forStack.length - 1; i >= 0; i--) {
                    if (forStack[i].var === varName) { ctx = forStack[i]; break; }
                }
                if (!ctx) return match;
                var rawVal = ctx.value;
                var full = normalizePath(rawVal);
                if (!modifier) return rawVal;
                var mod = modifier.toLowerCase();
                if (mod === '~') return rawVal.replace(/^["']|["']$/g, '');
                if (mod.indexOf('f') >= 0) return full;
                if (mod.indexOf('n') >= 0) return full.split('/').pop().replace(/\.[^/.]+$/, '');
                if (mod.indexOf('x') >= 0) {
                    var fname = full.split('/').pop();
                    return (fname.match(/\.[^/.]+$/) || [''])[0];
                }
                if (mod.indexOf('p') >= 0) return full.substring(0, full.lastIndexOf('/') + 1);
                return rawVal;
            });
        }

        function splitCmd(line) {
            var parts = [], cur = '', inQ = false;
            for (var i = 0; i < line.length; i++) {
                var ch = line[i];
                if (ch === '"') { inQ = !inQ; continue; }
                if ((ch === ' ' || ch === '\t') && !inQ) {
                    if (cur) { parts.push(cur); cur = ''; }
                } else cur += ch;
            }
            if (cur) parts.push(cur);
            return parts;
        }

        function makeStep(parts) {
            if (!parts || parts.length === 0) return null;
            var bin = parts[0].replace(/\\/g, '/').split('/').pop().replace(/\.exe$/i, '').toLowerCase();
            if (bin !== 'fastboot' && bin !== 'adb') return null;
            var rest = parts.slice(1);
            var globalParams = [];
            while (rest.length && rest[0].startsWith('--')) globalParams.push(rest.shift());

            // 跳过占位符 %* 和 %1-%9
            var skippedPlaceholders = [];
            while (rest.length && /^%[\*1-9]$/.test(rest[0])) skippedPlaceholders.push(rest.shift());
            if (rest.length === 0) return null;

            var action = rest[0].toLowerCase();
            var afterAction = rest.slice(1);
            var allParts = skippedPlaceholders.concat(rest);
            var rawBase = 'fastboot' + (globalParams.length ? ' ' + globalParams.join(' ') : '') + ' ' + allParts.join(' ');

            // getvar 不生成步骤
            if (action === 'getvar') return null;

            if (action === '-w') return { type: 'raw', raw: rawBase, risk: 'HIGH' };
            if (action === 'flash') {
                var partition = afterAction[0] || '';
                var imagePath = normalizePath(afterAction[1] || '');
                var extraParams = afterAction.slice(2).join(' ');
                return {
                    type: 'flash', partition: partition, imagePath: imagePath,
                    raw: rawBase, risk: getRisk(partition),
                    prefixParams: globalParams.join(' ') || undefined,
                    params: extraParams || undefined
                };
            }
            if (action === 'erase') return { type: 'erase', partition: afterAction[0] || '', raw: rawBase, risk: 'HIGH' };
            if (action === 'reboot') {
                var target = afterAction.join(' ') || 'system';
                return { type: 'reboot', target: target, raw: rawBase, risk: 'LOW' };
            }
            if (action === 'set_active' || action === '--set-active')
                return { type: 'set_active', partition: afterAction[0] || '', raw: rawBase, risk: 'MEDIUM' };
            if (action === 'delete-logical-partition')
                return { type: 'raw', raw: rawBase, risk: 'MEDIUM' };
            if (action === 'devices') return { type: 'raw', raw: rawBase, risk: 'LOW' };
            return { type: 'raw', raw: rawBase, risk: 'MEDIUM' };
        }

        function getRisk(p) {
            var map = { xbl:'CRITICAL',xbl_config:'CRITICAL',abl:'CRITICAL',bootloader:'CRITICAL',preloader_raw:'CRITICAL',modem:'HIGH',frp:'HIGH',metadata:'HIGH' };
            return map[(p || '').toLowerCase()] || 'MEDIUM';
        }

        // 第一阶段：收集普通 set 变量
        var lines = content.split(/\r?\n/);
        for (var i = 0; i < lines.length; i++) {
            var line = lines[i].trim();
            if (/^setlocal\s+enabledelayedexpansion/i.test(line)) delayedExpansion = true;
            var setMatch = line.match(/^set\s+"?(\w+)=(.+?)"?\s*$/i);
            if (setMatch) vars[setMatch[1]] = setMatch[2];
        }
        for (var k in vars) vars[k] = resolveVars(vars[k]);

        // 第二阶段：全量提取（无条件评估）
        var i = 0;
        // 括号深度计数器（用于跳过条件块的开头，但不影响内部命令提取）
        var ifDepth = 0;       // 当前 if 块深度（仅用于跟踪，不用于跳过）
        var skipMode = false;  // 是否处于被跳过的块中（始终 false，因为我们不跳过）

        while (i < lines.length) {
            var rawLine = lines[i].trim();
            i++;

            // 跳过无关行
            if (!rawLine || /^(::|rem\b|@echo|title|color|cls|echo|pause|timeout|chcp|endlocal|goto|exit\b)/i.test(rawLine)) continue;
            if (rawLine.startsWith('@')) rawLine = rawLine.substring(1).trim();
            if (/^:\w+/.test(rawLine)) continue;
            if (/^set\s+\/p\s+/i.test(rawLine)) continue;
            if (/^set\s+/i.test(rawLine)) continue; // 普通 set 已收集

            var expanded = resolveVars(rawLine);

            // 处理 if 块开始（不评估条件，直接进入块，提取内部命令）
            var ifStart = expanded.match(/^if\s+(.+?)\s*\(\s*$/i);
            if (ifStart) {
                ifDepth++;      // 进入一层 if
                continue;       // 跳过 if 行本身
            }

            // 处理 else / else if
            if (/^\)?\s*else\b/i.test(expanded)) {
                // 只是块结构的一部分，继续处理（不增加步骤）
                var elseIfMatch = expanded.match(/^\)?\s*else\s+if\s+(.+?)\s*\(\s*$/i);
                if (elseIfMatch) {
                    ifDepth++;  // 进入嵌套 if
                }
                continue;
            }

            // 闭合括号
            if (rawLine === ')') {
                if (ifDepth > 0) ifDepth--;
                continue;
            }

            // 清理管道、重定向和错误处理（||、&&）
            var cleanLine = expanded
                .replace(/\s*(\|\||&&).*$/i, '').trim();
            var pipeIdx = cleanLine.indexOf('|');
            if (pipeIdx >= 0) cleanLine = cleanLine.substring(0, pipeIdx).trim();
            cleanLine = cleanLine.replace(/\d*>&\d+/g, '').replace(/>[^ ]*/g, '').trim();
            if (!cleanLine) continue;

            // 分割命令并生成步骤
            var parts = splitCmd(cleanLine);
            if (parts.length === 0) continue;
            var step = makeStep(parts);
            if (step) steps.push(step);
        }

        // 检查是否有 %* 占位符，设置参数提示
        var hasParams = /%\*|%[1-9]/.test(content);

        return {
            steps: steps,
            hasScriptParams: hasParams,
            scriptParamHint: hasParams ? '如需要，请在参数框输入额外 fastboot 参数' : ''
        };
    }
};