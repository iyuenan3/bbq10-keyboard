#!/usr/bin/env python3
"""
bbq10ctl — BBQ10 (bredhat / lotlab firmware) 键盘配置命令行工具

这把键盘是 bredhat 出品、lotlab 固件(TMK 风格)的黑莓 Q10 改装键盘,
官方只有一个 2022 年停更、仅 Intel、证书已过期的 GUI(.NET 本地 server + 网页)。
本工具直接走该 server 的本地 REST API,绕开过期证书 / DNS / 系统代理:
直连 https://127.0.0.1:5001,忽略证书,raw socket 不过代理。

前置:bredhat 本地 server 必须在跑(它是 USB 桥)。见 README「启动 server」。
  Apple Silicon: 装 Rosetta 后  cd <tooldir> && ./bredhat
路线图 v0.2:直接走 USB HID,彻底去掉对该 server 的依赖。

支持的操作:
  list                          列出已连接键盘
  info [ID]                     设备详情
  dump [ID]                     打印当前 keymap(人类可读)
  backup <file> [ID]            备份 keymap + macro 到 JSON(可还原)
  restore <file> [ID]           从备份还原
  getkey L R C [ID]             读单键
  setkey L R C <KEY> [ID]       写单键(自动先备份;仅普通键/修饰键/穿透)

KEY 可用:键名(如 A 9 F9 ENTER LSHIFT TRANS)或数字 HID 码。
键位 L=层(0-7) R=行(0-6) C=列(0-4);偏移 = (L*7+R)*5+C。

红线:复杂键(Shift+符号、层切换、宏)存为索引表,v0.1 不支持直写,setkey 会拒绝。
"""
import sys, ssl, json, base64, http.client, os, time

HOST_IP, PORT, SNI = "127.0.0.1", 5001, "localhost.lotlab.org"
NLAYERS, NROWS, NCOLS = 8, 7, 5
USED = NLAYERS * NROWS * NCOLS  # 280

# ---- HID usage 键码表(name <-> code),含本固件可直写区 ----
_K = {0: "NONE", 1: "TRANS", 40: "ENTER", 41: "ESC", 42: "BKSP", 43: "TAB",
      44: "SPACE", 45: "-", 46: "=", 47: "[", 48: "]", 49: "\\", 51: ";",
      52: "'", 53: "`", 54: ",", 55: ".", 56: "/", 57: "CAPS",
      74: "INS", 75: "PGUP", 76: "DEL", 77: "END", 78: "PGDN",
      79: "RIGHT", 80: "LEFT", 81: "DOWN", 82: "UP", 83: "NUMLK", 85: "KP*",
      224: "LCTRL", 225: "LSHIFT", 226: "LALT", 227: "LGUI",
      228: "RCTRL", 229: "RSHIFT", 230: "RALT", 231: "RGUI"}
for i in range(4, 30):  _K[i] = chr(ord('A') + i - 4)          # 4..29 A..Z
for i, c in zip(range(30, 40), "1234567890"): _K[i] = c        # 30..39 1..0
for i in range(58, 70): _K[i] = f"F{i-57}"                     # 58..69 F1..F12
NAME2CODE = {v.upper(): k for k, v in _K.items()}

# 可安全直写的码:穿透 + 标准键(<192) + 修饰键(224-231)。192-223 是复杂键索引,拒写。
def is_direct_writable(code):
    return code == 1 or (4 <= code < 192) or (224 <= code <= 231)

def keyname(code):
    if code in _K: return _K[code]
    if 192 <= code <= 223: return f"CPLX#{code-192}"   # 复杂键(符号/层/宏)索引
    return f"0x{code:02X}"

def parse_key(s):
    s = s.strip()
    if s.upper() in NAME2CODE: return NAME2CODE[s.upper()]
    try:
        return int(s, 0)
    except ValueError:
        sys.exit(f"无法识别的键: {s}(用键名如 A/F9/ENTER/LSHIFT/TRANS 或数字)")

# ---- REST ----
def _conn():
    ctx = ssl._create_unverified_context()
    return http.client.HTTPSConnection(HOST_IP, PORT, context=ctx, timeout=8)

def _req(method, path, body=None):
    c = _conn()
    headers = {"Host": SNI}
    if body is not None:
        body = json.dumps(body); headers["Content-Type"] = "application/json"
    try:
        c.request(method, path, body=body, headers=headers)
        r = c.getresponse(); data = r.read().decode("utf-8", "replace")
        if r.status >= 400:
            sys.exit(f"HTTP {r.status} {method} {path}\n{data[:200]}\n"
                     f"(server 没在跑? 先启动 bredhat 本地 server)")
        return json.loads(data) if data.strip() else None
    except ConnectionError:
        sys.exit("连不上 127.0.0.1:5001 — bredhat 本地 server 没在跑。先启动它。")
    finally:
        c.close()

