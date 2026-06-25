#!/usr/bin/env python3
"""
bbq10codec — BBQ10 (bredhat/lotlab) keymap 编解码库

设备分两段存储(funcTable=0xD06: MouseKey on / Macro on / Actionmap off):
  keymap 4096B(1字节/键,offset=(L*7+R)*5+C,前280有效,余 0xFF)
  fn     256B (32 槽 ×16位LE码,空槽 0xFFFF),独立端点 /api/device/{id}/fn

单字节键义:
  0x00 无 | 0x01 穿透 | 0x04-0xA4 标准 HID | 0xA5-0xA7 System(0x81+n)
  0xA8-0xBE Consumer(查 CONSUMER_LUT) | 0xC0-0xDF fn 索引(槽=b-0xC0) | 0xE0-0xE7 修饰键

16 位码(>0xFF,存于 fn 表)按高 nibble 分类,见 decode_code/encode_code。
逆向来源与字节级 round-trip 验证见 docs/reverse-engineering.md。
"""
import re

NLAYERS, NROWS, NCOLS = 8, 7, 5
USED = NLAYERS * NROWS * NCOLS            # 280
FN_CAP = 32                               # 可寻址索引 0xC0..0xDF
FN_REGION = 256                           # fn 表字节数(128 槽,首 32 可寻址)
FN_OFFSET = 4096 - FN_REGION              # 3840:fn 表内嵌在 keymap 尾部

# ---- HID usage 名表 ----
HID = {0: "NONE", 1: "TRANS", 40: "ENTER", 41: "ESC", 42: "BKSP", 43: "TAB",
       44: "SPACE", 45: "-", 46: "=", 47: "[", 48: "]", 49: "\\", 51: ";",
       52: "'", 53: "`", 54: ",", 55: ".", 56: "/", 57: "CAPS",
       74: "INS", 75: "PGUP", 76: "DEL", 77: "END", 78: "PGDN",
       79: "RIGHT", 80: "LEFT", 81: "DOWN", 82: "UP", 83: "NUMLK", 85: "KP*"}
for i in range(4, 30): HID[i] = chr(ord('A') + i - 4)
for i, c in zip(range(30, 40), "1234567890"): HID[i] = c
for i in range(58, 70): HID[i] = f"F{i-57}"
MODBIT = {0x01: "LCtrl", 0x02: "LShift", 0x04: "LAlt", 0x08: "LGUI"}
MODKEY = {224: "LCtrl", 225: "LShift", 226: "LAlt", 227: "LGUI",
          228: "RCtrl", 229: "RShift", 230: "RAlt", 231: "RGUI"}
# Consumer LUT:设备单字节 0xA8+i <-> 16位码 0x4400|usage(从 app.js 提取)
CONSUMER_LUT = [0xe2, 0xe9, 0xea, 0xb5, 0xb6, 0xb3, 0xb4, 0xb7, 0xcd, 0xcc,
                0x183, 0x18a, 0x192, 0x194, 0x221, 0x223, 0x224, 0x225, 0x226,
                0x227, 0x22a, 0x6f, 0x70]
CONSUMER_NAME = {0xe2: "MUTE", 0xe9: "VOLUP", 0xea: "VOLDN", 0xb5: "NEXT",
                 0xb6: "PREV", 0xb3: "FFWD", 0xb4: "RWND", 0xb7: "STOP",
                 0xcd: "PLAYPAUSE", 0xcc: "STOPEJECT",
                 0x6f: "BRIGHTUP", 0x70: "BRIGHTDN"}      # 显示亮度+/-(Consumer 0x6F/0x70)
# InternalFunc(高位 0xF):code = 0xF000 | ((opt&0xF)<<8) | (id&0xFF)。名表/语义出自官方工具
# app.js 的 FunctionList(逆向已验,见 docs/reverse-engineering.md §5.1)。id=功能族(0 键盘控制,
# 1 输出/设备切换),opt=族内变体。0xF001 在蓝牙板上 = 在 USB 与当前蓝牙主机间切换输出。
INTFN = {0xF000: "SLEEP", 0xF100: "NKRO", 0xF200: "BATT", 0xF001: "USB",
         0xF801: "BT1", 0xF901: "BT2", 0xFA01: "BT3", 0xFB01: "BTBC", 0xF701: "BTUNBIND"}


def mods_label(mod):
    return "+".join(n for b, n in MODBIT.items() if mod & b)


