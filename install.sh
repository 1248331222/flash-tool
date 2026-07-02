#!/data/data/com.termux/files/usr/bin/bash
# 天树刷机 (Skytree Flasher) - 管理脚本（部署/启动/停止/重启/备份/恢复）
# 使用方法：在 Termux 中执行以下命令即可（curl 是 Termux 自带的，无需额外安装）
#
#   bash <(curl -sL "http://81.68.84.205:5244/sd/flash_tool/install.sh")
#
# 或先下载再执行：
#   curl -sLo ~/install.sh "http://81.68.84.205:5244/sd/flash_tool/install.sh" && bash ~/install.sh
#
set -e

# 全局非交互设置，防止 apt/pip/dpkg 弹出确认提示
export DEBIAN_FRONTEND=noninteractive
export DEBCONF_NONINTERACTIVE_SEEN=true
export DEBIAN_PRIORITY=critical

# ============ 配置区（按需修改） ============
REMOTE_ZIP="http://81.68.84.205:5244/sd/flash_tool/flash_tool.zip"
REMOTE_VERSION="http://81.68.84.205:5244/sd/flash_tool/version.txt"
FASTBOOT_BIN_URL="http://81.68.84.205:5244/sd/flash_tool/fastboot.1"
FASTBOOT_BIN_GITHUB="https://github.com/nicoh88/termux-adb-fastboot/releases/download/v35.0.2/fastboot-aarch64"
OFFLINE_DEP_URL="http://81.68.84.205:5244/sd/flash_tool/offline_deps.tar.gz"
AUTO_UPDATE_TIMEOUT=6   # 自动更新检查超时秒数
# ============================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()  { printf "${BLUE}[信息]${NC} %s\n" "$1"; }
ok()    { printf "${GREEN}[完成]${NC} %s\n" "$1"; }
warn()  { printf "${YELLOW}[提示]${NC} %s\n" "$1"; }
err()   { printf "${RED}[错误]${NC} %s\n" "$1"; }

if [ -z "$PREFIX" ] || [ ! -d "$PREFIX" ]; then
  err "请在 Termux 中运行本脚本。"
  exit 1
fi

INSTALL_DIR="$HOME/flash_tool"
APP_FILE="$INSTALL_DIR/app.py"
CONFIG_FILE="$INSTALL_DIR/config.py"
RUN_FILE="$INSTALL_DIR/run_flash_tool.sh"
WORK_DIR="$HOME/flash_tool_setup"
PID_FILE="$INSTALL_DIR/flash_tool.pid"
FASTBOOT_BIN_DIR="$HOME/.termux-adb"
FASTBOOT_BIN_FILE="$FASTBOOT_BIN_DIR/fastboot"

# ============ 检测安装状态（只要求 app.py 存在） ============
check_installed() {
  [ -f "$APP_FILE" ]
}

