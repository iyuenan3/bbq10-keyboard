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

然后用本项目 CLI(纯 Python 标准库,无需安装依赖):

```bash
python3 tools/bbq10ctl.py list                       # 列出键盘
python3 tools/bbq10ctl.py dump                       # 打印当前 keymap(人类可读)
python3 tools/bbq10ctl.py backup my-config.json      # 备份 keymap+macro
python3 tools/bbq10ctl.py setkey 0 3 1 F9            # 把 层0/行3/列1 改成 F9(自动先备份)
python3 tools/bbq10ctl.py restore my-config.json     # 还原
```

键位坐标 `L 层(0-7) R 行(0-6) C 列(0-4)`,偏移 `(L*7+R)*5+C`(扫描矩阵序,见逆向文档)。
`setkey` 目前支持普通键 / 修饰键 / 穿透;复杂键(Shift+符号、层切换、宏)在路线图。

## 仓库结构

```
bbq10-keyboard/
├── README.md                       公开说明(本文件)
├── tools/bbq10ctl.py               核心:命令行配置工具
├── docs/
│   ├── reverse-engineering.md      逆向笔记(身份 / 协议 / 格式)
│   └── runbook.md                  操作手册(启动 / 改键 / 备份还原 / 排错)
├── CLAUDE.md / PRD.md              开发上下文(可忽略)
└── backups/                        个人备份(gitignore,含设备序列号不入库)
```

## 路线图

- 复杂键(符号/层切换/宏)的 JSON↔设备二进制编解码 → `setkey` 全键支持。
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