def decode_code(code):
    """16位码(或单字节义)-> 人类可读标签。faithful,未知给 hex。"""
    if code <= 0xFF:
        b = code
        if b in HID: return HID[b]
        if b in MODKEY: return MODKEY[b]
        if 0xA5 <= b <= 0xA7: return f"SYS(0x{0x81+(b-0xA5):02X})"
        if 0xA8 <= b <= 0xBE:
            u = CONSUMER_LUT[b - 0xA8]
            return CONSUMER_NAME.get(u, f"CONS(0x{u:X})")
        return f"0x{b:02X}"
    cls = (code >> 12) & 0xF
    lo = code & 0xFF
    if cls == 0x0:                                         # 修饰+键(已验证,可读且可 parse)
        mod = (code >> 8) & 0xF
        key = HID.get(lo)
        if key is not None:
            return (mods_label(mod) + "+" + key) if mod else key
    if cls == 0x4 and ((code >> 10) & 3) == 1:            # Consumer(媒体键),命中表才友好
        u = code & 0x3FF
        if u in CONSUMER_NAME: return CONSUMER_NAME[u]
    if cls in (0xA, 0xB):                                  # 层操作(MO/TG/TO/DF 已验证)
        layer = ((code >> 8) & 0x1F) + 1
        if lo in (0xF0, 0xF1, 0xF2, 0xF3):
            return {0xF0: "MO", 0xF1: "TG", 0xF2: "TO", 0xF3: "DF"}[lo] + f"({layer})"
    if cls == 0xC and lo <= 0x1F:                          # 宏
        return f"MACRO({lo})"
    if cls == 0xF and code in INTFN:                       # InternalFunc(睡眠/USB/电量/蓝牙槽…已验证)
        return INTFN[code]
    # 其余(tap-mod/layermod/mouse/system/LayerTap/0xF 未命名功能 等,位域已知行为待验)→ 原始码,仍可 parse
    return f"0x{code:04X}"


# ---- parse:助记符 / 原始码 -> 16 位码(decode_code 的逆)----
NAME2HID = {v.upper(): k for k, v in HID.items()}         # A-Z 0-9 F1-F12 符号键 ENTER TRANS NONE...
MODKEY2 = {v.upper(): k for k, v in MODKEY.items()}       # LCTRL.. -> 224..
CONSUMER2 = {v: k for k, v in CONSUMER_NAME.items()}      # 名 -> usage
INTFN2 = {v: k for k, v in INTFN.items()}                 # SLEEP/USB/BT1.. -> 16位码
_MODIN = {"LCTRL": 0x01, "CTRL": 0x01, "LSHIFT": 0x02, "SHIFT": 0x02,
          "LALT": 0x04, "ALT": 0x04, "LGUI": 0x08, "GUI": 0x08, "CMD": 0x08, "WIN": 0x08}


def parse(s):
    """'A'/'LShift+3'/'MO(2)'/'MACRO0'/'VOLUP'/'SLEEP'/'USB'/'BT1'/'0xA2F1' -> 16位码。"""
    s = s.strip()
    u = s.upper()
    if u.startswith("0X"):
        return int(u, 16)
    m = re.fullmatch(r"(MO|TG|TO|DF)\((\d+)\)", u)
    if m:
        op = {"MO": 0xF0, "TG": 0xF1, "TO": 0xF2, "DF": 0xF3}[m.group(1)]
        layer = int(m.group(2))
        return 0xA000 | (((layer - 1) & 0x1F) << 8) | op
    m = re.fullmatch(r"MACRO\(?(\d+)\)?", u)
    if m:
        return 0xC000 | (int(m.group(1)) & 0xFF)
    if u in CONSUMER2:
        return 0x4400 | CONSUMER2[u]
    if u in INTFN2:                                         # SLEEP/USB/NKRO/BATT/BT1-3/BTBC/BTUNBIND
        return INTFN2[u]
    if "+" in s:                                            # 修饰+键
        parts = [p.strip().upper() for p in s.split("+") if p.strip()]
        *mods, key = parts
        modbits = 0
        for mm in mods:
            if mm not in _MODIN: raise ValueError(f"未知修饰键: {mm}")
            modbits |= _MODIN[mm]
        if key not in NAME2HID: raise ValueError(f"未知键: {key}")
        return (modbits << 8) | NAME2HID[key]
    if u in MODKEY2:
        return MODKEY2[u]
    if u in NAME2HID:
        return NAME2HID[u]
    if s in NAME2HID:                                       # 原样符号(大小写敏感的 ' ` 等)
        return NAME2HID[s]
    raise ValueError(f"无法解析: {s}(用键名/LShift+3/MO(2)/MACRO0/VOLUP/SLEEP/USB/BT1/0x原始码)")


