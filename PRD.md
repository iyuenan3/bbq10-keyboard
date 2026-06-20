# PRD · bbq10-keyboard

## 背景

无意间得到一把黑莓 Q10 键盘改装的 BBQ10 键盘(USB-C + 蓝牙双模,带 BB9900 触摸板)。

立项时按惯例误判为「ZitaoTech + ZMK」路线。逆向后纠正:真身是 **bredhat 出品、lotlab 固件(TMK 风格)** 的 BBQ10,VID/PID `0x6666`/`0x8888`,固件编译于 2022-04。官方配置工具(.NET 本地 server + 网页)已停更:仅 Intel、SSL 证书过期、服务器全死。这把键盘市面常见却几乎无公开技术资料,值得逆向 + 开源。

## 目标

1. **辨识 + 上手**:实读 USB 身份与固件信息,摸清三层布局、符号层、蓝牙多设备、触摸板,在 macOS 当日常键盘用。
2. **自定义 keymap(不依赖官方 GUI)**:逆向官方本地 REST API 与 keymap 二进制格式,做一个跨平台命令行工具 `bbq10ctl`(备份/还原/改键),绕开过期证书/代理/Rosetta 限制。
3. **开源发布**:把硬件辨识 + 协议/格式逆向 + `bbq10ctl` 作为开源项目发布到 GitHub(项目本身开源,非单篇 guide)。

## 范围

### 包含
- 硬件辨识与本机实读数据(VID/PID/HID 结构/固件信息)。
- 官方工具架构剖析 + 本地 REST API + keymap/macro 二进制格式与编码(逆向文档)。
- `bbq10ctl`:list/info/dump/backup/restore/getkey/setkey。
- 备份/还原/排错流程。

### 暂不包含
- 重新设计硬件/PCB。
- 给所有 BBQ10 变体做通用兼容(先聚焦本机这台 bredhat/lotlab)。
- 替换固件(刷 ZMK 等)——列为可选 v0.2,需先开盖确认主控。

## 交付物

- 开源 GitHub 仓库:README(中英)+ `docs/reverse-engineering.md` + `docs/runbook.md` + `tools/bbq10ctl.py` + LICENSE。
- 一套可备份/还原/改键的命令行流程,实测可用。

## 验收

- `bbq10ctl list` 列出真键盘;`dump` 输出可读 keymap。
- `setkey` 改一个键即时生效,`restore` 可一键还原(已实测 P→F9→P 闭环)。
- 仓库可被他人 clone,按 README 跑通(给定 USB 桥在跑)。
- 对外内容不含设备序列号。

## 风险 / 待定

- 复杂键(符号/层切换/宏)编解码未补全,setkey 暂只支持普通键。
- CLI 仍依赖官方 .NET server 作 USB 桥(v0.2 拟直连 HID 去依赖)。
- 推公库前需 scrub git 历史中的序列号(初始 commit 含)。