def devices():            return _req("GET", "/api/device") or []
def get_keymap(i):        return bytearray(base64.b64decode(_req("GET", f"/api/device/{i}/keymap")))
def set_keymap(i, raw):   return _req("POST", f"/api/device/{i}/keymap", base64.b64encode(bytes(raw)).decode())
def get_macro(i):         return _req("GET", f"/api/device/{i}/macro")
def set_macro(i, b64):    return _req("POST", f"/api/device/{i}/macro", b64)

def pick_id(args, n=0):
    if len(args) > n: return args[n]
    d = devices()
    if not d: sys.exit("没找到键盘(server 在跑吗?USB 连着吗?)")
    return d[0]["id"]

def offset(L, R, C): return (L * NROWS + R) * NCOLS + C

# ---- 命令 ----
def cmd_list(_):
    d = devices()
    if not d: print("(无设备)"); return
    for x in d:
        bd = time.strftime("%Y-%m-%d", time.localtime(x.get("buildDate", 0)))
        # bredhat 把真实 USB VID 0x6666 存成十进制数字 6666(数字位=十六进制位),原样当 hex 位显示
        print(f'{x["id"]}  VID=0x{x["vid"]:04d} PID=0x{x["pid"]:04d} '
              f'hwVer={x["hwVer"]} fw={x.get("firmwareVer")} 固件日期={bd}')

def cmd_info(a):
    i = pick_id(a)
    print(json.dumps(_req("GET", f"/api/device/{i}"), ensure_ascii=False, indent=2))

def cmd_dump(a):
    i = pick_id(a); raw = get_keymap(i)
    for L in range(NLAYERS):
        cells = [raw[offset(L, R, C)] for R in range(NROWS) for C in range(NCOLS)]
        if set(cells) <= {0, 1}: continue
        print(f"-- 层{L} (行×列, 偏移 {offset(L,0,0)}..{offset(L,NROWS-1,NCOLS-1)}) --")
        for R in range(NROWS):
            print("  " + " | ".join(f"{keyname(raw[offset(L,R,C)]):>7}" for C in range(NCOLS)))

def cmd_backup(a):
    if not a: sys.exit("用法: backup <file> [ID]")
    f = a[0]; i = pick_id(a, 1)
    dev = _req("GET", f"/api/device/{i}")
    obj = {"_tool": "bbq10ctl", "_ts": int(time.time()), "device": dev,
           "keymap_b64": base64.b64encode(bytes(get_keymap(i))).decode(),
           "macro_b64": get_macro(i)}
    json.dump(obj, open(f, "w"), ensure_ascii=False, indent=2)
    print(f"已备份 keymap+macro 到 {f}")

def cmd_restore(a):
    if not a: sys.exit("用法: restore <file> [ID]")
    f = a[0]; obj = json.load(open(f)); i = pick_id(a, 1)
    set_keymap(i, base64.b64decode(obj["keymap_b64"]))
    if obj.get("macro_b64"): set_macro(i, obj["macro_b64"])
    print(f"已从 {f} 还原 keymap+macro 到设备 {i}")

def cmd_getkey(a):
    if len(a) < 3: sys.exit("用法: getkey L R C [ID]")
    L, R, C = int(a[0]), int(a[1]), int(a[2]); i = pick_id(a, 3)
    code = get_keymap(i)[offset(L, R, C)]
    print(f"层{L} 行{R} 列{C} (偏移{offset(L,R,C)}) = {code} ({keyname(code)})")

def cmd_setkey(a):
    if len(a) < 4: sys.exit("用法: setkey L R C <KEY> [ID]")
    L, R, C = int(a[0]), int(a[1]), int(a[2]); code = parse_key(a[3]); i = pick_id(a, 4)
    if not is_direct_writable(code):
        sys.exit(f"拒绝: {keyname(code)}({code}) 不是可直写的键。"
                 f"复杂键(符号/层切换/宏)需索引表,v0.1 不支持。")
    raw = get_keymap(i); o = offset(L, R, C); old = raw[o]
    # 自动安全备份
    bdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backups")
    os.makedirs(bdir, exist_ok=True)
    bf = os.path.join(bdir, f"auto-{i}-{int(time.time())}.json")
    cmd_backup([bf, i])
    raw[o] = code; set_keymap(i, raw)
    if get_keymap(i)[o] != code: sys.exit("写入校验失败!")
    print(f"层{L} 行{R} 列{C}: {keyname(old)} -> {keyname(code)}  ✓ (备份在 {bf})")

CMDS = {"list": cmd_list, "info": cmd_info, "dump": cmd_dump, "backup": cmd_backup,
        "restore": cmd_restore, "getkey": cmd_getkey, "setkey": cmd_setkey}

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        print(__doc__); print("命令:", " ".join(CMDS)); sys.exit(0 if len(sys.argv) < 2 else 1)
    CMDS[sys.argv[1]](sys.argv[2:])

if __name__ == "__main__":
    main()