# ============ 检测运行状态 ============
check_running() {
  if [ -f "$PID_FILE" ]; then
    local pid
    pid=$(cat "$PID_FILE" 2>/dev/null)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
  fi
  if pgrep -f "python.*app.py" >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

get_status_text() {
  if check_running; then
    echo "${GREEN}运行中 - 浏览器打开 http://127.0.0.1:8080${NC}"
  elif check_installed; then
    echo "${YELLOW}已安装（未运行）${NC}"
  else
    echo "${RED}未安装${NC}"
  fi
}

banner() {
  printf "${GREEN}"
  cat <<'BANNER'
  ╔══════════════════════════════════════╗
  ║     天树刷机 (Skytree Flasher)       ║
  ╚══════════════════════════════════════╝
BANNER
  printf "${NC}"
}

check_storage_permission() {
  [ -d "$HOME/storage/shared" ] && [ -r "$HOME/storage/shared" ]
}

show_menu() {
  banner
  echo ""
  printf "  当前状态: %b\n" "$(get_status_text)"
  if ! check_storage_permission; then
    printf "  ${RED}${BOLD}存储权限未授权${NC}\n\n"
  else
    printf "  ${GREEN}存储权限已授权${NC}\n\n"
  fi
  printf "${CYAN}${BOLD}  请选择操作：${NC}\n"
  echo "  ─────────────────────────────────────"
  printf "  ${GREEN}1.${NC} 启动刷机工具\n"
  printf "  ${GREEN}2.${NC} 停止刷机工具\n"
  printf "  ${GREEN}3.${NC} 重启刷机工具\n"
  printf "  ${GREEN}4.${NC} 部署/重装刷机工具\n"
  printf "  ${RED}5.${NC} 卸载刷机工具\n"
  printf "  ${CYAN}6.${NC} 授权手机存储权限\n"
  printf "  ${CYAN}7.${NC} 检查更新（交互式）\n"
  printf "  ${YELLOW}8.${NC} 备份当前环境为离线恢复包\n"
  printf "  ${YELLOW}0.${NC} 退出\n"
  echo "  ─────────────────────────────────────"
  echo ""
}

# ============ 启动 ============
do_start() {
  if ! check_installed; then
    err "刷机工具未安装，请先选择 4 进行部署安装。"
    return 1
  fi
  if check_running; then
    warn "刷机工具已经在运行中"
    info "访问地址: http://127.0.0.1:8080"
    return 0
  fi

  # 确保 run_flash_tool.sh 存在
  if [ ! -f "$RUN_FILE" ]; then
    info "生成启动脚本 run_flash_tool.sh ..."
    cat > "$RUN_FILE" <<'RUNNER'
#!/data/data/com.termux/files/usr/bin/bash
cd "$HOME/flash_tool"
python app.py "$@"
RUNNER
    chmod +x "$RUN_FILE"
  fi

  # ---- 启动前自动更新检查 ----
  info "启动前检查更新（超时 ${AUTO_UPDATE_TIMEOUT} 秒）..."
  if do_auto_update; then
    info "自动更新完成，将启动新版本。"
  else
    info "无可用更新或检查失败，将启动当前版本。"
  fi

  # 确保 fastboot 二进制存在
  if [ ! -f "$FASTBOOT_BIN_FILE" ] || [ "$(stat -c%s "$FASTBOOT_BIN_FILE" 2>/dev/null)" -lt 1000 ]; then
    info "未检测到 fastboot 二进制，正在下载..."
    mkdir -p "$FASTBOOT_BIN_DIR"
    local fb_ok=0
    if command -v curl &>/dev/null; then
      curl --progress-bar -L -o "$FASTBOOT_BIN_FILE" "$FASTBOOT_BIN_URL" && chmod +x "$FASTBOOT_BIN_FILE" && fb_ok=1
    elif command -v wget &>/dev/null; then
      wget --show-progress -O "$FASTBOOT_BIN_FILE" "$FASTBOOT_BIN_URL" && chmod +x "$FASTBOOT_BIN_FILE" && fb_ok=1
    fi
    if [ "$fb_ok" -eq 0 ] && [ -n "$FASTBOOT_BIN_GITHUB" ]; then
      warn "主源下载失败，尝试备用源..."
      if command -v curl &>/dev/null; then
        curl --progress-bar -L -o "$FASTBOOT_BIN_FILE" "$FASTBOOT_BIN_GITHUB" && chmod +x "$FASTBOOT_BIN_FILE" && fb_ok=1
      elif command -v wget &>/dev/null; then
        wget --show-progress -O "$FASTBOOT_BIN_FILE" "$FASTBOOT_BIN_GITHUB" && chmod +x "$FASTBOOT_BIN_FILE" && fb_ok=1
      fi
    fi
    if [ "$fb_ok" -eq 1 ]; then
      ok "fastboot 二进制下载完成"
    else
      warn "fastboot 下载失败，将尝试使用系统 fastboot"
    fi
  fi

  info "正在启动刷机工具..."
  cd "$INSTALL_DIR"
  nohup python app.py > "$INSTALL_DIR/flash_tool.log" 2>&1 &
  local pid=$!
  echo "$pid" > "$PID_FILE"
  sleep 1
  if kill -0 "$pid" 2>/dev/null; then
    ok "刷机工具已启动"
    info "访问地址: http://127.0.0.1:8080"
    # 启动后静默检查（仅提示，不自动更新）
    do_check_update_silent
    return 0
  else
    err "启动失败，请检查日志: $INSTALL_DIR/flash_tool.log"
    rm -f "$PID_FILE"
    return 1
  fi
}

# ============ 自动更新函数（超时限制） ============
do_auto_update() {
  # 返回 0 表示执行了更新并成功，1 表示无需更新或更新失败
  local local_ver remote_ver
  local_ver=$(get_local_version)
  if [ -z "$local_ver" ]; then
    return 1
  fi

  remote_ver=$(timeout "$AUTO_UPDATE_TIMEOUT" curl -sL --max-time "$AUTO_UPDATE_TIMEOUT" "$REMOTE_VERSION" 2>/dev/null | head -1)
  remote_ver="${remote_ver%%[[:space:]]*}"
  if [ -z "$remote_ver" ]; then
    return 1
  fi

  local needs_update=0
  local lv=(${local_ver//./ })
  local rv=(${remote_ver//./ })
  for i in 0 1 2; do
    if [ "${rv[$i]:-0}" -gt "${lv[$i]:-0}" ] 2>/dev/null; then
      needs_update=1
      break
    fi
  done
  if [ "$needs_update" -eq 0 ]; then
    return 1
  fi

  info "发现新版本 v${remote_ver}，开始自动更新（无需确认）..."

  local backup_dir="${INSTALL_DIR}_backup_$(date +%Y%m%d%H%M%S)"
  info "备份当前版本到 $backup_dir"
  mv "$INSTALL_DIR" "$backup_dir"
  mkdir -p "$INSTALL_DIR"

  local zip_file="${WORK_DIR}/flash_tool.zip"
  mkdir -p "$WORK_DIR"
  if ! download_file "$REMOTE_ZIP" "$zip_file" "压缩包"; then
    err "下载失败，恢复备份"
    rm -rf "$INSTALL_DIR"
    mv "$backup_dir" "$INSTALL_DIR"
    return 1
  fi

  if ! unzip -q -o "$zip_file" -d "$INSTALL_DIR"; then
    err "解压失败，恢复备份"
    rm -rf "$INSTALL_DIR"
    mv "$backup_dir" "$INSTALL_DIR"
    rm -f "$zip_file"
    return 1
  fi

  if [ -d "$INSTALL_DIR/flash_tool" ] && [ ! -f "$INSTALL_DIR/app.py" ]; then
    mv "$INSTALL_DIR/flash_tool"/* "$INSTALL_DIR/"
    rmdir "$INSTALL_DIR/flash_tool"
  fi

  rm -f "$zip_file"
  chmod +x "$APP_FILE"

  cat > "$RUN_FILE" <<'RUNNER'
#!/data/data/com.termux/files/usr/bin/bash
cd "$HOME/flash_tool"
python app.py "$@"
RUNNER
  chmod +x "$RUN_FILE"

  ok "自动更新完成，已更新到 v${remote_ver}"
  return 0
}

# ============ 停止 ============
do_stop() {
  if ! check_installed; then
    err "刷机工具未安装，无需停止。"
    return 1
  fi
  if ! check_running; then
    warn "刷机工具当前未运行"
    return 0
  fi
  info "正在停止刷机工具..."
  local pid=""
  if [ -f "$PID_FILE" ]; then
    pid=$(cat "$PID_FILE" 2>/dev/null)
  fi
  if [ -n "$pid" ]; then
    kill "$pid" 2>/dev/null || true
    sleep 1
    kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
  fi
  pkill -f "python.*app.py" 2>/dev/null || true
  rm -f "$PID_FILE"
  ok "刷机工具已停止"
}

# ============ 重启 ============
do_restart() {
  if ! check_installed; then
    err "刷机工具未安装，请先选择 4 进行部署安装。"
    return 1
  fi
  do_stop
  sleep 1
  do_start
}

# ============ 卸载 ============
do_uninstall() {
  if ! check_installed; then
    err "刷机工具未安装，无需卸载。"
    return 1
  fi
  echo ""
  printf "${RED}${BOLD}警告：卸载将删除以下内容：${NC}\n"
  echo "  - 刷机工具程序文件 ($INSTALL_DIR)"
  echo "  - 运行日志 ($INSTALL_DIR/flash_tool.log)"
  echo "  - 线刷包目录 ($HOME/storage/shared/123456)"
  echo ""
  read -p "确认卸载？(输入 yes 确认): " confirm
  if [ "$confirm" != "yes" ]; then
    info "已取消卸载"
    return 0
  fi
  info "正在卸载刷机工具..."
  if check_running; then
    do_stop
  fi
  rm -rf "$INSTALL_DIR"
  ok "已删除程序文件"
  if [ -d "$HOME/storage/shared/123456" ]; then
    read -p "是否同时删除线刷包目录？(y/N) " del_roms
    if [ "$del_roms" = "y" ] || [ "$del_roms" = "Y" ]; then
      rm -rf "$HOME/storage/shared/123456"
      ok "已删除线刷包目录"
    else
      info "保留线刷包目录: $HOME/storage/shared/123456"
    fi
  fi
  ok "刷机工具卸载完成"
}

# ============ 授权存储权限 ============
do_grant_storage() {
  if check_storage_permission; then
    ok "存储权限已授权，无需重复操作"
    return 0
  fi
  info "正在请求存储权限..."
  info "请在弹出的对话框中点击【允许】"
  termux-setup-storage
  info "等待授权..."
  local retry=0
  while [ $retry -lt 30 ]; do
    sleep 1
    if check_storage_permission; then
      ok "存储权限授权成功"
      return 0
    fi
    retry=$((retry + 1))
  done
  err "等待超时，未检测到存储权限"
  warn "请手动执行: termux-setup-storage"
  return 1
}

# ============ 通用下载函数 ============
download_file() {
  local url="$1" output="$2" desc="$3"
  [ -n "$desc" ] && info "下载 $desc ..."
  if command -v curl &>/dev/null; then
    curl --progress-bar -L -o "$output" "$url" && return 0
  fi
  if command -v wget &>/dev/null; then
    wget --show-progress -O "$output" "$url" && return 0
  fi
  return 1
}

# ============ 版本提取函数（通用） ============
get_local_version() {
  local ver=""
  if [ -f "$CONFIG_FILE" ]; then
    ver=$(grep '^[[:space:]]*TOOL_VERSION' "$CONFIG_FILE" 2>/dev/null | head -1 | sed -n 's/.*"\([0-9.]*\)".*/\1/p')
  fi
  if [ -z "$ver" ] && [ -f "$APP_FILE" ]; then
    ver=$(grep '^[[:space:]]*TOOL_VERSION' "$APP_FILE" 2>/dev/null | head -1 | sed -n 's/.*"\([0-9.]*\)".*/\1/p')
  fi
  if [ -z "$ver" ] && [ -f "$CONFIG_FILE" ]; then
    ver=$(grep 'TOOL_VERSION' "$CONFIG_FILE" 2>/dev/null | head -1 | sed -n 's/.*"\([0-9.]*\)".*/\1/p')
  fi
  if [ -z "$ver" ] && [ -f "$APP_FILE" ]; then
    ver=$(grep 'TOOL_VERSION' "$APP_FILE" 2>/dev/null | head -1 | sed -n 's/.*"\([0-9.]*\)".*/\1/p')
  fi
  echo "$ver"
}

# ============ 检查更新（交互式） ============
do_check_update() {
  if ! check_installed; then
    err "刷机工具未安装，请先选择 4 进行部署安装。"
    return 1
  fi

  info "正在检查更新..."
  local local_version=""
  local_version=$(get_local_version)
  [ -z "$local_version" ] && local_version="未知"
  info "当前版本: v${local_version}"

  local remote_version=""
  remote_version=$(curl -sL --max-time 5 "$REMOTE_VERSION" 2>/dev/null | head -1)
  remote_version="${remote_version%%[[:space:]]*}"
  if [ -z "$remote_version" ]; then
    err "无法获取远程版本信息，请检查网络"
    return 1
  fi
  info "最新版本: v${remote_version}"

  if [ "$local_version" = "$remote_version" ]; then
    ok "已是最新版本"
    return 0
  fi

  local needs_update=0
  local lv=(${local_version//./ })
  local rv=(${remote_version//./ })
  for i in 0 1 2; do
    if [ "${rv[$i]:-0}" -gt "${lv[$i]:-0}" ] 2>/dev/null; then
      needs_update=1
      break
    fi
  done
  if [ "$needs_update" -eq 0 ]; then
    ok "已是最新版本"
    return 0
  fi

  printf "${YELLOW}发现新版本 v${remote_version}（当前 v${local_version}）${NC}\n"
  echo ""
  read -p "是否立即更新？(Y/n) " do_update
  do_update="${do_update:-Y}"
  if [ "$do_update" != "Y" ] && [ "$do_update" != "y" ]; then
    info "已取消更新"
    return 0
  fi

  if check_running; then
    do_stop
  fi

  local backup_dir="${INSTALL_DIR}_backup_$(date +%Y%m%d%H%M%S)"
  info "备份当前版本到 $backup_dir"
  mv "$INSTALL_DIR" "$backup_dir"
  mkdir -p "$INSTALL_DIR"

  local zip_file="${WORK_DIR}/flash_tool.zip"
  mkdir -p "$WORK_DIR"
  info "正在下载新版本 flash_tool.zip ..."
  if download_file "$REMOTE_ZIP" "$zip_file" "压缩包"; then
    ok "下载完成"
  else
    err "下载失败，恢复备份"
    rm -rf "$INSTALL_DIR"
    mv "$backup_dir" "$INSTALL_DIR"
    return 1
  fi

  info "正在解压..."
  if ! unzip -q -o "$zip_file" -d "$INSTALL_DIR"; then
    err "解压失败，恢复备份"
    rm -rf "$INSTALL_DIR"
    mv "$backup_dir" "$INSTALL_DIR"
    rm -f "$zip_file"
    return 1
  fi

  if [ -d "$INSTALL_DIR/flash_tool" ] && [ ! -f "$INSTALL_DIR/app.py" ]; then
    info "检测到 zip 内包含顶层目录，正在调整结构..."
    mv "$INSTALL_DIR/flash_tool"/* "$INSTALL_DIR/"
    rmdir "$INSTALL_DIR/flash_tool"
  fi

  rm -f "$zip_file"
  chmod +x "$APP_FILE"

  cat > "$RUN_FILE" <<'RUNNER'
#!/data/data/com.termux/files/usr/bin/bash
cd "$HOME/flash_tool"
python app.py "$@"
RUNNER
  chmod +x "$RUN_FILE"

  ok "更新完成！新版本已部署"
  do_stop
  sleep 1
  do_start
}

# ============ 备份环境 ============
do_backup() {
  if ! check_installed; then
    err "刷机工具未安装，无法备份。请先部署一次。"
    return 1
  fi
  if ! check_storage_permission; then
    err "存储权限未授权，无法保存备份。请先执行选项 6。"
    return 1
  fi

  local backup_dest="/storage/emulated/0/123456"
  local backup_file="$backup_dest/offline_deps.tar.gz"

  echo ""
  printf "${CYAN}${BOLD}离线恢复包备份（tar.gz 格式）${NC}\n"
  echo "─────────────────────────────────────"
  info "将要备份的内容："
  echo "  - Termux 运行环境 ($PREFIX)"
  echo "  - 刷机工具主程序 ($INSTALL_DIR)"
  echo "  - fastboot 免root 二进制 ($FASTBOOT_BIN_DIR)"
  echo ""
  printf "${YELLOW}备份文件将保存到：${NC}\n"
  echo "  $backup_file"
  echo ""
  read -p "确认开始备份？(Y/n) " confirm
  confirm="${confirm:-Y}"
  if [ "$confirm" != "Y" ] && [ "$confirm" != "y" ]; then
    info "已取消备份"
    return 0
  fi

  if check_running; then
    info "检测到刷机工具正在运行，正在停止..."
    do_stop
  fi

  mkdir -p "$backup_dest" 2>/dev/null || {
    err "无法创建目录 $backup_dest ，请检查存储权限。"
    return 1
  }

  if ! command -v tar &>/dev/null; then
    info "安装 tar ..."
    yes "" | DEBIAN_FRONTEND=noninteractive apt install -y tar || {
      err "无法安装 tar，请手动安装后重试。"
      return 1
    }
  fi

  info "开始打包（请耐心等待）..."
  cd /data/data/com.termux/files || { err "无法进入 Termux 数据目录"; return 1; }
  mkdir -p home/.termux-adb

  if tar \
    --exclude='usr/tmp' \
    --exclude='usr/var/cache/apt/archives' \
    --exclude='usr/var/log' \
    --exclude='usr/proc' \
    --exclude='usr/sys' \
    --exclude='usr/dev' \
    -czvf "$backup_file" \
    usr home/flash_tool home/.termux-adb 2>/dev/null; then
    ok "备份成功！恢复包已保存至：$backup_file"
  else
    err "备份失败，可能磁盘空间不足或权限问题。"
    rm -f "$backup_file"
  fi
}

# ============ 恢复环境 ============
perform_restore() {
  local restore_file="$1"
  if [ ! -f "$restore_file" ]; then
    err "恢复包不存在: $restore_file"
    return 1
  fi
  if [ ! -s "$restore_file" ]; then
    err "恢复包为空文件: $restore_file"
    return 1
  fi
  if ! check_storage_permission; then
    err "存储权限未授权，无法完成恢复。"
    return 1
  fi

  echo ""
  printf "${CYAN}${BOLD}开始从离线恢复包恢复环境${NC}\n"
  echo "─────────────────────────────────────"

  if check_running; then
    info "停止刷机工具..."
    do_stop
  fi

  info "正在解压恢复包...（可看到文件列表）"
  cd /data/data/com.termux/files || {
    err "无法进入 Termux 数据目录"
    return 1
  }

  if tar -xzvf "$restore_file" 2>/dev/null; then
    ok "恢复完成！"
    echo ""
    printf "${YELLOW}重要：${NC}请立即退出并重新打开 Termux 以使新环境生效。\n"
  else
    err "解压失败，请检查恢复包是否完整。"
    return 1
  fi
}

download_restore_package() {
  local url="$1"
  local dest="/storage/emulated/0/123456/offline_deps.tar.gz"

  info "正在下载离线恢复包..."
  mkdir -p "$(dirname "$dest")" 2>/dev/null

  if command -v curl &>/dev/null; then
    curl --progress-bar -L -o "$dest" "$url" && ok "下载完成" || { err "下载失败"; return 1; }
  elif command -v wget &>/dev/null; then
    wget --show-progress -O "$dest" "$url" && ok "下载完成" || { err "下载失败"; return 1; }
  else
    err "无可用下载工具"
    return 1
  fi

  perform_restore "$dest"
}

restore_from_local() {
  local local_tar="/storage/emulated/0/123456/offline_deps.tar.gz"
  if [ -f "$local_tar" ]; then
    perform_restore "$local_tar"
  else
    err "未在 /storage/emulated/0/123456/ 找到 offline_deps.tar.gz"
    return 1
  fi
}

offline_restore_menu() {
  echo ""
  printf "${CYAN}${BOLD}离线恢复包安装${NC}\n"
  echo "─────────────────────────────────────"
  printf "  ${GREEN}1)${NC} 从 OpenList 下载并恢复\n"
  printf "  ${GREEN}2)${NC} 从本地 /storage/emulated/0/123456/ 读取\n"
  printf "  ${GREEN}3)${NC} 输入自定义下载链接并恢复\n"
  printf "  ${YELLOW}0)${NC} 返回\n"
  echo "─────────────────────────────────────"
  read -p "请输入选项 [0-3]: " restore_choice
  case "$restore_choice" in
    1) download_restore_package "$OFFLINE_DEP_URL" ;;
    2) restore_from_local ;;
    3)
      read -p "请输入恢复包的直链地址（仅支持 .tar.gz）： " custom_url
      [ -n "$custom_url" ] && download_restore_package "$custom_url" || err "链接不能为空"
      ;;
    0) return ;;
    *) err "无效选项" ;;
  esac
}

# ============ 镜像源列表 ============
declare -A TERMUX_MIRRORS=(
  ["1"]="https://mirrors.tuna.tsinghua.edu.cn/termux/apt/termux-main|清华源"
  ["2"]="https://mirrors.ustc.edu.cn/termux/apt/termux-main|中科大源"
  ["3"]="https://mirrors.aliyun.com/termux/apt/termux-main|阿里云源"
  ["4"]="https://mirrors.bfsu.edu.cn/termux/apt/termux-main|北外源"
  ["5"]="https://mirrors.nju.edu.cn/termux/apt/termux-main|南京大学源"
  ["6"]="https://packages.termux.dev/apt/termux-main|官方源(国外)"
)

declare -A PIP_MIRRORS=(
  ["1"]="https://pypi.tuna.tsinghua.edu.cn/simple|清华PyPI"
  ["2"]="https://pypi.mirrors.ustc.edu.cn/simple|中科大PyPI"
  ["3"]="https://mirrors.aliyun.com/pypi/simple|阿里云PyPI"
  ["4"]="https://mirrors.bfsu.edu.cn/pypi/simple|北外PyPI"
  ["5"]="https://pypi.org/simple|官方PyPI(国外)"
)

select_and_set_termux_mirror() {
  echo ""
  printf "${CYAN}${BOLD}请选择 Termux 软件源：${NC}\n"
  echo "─────────────────────────────────────"
  for key in $(echo "${!TERMUX_MIRRORS[@]}" | tr ' ' '\n' | sort -n); do
    local val="${TERMUX_MIRRORS[$key]}"
    local url="${val%%|*}"
    local name="${val##*|}"
    printf "  ${GREEN}%s)${NC} %-20s %s\n" "$key" "$name" "$url"
  done
  echo "─────────────────────────────────────"
  local choice
  while true; do
    read -p "请输入选项 [1-6] (默认1): " choice
    choice="${choice:-1}"
    [ -n "${TERMUX_MIRRORS[$choice]}" ] && break
    printf "${RED}无效选项，请重新输入${NC}\n"
  done
  local val="${TERMUX_MIRRORS[$choice]}"
  local mirror_url="${val%%|*}"
  local mirror_name="${val##*|}"
  info "正在切换到 $mirror_name ..."
  cp "$PREFIX/etc/apt/sources.list" "$PREFIX/etc/apt/sources.list.bak" 2>/dev/null || true
  cat > "$PREFIX/etc/apt/sources.list" <<EOF
# $mirror_name (由一键脚本自动配置)
deb $mirror_url stable main
EOF
  ok "已切换到 $mirror_name"
}

select_pip_mirror() {
  echo ""
  printf "${CYAN}${BOLD}请选择 pip 镜像源：${NC}\n"
  echo "─────────────────────────────────────"
  for key in $(echo "${!PIP_MIRRORS[@]}" | tr ' ' '\n' | sort -n); do
    local val="${PIP_MIRRORS[$key]}"
    local url="${val%%|*}"
    local name="${val##*|}"
    printf "  ${GREEN}%s)${NC} %-20s %s\n" "$key" "$name" "$url"
  done
  echo "─────────────────────────────────────"
  local choice
  while true; do
    read -p "请输入选项 [1-5] (默认1): " choice
    choice="${choice:-1}"
    [ -n "${PIP_MIRRORS[$choice]}" ] && break
    printf "${RED}无效选项，请重新输入${NC}\n"
  done
  local val="${PIP_MIRRORS[$choice]}"
  PIP_MIRROR_URL="${val%%|*}"
  ok "将使用 ${val##*|}"
}

# ============ 部署（在线） ============
do_deploy() {
  banner
  echo ""
  printf "${CYAN}${BOLD}请选择安装方式：${NC}\n"
  echo "─────────────────────────────────────"
  printf "  ${GREEN}1)${NC} 换国内源 + 安装（推荐，速度快）\n"
  printf "  ${GREEN}2)${NC} 临时用国内源安装，装完恢复原源\n"
  printf "  ${GREEN}3)${NC} 不换源，直接用当前源（速度慢）\n"
  printf "  ${YELLOW}4)${NC} 从离线恢复包安装（本地/OpenList/自定义链接）\n"
  echo "─────────────────────────────────────"
  echo ""
  local src_choice=""
  while true; do
    read -p "请输入选项 [1-4] (默认1): " src_choice
    src_choice="${src_choice:-1}"
    case "$src_choice" in
      1|2|3|4) break ;;
      *) printf "${RED}无效选项，请重新输入${NC}\n" ;;
    esac
  done

  if [ "$src_choice" = "4" ]; then
    offline_restore_menu
    return
  fi

  local temp_mirror=0
  case "$src_choice" in
    1) select_and_set_termux_mirror ;;
    2) info "将临时使用国内源安装依赖，安装完成后恢复原源"; select_and_set_termux_mirror; temp_mirror=1 ;;
    3) info "跳过换源，使用当前源（下载可能较慢）" ;;
  esac

  info "更新系统软件包..."
  apt update -y || {
    warn "apt update 失败，尝试恢复源并重试..."
    [ -f "$PREFIX/etc/apt/sources.list.bak" ] && cp "$PREFIX/etc/apt/sources.list.bak" "$PREFIX/etc/apt/sources.list" && apt update -y || warn "apt update 仍然失败，继续尝试"
  }
  yes "" | DEBIAN_FRONTEND=noninteractive apt full-upgrade -y || warn "full-upgrade 失败，继续安装依赖（可忽略）"
  ok "系统更新完成"

  info "安装 Termux 依赖包..."
  local need_pkgs=""
  for pkg in python python-pip termux-api android-tools p7zip unrar unzip libusb; do
    if ! dpkg -s "$pkg" &>/dev/null; then
      need_pkgs="$need_pkgs $pkg"
    fi
  done
  if [ -n "$need_pkgs" ]; then
    info "需要安装:$need_pkgs"
    yes "" | DEBIAN_FRONTEND=noninteractive apt install -y --no-install-recommends $need_pkgs || {
      err "依赖安装失败！请检查网络后重试。"
      exit 1
    }
  else
    ok "所有依赖已安装，跳过"
  fi

  info "授权存储权限..."
  if [ -d "$HOME/storage/shared" ]; then
    ok "存储权限已授权"
  else
    info "正在请求存储权限，请在弹出的对话框中点击【允许】..."
    termux-setup-storage 2>/dev/null || warn "存储授权未完成，如无法访问文件请手动执行 termux-setup-storage"
    sleep 2
    if [ -d "$HOME/storage/shared" ]; then
      ok "存储权限授权成功"
    else
      warn "未检测到存储目录，继续安装"
    fi
  fi

  info "安装 Python 依赖..."
  select_pip_mirror
  yes "" | python -m pip install --upgrade pip --break-system-packages -i "$PIP_MIRROR_URL" || true
  yes "" | python -m pip install flask flask-socketio --break-system-packages --ignore-installed blinker -i "$PIP_MIRROR_URL" || {
    err "Python 依赖安装失败，请检查网络后重试。"
    exit 1
  }
  ok "Python 依赖安装完成"

  if [ "$temp_mirror" = "1" ] && [ -f "$PREFIX/etc/apt/sources.list.bak" ]; then
    info "恢复原有软件源..."
    cp "$PREFIX/etc/apt/sources.list.bak" "$PREFIX/etc/apt/sources.list"
    ok "已恢复原有软件源"
  fi

  info "下载项目文件..."
  mkdir -p "$WORK_DIR" "$INSTALL_DIR" "$HOME/storage/shared/123456/image"

  info "下载 fastboot 免root 二进制..."
  mkdir -p "$FASTBOOT_BIN_DIR"
  if [ -f "$FASTBOOT_BIN_FILE" ] && [ "$(stat -c%s "$FASTBOOT_BIN_FILE" 2>/dev/null)" -gt 1000 ]; then
    ok "fastboot 已存在，跳过下载"
  else
    if download_file "$FASTBOOT_BIN_URL" "$FASTBOOT_BIN_FILE" "fastboot 二进制"; then
      chmod +x "$FASTBOOT_BIN_FILE"
      ok "fastboot 二进制下载完成"
    else
      warn "fastboot 下载失败，启动时将自动重试"
    fi
  fi

  local zip_file="${WORK_DIR}/flash_tool.zip"
  if download_file "$REMOTE_ZIP" "$zip_file" "项目压缩包 (flash_tool.zip)"; then
    ok "项目压缩包下载完成"
  else
    err "项目压缩包下载失败！请检查 OpenList 地址是否正确：$REMOTE_ZIP"
    exit 1
  fi

  info "正在解压项目文件到 $INSTALL_DIR ..."
  if ! unzip -q -o "$zip_file" -d "$INSTALL_DIR"; then
    err "解压失败，请检查 zip 文件是否完整。"
    exit 1
  fi
  rm -f "$zip_file"

  if [ -d "$INSTALL_DIR/flash_tool" ] && [ ! -f "$INSTALL_DIR/app.py" ]; then
    info "检测到 zip 内包含顶层目录，正在调整结构..."
    mv "$INSTALL_DIR/flash_tool"/* "$INSTALL_DIR/"
    rmdir "$INSTALL_DIR/flash_tool"
  fi

  chmod +x "$APP_FILE"

  cat > "$RUN_FILE" <<'RUNNER'
#!/data/data/com.termux/files/usr/bin/bash
cd "$HOME/flash_tool"
python app.py "$@"
RUNNER
  chmod +x "$RUN_FILE"
  rm -rf "$WORK_DIR"
  ok "项目文件部署完成"

  echo ""
  if check_running; then
    info "检测到刷机工具正在运行，正在重启..."
    do_stop
    sleep 1
    do_start
  else
    info "正在启动刷机工具..."
    do_start
  fi
}

# ============ 静默检查更新（仅提示，不自动更新） ============
do_check_update_silent() {
  (
    set +e
    local local_ver=""
    local_ver=$(get_local_version)
    [ -z "$local_ver" ] && exit 0

    local remote_ver=""
    remote_ver=$(curl -sL --max-time 3 "$REMOTE_VERSION" 2>/dev/null | head -1)
    remote_ver="${remote_ver%%[[:space:]]*}"

    if [ -n "$remote_ver" ]; then
      _ver_gt() {
        local a b i
        a=$(echo "$1" | tr '.' ' ')
        b=$(echo "$2" | tr '.' ' ')
        for i in 1 2 3 4 5; do
          local va=$(echo "$a" | cut -d' ' -f$i 2>/dev/null)
          local vb=$(echo "$b" | cut -d' ' -f$i 2>/dev/null)
          va=${va:-0}; vb=${vb:-0}
          [ "$vb" -gt "$va" ] 2>/dev/null && return 0
          [ "$vb" -lt "$va" ] 2>/dev/null && return 1
        done
        return 1
      }
      if _ver_gt "$local_ver" "$remote_ver"; then
        printf "${YELLOW}╔════════════════════════════════════════════════════╗${NC}\n"
        printf "${YELLOW}║  发现新版本 v%s（当前 v%s）                      ${NC}\n" "$remote_ver" "$local_ver"
        printf "${YELLOW}║  请选择菜单 7 更新，或重新启动以自动更新。    ${NC}\n"
        printf "${YELLOW}╚════════════════════════════════════════════════════╝${NC}\n"
      else
        ok "已是最新版本 v${local_ver}"
      fi
    fi
  )
}

# ============ 主循环 ============
while true; do
  show_menu
  menu_choice=""
  read -p "  请输入选项 [0-8]: " menu_choice

  case "$menu_choice" in
    1) do_start ;;
    2) do_stop ;;
    3) do_restart ;;
    4) do_deploy ;;
    5) do_uninstall ;;
    6) do_grant_storage ;;
    7) do_check_update ;;
    8) do_backup ;;
    0) info "已退出"; exit 0 ;;
    *) err "无效选项，请重新输入" ;;
  esac

  echo ""
  read -p "  按回车键返回主菜单..." _
done