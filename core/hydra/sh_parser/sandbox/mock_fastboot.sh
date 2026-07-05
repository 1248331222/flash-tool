#!/system/bin/sh
# Skytree Flasher / core/hydra/sh_parser/sandbox/mock_fastboot.sh
"""
Mock fastboot — PATH 劫持伪沙箱核心
被刷机脚本调用，记录所有 fastboot 命令到 jsonl 日志。

执行流程：
  1. 脚本调 fastboot xxx → Shell 在 PATH 里找到此脚本
  2. Mock 记录命令到 $SH_SANDBOX_LOG
  3. Mock 对 getvar 返回模拟值或占位符
  4. Mock 始终 exit 0（让脚本跑完全程）
"""

LOG_FILE="${SH_SANDBOX_LOG:-/tmp/sh_sandbox_commands.jsonl}"
GETVAR_DEFS="${SH_SANDBOX_GETVAR_DEFS:-/tmp/sh_sandbox_getvar_defs.json}"

# JSON 转义函数
escape_json() {
    printf '%s' "$*" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

# 记录一行命令到 jsonl
log_command() {
    local escaped_cmd
    escaped_cmd=$(escape_json "$1")
    printf '{"cmd":"%s","pending":%s}\n' "$escaped_cmd" "$2" >> "$LOG_FILE"
}

# 检查 pending 变量列表（参数中是否含 ${DECISION:xxx}）
check_pending() {
    local result="[]"
    local first=true
    for arg in "$@"; do
        case "$arg" in
            \$\{DECISION:*)
                if [ "$first" = true ]; then
                    result="[\"$arg\""
                    first=false
                else
                    result="$result, \"$arg\""
                fi
                ;;
        esac
    done
    if [ "$first" = false ]; then
        result="$result]"
    fi
    echo "$result"
}

# 从 getvar_defs.json 中查询某个字段的模拟值
get_mock_value() {
    local field="$1"
    if [ -f "$GETVAR_DEFS" ]; then
        grep -oP "\"$field\":\s*\"[^\"]*\"" "$GETVAR_DEFS" | grep -oP ':\s*"\K[^"]*'
    fi
}

SUBCMD="$1"

case "$SUBCMD" in
    --version|-v)
        echo "fastboot mock v1.0 (skytree-flasher)"
        log_command "fastboot $*" "[]"
        exit 0
        ;;

    --help|-h)
        echo "Usage: fastboot [OPTION...] COMMAND..."
        log_command "fastboot $*" "[]"
        exit 0
        ;;

    getvar)
        FIELD="$2"
        VALUE=$(get_mock_value "$FIELD")
        if [ -n "$VALUE" ]; then
            # 检查值是否含占位符
            case "$VALUE" in
                \$\{DECISION:*)
                    echo "$FIELD: $VALUE"
                    log_command "fastboot $*" "[\"${VALUE}\"]"
                    ;;
                *)
                    echo "$FIELD: $VALUE"
                    log_command "fastboot $*" "[]"
                    ;;
            esac
        else
            # 未知字段 → 记录为待决议
            local placeholder="\${DECISION:getvar_${FIELD}}"
            echo "$FIELD: $placeholder"
            log_command "fastboot $*" "[\"${placeholder}\"]"
        fi
        exit 0
        ;;

    flash|erase|reboot|reboot-bootloader|reboot-fastboot|reboot-edl|format)
        # 标准刷机操作 → 检查参数中的占位符
        PENDING=$(check_pending "$@")
        log_command "fastboot $*" "$PENDING"
        exit 0
        ;;

    oem|flashing|set_active|delete-logical-partition)
        # oem/flashing 类命令 — 依旧记录
        PENDING=$(check_pending "$@")
        log_command "fastboot $*" "$PENDING"
        exit 0
        ;;

    *)
        # 未知子命令，仍然记录（不跳过）
        log_command "fastboot $*" "[\"unknown_subcommand_${SUBCMD}\"]"
        exit 0
        ;;
esac
