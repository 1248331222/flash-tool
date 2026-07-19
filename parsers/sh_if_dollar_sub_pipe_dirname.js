// sh_if_dirname.js
// 规则：解析所有 fastboot/adb 命令，但仅忽略 getvar 类型（不生成步骤）
// 其他命令（flash, erase, reboot, set_active, oem, flashing, shell, raw）均生成步骤

export async function parse(content, ctx) {
    const steps = [];
    const romDir = ctx.romDir || '';
    const extraArgs = ctx.extraArgs || '';

    // ---------- 预处理：合并续行，去除注释 ----------
    let lines = content.split('\n');
    let mergedLines = [];
    let currentLine = '';
    for (let line of lines) {
        line = line.replace(/\r$/, '');
        if (line.endsWith('\\')) {
            currentLine += line.slice(0, -1) + ' ';
            continue;
        } else {
            currentLine += line;
            // 移除注释（简单处理 #，不处理转义）
            let commentIndex = currentLine.search(/(?<!\\)#/);
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

    // ---------- 处理每一行 ----------
    for (let line of mergedLines) {
        // 1. 替换变量
        let cmd = line;

        if (extraArgs) {
            cmd = cmd.replace(/\$\*/g, extraArgs);
        } else {
            cmd = cmd.replace(/\s*\$\*\s*/g, ' ');
            cmd = cmd.replace(/\s{2,}/g, ' ').trim();
        }

        if (romDir) {
            cmd = cmd.replace(/\$\(dirname\s+\$0\)/g, romDir);
            cmd = cmd.replace(/`dirname\s+\$0`/g, romDir);
        }

        // 2. 跳过非 fastboot/adb 命令
        if (!/^(fastboot|adb)\s+/.test(cmd)) continue;

        // 3. 按子命令类型生成步骤
        let m;

        // 3.1 首先检查是否为 getvar —— 如果是，直接跳过，不生成步骤
        if (/^fastboot\s+getvar\s+/i.test(cmd)) {
            // 完全忽略，不 push 任何步骤
            continue;
        }

        // 3.2 fastboot flash
        m = cmd.match(/^fastboot\s+flash\s+(\S+)\s+(.+)/i);
        if (m) {
            let partition = m[1];
            let imagePath = m[2];
            if (romDir && !imagePath.startsWith('/')) {
                imagePath = romDir + '/' + imagePath;
            }
            // 通配符展开
            if (imagePath.includes('*') || imagePath.includes('?')) {
                const dir = imagePath.substring(0, imagePath.lastIndexOf('/'));
                const pattern = imagePath.substring(imagePath.lastIndexOf('/') + 1);
                try {
                    const files = await ctx.fileApi.glob(pattern, dir);
                    if (files.length > 0) {
                        imagePath = files[0];
                    }
                } catch (e) {}
            }
            steps.push({
                type: 'flash',
                partition: partition,
                imagePath: imagePath,
                raw: `fastboot flash ${partition} ${imagePath}`,
                risk: 'MEDIUM'
            });
            continue;
        }

        // 3.3 fastboot erase
        m = cmd.match(/^fastboot\s+erase\s+(\S+)/i);
        if (m) {
            steps.push({
                type: 'erase',
                partition: m[1],
                raw: cmd,
                risk: 'HIGH'
            });
            continue;
        }

        // 3.4 fastboot reboot
        m = cmd.match(/^fastboot\s+reboot\s*(\S*)/i);
        if (m) {
            const target = m[1] || 'system';
            steps.push({
                type: 'reboot',
                target: target,
                raw: cmd,
                risk: 'LOW'
            });
            if (target === 'bootloader' || target === 'fastboot') {
                steps.push({
                    type: 'wait_reconnect',
                    target: target,
                    raw: 'wait for device reconnect',
                    risk: 'LOW'
                });
            }
            continue;
        }

        // 3.5 fastboot --set-active
        m = cmd.match(/^fastboot\s+--set-active\s*=\s*(\S+)/i);
        if (m) {
            steps.push({
                type: 'set_active',
                partition: m[1],
                raw: cmd,
                risk: 'LOW'
            });
            continue;
        }

        // 3.6 fastboot oem
        if (/^fastboot\s+oem\s+/i.test(cmd)) {
            steps.push({
                type: 'oem',
                raw: cmd,
                risk: 'MEDIUM'
            });
            continue;
        }

        // 3.7 fastboot flashing
        if (/^fastboot\s+flashing\s+/i.test(cmd)) {
            steps.push({
                type: 'flashing',
                raw: cmd,
                risk: 'MEDIUM'
            });
            continue;
        }

        // 3.8 adb shell
        if (/^adb\s+shell\s+/i.test(cmd)) {
            steps.push({
                type: 'shell',
                raw: cmd,
                risk: 'MEDIUM'
            });
            continue;
        }

        // 3.9 其他 fastboot/adb 命令作为 raw
        if (/^(fastboot|adb)\s+/.test(cmd)) {
            steps.push({
                type: 'raw',
                raw: cmd,
                risk: 'MEDIUM'
            });
        }
    }

    return { steps };
}