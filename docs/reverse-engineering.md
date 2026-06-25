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
| GET | `/api/device/{id}/fn` | 读 fn 表(base64,256B,复杂键 16 位码表) |
| POST | `/api/device/{id}/fn` | 写 fn 表(写复杂键须与 keymap 两段同步) |

注:`PUT` 返回 405,写入用 `POST`。settings(休眠时间等)无 REST 读端点。`{id}` = 设备序列号字符串。直连 `http://127.0.0.1:5000` 即可(纯 http,无需证书/lotlab 域名/resolve;前端也走这条同源相对路径)。

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

### 4.1 fn 表(复杂键)与 funcTable

- **复杂键**(修饰+键、层切换、宏、Consumer/System、BT/RGB)= 字节 `0xC0-0xDF`(32 个可寻址槽),槽号 = 字节 `- 0xC0`,指向 **fn 表**里的一个 16 位 LE 码。
- **fn 表 = 256 字节**(128 槽,首 32 可寻址,空槽 `0xFFFF`)。它**同时**:① 内嵌在 keymap blob 尾部 `keymap[3840:4096]`(`4096-256=3840`);② 经独立端点 `/api/device/{id}/fn` 暴露。两者内容一致。写复杂键须 keymap 与 fn 两段同步,否则索引悬空。
- fn 表构建 = **去重 + 首现顺序**:按扫描序遍历所有键,凡 16 位码 >0xFF 的复杂键 `indexOf` 命中则复用槽,否则追加(满 32 报错),keymap 该格写 `0xC0+槽号`。确定性映射。
- **funcTable**(本机 `3334=0xD06`)= 固件能力位掩码,非映射表版本号:`0x2`=MouseKey、`0x400`=Macro、`0x200`=Actionmap(合并 vs 拆分存储)。`0xD06` → MouseKey on / Macro on / **Actionmap off**(故走 keymap+fn 两段拆分存储;若某固件 Actionmap on 则走单段合并 `/actionmap`,编码偏移不同,需先判此位)。

## 5. 工具 JSON 导出格式(与设备二进制不同的另一套编码)

官方「保存/导出」得到的 `.json`(`{"Data":{"Keys":[8][7][5], "Macros":[...], "Settings":[...]}, "VID":6666, "PID":8888}`)用 **16 位码**,与设备 1 字节码经 `funcTable` 互转:

- 普通键:同 HID usage。
- **修饰+键**:`0xMMKK`,高字节 MM=HID 修饰位掩码(`0x02`=LShift…),低字节 KK=HID 键码。例:`#`=`0x0220`(LShift+`3`)、`(`=`0x0226`(LShift+`9`)。已对官方说明 PDF 符号层逐键验证。
16 位码按**高 nibble** 分类(已在 `tools/bbq10codec.py` 实现完整 decode,并对实机做过**字节级 round-trip 验证**):

| 高nibble | 类别 | 解码 |
|---|---|---|
| `0x0`/`0x1` | 修饰+键(`0x1`=右修饰标记) | `mod=(c>>8)&0xf`(LCtrl1/LShift2/LAlt4/LGUI8),`key=c&0xff` |
| `0x2`/`0x3` | 修饰-tap(`0x3`=右手) | `0x2000\|(mod<<8)\|低`;低=0 单发,1 粘滞,其它=修饰或键(MT)。见 §5.2 |
| `0x4` | System/Consumer | `sub=(c>>10)&3`:0=System,1=Consumer;`x=c&0x3ff` |
| `0x5` | MouseKey | `c&0x7ff` |
| `0x8` | 层位运算(关/开/反转TG/仅开TO) | `0x8000\|(事件<<10)\|(时序<<8)\|((层//4)<<5)\|(1<<层%4)`。见 §5.2 |
| `0xA`/`0xB` | 层-tap(层号 0-based) | `layer=(c>>8)&0x1f`;低 `0xF1`=开关层(MO按住),`C0-DF`=切层+修饰(LM),其它有效HID=切层或键(LT)。见 §5.2 |
| `0xC` | 宏 | `c&0xff`=宏号 |
| `0xF` | InternalFunc(内置功能:睡眠/USB/电量/蓝牙槽/RGB) | `id=c&0xff`,`opt=(c>>8)&0xf`;查 FunctionList,见 §5.1。已验证 |

另有单字节别名:设备字节 `0xA5-0xA7`=System(`0x81+n`),`0xA8-0xBE`=Consumer(查 `CONSUMER_LUT`,23 项媒体键 usage)。

> `bbq10ctl` 的 backup/restore 直接搬运设备二进制,与编码无关、绝对可靠。复杂键的完整编解码(含去重建表)已在 `bbq10codec.py` 复现并验证,可脱离厂商工具读写符号/层/宏。

### 5.1 InternalFunc(高位 `0xF` 内置功能)

逆向来源 = **官方工具 `app.js` 自己的编码/解码函数 + 内嵌 FunctionList 表**(它写这些码,故为 ground truth;并用 Node 实跑 round-trip 验证):

- **编码**(`app.js` idx 262305):`code = 0xF000 + ((0xf & opt) << 8) + (0xff & id)`,即 `code = 0xF000 | ((opt&0xF)<<8) | (id&0xFF)`。
- **解码**(idx ~392981):`id = code & 0xff`,`opt = (code>>8) & 0xf`,`class = (code>>12) & 0xf`;`class==0xF` 派发 `InternalFunc(id, opt)`。`ActionType` 枚举 `InternalFunc=0x15`(= TMK `ACT_FUNCTION`,kind `0b1111`)。
- **标签** = 在 FunctionList 里按 `(id,opt)` 查;查不到回退 `功能<id>:<opt>` / `Func <id>:<opt>`。