# ---- 设备字节 <-> 每格 16 位码 ----
def expand(keymap, fn):
    """设备 keymap+fn -> 8x7x5 的 16位码数组(0xC0-0xDF 经 fn 展开)。"""
    fcodes = [fn[i] | (fn[i + 1] << 8) for i in range(0, len(fn), 2)]
    grid = [[[0] * NCOLS for _ in range(NROWS)] for _ in range(NLAYERS)]
    for L in range(NLAYERS):
        for R in range(NROWS):
            for C in range(NCOLS):
                b = keymap[(L * NROWS + R) * NCOLS + C]
                grid[L][R][C] = fcodes[b - 0xC0] if 0xC0 <= b <= 0xDF else b
    return grid


def build(grid):
    """8x7x5 的 16位码数组 -> (keymap 4096B 含尾部 fn, fn 256B)。去重+首现顺序。"""
    keymap = bytearray([0xFF] * 4096)
    fn = []                                                 # 16位码列表
    for L in range(NLAYERS):
        for R in range(NROWS):
            for C in range(NCOLS):
                code = grid[L][R][C]
                off = (L * NROWS + R) * NCOLS + C
                if code <= 0xFF:
                    keymap[off] = code
                else:
                    if code in fn:
                        idx = fn.index(code)
                    else:
                        if len(fn) >= FN_CAP:
                            raise ValueError(f"复杂键超过 {FN_CAP} 种上限")
                        idx = len(fn); fn.append(code)
                    keymap[off] = 0xC0 + idx
    # fn 表内嵌在 keymap 尾部 [FN_OFFSET:4096],已用槽写码,其余保持 0xFF
    for n, c in enumerate(fn):
        keymap[FN_OFFSET + n * 2] = c & 0xFF
        keymap[FN_OFFSET + n * 2 + 1] = (c >> 8) & 0xFF
    fnb = bytes(keymap[FN_OFFSET:])                          # 256B,= /fn 端点内容
    return bytes(keymap), fnb


def roundtrip_ok(keymap, fn):
    """读->展开->重建,断言与原设备字节逐字节一致。返回 (ok, 详情)。"""
    grid = expand(keymap, fn)
    km2, fn2 = build(grid)
    ok_km = km2 == bytes(keymap)
    ok_fn = fn2 == bytes(fn)
    return ok_km and ok_fn, {"keymap": ok_km, "fn": ok_fn}


if __name__ == "__main__":
    import sys, json, base64, ssl, http.client
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        ctx = ssl._create_unverified_context()
        def get(path):
            c = http.client.HTTPConnection("127.0.0.1", 5000, timeout=8)
            c.request("GET", path); r = c.getresponse(); d = r.read(); c.close()
            return base64.b64decode(json.loads(d))
        c = http.client.HTTPConnection("127.0.0.1", 5000, timeout=8)
        c.request("GET", "/api/device"); dev = json.loads(c.getresponse().read()); c.close()
        i = dev[0]["id"]
        km = get(f"/api/device/{i}/keymap"); fn = get(f"/api/device/{i}/fn")
        ok, detail = roundtrip_ok(km, fn)
        print(f"设备 {i}: 字节级 round-trip {'✓ 一致' if ok else '✗ 失败'} {detail}")
        # parse(decode(c))==c 覆盖全网格所有出现的码
        grid = expand(km, fn)
        codes = sorted({grid[L][R][C] for L in range(NLAYERS) for R in range(NROWS) for C in range(NCOLS)})
        bad = []
        for c in codes:
            try:
                if parse(decode_code(c)) != c: bad.append((c, decode_code(c), parse(decode_code(c))))
            except Exception as e:
                bad.append((c, decode_code(c), repr(e)))
        if bad:
            print(f"parse/decode round-trip ✗ {len(bad)} 处:")
            for c, lbl, got in bad[:10]: print(f"  0x{c:04X} decode='{lbl}' parse->{got}")
        else:
            print(f"parse/decode round-trip ✓ 全网格 {len(codes)} 种码全部 parse(decode(c))==c")
        sys.exit(0 if ok and not bad else 1)
    print(__doc__)
