// 文件名：bat_if_goto_percent.js
export async function* parse(content, ctx) {
    var vars = {};
    var romDir = ctx.romDir || '';
    var fileApi = ctx.fileApi;

    // ========== 工具函数 ==========
    function resolveVars(text) {
        text = text.replace(/%~dp0/gi, romDir + '/');
        text = text.replace(/%(\w+)%/g, function(_, name) {
            if (name === '*' || /^[1-9]$/.test(name)) return _;
            return vars[name] !== undefined ? vars[name] : _;
        });
        return text;
    }

    function normalizePath(p) {
        p = p.replace(/\\/g, '/').replace(/^["']|["']$/g, '');
        if (p.indexOf('/') === 0) return p;
        return romDir ? romDir.replace(/\/+$/, '') + '/' + p : p;
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

        var skipped = [];
        while (rest.length && /^%[\*1-9]$/.test(rest[0])) skipped.push(rest.shift());
        if (rest.length === 0) return null;

        var action = rest[0].toLowerCase();
        var after = rest.slice(1);
        var allParts = skipped.concat(rest);
        var raw = 'fastboot' + (globalParams.length ? ' ' + globalParams.join(' ') : '') + ' ' + allParts.join(' ');

        if (action === 'getvar') return null;
        if (action === '-w') return { type: 'raw', raw: raw, risk: 'HIGH' };
        if (action === 'flash') {
            var part = after[0] || '', img = normalizePath(after[1] || ''), extra = after.slice(2).join(' ');
            return {
                type: 'flash', partition: part, imagePath: img,
                raw: raw, risk: getRisk(part),
                prefixParams: globalParams.join(' ') || undefined,
                params: extra || undefined
            };
        }
        if (action === 'erase') return { type: 'erase', partition: after[0] || '', raw: raw, risk: 'HIGH' };
        if (action === 'reboot') {
            var target = after.join(' ') || 'system';
            return { type: 'reboot', target: target, raw: raw, risk: 'LOW' };
        }
        if (action === 'set_active' || action === '--set-active')
            return { type: 'set_active', partition: after[0] || '', raw: raw, risk: 'MEDIUM' };
        if (action === 'delete-logical-partition')
            return { type: 'raw', raw: raw, risk: 'MEDIUM' };
        return { type: 'raw', raw: raw, risk: 'MEDIUM' };
    }

    function getRisk(p) {
        var map = { xbl:'CRITICAL',xbl_config:'CRITICAL',abl:'CRITICAL',bootloader:'CRITICAL',preloader_raw:'CRITICAL',modem:'HIGH',frp:'HIGH',metadata:'HIGH' };
        return map[(p || '').toLowerCase()] || 'MEDIUM';
    }

    function evalCondition(cond) {
        cond = cond.trim();
        var negated = false;
        if (/^not\s+/i.test(cond)) { negated = true; cond = cond.replace(/^not\s+/i, '').trim(); }
        var result = false;

        if (/^exist\s+/i.test(cond)) {
            result = true;
        } else if (/^\/i\s+/i.test(cond)) {
            var m = cond.match(/^\/i\s+"?([^"'\s]+)"?\s*==\s*"?(.+?)"?$/i);
            if (m) {
                var left = resolveVars(m[1]).toLowerCase();
                result = (left === m[2].toLowerCase());
            }
        } else {
            var m = cond.match(/^"?([^"'\s]+)"?\s*==\s*"?(.+?)"?$/i);
            if (m) {
                var left = resolveVars(m[1]).toLowerCase();
                result = (left === m[2].toLowerCase());
            }
        }
        return negated ? !result : result;
    }

    // ========== 第一阶段：收集普通 set 变量 ==========
    var lines = content.split(/\r?\n/);
    for (var i = 0; i < lines.length; i++) {
        var line = lines[i].trim();
        var setMatch = line.match(/^set\s+"?(\w+)=(.+?)"?\s*$/i);
        if (setMatch && !/^\/p$/i.test(setMatch[1])) {
            vars[setMatch[1]] = setMatch[2];
        }
    }
    for (var k in vars) vars[k] = resolveVars(vars[k]);

    // ========== 第二阶段：交互式收集用户选择 ==========
    for (var i = 0; i < lines.length; i++) {
        var line = lines[i].trim();
        var m = line.match(/^set\s+\/p\s+(\w+)\s*=\s*(.*)$/i);
        if (m) {
            var varName = m[1];
            var promptText = m[2].replace(/^["']|["']$/g, '');
            var userChoice = yield {
                type: 'choice',
                prompt: promptText,
                options: ['Y', 'N']
            };
            vars[varName] = (userChoice === 0 ? 'y' : 'n');
        }
    }

    // ========== 第三阶段：基于执行栈的步骤提取 ==========
    var i = 0;
    var execStack = [true];

    while (i < lines.length) {
        var rawLine = lines[i].trim();
        i++;

        if (!rawLine || /^(::|rem\b|@echo|title|color|cls|echo|pause|timeout|chcp|endlocal|goto|exit\b)/i.test(rawLine)) continue;
        if (rawLine.startsWith('@')) rawLine = rawLine.substring(1).trim();
        if (/^:\w+/.test(rawLine)) continue;
        if (/^set\s+\/p\s+/i.test(rawLine)) continue;
        if (/^set\s+/i.test(rawLine)) continue;

        var expanded = resolveVars(rawLine);

        // 处理 if 块开始
        var ifStart = expanded.match(/^if\s+(.+?)\s*\(\s*$/i);
        if (ifStart) {
            var cond = ifStart[1];
            if (/^errorlevel\s+\d+$/i.test(cond)) {
                var d = 1;
                while (i < lines.length && d > 0) {
                    var sl = lines[i].trim();
                    i++;
                    if (sl === ')') d--;
                    else if (/\(\s*$/.test(sl)) d++;
                }
                continue;
            }
            var condResult = evalCondition(cond);
            execStack.push(condResult);
            continue;
        }

        // 处理 else / else if
        if (/^\)?\s*else\b/i.test(expanded)) {
            if (execStack.length > 1) execStack.pop();
            var elseIfMatch = expanded.match(/^\)?\s*else\s+if\s+(.+?)\s*\(\s*$/i);
            if (elseIfMatch) {
                var cond2 = elseIfMatch[1];
                var condResult2 = evalCondition(cond2);
                execStack.push(condResult2);
            }
            continue;
        }

        // 闭合括号
        if (rawLine === ')') {
            if (execStack.length > 1) execStack.pop();
            continue;
        }

        // 判断当前是否应该执行
        var shouldExec = execStack.every(function(v) { return v; });
        if (!shouldExec) continue;

        // 清理命令并提取
        var cleanLine = expanded
            .replace(/\s*(\|\||&&).*$/i, '').trim();
        var pipeIdx = cleanLine.indexOf('|');
        if (pipeIdx >= 0) cleanLine = cleanLine.substring(0, pipeIdx).trim();
        cleanLine = cleanLine.replace(/\d*>&\d+/g, '').replace(/>[^ ]*/g, '').trim();
        if (!cleanLine) continue;

        var parts = splitCmd(cleanLine);
        if (parts.length === 0) continue;
        var step = makeStep(parts);
        if (step) yield { type: 'step', step: step };
    }
}