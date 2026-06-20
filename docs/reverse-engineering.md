# BBQ10 (bredhat / lotlab firmware) 逆向笔记

把一把市面常见、却几乎没有公开技术资料的 **bredhat BBQ10**(黑莓 Q10 键盘 + BB9900 触摸板改装件)彻底摸清:USB 身份、官方工具架构、本地 REST API、keymap 二进制格式与编码。官方配置工具 2022 年已停更(仅 Intel、证书过期、服务器全死),本文档让这把键盘**脱离官方工具**也能完全掌控。

> 立项时曾误判为 ZitaoTech/ZMK 路线。实证(随机附带的 bredhat 工具 + JSON + 实读 USB)推翻了它,见下文。

## 1. 设备身份(USB)

`ioreg -p IOUSB -l -w 0 | grep -A20 BBQ10` 实读:

| 项 | 值 |
|---|---|
| Product / Vendor 串 | `BBQ10` / `bredhat` |
| VID / PID | `0x6666` / `0x8888` |
| bcdUSB / 速率 | 0x0110 / Full-Speed |
| HID 接口 ① | 标准 boot 键盘 |
| HID 接口 ② | System Control + Consumer + Mouse(BB9900 触摸板) |

固件信息(经下文 REST API 读出):`firmwareVer=E9FA8E68`,`buildDate=1651120925`(2022-04-28),`funcTable=3334`,`hwVer=0`。

> 判定关键:厂商串 `bredhat` 与随机附带的「bredhat 键盘配置工具」同名;工具说明里写明 **TMK 固件**、8 层、穿透/无 按键;配置是 **JSON**(非 ZMK 的设备树)。开发方域名 `lotlab.org`、临时目录 `lkb-configurator-server` 指向作者 lotlab。

## 2. 官方工具架构(及其为何不能直接用)

- 组成:**.NET 本地 server(USB 桥,x86_64)** + **Vue 网页 UI**。server 同时在 `:5000`(http)和 `:5001`(https)服务网页 + REST API。
- 网页与 server 走加密通道 `https://localhost.lotlab.org:5001`(该公网域名 DNS 解析到 `127.0.0.1`,配一张发给它的证书)。
- **三个致命问题**(2026 年):
  1. server 二进制仅 x86_64 → Apple Silicon 要 Rosetta。
  2. 证书 `CN=localhost.lotlab.org` 有效期 2021-01~**2022-01,已过期** → 浏览器 `ERR_CERT_DATE_INVALID` 拒连,网页报「配置工具没有响应」退回模拟设备。
  3. 公网域名经系统代理(如 Clash 全局)被劫持 → `ERR_CONNECTION_CLOSED`。

**绕过办法(本项目采用)**:跳过网页,直接打 server 的本地 REST API,连 `127.0.0.1:5001`(raw socket 不过代理、不依赖 DNS),忽略证书:

```bash
curl -ks --resolve localhost.lotlab.org:5001:127.0.0.1 https://localhost.lotlab.org:5001/api/device
# 或直连 IP(更干净): bbq10ctl.py 用 http.client 连 127.0.0.1:5001 + 不校验证书
```

## 3. 本地 REST API

基址 `https://127.0.0.1:5001`(忽略证书):

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/device` | 列出已连键盘(数组) |
| GET | `/api/device/{id}` | 设备信息(id=序列号, vid, pid, hwVer, buildDate, firmwareVer, funcTable) |
| GET | `/api/device/{id}/keymap` | 读 keymap(base64 二进制) |
| POST | `/api/device/{id}/keymap` | 写 keymap(body=JSON 字符串的 base64;立即生效) |
| GET | `/api/device/{id}/macro` | 读宏(base64 二进制) |
| POST | `/api/device/{id}/macro` | 写宏 |

注:`PUT` 返回 405,写入用 `POST`。settings(休眠时间等)无 REST 读端点。`{id}` = 设备序列号字符串。

> bredhat 在 JSON/接口里把 USB 真实 VID `0x6666` 存成十进制 `6666`(数字位当十六进制位),展示时按字面位还原成 `0x6666`。

## 4. keymap 二进制格式

base64 解码后 **4096 字节**:

- **布局**:8 层 × 7 行 × 5 列,packed,层步长 35。`偏移(L,R,C) = (L*7 + R)*5 + C`。前 280 字节有效,其后 `0xFF` 填充。
- **每键 1 字节**,取值含义:

| 字节 | 含义 |
|---|---|
| `0x00` | 无(未用) |
| `0x01` | 穿透(▽透,查更低层) |
| `0x04`~`~0xA4` | 标准 HID Keyboard/Keypad usage(字母/数字/符号键/F键/方向/Enter/Bksp…),原始值 |
| `0xC0`~`0xDF` | **复杂键索引**:指向一张去重表,按首次出现顺序编号。表项=带修饰的键(如 Shift+3=`#`)、层切换、宏触发等 |
| `0xE0`~`0xE7` | 修饰键 LCtrl/LShift/LAlt/LGUI/RCtrl/RShift/RAlt/RGUI |

- **行列 = 扫描矩阵序**,非视觉布局。本机 layer0 解码:`Q E R U O / W S G H L / Caps D T Y I / A P [复杂] Enter Bksp / [复杂] X V B [复杂] / Space Z C N M / LGUI LShift F J K`。

## 5. 工具 JSON 导出格式(与设备二进制不同的另一套编码)

官方「保存/导出」得到的 `.json`(`{"Data":{"Keys":[8][7][5], "Macros":[...], "Settings":[...]}, "VID":6666, "PID":8888}`)用 **16 位码**,与设备 1 字节码经 `funcTable` 互转:

- 普通键:同 HID usage。
- **修饰+键**:`0xMMKK`,高字节 MM=HID 修饰位掩码(`0x02`=LShift…),低字节 KK=HID 键码。例:`#`=`0x0220`(LShift+`3`)、`(`=`0x0226`(LShift+`9`)。已对官方说明 PDF 符号层逐键验证。
- 层操作:`0xA?xx`;宏:`0xC0xx`;蓝牙槽/内置:`0xF0xx`/`0xF2xx`(语义部分推测)。

> 即:设备端用「索引表」省空间,JSON 端用「自描述 16 位码」。`bbq10ctl` 的 backup/restore 直接搬运设备二进制,与编码无关、绝对可靠;setkey 目前只直写普通键/修饰键/穿透(复杂键需重建索引表,见路线图)。

## 6. 宏格式

base64 解码后为事件字节流:每个事件 1 字节 HID 键码,**高位 `0x80` = 抬键**(否则按下),`0x00` 填充。本机原厂宏 = `h e l l o w o r l d Enter`(打 `helloworld` + 回车)。

## 7. 复现 / 工具

- 启动 USB 桥:装 Rosetta(`softwareupdate --install-rosetta`)→ `cd ~/bbq10-bredhat-tool && ./bredhat`。
- 读写:`tools/bbq10ctl.py`(纯 Python 标准库)。`backup`/`restore`/`dump`/`getkey`/`setkey`。
- 路线图 v0.2:逆向键盘原始 USB HID 报文协议,让 CLI 直连键盘、彻底去掉对 .NET server 的依赖。
