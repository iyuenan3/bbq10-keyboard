# CLAUDE.md · bbq10-keyboard

> 一把黑莓 Q10 键盘改装的 BBQ10 蓝牙/USB 键盘的折腾 + 开源项目。
> 真身:**bredhat 出品、lotlab 固件(TMK 风格)** 的 BBQ10。**不是 ZitaoTech/ZMK**(立项时的误判,已纠正,见 `docs/reverse-engineering.md`)。
> 项目核心 = 逆向这把没人记录过的键盘 + 开源 CLI `bbq10ctl`。

## 设备身份(本机实读)

- 厂商串 `bredhat`,VID `0x6666` / PID `0x8888`,USB Full-Speed(bredhat 把 USB 真实 VID `0x6666` 在配置里存成十进制数字 `6666`,数字位=十六进制位)。
- 固件:lotlab 的 TMK 风格固件,编译于 **2022-04-28**,`firmwareVer=E9FA8E68`,`funcTable=3334`,`hwVer=0`,8 层模型。
- 两个 HID 接口:① 标准 boot 键盘;② System Control + Consumer + Mouse(BB9900 触摸板)。
- 序列号:**不写进任何入库文件**(红线)。需要时实读:`ioreg -p IOUSB -l -w 0 | grep -A20 BBQ10` 看 `USB Serial Number`。
- 枚举命令同上(`system_profiler SPUSBDataType` 在 Apple Silicon 上对 USB 返回空,别用)。

## 改键体系(本机这台的真相)

- 官方工具 = bredhat 配置工具:.NET 本地 server(USB 桥) + 网页 UI。**2022 年停更**:仅 Intel、SSL 证书过期、在线/更新服务器全死、`localhost.lotlab.org` 域名仍解析到 127.0.0.1。
- 本项目自研 **`tools/bbq10ctl.py`**:绕开过期证书/代理/DNS,直连本地 server REST API(`https://127.0.0.1:5001/api/device/...`)读写键盘。已实测 list/info/dump/backup/restore/getkey/setkey 全通(P→F9→P 闭环)。
- keymap 编码已破解(`docs/reverse-engineering.md`):4096B,层步长 35,偏移 `(L*7+R)*5+C`;普通键=原始 HID 字节,复杂键=`0xC0-0xDF` 索引表,修饰键=`0xE0-0xE7`,`1`=穿透;macro 字节流高位 `0x80`=抬键。

## 当前状态(2026-06-20)

- 设备彻底逆向完成,已推 GitHub 公库 `github.com/iyuenan3/bbq10-keyboard`(无序列号)。
- **完整 codec** `tools/bbq10codec.py`:设备(keymap 4096B + fn 256B)↔16位码双向,**字节级 round-trip + parse/decode 全网格验证通过**。
- **`bbq10ctl` 全功能**:list/info/dump/backup/restore/getkey/setkey(**含复杂键**:符号/层/宏/媒体键,自动管 fn 表)/serve。实测复杂键写入闭环。
- **图形编辑器** `tools/editor.html` + `serve`:可视化点键改键,后端 API 端到端实测通过。
- 文档已全面纠正为 bredhat/CLI 现实;backups/ gitignore 不入公库。

## 下一步(待办)

1. 高级动作助记符(tap-mod/layer-modify/BT槽/RGB):位域已知,用官方 UI(127.0.0.1:5000)当真值机逐类对验实机行为(当前可用原始码 0xXXXX 设置)。
2. 出厂 `archive/keymaps/factory_原始.json`(工具 JSON 16位码格式)→设备二进制转换,支持 CLI 一键回厂。
3. v0.2:逆向键盘原始 USB HID 报文,CLI/编辑器直连键盘,去掉对 .NET server 的依赖。
4. (可选)开背盖确认主控;若 nRF52840 + bootloader,评估刷 ZMK。
5. 把新增工具(codec/editor/serve)commit + push。

## 红线

- **任何入库/对外内容不带设备序列号**。CLAUDE.md 初始 commit 曾含序列号 → 推公库前需 scrub git 历史或重开仓库。
- 改键前先备份:`bbq10ctl.py backup <file>`(setkey 会自动先备份)。出厂原始配置 = `archive/keymaps/factory_原始.json`(工具 JSON 格式;`archive/` 为厂商原始资料,gitignore 不入公库)。
- 写 keymap 不会刷砖(最坏键位错,重写即可);别碰固件本身。
- bredhat server 是 USB 桥,CLI 依赖它在跑:`cd ~/bbq10-bredhat-tool && ./bredhat`(需先装 Rosetta)。

## 与 worklog 的关系

本项目独立 git 仓库、独立 Claude session。worklog 侧:待加入扫描列表 + 建 `wiki/projects/bbq10-keyboard.md`(由 worklog session 维护)。
