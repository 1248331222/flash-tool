// 文件名：按分类器特征键命名，如 bat_rule_based.js
module.exports = {
    parse: async function(content, ctx) {
        var steps = [];
        var vars = {};
        var romDir = ctx.romDir || '';
        var fileApi = ctx.fileApi;
        var delayedExpansion = false;

        function resolveVars(text) {
            text = text.replace(/%~dp0/gi, romDir + '/');
            text = text.replace(/%(\w+)%/g, function(_, name) {
                if (name === '*' || /^[1-9]$/.test(name)) return _;
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

        function makeStep(parts, prefixParams) {
            if (!parts || parts.length === 0) return null;
            var bin = parts[0].replace(/\\/g, '/').split('/').pop().replace(/\.exe$/i, '').toLowerCase();
            if (bin !== 'fastboot' && bin !== 'adb') return null;
            var rest = parts.slice(1);
            var globalParams = [];
            while (rest.length && rest[0].startsWith('--')) globalParams.push(rest.shift());
            if (prefixParams) globalParams = prefixParams.split(/\s+/).concat(globalParams);

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

            if (action === '-w') {
                return { type: 'raw', raw: rawBase, risk: 'HIGH' };
            }
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
            if (action === 'erase') {
                return { type: 'erase', partition: afterAction[0] || '', raw: rawBase, risk: 'HIGH' };
            }
            if (action === 'reboot') {
                var target = afterAction.join(' ') || 'system';
                return { type: 'reboot', target: target, raw: rawBase, risk: 'LOW' };
            }
            if (action === 'set_active' || action === '--set-active') {
                return { type: 'set_active', partition: afterAction[0] || '', raw: rawBase, risk: 'MEDIUM' };
            }
            if (action === 'delete-logical-partition') {
                return { type: 'raw', raw: rawBase, risk: 'MEDIUM' };
            }
            if (action === 'devices') {
                return { type: 'raw', raw: rawBase, risk: 'LOW' };
            }
            return { type: 'raw', raw: rawBase, risk: 'MEDIUM' };
        }

        function getRisk(part) {
            var map = { xbl:'CRITICAL',xbl_config:'CRITICAL',abl:'CRITICAL',bootloader:'CRITICAL',preloader_raw:'CRITICAL',modem:'HIGH',frp:'HIGH',metadata:'HIGH' };
            return map[(part || '').toLowerCase()] || 'MEDIUM';
        }

        // 收集 set
        var lines = content.split(/\r?\n/);
        for (var i = 0; i < lines.length; i++) {
            var line = lines[i].trim();
            if (/^setlocal\s+enabledelayedexpansion/i.test(line)) delayedExpansion = true;
            var setMatch = line.match(/^set\s+"?(\w+)=(.+?)"?\s*$/i);
            if (setMatch) vars[setMatch[1]] = setMatch[2];
        }
        for (var k in vars) vars[k] = resolveVars(vars[k]);

        async function processLines(linesArray, localVars, forStack) {
            var savedVars = Object.assign({}, vars);
            if (localVars) Object.assign(vars, localVars);
            var stack = forStack || [];
            var idx = 0;
            var pendingFor = null, pendingIf = null;

            async function executeLine(line) {
                line = expandAllForVars(line, stack);
                line = resolveVars(line);
                // 1. 移除错误处理
                line = line.replace(/\s*(\|\||&&).*$/i, '').trim();
                // 2. 提取管道前有效命令
                var pipeIdx = line.indexOf('|');
                if (pipeIdx >= 0) line = line.substring(0, pipeIdx).trim();
                // 3. 移除重定向
                line = line.replace(/\d*>&\d+/g, '').replace(/>[^ ]*/g, '').trim();
                if (!line) return;
                var setMatch = line.match(/^\s*set\s+"?(\w+)=(.+?)"?\s*$/i);
                if (setMatch) { vars[setMatch[1]] = resolveVars(setMatch[2]); return; }
                var parts = splitCmd(line);
                if (parts.length === 0) return;
                parts = parts.map(function(p) { return expandAllForVars(p, stack); });
                var step = makeStep(parts);
                if (step) steps.push(step);
            }

            async function executeForBlock(block) {
                var items = await expandCollection(block.collection);
                for (var j = 0; j < items.length; j++) {
                    vars[block.varName] = items[j];
                    stack.push({ var: block.varName, value: items[j] });
                    await processLines(block.body, null, stack);
                    stack.pop();
                }
            }

            async function executeIfBlock(block) {
                var expandedCond = expandAllForVars(block.condition, stack);
                expandedCond = resolveVars(expandedCond);
                if (evalCondition(expandedCond)) {
                    await processLines(block.body, null, stack);
                }
            }

            function evalCondition(cond) {
                cond = cond.trim();
                var negated = false;
                if (/^not\s+/i.test(cond)) { negated = true; cond = cond.replace(/^not\s+/i, '').trim(); }
                var result;
                if (/^exist\s+/i.test(cond)) {
                    result = true;
                } else if (/^\/i\s+/i.test(cond)) {
                    var ciMatch = cond.match(/^\/i\s+"?([^"'\s]+)"?\s*==\s*"?(.+?)"?$/i);
                    if (ciMatch) result = ciMatch[1].toLowerCase() === ciMatch[2].toLowerCase();
                    else result = false;
                } else {
                    var strMatch = cond.match(/^"?([^"'\s]+)"?\s*==\s*"?(.+?)"?$/i);
                    if (strMatch) result = strMatch[1] === strMatch[2];
                    else {
                        var numMatch = cond.match(/^(\S+)\s+(equ|neq|gtr|geq|lss|leq)\s+(\S+)$/i);
                        if (numMatch) {
                            var l = parseInt(numMatch[1]), r = parseInt(numMatch[3]);
                            if (isNaN(l) || isNaN(r)) result = numMatch[2].toLowerCase() === 'equ' ? numMatch[1] === numMatch[3] : numMatch[1] !== numMatch[3];
                            else {
                                switch (numMatch[2].toLowerCase()) {
                                    case 'equ': result = l === r; break;
                                    case 'neq': result = l !== r; break;
                                    default: result = false;
                                }
                            }
                        } else if (/^errorlevel\s+\d+$/i.test(cond)) result = false;
                        else result = true;
                    }
                }
                return negated ? !result : result;
            }

            async function expandCollection(collection) {
                collection = collection.replace(/^["']|["']$/g, '');
                collection = resolveVars(collection);
                if (/\*|\?/.test(collection)) {
                    if (fileApi && fileApi.glob) {
                        var lastSlash = collection.replace(/\\/g, '/').lastIndexOf('/');
                        var dir = lastSlash >= 0 ? collection.substring(0, lastSlash) : '';
                        var pattern = lastSlash >= 0 ? collection.substring(lastSlash + 1) : collection;
                        try {
                            var files = await fileApi.glob(pattern, dir || romDir);
                            if (files && files.length) return files.map(f => f.replace(/\\/g, '/'));
                        } catch(e) {}
                    }
                    return [];
                }
                return collection.split(/[\s,]+/).filter(Boolean);
            }

            while (idx < linesArray.length) {
                var rawLine = linesArray[idx].trim();
                idx++;
                if (!rawLine || /^(::|rem\b|@echo|title|color|cls|echo|pause|timeout|chcp|endlocal|goto|exit\b)/i.test(rawLine)) continue;
                if (rawLine.startsWith('@')) rawLine = rawLine.substring(1).trim();

                if (pendingFor) {
                    if (rawLine === ')') {
                        if (pendingFor.depth > 0) { pendingFor.body.push(rawLine); pendingFor.depth--; }
                        else { await executeForBlock(pendingFor); pendingFor = null; }
                    } else {
                        pendingFor.body.push(rawLine);
                        if (/\(\s*$/.test(rawLine)) pendingFor.depth++;
                    }
                    continue;
                }
                if (pendingIf) {
                    if (rawLine === ')') {
                        if (pendingIf.depth > 0) { pendingIf.body.push(rawLine); pendingIf.depth--; }
                        else { await executeIfBlock(pendingIf); pendingIf = null; }
                    } else {
                        pendingIf.body.push(rawLine);
                        if (/\(\s*$/.test(rawLine)) pendingIf.depth++;
                    }
                    continue;
                }

                var expanded = expandAllForVars(rawLine, stack);
                expanded = resolveVars(expanded);

                var forStart = expanded.match(/^for\s+%%(\w)\s+in\s+\((.+?)\)\s+do\s*\(\s*$/i);
                if (forStart) {
                    pendingFor = { varName: forStart[1], collection: forStart[2], body: [], depth: 0 };
                    continue;
                }

                var ifStart = expanded.match(/^if\s+(.+?)\s*\(\s*$/i);
                if (ifStart) {
                    if (/^errorlevel\s+\d+$/i.test(ifStart[1])) {
                        var depth2 = 1;
                        while (idx < linesArray.length && depth2 > 0) {
                            var skipLine = linesArray[idx].trim();
                            idx++;
                            if (skipLine === ')') depth2--;
                            else if (/\(\s*$/.test(skipLine)) depth2++;
                        }
                        continue;
                    }
                    pendingIf = { condition: ifStart[1], body: [], depth: 0 };
                    continue;
                }

                var singleFor = expanded.match(/^for\s+%%(\w)\s+in\s+\((.+?)\)\s+do\s+(.+)/i);
                if (singleFor) {
                    var varName = singleFor[1], collection = singleFor[2], command = singleFor[3];
                    var items = await expandCollection(collection);
                    for (var j = 0; j < items.length; j++) {
                        vars[varName] = items[j];
                        stack.push({ var: varName, value: items[j] });
                        var expandedCmd = expandAllForVars(command, stack);
                        expandedCmd = resolveVars(expandedCmd);
                        await executeLine(expandedCmd);
                        stack.pop();
                    }
                    continue;
                }

                var singleIf = expanded.match(/^if\s+(not\s+)?exist\s+"?([^"\s]+)"?\s+(.+)/i);
                if (singleIf) {
                    var notExist = !!singleIf[1], path = singleIf[2], action = singleIf[3].replace(/\)\s*$/, '');
                    if (!notExist) await executeLine(action);
                    continue;
                }

                var ifSet = expanded.match(/^if\s+(?:\/i\s+)?["']?!?(\w+)!?["']?\s*==\s*["']?([^"'\s]+)["']?\s+set\s+"?(\w+)=(.+?)"?\s*$/i);
                if (ifSet) {
                    var leftVal = resolveVars(ifSet[1]);
                    var rightVal = expandAllForVars(ifSet[2], stack);
                    if (ifSet[1].toLowerCase() === rightVal.toLowerCase() || leftVal === rightVal) {
                        vars[ifSet[3]] = ifSet[4];
                    }
                    continue;
                }

                await executeLine(expanded);
            }

            if (localVars) vars = savedVars;
        }

        await processLines(lines, null, []);
        return { steps: steps };
    }
};