`id` = 功能族,`opt` = 族内变体。基础表 `ab3e`(4 项)+ 每键盘 `Profile.AdditionFns`(本机 28 项)拼接:

| code | id,opt | 名 | 含义(官方原文) |
|---|---|---|---|
| `0xF000` | 0,0 | SLEEP | 使键盘进入睡眠状态 |
| `0xF100` | 0,1 | NKRO | 启用/禁用全键无冲 |
| `0xF200` | 0,2 | BATT | 打印当前键盘的电量 |
| `0xF001` | 1,0 | USB | 启用/禁用 USB 设备(蓝牙板上=在 USB 与当前蓝牙主机间切换输出) |
| `0xF801` | 1,8 | BT1 | 蓝牙通道一 |
| `0xF901` | 1,9 | BT2 | 蓝牙通道二 |
| `0xFA01` | 1,10 | BT3 | 蓝牙通道三 |
| `0xFB01` | 1,11 | BTBC | 重新蓝牙广播 |
| `0xF701` | 1,7 | BTUNBIND | 解除蓝牙绑定 |

另有 `id=16`(特殊组合键)、`id=17/18`(RGB/WS2812 灯),标签随机型而异,暂留原始码。`0xF000/0xF001/0xF200` 实见于出厂第 3 层(与方向键/媒体键同层)。已在 `bbq10codec.py` 的 `INTFN` 表实现 decode/parse,`bbq10ctl` 与编辑器(「系统/蓝牙」分类)可直接按名设置。

> 保留项:`0xF001` 在蓝牙下的操作细节(切回 USB vs 开关 USB)未上手按键实测,码的身份(id=1 设备切换,opt=0 USB)确定无疑。

### 5.2 层操作 + tap-hold(类 `0x8` / `0xA` / `0x2`)

逆向自 app.js 的编码器/解码器,用 **3 个出厂实证码当锚点**(`0x8902`=反转层1、`0xA3F1`=开关层3、`0xA2C2`=层2+LShift)encode/decode 双向验证,见 `tools/bbq10codec.py`。**层号一律 0-based**(官方手册的「第 N 层」= 0-based 的 N-1)。

**类 `0x8` 层位运算**:`code = 0x8000 | (事件<<10) | (时序<<8) | ((层//4)<<5) | (1<<层%4)`。
- 事件(LayerEvent):`0`=关闭(LOFF)、`1`=开启(LON)、`2`=反转/toggle(**TG**,点按锁定)、`3`=仅开启/其他全关(**TO**)。
- 层号拆成 `p3=层//4`(bit7-5)+ `p4=1<<层%4`(bit4-0);解码 `层=p3*4+log2(p4)`。
- 时序(bit9-8)= 触发边沿(按下/抬起),不影响开关语义;出厂反转层用 `1`,codec 固定用 `1`。
- 锚点 `0x8902` = 事件2(反转) 时序1 层1 → **TG(1)**。

**类 `0xA` 层-tap**:`code = 0xA000 | (层<<8) | 低字节`,`层=(c>>8)&0x1f`。
- 低 `0xF1` = **开关层 MO**(按住进层、松开退,**不是 toggle**;用户实测证实)。`0xF0/0xF2/0xF3` 为 on-off/关开/强制的 momentary 变体。
- 低 `0xC0..0xDF` = **切层和修饰 LM**:`mod=低&0xf`(Ctrl1/Shift2/Alt4/GUI8),`set 标志=低&0x10`。锚点 `0xA2C2` = 层2 + LShift。
- 低为有效 HID 键(`0x04-0xA4` / `0xE0-0xE7`)= **切层或按键 LT**:按住=进层,点按=该键(点按在抬起时触发)。
- 锚点 `0xA3F1` = 层3 开关层 → **MO(3)**。

**类 `0x2`/`0x3` 修饰-tap**(`0x3`=右手):`code = 0x2000 | (mod<<8) | 低字节`。
- 低 `0x00` = **单发修饰 OSM**(按一下= 该修饰键按下+抬起)。
- 低 `0x01` = **粘滞修饰 SM**(Windows 粘滞键逻辑)。
- 其它有效 HID = **修饰或按键 MT**(按住=修饰键、点按=该键)。例 `0x2129` = 按住 LCtrl / 点按 Esc。MT 可在键少时一键兼修饰键,补足缺的 Ctrl 等。

> 助记符(`bbq10ctl`/编辑器):`MO(n) TG(n) TO(n) LON(n) LOFF(n)`、`LT(n,键)`、`LM(n,修饰)`、`MT(修饰,键)`、`OSM(修饰)`、`SM(修饰)`,均 0-based、已字节级 round-trip 验证。

## 6. 宏格式

base64 解码后为事件字节流:每个事件 1 字节 HID 键码,**高位 `0x80` = 抬键**(否则按下),`0x00` 填充。本机原厂宏 = `h e l l o w o r l d Enter`(打 `helloworld` + 回车)。

## 7. 复现 / 工具

- 启动 USB 桥:装 Rosetta(`softwareupdate --install-rosetta`)→ `cd ~/bbq10-bredhat-tool && ./bredhat`。
- 读写:`tools/bbq10ctl.py`(纯 Python 标准库)。`backup`/`restore`/`dump`/`getkey`/`setkey`。
- 路线图 v0.2:逆向键盘原始 USB HID 报文协议,让 CLI 直连键盘、彻底去掉对 .NET server 的依赖。
