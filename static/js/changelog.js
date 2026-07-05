// flash_tool/static/js/changelog.js
// 更新日志内容（从 index.html 提取，减少 HTML 体积）

const CHANGELOG_TEXT = `v3.8.0 (2026-07-05)
- 新增：纯 Python SH 脚本模拟执行器（ShSimulator），替代系统 shell 沙箱，完全脱离 Termux 依赖
- 新增：解析方式标识 —— 前端显示🔍沙箱(纯Python) 或 🔍静态提取
- 新增：SH/BAT 管线拆分 —— 每个 class 拥有独立管线副本可魔改（native/vendor/community 等）
- 新增：基类模板保护机制 —— ShPipeline/BatPipeline 直接实例化会报错提示
- 新增：脚本自动分类归档 —— ZS/sh/ 下按 class_id 建立子目录
- 修复：路径展开 —— fastboot 命令中的`dirname $0`/images/xxx.img 正确展开为真实路径
- 修复：沙箱模拟器支持单行 if 条件分支（`if cond; then cmd; fi`）
- 修复：多级 elif/else/fi 嵌套逻辑
- 优化：模拟器手动拆分 fastboot 参数（保留反引号路径为一个整体，不受 shlex 拆分干扰）

v3.4.3 (2026-07-02)
- 新增：独立「版本」页面（导航栏新增竖排版本按钮，宽度减半）
- 新增：版本页可折叠更新日志（当前版本默认展开）
- 修复：刷机包目录无法扫描的问题（清理残留的proot容器进程，释放端口冲突）
- 前端：导航栏从4项扩展为5项（设备→线刷→版本→工具→工作台）
- 优化：设备页移除版本/更新/更新日志区域，改为后端地址行
- 优化：服务器支持 --lan 参数监听 0.0.0.0（局域网访问）
- 优化：app.py 新增 /static/ 静态文件路由

v3.4.1 (2026-07-01)
- 新增：脚本上传功能（WebDAV→OpenList + 天树引擎预解析 + 安全扫描）
- 新增：底部悬浮「📤」上传按钮
- 前端：底部导航栏精简为 4 项
- 优化：去掉 flask-cors 依赖，使用原生 CORS headers

v3.4.0 (2026-07-01)
- 天树引擎：修复 SH 嵌套 for 循环 + if 条件后的命令被 AST 解析器忽略的问题
- 天树引擎：新增 $(cd ... && pwd) 子 shell 简化，修复 CURRENT_DIR 推导
- 天树引擎：新增 set /p 用户输入模拟，set /a 算术表达式标记
- 天树引擎：新增 call :label 位置参数 %1 %2 传递支持
- 天树引擎：新增预设 BAT 系统变量（%CD%/%DATE%/%TIME%等）
- 天树引擎：新增 for /F 静态列表提取支持
- 天树引擎：新增 && / || 链式命令拆分提取
- 天树引擎：新增 note 字段（devices/getvar/reboot 步骤说明）
- 天树引擎：修复 SH 未定义变量展开为空字符串
- 天树引擎：修复 SH 引用赋值中引号嵌套导致路径错误
- 天树引擎：修复 BAT if exist 文件不存在时返回 None 而非 False
- 天树引擎：修复通配符 for 缺镜像时分区名非法
- 天树引擎：修复 prefixParams 未正确映射到 params
- ROM 解析：SH 脚本与 BAT 脚本一视同仁，is_native_sh 根据 is_simple 动态决定
- ROM 解析：script_type 根据解析结果动态设置，不再硬编码为 'sh'
- 原生执行：force_rewrite_fastboot_paths 跳过赋值语句避免路径拼接错误
- 原生执行：inject_reconnect_wait 替换原始 TOOL_PATH 赋值，确保文件存在性检查通过
- 原生执行：inject_reconnect_wait 变量覆盖移到脚本末尾避免被原始赋值覆盖
- 原生执行：reboot_re 正则扩展匹配 $VAR/"$VAR" 形式的变量调用

v3.3.1 (2026-06-30)
- 天树引擎：修复 BAT if 条件变量展开判等逻辑（乱判断镜像类型）
- 天树引擎：修复 BAT 通配符 for 体内 call :label 内联展开后再解析的步骤丢失
- 天树引擎：新增 test_hydra.py 单元测试框架（32项测试用例，12个样本脚本）
- 天树引擎：修复 SH 循环体内 simple_flag 未重置，后续普通命令被误判为循环体

v3.2.2 (2026-06-27)
- 快捷操作改为双按钮切换：添加 Fastboot 快捷命令 / 添加 ADB 快捷命令
- 默认不展示按钮内容，点击展开对应分类，再点收起；点另一类自动切换
- 修复 loadProjectImages/renderProjectImageList 旧单刷 DOM 元素空引用报错

v3.2.1 (2026-06-27)
- 快捷操作重构为 Fastboot/ADB 两大分类，每个分类独立包含完整重启命令
- 快捷操作改名为「添加快捷操作」，默认收起，节省空间
- 重启按钮文案统一为「重启到XX」格式
- 修复快捷操作按钮点击无效果的问题（去掉模式判断，直接绑定工具类型）
- 修复线刷包列表加载失败（后端返回对象数组前端按字符串处理）
- 修复 fillSelect 空引用导致「加载镜像失败」错误
- 修复方案管理删除确认弹窗被方案面板遮挡
- install.sh 移除菜单入口前的更新检测（仅保留启动工具后检测）
- 所有 UI 文案中 BL 简写统一为完整 Bootloader 原名

v3.2.0 (2026-06-26)
- 工作台全面改造：方案管理面板（删除/列表）、按钮式步骤类型切换
- 镜像来源支持线刷包下拉选择+自定义路径，导出脚本使用相对路径
- 25+快捷操作按钮（按设备/刷写/分区/系统/高级/重启分类，风险颜色标注）
- 分区选择支持设备检测+自定义两种模式
- 重启命令区分 Bootloader/Fastbootd 两种模式
- 步骤列表增加人性化中文描述和风险标识
- 所有 UI 文案中 BL 简写统一为完整 Bootloader 原名

v3.1.0 (2026-06-26)
- 新增「工作台」页面：合并原单刷和命令页面，支持自定义步骤管理
- 支持三种步骤类型：刷机命令（表单式）、ADB命令、自定义Shell
- 8个快捷操作按钮（设备列表/全部变量/当前槽位/Bootloader状态等）
- 步骤支持上移/下移排序、单步执行、全部执行、模拟执行
- 导出 .sh 脚本功能：支持复制/下载/展开查看
- 方案保存/加载（localStorage）
- 后端新增 /api/shell/run_single 单条命令执行 API

v3.0.9 (2026-06-26)
- 复杂 BAT 脚本返回原脚本时自动注入注释提示（含免root fastboot路径和转换建议）
- install.sh 启动时改为前台更新检测，8秒倒计时，无网络不影响启动

v3.0.8 (2026-06-26)
- for 通配符展开增加大小写不敏感回退（兼容 Windows ROM 包在 Linux 下目录名大小写不匹配）
- call :label 子程序内联增加递归保护（防止循环调用导致步骤爆炸）

v3.0.7 (2026-06-26)
- BAT 解析引擎 v3：变量展开后语义判断，不再依赖原始文本匹配
- 支持 for /L 数值循环自动展开（如 for /L %%a in (1,1,3)）
- 支持 for /F 读取文本文件列表展开
- 支持 if 比较（equ/==/neq/lss/leq/gtr/geq）静态判断
- 支持 call :label 同文件子程序内联
- 支持 %~dp0 等路径修饰符、%var:old=new% 字符串替换、%var:~s,l% 切片
- 变量先展开再判断复杂度：含已定义变量的 for/if 不再被误判为复杂脚本
- install.sh 启动后后台静默检查更新，有新版本时提示，离线不受影响

v3.0.6 (2026-06-26)
- BAT 解析引擎重构 v2：严格白名单判定，只放行简单 for 循环（字面量/通配符）和简单 if exist（无变量无 else）
- 简单 for 循环（如 for %%i in (*.img) do ...）现在自动展开为步骤列表，不再判定为复杂脚本
- 简单 if exist（路径无变量、无 else）现在静态判断文件存在性，自动解析条件分支
- 引号-aware 括号匹配，修复路径含括号时解析错误
- 复杂脚本原因具体化：前端显示具体拦截原因（如"goto 跳转"、"for /f"等）
- 新增缺失文件检测：通配符展开失败时提醒用户，弹窗确认测试/刷机模式

v3.0.5 (2026-06-26)
- BAT 解析器重构为子命令锚点匹配：不再依赖变量名，只要行中出现 flash/erase/reboot 等子命令即可识别
- 支持嵌套变量多轮展开（如 set A=%B%; set B=fastboot）
- 扩展 fastboot 子命令支持：boot、unlock、lock、continue、getvar、devices
- 线刷输出写入独立区域，不再挤占通用日志
- 通用日志上限从 500 行提升到 2000 行

v3.0.4 (2026-06-25)
- 新增 fastboot 二进制路径强制兼容方案：路径预处理替换 + Bash 函数覆盖 + 软链接
- 无论用户脚本写 fastboot、$FASTBOOT、$TOOL_PATH 还是硬编码系统路径，最终都使用项目内置二进制
- 补充 adb 路径替换和 BAT 残留 %变量% 路径替换
- 修复模拟执行时注入函数内部行不在日志中刷屏
- 前端原生 .sh / 复杂脚本区域显示环境兼容提示

v3.0.3 (2026-06-25)
- 修复原生 .sh 和复杂 BAT 模式下模拟刷入按钮未启用的问题
- 修复模拟执行时 flash 命令 format 字符串参数不匹配导致的 IndexError 崩溃

v3.0.2 (2026-06-25)
- 所有脚本类型（简单 BAT / 复杂 BAT / 原生 .sh）统一支持模拟刷入按钮
- 模拟执行通过 dry_run 模式运行，完整展示命令序列和重启等待流程
- 简单脚本模拟时自动将步骤列表转换为 .sh 格式后执行
- 复杂脚本和原生 .sh 脚本直接模拟用户输入的脚本内容

v3.0.1 (2026-06-25)
- 脚本执行改为注入等待函数方案：在脚本中的 reboot bootloader/fastboot 命令后自动插入重连等待代码
- 整个脚本作为单一 bash 进程执行，变量和函数完全保留，无需分段
- 等待函数通过 $FASTBOOT devices 检测设备，最多等待 180 秒，支持 USB/OTG 授权弹窗提示
- 支持原生 .sh 脚本直接预览执行，无需手动转换
- 复杂 BAT 脚本提供原源码查看和复制功能

v3.0.0 (2026-06-25)
- 重构线刷脚本解析引擎：移除复杂脚本自动转换为 .sh 的逻辑
- 复杂脚本（含循环/条件/子脚本调用等）改为展示手动输入框，由用户自行转换为 .sh 格式后输入
- 复杂脚本不再有步骤管理，直接执行用户手动输入的 .sh 脚本
- 简单 BAT 脚本解析流程保持不变

v2.2.8 (2026-06-25)
- 修复 ADB 设备无法连接：添加 _detect_adb() 自动检测 adb 路径
- 修复 install.sh 部署时自动下载 adb 二进制
- 修复导出日志 404：前端 API 路径与后端不匹配

v2.2.8 (2026-06-25)
- 修复全局后处理 if/then 双重嵌套 bug
- 修复 run_step 描述未自动生成（$FASTBOOT 被引号包裹导致正则不匹配）
- 修复 reboot 后 __wait_for_device 注入失败（改为匹配命令而非描述）
- 修复复杂脚本步骤列表删除按钮未隐藏（选择器 class 不匹配）

v2.2.6 (2026-06-25)
- 修复转换引擎全局后处理：所有修复规则改为对输出脚本做统一替换（不再依赖逐行 handler）
- 修复 TOOL_PATH/fastboot.exe 未替换为 $FASTBOOT
- 修复 \${TOOL_PATH} 引用未替换
- 修复 if [ ! -f "$FASTBOOT" ] 文件检测改为 command -v
- 修复 fastboot devices 退出码判断改为 grep
- 修复 \${p}_a-cow 变量拼接改为 \${p}_a_cow
- 修复 >/dev/null 2 重定向改为 2>/dev/null || true
- 修复 name="\${f%.*}" 改为 basename 提取
- 修复 run_step 描述自动生成（不再写死 "fastboot fastboot"）
- 修复 reboot 后自动注入 __wait_for_device 等待重连

v2.2.5 (2026-06-25)
- 修复简单脚本导入解包失败（返回值元组数量不一致）
- 移除转换统计卡片和警告列表（避免干扰基础脚本解析）
- 确保简单脚本和复杂脚本两套解析方案完全独立

v2.2.4 (2026-06-25)
- 转换引擎参考豆包方案全面优化
- 统一预处理过滤列表（setlocal/chcp/color/cls/title/pause/timeout）
- 新增转换警告列表（残留 %变量%、.exe、反斜杠路径等）
- 新增转换统计信息（刷写/擦除/重启/条件/循环数量）
- 新增环境前置检测（fastboot 命令可用性）
- 新增最终自检（残留 Windows 语法检测）
- 前端展示转换统计卡片和警告列表

v2.2.3 (2026-06-25)
- 新增转换后 Shell 脚本的复制按钮
- 修复 clear 清屏命令破坏前端日志连续性
- 修复 fastboot.exe 存在性检测（改为 command -v fastboot）
- 修复 fastboot devices 退出码判断（改为 grep 检测设备）
- 修复 setlocal enabledelayedexpansion 未过滤
- 修复 $SCRIPT_DIR 未定义（改为 $__SCRIPT_DIR）
- 修复 TOOL_PATH 未替换为 $FASTBOOT
- 修复 2>nul 未转换为 2>/dev/null
- 修复 \${f%.*} 路径问题（改为 basename）
- 修复循环变量拼接 $p_a → \${p}_a
- 修复 pause 转为 read 在真实执行时卡住
- 注入变量加 __ 前缀避免与原厂脚本冲突
- reboot 后自动注入 __wait_for_device 等待重连
- 断点续刷：reboot 后设备重连才标记进度

v2.2.1 (2026-06-25)
- 移除专用 adb 二进制下载，改用系统 pkg install android-tools
- 设备重连等待时间从 90 秒增加到 180 秒（适配慢设备进 Fastboot）
- 复杂脚本识别改为纯语法特征判定（不再按行数）
- 新增 for /f /r /d、else 块、标签定义的复杂脚本识别
- 新增 if not / if == 等比较条件的复杂脚本识别

v2.0.2 (2026-06-24)
- UI 全面重构为 iOS 设计风格
- 毛玻璃效果：底部导航、状态栏、弹窗使用 backdrop-filter
- iOS 系统色：蓝#0a84ff 绿#30d158 橙#ff9f0a 红#ff453a 紫#bf5af2
- 圆润组件：按钮12px、弹窗16px、导航24px 圆角
- iOS 触控标准：按钮最小44px高度
- 按压缩放效果：scale(0.97) 替代 translateY
- 输入框聚焦环：蓝色 box-shadow 光晕
- 模块状态改为左侧色条样式
- 去除硬边框，改用柔和阴影营造层次感
- SF Pro 字体渲染优化

v2.0.1 (2026-06-24)
- 配置项集中管理：超时时间、轮询间隔等 11 个常量统一到 config 模块
- 错误消息统一：新增 api_ok/api_err 辅助函数，统一响应格式
- 重复 import 清理：删除 35 行重复的 import 语句
- 刷机包自动识别：解压后自动检测类型（小米/高通/MTK/通用）
- WebSocket 进度推送：解压和刷机进度实时通过 WS 推送
- confirm() 全部替换为 showConfirm 非阻塞弹窗
- 刷机前电量检查：低于 20% 显示警告
- XSS 修复：escHtml 转义所有 innerHTML 中的用户数据
- 操作历史持久化：刷机记录保存到 JSON，支持查看历史
- API 响应格式统一：msg/error 字段规范化
- 全局变量双向同步：Object.defineProperty 替代 let 别名
- 事件委托：底部导航改为容器级事件委托
- 刷机流程简化：解压后自动选中、解析后自动检测设备
- 前端错误诊断增强：调用后端 18 种规则替代本地 5 种
- ModuleTask 抽象类：统一状态/进度/确认/双模式/错误处理
- 前端 toast 提示：替代 alert 阻塞弹窗

v2.0.0 (2026-06-24)
- 代码审计：修复 request.get_json() 未校验 None（18处）
- 代码审计：日志区域上限 500 条，防止内存泄漏
- 代码审计：清理死代码、修复重复文案
- 全局变量封装到 App 对象，集中管理应用状态
- extractFastbootVar 正则修复，正确匹配 fastboot 输出
- init() 初始化改为并行加载，加快启动速度
- renderSteps 使用 DocumentFragment 减少 DOM 重排
- alert() 全部替换为非阻塞 toast 提示
- 脚本解析公共逻辑抽取，消除重复代码
- 版本号统一从 app.py 读取，单一来源管理

v1.4.1 (2026-06-24)
- 线刷包管理优化：添加操作流程说明、列表头计数、当前项目高亮
- 多包列表自适应高度，支持滚动浏览
- 新增「清空全部」按钮，一键删除所有解压包
- 修复列表滚动失效问题

v1.4.0 (2026-06-24)
- 脚本解析器重写：支持 if exist 条件块、for 循环展开、变量追踪
- COW 动态清理：运行时查询存在的分区，跳过不存在的
- 错误诊断增强：新增空间不足、只读分区、槽位不存在等 7 条规则
- 结构化日志导出：支持导出完整刷机日志为 txt 文件
- 步骤标签：禁用AVB、COW动态清理、条件执行、循环展开
- 脚本类型检测：EDL/MTK/QFIL 等非 fastboot 脚本明确提示
- 解析按钮改为「解析脚本」，移至选择脚本右侧

v1.3.9 (2026-06-23)
- 新增解析线刷脚本功能（支持 BAT/SH 格式）
- 支持小米、高通、MTK 等多种刷机脚本格式

v1.3.6 (2026-06-21)
- 移除线刷前 Bootloader 锁检测（各手机检测方式不同，容易误判）
- 后端线刷任务轮询间隔从 2 秒改为 1 秒
- 等待设备重连检测间隔从 3 秒改为 1 秒

v1.3.5 (2026-06-21)
- 启动时自动下载免root fastboot二进制到 ~/.termux-adb/fastboot
- 线刷页面说明根据刷机包数量自动展开/收起

v1.3.3 (2026-06-21)
- 移除内置 fastboot/adb 二进制依赖，完全使用系统 android-tools 提供的命令

- 内置 adb 二进制更新（PI 可执行版本，4.9MB）
- 线刷页面说明根据刷机包数量自动展开/收起（无刷机包时展开说明，有刷机包时收起）

v1.2.6 (2026-06-21)
- 修复确认弹窗在浏览器小窗模式下无法点击的问题（弹窗内容过长时超出视口）
- 弹窗modal-box增加max-height:80vh限制，内容区域可滚动，按钮始终可见
- 优化重启步骤弹窗逻辑：脚本最后一步是重启且前面无其它重启时不再弹窗提示

v1.2.5 (2026-06-21)
- 默认主题根据北京时间自动判断（07:00-22:00白天模式，其余夜间模式），手动切换后记忆
- 双清操作新增「擦除metadata」按钮，支持擦除metadata分区（解决加密状态异常等问题）
- 擦除metadata支持WebUSB和后端双模式，分区不存在时自动忽略

v1.2.4 (2026-06-21)
- 选用按钮改为与删除按钮同大小同UI效果（绿色pick-btn样式）
- 立即刷写按钮改为蓝色背景
- 单刷页面说明精简为2条
- VBmeta校验状态badge移到标题右侧（类似Bootloader锁状态），检测状态按钮在badge左侧

v1.2.3 (2026-06-21)
- 镜像管理列表选用和删除按钮互换，选用按钮改为绿色背景
- 选用镜像时智能处理来源切换（刷机包模式选用手机目录镜像时自动切换来源）
- VBmeta校验状态改为按钮触发+内联badge显示，位于关闭校验按钮右侧
- VBmeta检测状态按钮需Fastboot设备在线才可用

v1.2.1 (2026-06-21)
- 单刷页面重构：分区名、镜像来源、附加参数分行显示，布局更清晰
- 单刷页面镜像管理新增「选用」按钮，选用后自动同步到镜像选择下拉框
- 单刷页面说明文案优化，详细说明各来源使用方式
- VBmeta校验状态自动检测：检测到 Fastboot 设备后自动查询并内联显示校验状态
- VBmeta校验状态显示：已去除/未去除/已去除部分（具体去除了哪部分）/未知
- 统一后端模式和WebUSB模式的单刷镜像选择逻辑，移除本地上传功能
- 修复多处JS语法错误（单引号字符串跨行、Python转义等）

v1.0.1 (2026-06-20)
- 单刷页面后端模式支持从已解压刷机包选择镜像
- 关闭VBmeta校验改为单分区（去除AB双分区）
- Bootloader锁管理状态文本优化
- 脚本解析兼容性增强（%VAR%清理、if exist支持等）
- 脚本风险检测增强（刷Bootloader/Modem/上锁等）
- 版本检测与在线更新功能

v1.0.0 (2026-06-20)
- 初始版本发布
- 支持后端模式线刷、单分区刷写
- 支持 WebUSB 模式直连
- 支持小米/高通/MTK 线刷脚本解析
- 支持 VBmeta 校验关闭、Bootloader 锁管理
- 支持断点续刷、自动重连`;

