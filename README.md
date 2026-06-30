# Flash Tool - Termux 网页刷机工具

一站式安卓刷机工具，支持 BAT/SH 刷机脚本解析执行。

## 目录结构

```
flash-tool/
├── app.py                 # Flask 后端入口
├── config.py              # 配置文件
├── run.sh                 # 一键启动脚本
├── requirements.txt       # Python 依赖
├── core/                  # 核心引擎
│   ├── hydra/             # Hydra 脚本解析执行引擎
│   ├── batch_flasher.py   # 步骤级刷机
│   ├── device.py          # 设备管理
│   └── ...
├── routes/                # API 路由
├── static/                # 前端页面 ← GitHub Pages 部署目录
│   ├── index.html
│   ├── css/
│   └── js/
├── hydra_samples/         # 测试脚本样本
└── hydra_tests/           # 单元测试
```

## 快速开始

```bash
bash run.sh
```

然后浏览器访问 http://手机IP:5000

## GitHub Pages

前端已部署到：https://1248331222.github.io/flash-tool/
需要手机后端运行后才能使用。
