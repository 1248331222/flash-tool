// sh_generic.js
// 通用 Shell 线刷脚本解析器，支持常见变量替换

export async function parse(content, ctx) {
    const steps = [];
    const romDir = ctx.romDir || '';
    const extraArgs = ctx.extraArgs || '';

    // ---------- 1. 预处理：合并续行，去除注释 ----------
    const lines = content.split('\n');
    const mergedLines = [];
    let currentLine = '';
    for (let line of lines) {
        line = line.replace(/\r$/, '');
        if (line.endsWith('\\')) {
            currentLine += line.slice(0, -1) + ' ';
            continue;
        } else {
            currentLine += line;
            const commentIndex = currentLine.search(/(?<!\\)#/);
            if (commentIndex !== -1) {
                currentLine = currentLine.substring(0, commentIndex);
            }
            if (currentLine.trim() !== '') {
                mergedLines.push(currentLine.trim());
            }
            currentLine = '';
        }
    }
    if (currentLine.trim() !== '') {
        mergedLines.push(currentLine.trim());
    }

    // ---------- 2. 逐行处理 ----------
    for (let line of mergedLines) {
        let cmd = line;

        // 2.1 替换 $* 和 dirname
        if (extraArgs) {
            cmd = cmd.replace(/\$\*/g, extraArgs);
        } else {
            cmd = cmd.replace(/\s*\$\*\s*/g, ' ');
            cmd = cmd.replace(/\s{2,}/g, ' ').trim();
        }
        if (romDir) {
            // 替换 $(dirname $0) 和 `dirname $0`
            cmd = cmd.replace(/\$\(dirname\s+\$0\)/g, romDir);
            cmd = cmd.replace(/`dirname\s+\$0`/g, romDir);
            // 替换 ${SCRIPT_PATH} 和 $SCRIPT_PATH
            cmd = cmd.replace(/\$\{SCRIPT_PATH\}/g, romDir);
            cmd = cmd.replace(/\$SCRIPT_PATH\b/g, romDir); // \b 确保不匹配 SCRIPT_PATH_VAR
            // 可选的：替换 ${PWD} / $PWD
            cmd = cmd.replace(/\$\{PWD\}/g, romDir);
            cmd = cmd.replace(/\$PWD\b/g, romDir);
        }

        // 2.2 只处理 fastboot/adb 开头的行
        if (!/^(fastboot|adb)\s+/.test(cmd)) continue;

        // 2.3 规则：忽略 getvar（可注释掉以保留）
        if (/^fastboot\s+getvar\s+/i.test(cmd)) continue;

        // 2.4 提取纯净命令：去除控制符（||, &&, |, ;, >, <）及其后的内容
        let pureCmd = cmd;
        const controlMatch = cmd.match(/^(.*?)(?=\s*(?:\|\||&&|\||;|>|<)\s+)/);
        if (controlMatch) {
            pureCmd = controlMatch[1].trim();
        }
        if (!pureCmd) continue;

        // 2.5 分类匹配
        let m;

        // ---- flash ----
        m = pureCmd.match(/^fastboot\s+flash\s+(\S+)\s+(.+)/i);
        if (m) {
            const partition = m[1];
            let imagePath = m[2];

            // 注意：此时 imagePath 可能已经是替换后的绝对路径
            // 如果仍然不是绝对路径（不以 / 开头），则拼接 romDir
            if (romDir && !imagePath.startsWith('/') && !imagePath.startsWith('http')) {
                imagePath = romDir + '/' + imagePath;
            }
            // 通配符展开：仅当不含未替换的变量（即 $ 符号）且确实有通配符
            if (!imagePath.includes('$') && (imagePath.includes('*') || imagePath.includes('?'))) {
                const dir = imagePath.substring(0, imagePath.lastIndexOf('/'));
                const pattern = imagePath.substring(imagePath.lastIndexOf('/') + 1);
                try {
                    const files = await ctx.fileApi.glob(pattern, dir);
                    if (files.length > 0) {
                        imagePath = files[0]; // 取第一个，可扩展
                    }
                } catch (e) {}
            }

            const cleanRaw = `fastboot ${extraArgs} flash ${partition} ${imagePath}`;
            steps.push({
                type: 'flash',
                partition,
                imagePath,
                raw: cleanRaw,
                risk: 'MEDIUM'
            });
            continue;
        }

        // ---- erase ----
        m = pureCmd.match(/^fastboot\s+erase\s+(\S+)/i);
        if (m) {
            const partition = m[1];
            const cleanRaw = `fastboot ${extraArgs} erase ${partition}`;
            steps.push({
                type: 'erase',
                partition,
                raw: cleanRaw,
                risk: 'HIGH'
            });
            continue;
        }

        // ---- reboot ----
        m = pureCmd.match(/^fastboot\s+reboot\s*(\S*)/i);
        if (m) {
            const target = m[1] || 'system';
            const cleanRaw = `fastboot ${extraArgs} reboot ${target}`;
            steps.push({
                type: 'reboot',
                target,
                raw: cleanRaw,
                risk: 'LOW'
            });
            if (target === 'bootloader' || target === 'fastboot') {
                steps.push({
                    type: 'wait_reconnect',
                    target,
                    raw: 'wait for device reconnect',
                    risk: 'LOW'
                });
            }
            continue;
        }

        // ---- set_active ----
        m = pureCmd.match(/^fastboot\s+--set-active\s*=\s*(\S+)/i);
        if (m) {
            const slot = m[1];
            const cleanRaw = `fastboot ${extraArgs} --set-active=${slot}`;
            steps.push({
                type: 'set_active',
                partition: slot,
                raw: cleanRaw,
                risk: 'LOW'
            });
            continue;
        }

        // ---- oem ----
        m = pureCmd.match(/^fastboot\s+oem\s+(.+)/i);
        if (m) {
            const sub = m[1];
            const cleanRaw = `fastboot ${extraArgs} oem ${sub}`;
            steps.push({ type: 'oem', raw: cleanRaw, risk: 'MEDIUM' });
            continue;
        }

        // ---- flashing ----
        m = pureCmd.match(/^fastboot\s+flashing\s+(.+)/i);
        if (m) {
            const sub = m[1];
            const cleanRaw = `fastboot ${extraArgs} flashing ${sub}`;
            steps.push({ type: 'flashing', raw: cleanRaw, risk: 'MEDIUM' });
            continue;
        }

        // ---- adb shell ----
        m = pureCmd.match(/^adb\s+shell\s+(.+)/i);
        if (m) {
            const sub = m[1];
            const cleanRaw = `adb shell ${sub}`;
            steps.push({ type: 'shell', raw: cleanRaw, risk: 'MEDIUM' });
            continue;
        }

        // ---- 其他 fastboot/adb 命令（兜底） ----
        steps.push({
            type: 'raw',
            raw: pureCmd,
            risk: 'MEDIUM'
        });
    }

    return { steps };
}