// 解析更新日志为结构化版本列表
function parseChangelog(text) {
    const versions = [];
    const lines = text.split('\n');
    let current = null;
    for (const line of lines) {
        const m = line.match(/^(v[\d.]+) \((\d{4}-\d{2}-\d{2})\)$/);
        if (m) {
            current = { version: m[1], date: m[2], lines: [] };
            versions.push(current);
        } else if (current) {
            current.lines.push(line);
        }
    }
    return versions;
}

// 可折叠版本日志渲染
function renderChangelog(containerId, currentVersion) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const versions = parseChangelog(CHANGELOG_TEXT);
    let html = '';
    for (const ver of versions) {
        const isCurrent = ver.version === 'v' + currentVersion;
        const bodyId = 'ver-body-' + ver.version.replace(/\./g, '-');
        const isOpen = isCurrent;
        html += '<div class="ver-item' + (isCurrent ? ' ver-current' : '') + '">';
        html += '<div class="ver-header" onclick="toggleVerBody(\'' + bodyId + '\')">';
        html += '<span>' + escHtml(ver.version) + ' <span style="font-weight:400;color:var(--text-muted);font-size:12px">' + escHtml(ver.date) + '</span></span>';
        if (isCurrent) html += '<span style="font-size:10px;color:var(--accent-green);font-weight:400;margin-right:6px">当前</span>';
        html += '<span class="ver-arrow' + (isOpen ? ' open' : '') + '">▸</span>';
        html += '</div>';
        html += '<div class="ver-body' + (isOpen ? ' open' : '') + '" id="' + bodyId + '">';
        html += ver.lines.join('\n');
        html += '</div></div>';
    }
    container.innerHTML = html;
}

function toggleVerBody(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.toggle('open');
    const header = el.previousElementSibling;
    if (header) {
        const arrow = header.querySelector('.ver-arrow');
        if (arrow) arrow.classList.toggle('open');
    }
}