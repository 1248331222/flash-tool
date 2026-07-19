// 文件名：按分类器特征键命名，如 bat_rule_based.js
module.exports = {
    parse: function(content, ctx) {
        // 检测交互式输入（set /p），如果有则使用 generator 模式支持用户选择
        if (/\bset\s+\/p\b/i.test(content)) {
            return _interactiveParse(content, ctx);
        }
        return _normalParse(content, ctx);
    }
};

var _normalParse = async function(content, ctx) {
        var steps = [];
        var vars = {};
        var romDir = ctx.romDir || '';
        var fileApi = ctx.fileApi;
        var delayedExpansion = false;

        // ========== 工具函数 ==========
        function resolveVars(text) {
            text = text.replace(/%~dp0/gi, romDir + '/');
            // 保留 %* 和 %1-%9
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

            // ★ 支持解压命令：zstd / 7z / 7za / unzip
            if (bin === 'zstd') {
                // zstd -d input.zst -o output.img  或  zstd --rm -d input.zst -o output.img
                var zInput = '', zOutput = '', zRm = false;
                for (var zi = 1; zi < parts.length; zi++) {
                    if (parts[zi] === '-d' || parts[zi] === '--decompress') continue;
                    if (parts[zi] === '--rm') { zRm = true; continue; }
                    if (parts[zi] === '-o') { zi++; if (zi < parts.length) zOutput = parts[zi]; continue; }
                    if (parts[zi] === '-f' || parts[zi] === '--force') continue;
                    if (!parts[zi].startsWith('-') && !zInput) zInput = parts[zi];
                }
                if (!zOutput && zInput) {
                    // 无 -o 时，输出文件名 = 输入去掉 .zst 后缀
                    zOutput = zInput.replace(/\.zst$/i, '');
                }
                return {
                    type: 'decompress',
                    format: 'zstd',
                    inputFile: normalizePath(zInput),
                    outputFile: normalizePath(zOutput),
                    removeSource: zRm,
                    raw: parts.join(' '),
                    risk: 'LOW'
                };
            }
            if (bin === '7z' || bin === '7za' || bin === '7zr') {
                // 7z x archive.7z -o<dir>  或  7z e archive.zip
                var z7Action = parts[1] || '';
                var z7Input = '', z7OutDir = '';
                for (var zi2 = 2; zi2 < parts.length; zi2++) {
                    if (parts[zi2].startsWith('-o')) { z7OutDir = parts[zi2].substring(2); continue; }
                    if (parts[zi2].startsWith('-')) continue;
                    if (!z7Input) z7Input = parts[zi2];
                }
                var z7Format = z7Input.match(/\.(\w+)$/);
                return {
                    type: 'decompress',
                    format: z7Format ? z7Format[1].toLowerCase() : '7z',
                    inputFile: normalizePath(z7Input),
                    outputFile: z7OutDir ? normalizePath(z7OutDir) : '',
                    removeSource: false,
                    raw: parts.join(' '),
                    risk: 'LOW'
                };
            }

            if (bin !== 'fastboot' && bin !== 'adb') return null;
            var rest = parts.slice(1);
            var globalParams = [];
            while (rest.length && rest[0].startsWith('--')) globalParams.push(rest.shift());
            // 跳过 %* 和 %1-%9 参数占位符（保留用于 raw 构建）
            var paramPlaceholders = [];
            while (rest.length && /^%(\*|[1-9])$/.test(rest[0])) paramPlaceholders.push(rest.shift());
            var ppStr = paramPlaceholders.length ? ' ' + paramPlaceholders.join(' ') : '';
            if (prefixParams) globalParams = prefixParams.split(/\s+/).concat(globalParams);
            var action = rest[0] ? rest[0].toLowerCase() : '';

            if (action === '-w') {
                return { type: 'raw', raw: 'fastboot' + ppStr + ' -w', risk: 'HIGH' };
            }
            if (action === 'getvar') {
                return { type: 'getvar', raw: 'fastboot' + ppStr + ' ' + rest.join(' '), risk: 'LOW' };
            }
            if (action === 'flash') {
                var partition = rest[1] || '';
                var imagePath = normalizePath(rest[2] || '');
                var extraParams = rest.slice(3).join(' ');
                var raw = 'fastboot' + ppStr + (globalParams.length ? ' ' + globalParams.join(' ') : '') + ' flash ' + partition + ' ' + imagePath + (extraParams ? ' ' + extraParams : '');
                return {
                    type: 'flash', partition: partition, imagePath: imagePath,
                    raw: raw, risk: getRisk(partition),
                    prefixParams: globalParams.join(' ') || undefined,
                    params: extraParams || undefined
                };
            }
            if (action === 'erase') {
                return { type: 'erase', partition: rest[1] || '', raw: 'fastboot' + ppStr + ' erase ' + rest[1], risk: 'HIGH' };
            }
            if (action === 'reboot') {
                var target = rest.slice(1).join(' ') || 'system';
                return { type: 'reboot', target: target, raw: 'fastboot' + ppStr + ' reboot' + (target !== 'system' ? ' ' + target : ''), risk: 'LOW' };
            }
            if (action === 'set_active' || action === '--set-active') {
                return { type: 'set_active', partition: rest[1] || '', raw: 'fastboot' + ppStr + ' set_active ' + rest[1], risk: 'MEDIUM' };
            }
            if (action === 'delete-logical-partition') {
                return { type: 'raw', raw: 'fastboot delete-logical-partition ' + rest[1], risk: 'MEDIUM' };
            }
            if (action === 'devices') {
                return { type: 'raw', raw: 'fastboot devices', risk: 'LOW' };
            }
            return { type: 'raw', raw: 'fastboot ' + rest.join(' '), risk: 'MEDIUM' };
        }

        function getRisk(part) {
            var map = { xbl:'CRITICAL',xbl_config:'CRITICAL',abl:'CRITICAL',bootloader:'CRITICAL',preloader_raw:'CRITICAL',modem:'HIGH',frp:'HIGH',metadata:'HIGH' };
            return map[part.toLowerCase()] || 'MEDIUM';
        }

        // ========== 第一阶段：收集 set 变量 ==========
        var lines = content.split(/\r?\n/);
        for (var i = 0; i < lines.length; i++) {
            var line = lines[i].trim();
            if (/^setlocal\s+enabledelayedexpansion/i.test(line)) delayedExpansion = true;
            var setMatch = line.match(/^set\s+"?(\w+)=(.+?)"?\s*$/i);
            if (setMatch) vars[setMatch[1]] = setMatch[2];
        }
        for (var k in vars) vars[k] = resolveVars(vars[k]);

        // ========== 第二阶段：状态机 + 递归处理 ==========
        async function processLines(linesArray, localVars, forStack) {
            var savedVars = Object.assign({}, vars);
            if (localVars) Object.assign(vars, localVars);
            var stack = forStack || [];
            var idx = 0;
            var pendingFor = null, pendingIf = null;

            async function executeLine(line) {
                line = expandAllForVars(line, stack);
                line = resolveVars(line);
                // ★ 精确过滤：仅跳过明显是管道/校验的行，不误伤正常命令
                if (/^(fastboot|adb)\s+.+\|/.test(line) || /findstr/i.test(line)) return;
                var setMatch = line.match(/^\s*set\s+"?(\w+)=(.+?)"?\s*$/i);
                if (setMatch) { vars[setMatch[1]] = resolveVars(setMatch[2]); return; }
                // 在提取命令前，先移除可能存在的无害重定向（如 >nul 2>&1），但保留主命令
                var cleanLine = line.replace(/>.*$/i, '').trim();
                if (!cleanLine) return;
                var parts = splitCmd(cleanLine);
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

                // ★ 兼容 if errorlevel 等多行块
                var ifStart = expanded.match(/^if\s+(.+?)\s*\(\s*$/i);
                if (ifStart) {
                    // 跳过纯 errorlevel 块，但保留其块结构以防止括号匹配错误
                    if (/^errorlevel\s+\d+$/i.test(ifStart[1])) {
                        // 跳过整个块
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
;

// ========== 交互式解析器（generator 模式，支持 set /p + goto + if 条件分支） ==========

async function* _interactiveParse(content, ctx) {
    var steps = [];
    var vars = {};
    var romDir = ctx.romDir || '';
    var fileApi = ctx.fileApi;
    var delayedExpansion = false;

    // ========== 工具函数（复用） ==========
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

    function getRisk(part) {
        var map = { xbl:'CRITICAL',xbl_config:'CRITICAL',abl:'CRITICAL',bootloader:'CRITICAL',preloader_raw:'CRITICAL',modem:'HIGH',frp:'HIGH',metadata:'HIGH' };
        return map[part.toLowerCase()] || 'MEDIUM';
    }

    function makeStep(parts) {
        if (!parts || parts.length === 0) return null;
        var bin = parts[0].replace(/\\/g, '/').split('/').pop().replace(/\.exe$/i, '').toLowerCase();

        // zstd 解压
        if (bin === 'zstd') {
            var zInput = '', zOutput = '', zRm = false;
            for (var zi = 1; zi < parts.length; zi++) {
                if (parts[zi] === '-d' || parts[zi] === '--decompress') continue;
                if (parts[zi] === '--rm') { zRm = true; continue; }
                if (parts[zi] === '-o') { zi++; if (zi < parts.length) zOutput = parts[zi]; continue; }
                if (parts[zi] === '-f' || parts[zi] === '--force') continue;
                if (!parts[zi].startsWith('-') && !zInput) zInput = parts[zi];
            }
            if (!zOutput && zInput) zOutput = zInput.replace(/\.zst$/i, '');
            return { type: 'decompress', format: 'zstd', inputFile: normalizePath(zInput), outputFile: normalizePath(zOutput), removeSource: zRm, raw: parts.join(' '), risk: 'LOW' };
        }

        if (bin !== 'fastboot' && bin !== 'adb') return null;
        var rest = parts.slice(1);
        var globalParams = [];
        while (rest.length && rest[0].startsWith('--')) globalParams.push(rest.shift());
        // 跳过 %* 和 %1-%9 参数占位符（保留用于 raw 构建，但跳过 action 识别）
        var paramPlaceholders = [];
        while (rest.length && /^%(\*|[1-9])$/.test(rest[0])) paramPlaceholders.push(rest.shift());
        var ppStr = paramPlaceholders.length ? ' ' + paramPlaceholders.join(' ') : '';
        var action = rest[0] ? rest[0].toLowerCase() : '';

        if (action === '-w') return { type: 'raw', raw: 'fastboot' + ppStr + ' -w', risk: 'HIGH' };
        if (action === 'flash') {
            var partition = rest[1] || '';
            var imagePath = normalizePath(rest[2] || '');
            var extraParams = rest.slice(3).join(' ');
            var raw = 'fastboot' + ppStr + (globalParams.length ? ' ' + globalParams.join(' ') : '') + ' flash ' + partition + ' ' + imagePath + (extraParams ? ' ' + extraParams : '');
            return { type: 'flash', partition: partition, imagePath: imagePath, raw: raw, risk: getRisk(partition), prefixParams: globalParams.join(' ') || undefined, params: extraParams || undefined };
        }
        if (action === 'erase') return { type: 'erase', partition: rest[1] || '', raw: 'fastboot' + ppStr + ' erase ' + rest[1], risk: 'HIGH' };
        if (action === 'reboot') {
            var target = rest.slice(1).join(' ') || 'system';
            return { type: 'reboot', target: target, raw: 'fastboot' + ppStr + ' reboot' + (target !== 'system' ? ' ' + target : ''), risk: 'LOW' };
        }
        if (action === 'set_active' || action === '--set-active') return { type: 'set_active', partition: rest[1] || '', raw: 'fastboot' + ppStr + ' set_active ' + rest[1], risk: 'MEDIUM' };
        if (action === 'delete-logical-partition') return { type: 'raw', raw: 'fastboot delete-logical-partition ' + rest[1], risk: 'MEDIUM' };
        if (action === 'devices') return { type: 'raw', raw: 'fastboot devices', risk: 'LOW' };
        return { type: 'raw', raw: 'fastboot ' + rest.join(' '), risk: 'MEDIUM' };
    }

    function makeStepFromLine(line) {
        line = resolveVars(line);
        var cleanLine = line.replace(/>.*$/i, '').trim();
        if (!cleanLine) return null;
        var parts = splitCmd(cleanLine);
        if (parts.length === 0) return null;
        return makeStep(parts);
    }

    async function checkFileExists(path) {
        path = resolveVars(path);
        path = path.replace(/\\/g, '/').replace(/^["']|["']$/g, '');
        if (!path.startsWith('/')) path = romDir ? romDir.replace(/\/+$/, '') + '/' + path : path;
        if (fileApi && fileApi.exists) {
            try { return await fileApi.exists(path); } catch(e) {}
        }
        return false;  // 无法确认时默认不存在
    }

    // ========== 预扫描标签 ==========
    var allLines = content.split(/\r?\n/);
    var labels = {};
    for (var i = 0; i < allLines.length; i++) {
        var trimmed = allLines[i].trim();
        var labelMatch = trimmed.match(/^:(\w+)/);
        if (labelMatch) labels[labelMatch[1].toLowerCase()] = i;
    }

    // 检测 setlocal enabledelayedexpansion
    if (/setlocal\s+enabledelayedexpansion/i.test(content)) delayedExpansion = true;

    // 收集 set 变量
    for (var si = 0; si < allLines.length; si++) {
        var sl = allLines[si].trim();
        var sm = sl.match(/^set\s+"?(\w+)=(.+?)"?\s*$/i);
        if (sm && !/\bset\s+\/p\b/i.test(sl)) vars[sm[1]] = resolveVars(sm[2]);
    }

    // ========== 预处理：合并多行 if 块为单行 ==========
    // BAT 中 if /i "%VAR%" == "X" ( 换行 goto LABEL 换行 ) → 合并为 if /i "%VAR%" == "X" (goto LABEL)
    var processedLines = [];
    var pIdx = 0;
    while (pIdx < allLines.length) {
        var pLine = allLines[pIdx].trim();
        pIdx++;
        // 检测 if ... ( 行末尾有括号开始多行块
        if (/^if\s+\/i\s+"?%(\w+)%"?\s*==\s*"?(.+?)"?\s*\(\s*$/i.test(pLine) ||
            (/^if\s+\/i\s+"?%(\w+)%"?\s*==\s*"?(.+?)"?\s*\(/i.test(pLine) && !/\)\s*(else\s|$)/i.test(pLine))) {
            // 收集块体直到所有括号匹配
            var blockParts = [pLine.replace(/\(\s*$/, ' (')];
            var depth = (pLine.match(/\(/g) || []).length - (pLine.match(/\)/g) || []).length;
            while (pIdx < allLines.length && depth > 0) {
                var bLine = allLines[pIdx].trim();
                pIdx++;
                depth += (bLine.match(/\(/g) || []).length - (bLine.match(/\)/g) || []).length;
                blockParts.push(bLine);
            }
            // 合并为单行：命令行添加 ; 分隔，清理括号前的分号和多余空格
            var merged = blockParts.map(function(line, idx) {
                if (idx === 0) return line.replace(/\(\s*$/, '(');
                if (/^\)/.test(line)) return line;
                return line + ';';
            }).join(' ').replace(/;\s*\)/g, ')').replace(/\(\s+/g, '(').replace(/\s+\)/g, ')').replace(/\s+/g, ' ').trim();
            processedLines.push(merged);
        } else {
            processedLines.push(pLine);
        }
    }
    allLines = processedLines;

    // 重新扫描标签（合并后行号变了）
    labels = {};
    for (var li = 0; li < allLines.length; li++) {
        var lt = allLines[li].trim();
        var lm = lt.match(/^:(\w+)/);
        if (lm) labels[lm[1].toLowerCase()] = li;
    }

    // ========== 主执行循环 ==========
    var ip = 0;
    var maxIter = 50000;
    var iter = 0;
    var visitedLabels = {};

    while (ip < allLines.length && iter < maxIter) {
        iter++;
        var rawLine = allLines[ip].trim();
        ip++;

        // 跳过空行、注释、无关命令
        if (!rawLine || /^(::|rem\b|@echo|echo\b|title|color|cls|pause|timeout|chcp|endlocal|mode\b)/i.test(rawLine)) continue;
        if (rawLine.startsWith('@')) rawLine = rawLine.substring(1).trim();
        if (!rawLine) continue;

        // 跳过标签定义
        if (/^:\w+/.test(rawLine)) continue;

        // === set /p 交互式输入 → yield choice ===
        var setPMatch = rawLine.match(/^set\s+\/p\s+(\w+)="?(.+?)"?\s*$/i);
        if (setPMatch) {
            var pVarName = setPMatch[1];
            var pPrompt = setPMatch[2].replace(/["]/g, '');
            var choiceIdx = yield { type: 'choice', prompt: pPrompt, options: ['Y - 是', 'N - 否'] };
            vars[pVarName] = (choiceIdx === 0) ? 'y' : 'n';
            continue;
        }

        // === set 变量赋值 ===
        var setMatch = rawLine.match(/^set\s+"?(\w+)=(.+?)"?\s*$/i);
        if (setMatch && !/\bset\s+\/p\b/i.test(rawLine)) {
            vars[setMatch[1]] = resolveVars(setMatch[2]);
            continue;
        }

        // === goto 跳转 ===
        var gotoMatch = rawLine.match(/^goto\s+(\w+)/i);
        if (gotoMatch) {
            var gotoLabel = gotoMatch[1].toLowerCase();
            if (labels[gotoLabel] !== undefined) {
                // 检测死循环（如 :Finish goto Finish）
                if (visitedLabels[gotoLabel] && visitedLabels[gotoLabel] > 3) break;
                visitedLabels[gotoLabel] = (visitedLabels[gotoLabel] || 0) + 1;
                ip = labels[gotoLabel];
            }
            continue;
        }

        // === exit ===
        if (/^exit\b/i.test(rawLine)) break;

        // === 统一处理 if /i "%VAR%" == "X" (action) [else if ... (action)] [else (action)] ===
        // action 可以是 goto LABEL、exit、或 fastboot/adb 命令
        var ifChainMatch = rawLine.match(/^if\s+\/i\s+"?%(\w+)%"?\s*==\s*"?(.+?)"?\s*\((.+?)\)/i);
        if (ifChainMatch) {
            var _matched = false;
            var _varVal = (vars[ifChainMatch[1]] || '').toLowerCase();
            var _cmpVal = ifChainMatch[2].toLowerCase();
            if (_varVal === _cmpVal) {
                _matched = true;
                var _action = ifChainMatch[3].trim();
                var _gotoM = _action.match(/^goto\s+(\w+)/i);
                if (_gotoM) {
                    var _gl = _gotoM[1].toLowerCase();
                    if (labels[_gl] !== undefined) ip = labels[_gl];
                } else if (/^exit\b/i.test(_action)) {
                    break;
                } else {
                    var _cmds = _action.split(/\s*;\s*/);
                    for (var _ci = 0; _ci < _cmds.length; _ci++) {
                        var _step = makeStepFromLine(_cmds[_ci]);
                        if (_step) { steps.push(_step); yield { type: 'step', step: _step }; }
                    }
                }
            }
            // 检查 else if 链
            if (!_matched) {
                var _remaining = rawLine.substring(ifChainMatch[0].length);
                var _elseIfRegex = /else\s+if\s+\/i\s+"?%(\w+)%"?\s*==\s*"?(.+?)"?\s*\((.+?)\)/gi;
                var _elseIfMatch;
                while ((_elseIfMatch = _elseIfRegex.exec(_remaining))) {
                    var _ev = (vars[_elseIfMatch[1]] || '').toLowerCase();
                    var _cv = _elseIfMatch[2].toLowerCase();
                    if (_ev === _cv) {
                        _matched = true;
                        var _action2 = _elseIfMatch[3].trim();
                        var _gotoM2 = _action2.match(/^goto\s+(\w+)/i);
                        if (_gotoM2) {
                            var _gl2 = _gotoM2[1].toLowerCase();
                            if (labels[_gl2] !== undefined) ip = labels[_gl2];
                        } else if (/^exit\b/i.test(_action2)) {
                            ip = allLines.length;
                        } else {
                            var _cmds2 = _action2.split(/\s*;\s*/);
                            for (var _ci2 = 0; _ci2 < _cmds2.length; _ci2++) {
                                var _step2 = makeStepFromLine(_cmds2[_ci2]);
                                if (_step2) { steps.push(_step2); yield { type: 'step', step: _step2 }; }
                            }
                        }
                        break;
                    }
                }
            }
            // 检查 else
            if (!_matched) {
                var _elseMatch = rawLine.match(/(?:\)\s*)?else\s*\((.+?)\)\s*$/i);
                if (_elseMatch) {
                    var _action3 = _elseMatch[1].trim();
                    var _gotoM3 = _action3.match(/^goto\s+(\w+)/i);
                    if (_gotoM3) {
                        var _gl3 = _gotoM3[1].toLowerCase();
                        if (labels[_gl3] !== undefined) ip = labels[_gl3];
                    } else if (/^exit\b/i.test(_action3)) {
                        break;
                    } else {
                        var _cmds3 = _action3.split(/\s*;\s*/);
                        for (var _ci3 = 0; _ci3 < _cmds3.length; _ci3++) {
                            var _step3 = makeStepFromLine(_cmds3[_ci3]);
                            if (_step3) { steps.push(_step3); yield { type: 'step', step: _step3 }; }
                        }
                    }
                }
            }
            continue;
        }

        // === if exist path (command) === 单行
        var ifExistSingle = rawLine.match(/^if\s+exist\s+"?([^"\s]+)"?\s+\((.+?)\)\s*$/i);
        if (ifExistSingle) {
            var _existPath = ifExistSingle[1];
            var _existCmd = ifExistSingle[2];
            var _exists = await checkFileExists(_existPath);
            if (_exists) {
                var _existStep = makeStepFromLine(_existCmd);
                if (_existStep) { steps.push(_existStep); yield { type: 'step', step: _existStep }; }
            }
            continue;
        }

        // === if exist path ( 多行块 ) ===
        var ifExistBlock = rawLine.match(/^if\s+exist\s+"?([^"\s]+)"?\s*\(\s*$/i);
        if (ifExistBlock) {
            var _blockPath = ifExistBlock[1];
            var _blockBody = [];
            var _blockDepth = 1;
            while (ip < allLines.length && _blockDepth > 0) {
                var _bl = allLines[ip].trim();
                ip++;
                if (_bl === ')') { _blockDepth--; if (_blockDepth > 0) _blockBody.push(_bl); }
                else { _blockBody.push(_bl); if (/\(\s*$/.test(_bl)) _blockDepth++; }
            }
            var _blockExists = await checkFileExists(_blockPath);
            if (_blockExists) {
                for (var bi = 0; bi < _blockBody.length; bi++) {
                    var _bStep = makeStepFromLine(_blockBody[bi]);
                    if (_bStep) { steps.push(_bStep); yield { type: 'step', step: _bStep }; }
                }
            }
            continue;
        }

        // === 普通 fastboot/adb 命令 ===
        var _normalStep = makeStepFromLine(rawLine);
        if (_normalStep) { steps.push(_normalStep); yield { type: 'step', step: _normalStep }; }
    }

    return { steps: steps };
}