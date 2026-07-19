// static/js/core/classifier.js
// 脚本分类器 — 类别+变体模型
// 输出特征组合字符串，如 "bat_for_if_percent"、"sh_plain"

var ScriptClassifier = (function() {
    'use strict';

    // ============ BAT 类别定义 ============
    var BAT_CATEGORIES = {
        loop: {
            none:     null,
            for:      /\bfor\s+%%\w+\s+in\s+\(/i,
            for_f:    /\bfor\s+\/f/i,
            nested_for: null,  // 由后处理检测
        },
        condition: {
            none:     null,
            if:       /\bif\s+/i,
        },
        branch: {
            none:       null,
            goto:       null,  // 需同时检测 label
            call:       /\bcall\s+:/i,
            interactive: /\b(set\s+\/p|choice\s+\/)/i,
        },
        variable: {
            none:     null,
            percent:  /%(?!%)([A-Z_][A-Z0-9_]*)%|%(?!%)(~[fdpnxstrz]+)?\d/i,   // %VAR% 和 %~dp0 等参数修饰符
            delayed:  /!(?![\w]*errorlevel)([A-Z_][A-Z0-9_]*)!/i,  // 排除 !errorlevel! 等内置
        },
        tool_ref: {
            none:       null,
            direct:     /(?:^|\n)\s*(?:fastboot|adb)\s/im,
            indirect:   /%[\w]*(TOOL|PATH|FASTBOOT)[\w]*%/i,
            prefixed:   /"[^"]*(?:fastboot|adb)\.(?:exe|bat|cmd)"/i,
        },
        decompress: {
            none:   null,
            zstd:   /\bzstd\b/i,
            p7zip:  /\b7z[aer]?\b/i,
            unzip:  /\bunzip\b/i,
        },
    };

    // ============ SH 类别定义 ============
    var SH_CATEGORIES = {
        loop: {
            none:   null,
            for:    /\bfor\s+(?!\(\()\w+\s+in\b/,
            cfor:   /\bfor\s+\(\(/,
            while:  /\bwhile\s+/,
        },
        condition: {
            none:   null,
            if:     /\bif\s+[\[(]/,
            case:   /\bcase\s+\S+\s+in\b/,
        },
        function_def: {
            none:   null,
            defined: /(?:^|\n)\s*(?:function\s+\w+|\w+\s*\(\))\s*\{/,
        },
        expansion: {
            none:        null,
            dollar_sub:  /\$\(/,
            backtick:    /`[^`]+`/,
            dollar_brace: /\$\{/,
        },
        structure: {
            none:    null,
            pipe:    /\|/,
            redirect: /[<>]{1,2}/,
        },
        path_util: {
            none:    null,
            dirname: /\b(?:dirname|readlink|pwd|realpath)\b/,
        },
        decompress: {
            none:   null,
            zstd:   /\bzstd\b/i,
            p7zip:  /\b7z[aer]?\b/i,
            unzip:  /\bunzip\b/i,
        },
    };

    // ============ 检测单个类别 ============
    function _detectCategory(text, variants) {
        for (var name in variants) {
            if (name === 'none') continue;
            var regex = variants[name];
            if (regex && regex.test(text)) return name;
        }
        return 'none';
    }

    // ============ BAT 嵌套 for 后处理 ============
    function _detectNestedFor(text) {
        // 简单检测：同一脚本中出现两个以上 for 语句
        var matches = text.match(/\bfor\s+%%\w+\s+in\b/gi);
        return (matches && matches.length >= 2) ? 'nested_for' : null;
    }

    // ============ BAT goto 后处理（需要同时有 goto 和 :label）============
    function _detectGoto(text) {
        var hasGoto = /\bgoto\s+:?\w+/i.test(text);
        var hasLabel = /^:\w+/m.test(text);
        return (hasGoto && hasLabel) ? 'goto' : null;
    }

    // ============ 检测 %* / %1 参数占位符 ============
    function _detectScriptParams(text, scriptType) {
        if (scriptType === 'bat') {
            return /%\*|%[1-9]/.test(text);
        }
        // SH: $1 $2 $@ 等
        return /\$[1-9@*]/.test(text);
    }

    // ============ 主分类函数 ============
    // fileName: 可选，文件名（用于按后缀判断脚本类型）
    function classify(content, fileName) {
        if (!content || typeof content !== 'string') return { scriptType: 'unknown', key: '', hasParams: false, features: {} };

        var trimmed = content.trim();
        var firstLine = trimmed.split('\n')[0] || '';

        // 按文件后缀直接判断脚本类型（优先）
        var scriptType = 'bat';  // 默认 bat
        var ext = '';
        if (fileName) {
            var dotIdx = fileName.lastIndexOf('.');
            if (dotIdx >= 0) ext = fileName.substring(dotIdx).toLowerCase();
        }
        if (ext === '.sh') {
            scriptType = 'sh';
        } else if (ext === '.bat' || ext === '.cmd') {
            scriptType = 'bat';
        } else {
            // 无后缀或未知后缀：用 shebang 兜底
            if (/^#!\s*\/bin\/(ba)?sh/i.test(firstLine)) {
                scriptType = 'sh';
            }
            // 否则保持默认 bat
        }

        var categories, features;

        if (scriptType === 'sh') {
            categories = SH_CATEGORIES;
            features = {};
            for (var cat in categories) {
                features[cat] = _detectCategory(trimmed, categories[cat]);
            }
        } else {
            categories = BAT_CATEGORIES;
            features = {};
            for (var cat2 in categories) {
                features[cat2] = _detectCategory(trimmed, categories[cat2]);
            }
            // 后处理：嵌套 for 和 goto
            var nested = _detectNestedFor(trimmed);
            if (nested) features.loop = 'nested_for';
            var gotoVal = _detectGoto(trimmed);
            if (gotoVal) features.branch = 'goto';
        }

        // 构建文件名 key
        var parts = [scriptType];
        for (var cat3 in features) {
            if (features[cat3] !== 'none') {
                parts.push(features[cat3]);
            }
        }
        var key = parts.join('_');

        return {
            scriptType: scriptType,
            key: key,
            hasParams: _detectScriptParams(trimmed, scriptType),
            features: features,
        };
    }

    return {
        classify: classify,
    };
})();

if (typeof Modules !== 'undefined' && Modules.register) {
    Modules.register('classifier', [], function() {
        console.log('[classifier] 脚本分类器已初始化');
        return true;
    });
}
