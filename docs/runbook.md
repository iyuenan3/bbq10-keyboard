# BBQ10 (bredhat / lotlab) Runbook:启动 / 改键 / 备份还原 / 排错

本机硬件 = **bredhat BBQ10**,lotlab TMK 风格固件,VID/PID `0x6666`/`0x8888`。改键走 **官方本地 server REST API + 本项目 `bbq10ctl`**(非 ZMK/ZMK Studio,那是立项误判)。设备身份与协议逆向见 [`reverse-engineering.md`](reverse-engineering.md)。

> 序列号等唯一标识不写入对外内容;需要时 `ioreg -p IOUSB -l -w 0 | grep -A20 BBQ10` 实读。

---

## Step 1 — 启动 USB 桥(官方本地 server)

CLI 通过官方 .NET 本地 server 读写键盘,该 server 必须在跑。

```bash
# Apple Silicon 先装 Rosetta(Intel Mac 跳过)
softwareupdate --install-rosetta --agree-to-license
# 工具从官方 .dmg 拷到可写目录并去隔离属性(首次):
#   hdiutil attach <BBQ10改键工具.dmg>; cp -R /Volumes/bredhat改键工具/. ~/bbq10-bredhat-tool/
#   xattr -dr com.apple.quarantine ~/bbq10-bredhat-tool
cd ~/bbq10-bredhat-tool && ./bredhat          # 保持窗口开着;它是 USB 桥
```

server 起来后会在 `127.0.0.1:5000`(http)/`:5001`(https)服务。**不要用浏览器开网页**(证书 2022 过期 + 公网域名被代理劫持,连不上)——直接用下面的 CLI。

验证连通:
```bash
python3 tools/bbq10ctl.py list
# 0136...  VID=0x6666 PID=0x8888 hwVer=0 fw=E9FA8E68 固件日期=2022-04-28
```

---

## Step 2 — 正常用起来(macOS)

- **USB-C 直连**:即插即用,Apple 通用 HID 驱动接管,无需装驱动。
- **蓝牙**:装电池 → 拨电源 → 进配对(顶排大按钮 + 双击触摸板)→ Mac 蓝牙设置连;顶排大按钮切多设备槽。
- **三层布局(默认,官方说明)**:L0 字母;L1(按 SYM/Alt)数字+符号;更高层方向/媒体/蓝牙。`bbq10ctl dump` 可打印实际映射。

---

## Step 3 — 改键 / 备份 / 还原

### 图形界面(推荐)
```bash
python3 tools/bbq10ctl.py serve          # 默认端口 8770
# 浏览器开 http://127.0.0.1:8770:点键选行为应用,顶部备份/还原
```

### 命令行
```bash
python3 tools/bbq10ctl.py dump                    # 看当前 keymap(复杂键已解码)
python3 tools/bbq10ctl.py backup my.json          # 备份 keymap+fn+macro
python3 tools/bbq10ctl.py getkey 0 3 1            # 读 层0行3列1
python3 tools/bbq10ctl.py setkey 0 3 1 F9         # 普通键(自动先备份到 backups/)
python3 tools/bbq10ctl.py setkey 1 0 0 LShift+3   # 符号/复杂键(自动入 fn 表)
python3 tools/bbq10ctl.py setkey 0 4 0 MO(2)      # 层操作;媒体键 VOLUP;原始码 0xA2F1
python3 tools/bbq10ctl.py restore my.json         # 还原
```

- 坐标:`L 层(0-7) R 行(0-6) C 列(0-4)`,偏移 `(L*7+R)*5+C`,扫描矩阵序。
- 复杂键(符号/层/宏/媒体键)全支持,自动管理 fn 索引表(上限 32 种);高级动作用原始码兜底。
- 出厂原始配置(工具 JSON 格式)= `archive/keymaps/factory_原始.json`,可用官方工具「打开→保存并应用」回厂。`archive/` 含厂商原始资料(工具 .dmg/.exe、官方 PDF、出厂/改版 keymap),gitignore 不入公库。

### macOS 功能键(F 区)映射速查

把 Mac 顶排功能映射到本键盘(编辑器「媒体 / Mac」分类一点即设,或 `setkey`)。结论经实证核验(Consumer = TMK `0x4400|usage`;10 位 usage 如 `0x2A0` 写成 `0x46XX`):

| Mac 功能 | 设成 | 说明 / 坑 |
|---|---|---|
| 音量 − / + / 静音 | `VOLDN` `VOLUP` `MUTE` | Consumer 媒体键,稳 |
| 播放暂停 / 上一首 / 下一首 | `PLAYPAUSE` `PREV` `NEXT` | 稳;长按 PREV/NEXT = 曲内快退/进 |
| 屏幕亮度 − / + | `BRIGHTDN` `BRIGHTUP` | 仅**内置屏 / macOS 能原生调亮度的外接屏**生效;普通外接显示器需装 MonitorControl/Lunar(走 DDC) |
| 聚焦搜索 Spotlight | `LGUI+SPACE` | = ⌘Space 系统默认,最稳 |
| 调度中心 Mission Control | `LCtrl+UP` | = Control+↑ 系统默认 |
| 启动台 Launchpad | `0x46A0` | Consumer `0x2A0`;无默认组合;macOS Tahoe 26 起 Launchpad 被取代,新系统可能失效 |
| 语音输入 / 听写 | `LCtrl+LALT+D` | 先在「系统设置 > 键盘 > 听写 > 快捷键 > 自定」按下 Ctrl+Option+D,再映此键(无默认文本组合) |
| 专注 / 勿扰 | `LCtrl+LALT+F` | 用「快捷指令.app」建勿扰快捷指令、在其信息面板加全局热键 Ctrl+Option+F,再映此键 |
| 键盘背光 − / + | 不可经 macOS 实现 | Apple 走 vendor usage,标准 Consumer `0x79/0x7A` 不被 honor;第三方键盘背光归固件自身管 |

---

## Step 4 — 深挖(可选)

- **直连 HID(v0.2)**:逆向键盘原始 USB HID 报文,CLI 直接读写键盘,去掉对 .NET server 的依赖。
- **换固件(可选)**:开背盖看主控丝印 + 试 bootloader(复位孔/U 盘名)。若 nRF52840 且有 bootloader,可评估刷 ZMK 换取完全开放固件——但会丢 bredhat 的蓝牙/触摸板适配,谨慎。

---

## 验证 / 排错

1. **连不上**(`bbq10ctl` 报 HTTP/连接错):确认 `./bredhat` 在跑;`curl -ks https://127.0.0.1:5001/api/device` 应返回设备数组。
2. **list 为空**:USB 线/口换一个;`ioreg ... | grep BBQ10` 确认枚举到。
3. **改键不生效**:`getkey` 复读确认写入;部分改动需重新 `setkey`/`restore`。
4. **回滚**:`restore <备份>`;或官方工具加载 `_原始.json` 保存并应用。

## 红线 / 风险

- 改键前先 backup(setkey 自动做)。
- 对外内容不带序列号;推公库前 scrub 历史。
- 写 keymap 不刷砖;不碰固件本身。
