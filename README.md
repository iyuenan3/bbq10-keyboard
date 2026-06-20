# BBQ10 Keyboard (bredhat / lotlab firmware) 逆向 + 开源工具

把一把市面常见、却几乎没有公开技术资料的 **bredhat BBQ10**(黑莓 Q10 原装 QWERTY 键盘 + BB9900 触摸板改装件,USB-C + 蓝牙双模)彻底玩明白:辨识硬件、摸清本地配置协议、用一个不依赖官方工具的命令行工具 **`bbq10ctl`** 备份 / 还原 / 改键。

> 官方「bredhat 配置工具」2022 年已停更:仅 Intel、SSL 证书过期、在线/更新服务器全死。本项目逆向出它的本地 REST API 与 keymap 二进制格式,让这把键盘**脱离官方工具也能完全掌控**。

## 这是什么设备

- 厂商串 `bredhat`,VID `0x6666` / PID `0x8888`,USB Full-Speed。
- **lotlab 的 TMK 风格固件**(8 层),非 ZitaoTech/ZMK。
- 两个 HID 接口:① 标准键盘;② System Control + Consumer + Mouse(BB9900 触摸板)。

完整逆向(USB 身份、官方工具架构、REST API、keymap 二进制格式与编码、宏格式)见 **[`docs/reverse-engineering.md`](docs/reverse-engineering.md)**。

## 快速上手

前置:官方本地 server 作为 USB 桥需在跑。

```bash
# 1) Apple Silicon 装 Rosetta(Intel Mac 跳过)
softwareupdate --install-rosetta --agree-to-license
# 2) 启动 bredhat 本地 server(USB 桥)
cd ~/bbq10-bredhat-tool && ./bredhat        # 保持此窗口
```

然后用本项目工具(纯 Python 标准库,无需安装依赖):

### 图形界面(推荐)

```bash
python3 tools/bbq10ctl.py serve          # 起本地编辑器
# 浏览器打开 http://127.0.0.1:8770
```

可视化 7×5 键盘 × 8 层,点一个键 → 选行为(普通键 / 修饰+键 / 层操作 / 媒体键 / 宏 / 原始码)→ 应用,即时写入键盘。顶部「备份 / 还原」按钮。纯本地 http,无证书/代理/DNS 坑。

### 命令行

```bash
python3 tools/bbq10ctl.py list                  # 列出键盘
python3 tools/bbq10ctl.py dump                  # 打印当前 keymap(复杂键已解码)
python3 tools/bbq10ctl.py backup my.json        # 备份 keymap+fn+macro
python3 tools/bbq10ctl.py setkey 0 3 1 F9       # 普通键
python3 tools/bbq10ctl.py setkey 1 0 0 LShift+3 # 符号(复杂键,自动入 fn 表)
python3 tools/bbq10ctl.py setkey 0 4 0 MO(2)    # 层操作
python3 tools/bbq10ctl.py setkey 0 6 0 VOLUP    # 媒体键
python3 tools/bbq10ctl.py restore my.json       # 还原
```

坐标 `L 层(0-7) R 行(0-6) C 列(0-4)`。**复杂键(符号/层切换/宏/媒体键)全支持**,自动管理 fn 索引表(全键盘上限 32 种);高级动作可用原始码 `0xA2F1` 兜底。每次写入自动先备份 + 回读校验。编解码见 `tools/bbq10codec.py`(设备↔16位码,已字节级验证)。

## 仓库结构

```
bbq10-keyboard/
├── README.md                       公开说明(本文件)
├── tools/
│   ├── bbq10ctl.py                 CLI + 编辑器 server(list/dump/backup/restore/setkey/serve)
│   ├── bbq10codec.py               编解码库(设备 keymap+fn ↔ 16位码,字节级验证)
│   └── editor.html                 可视化网页编辑器(serve 托管)
├── docs/
│   ├── reverse-engineering.md      逆向笔记(身份 / 协议 / 格式)
│   └── runbook.md                  操作手册(启动 / 改键 / 备份还原 / 排错)
├── CLAUDE.md / PRD.md              开发上下文(可忽略)
└── backups/                        个人备份(gitignore,含设备序列号不入库)
```

## 路线图

- ✅ 复杂键(符号/层切换/宏/媒体键)编解码 + 图形编辑器(已完成)。
- 高级动作(tap-mod / layer-modify / BT 槽 / RGB)的助记符:位域已知,待用官方 UI 当真值机逐类对验实机行为(当前可用原始码设置)。
- 直连键盘原始 USB HID,**去掉对官方 .NET server 的依赖**(原生、免 Rosetta)。
- (可选)开背盖确认主控;若 nRF52840 则评估刷开源 ZMK。

## 安全

- keymap 写入不会刷砖(最坏键位错,重写即可);本工具不触碰固件本身。
- 改键前务必 `backup`(`setkey` 会自动先备份)。

## 致谢 / 声明

硬件与官方固件 © bredhat;固件框架 lotlab(TMK 风格)。本项目仅为互操作目的逆向其**本地配置接口**,不含任何官方固件或工具的代码/二进制,纯属个人折腾与学习。

---

### English (short)

`bbq10ctl` is a dependency-free Python CLI to back up / restore / remap a **bredhat BBQ10** keyboard (BlackBerry Q10 keys + BB9900 trackpad, lotlab TMK-style firmware). The vendor's config tool is abandonware (Intel-only, expired TLS cert, dead servers); this project reverse-engineers its **local REST API** (`https://127.0.0.1:5001/api/device/...`) and the **keymap binary format** so you can fully control the keyboard without it. Full teardown in [`docs/reverse-engineering.md`](docs/reverse-engineering.md). Requires the vendor's local server running as a USB bridge (Rosetta on Apple Silicon). Roadmap: direct USB-HID to drop that dependency.
