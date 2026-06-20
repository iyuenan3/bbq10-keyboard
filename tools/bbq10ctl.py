#!/usr/bin/env python3
"""
bbq10ctl — BBQ10 (bredhat / lotlab firmware) 键盘配置命令行工具

经厂商本地 server REST API(http://127.0.0.1:5000,纯 http,无需证书/代理/DNS)
读写键盘。编解码见同目录 bbq10codec.py(设备 keymap+fn <-> 16位码,已字节级验证)。

前置:bredhat 本地 server 在跑(USB 桥)。Apple Silicon 装 Rosetta 后:
  cd ~/bbq10-bredhat-tool && ./bredhat
路线图 v0.2:直接走 USB HID,去掉对该 server 的依赖。

命令:
  list                          列出已连接键盘
  info [ID]                     设备详情
  dump [ID]                     打印当前 keymap(复杂键已解码)
  backup <file> [ID]            备份 keymap+fn+macro 到 JSON
  restore <file> [ID]           从备份还原
  getkey L R C [ID]             读单键
  setkey L R C <KEY> [ID]       写单键(支持复杂键;自动先备份+回读校验)
  serve [PORT]                  起本地图形编辑器(默认 8770),浏览器打开改键

KEY:键名 A 9 F9 ENTER SPACE -;修饰键 LSHIFT;修饰+键 LShift+3;
     层操作 MO(2) TG(3) TO(1) DF(0);宏 MACRO0;媒体键 VOLUP MUTE NEXT;
     或原始 16 位码 0xA2F1(高级动作的兜底)。
坐标 L=层(0-7) R=行(0-6) C=列(0-4)。复杂键全键盘上限 32 种。
"""
import sys, json, base64, http.client, os, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bbq10codec as cdc

HOST, PORT = "127.0.0.1", 5000


def _req(method, path, body=None):
    try:
        c = http.client.HTTPConnection(HOST, PORT, timeout=8)
        headers = {}
        if body is not None:
            body = json.dumps(body); headers["Content-Type"] = "application/json"
        c.request(method, path, body=body, headers=headers)
        r = c.getresponse(); data = r.read().decode("utf-8", "replace"); c.close()
        if r.status >= 400:
            sys.exit(f"HTTP {r.status} {method} {path}\n{data[:200]}")
        return json.loads(data) if data.strip() else None
    except (ConnectionError, OSError) as e:
        sys.exit(f"连不上 {HOST}:{PORT} — bredhat 本地 server 没在跑?先启动它。({e})")


def devices():        return _req("GET", "/api/device") or []
def get_keymap(i):    return bytearray(base64.b64decode(_req("GET", f"/api/device/{i}/keymap")))
def get_fn(i):        return bytearray(base64.b64decode(_req("GET", f"/api/device/{i}/fn")))
def get_macro(i):     return _req("GET", f"/api/device/{i}/macro")            # base64 str
def set_keymap(i, r): return _req("POST", f"/api/device/{i}/keymap", base64.b64encode(bytes(r)).decode())
def set_fn(i, r):     return _req("POST", f"/api/device/{i}/fn", base64.b64encode(bytes(r)).decode())
def set_macro(i, b64): return _req("POST", f"/api/device/{i}/macro", b64)


def pick_id(args, n=0):
    if len(args) > n: return args[n]
    d = devices()
    if not d: sys.exit("没找到键盘(server 在跑吗?USB 连着吗?)")
    return d[0]["id"]


def set_one(i, L, R, C, code):
    """写单格(自动去重建 fn,keymap+fn 两段同步,回读校验)。返回 ok。"""
    grid = cdc.expand(get_keymap(i), get_fn(i))
    grid[L][R][C] = code
    km2, fn2 = cdc.build(grid)                    # 可能因 >32 复杂键 raise ValueError
    set_keymap(i, km2); set_fn(i, fn2)
    return cdc.expand(get_keymap(i), get_fn(i))[L][R][C] == code


def grid_payload(i):
    grid = cdc.expand(get_keymap(i), get_fn(i))
    def cell(L, R, C):
        c = grid[L][R][C]
        return {"code": c, "label": cdc.decode_code(c), "cplx": c > 0xFF}
    layers = [[[cell(L, R, C) for C in range(cdc.NCOLS)] for R in range(cdc.NROWS)] for L in range(cdc.NLAYERS)]
    base = [[cdc.decode_code(grid[0][R][C]) for C in range(cdc.NCOLS)] for R in range(cdc.NROWS)]
    fnused = len({grid[L][R][C] for L in range(cdc.NLAYERS) for R in range(cdc.NROWS)
                  for C in range(cdc.NCOLS) if grid[L][R][C] > 0xFF})
    return {"device": _req("GET", f"/api/device/{i}"), "layers": layers, "base": base,
            "fnUsed": fnused, "fnCap": cdc.FN_CAP, "nlayers": cdc.NLAYERS,
            "nrows": cdc.NROWS, "ncols": cdc.NCOLS}


def catalog():
    keys = [n for c, n in sorted(cdc.HID.items()) if c not in (0,)]
    return {"keys": keys, "mods": ["LCTRL", "LSHIFT", "LALT", "LGUI"],
            "media": list(cdc.CONSUMER_NAME.values()), "layerOps": ["MO", "TG", "TO", "DF"],
            "nlayers": cdc.NLAYERS}


def cmd_list(_):
    d = devices()
    if not d: print("(无设备)"); return
    for x in d:
        bd = time.strftime("%Y-%m-%d", time.localtime(x.get("buildDate", 0)))
        print(f'{x["id"]}  VID=0x{x["vid"]:04d} PID=0x{x["pid"]:04d} '
              f'hwVer={x["hwVer"]} fw={x.get("firmwareVer")} 固件日期={bd}')


def cmd_info(a):
    print(json.dumps(_req("GET", f"/api/device/{pick_id(a)}"), ensure_ascii=False, indent=2))


def cmd_dump(a):
    i = pick_id(a); grid = cdc.expand(get_keymap(i), get_fn(i))
    for L in range(cdc.NLAYERS):
        cells = [grid[L][R][C] for R in range(cdc.NROWS) for C in range(cdc.NCOLS)]
        if set(cells) <= {0, 1}: continue
        print(f"-- 层{L} --")
        for R in range(cdc.NROWS):
            print("  " + " | ".join(f"{cdc.decode_code(grid[L][R][C]):>11}" for C in range(cdc.NCOLS)))


def _backup_obj(i):
    return {"_tool": "bbq10ctl", "_ts": int(time.time()), "device": _req("GET", f"/api/device/{i}"),
            "keymap_b64": base64.b64encode(bytes(get_keymap(i))).decode(),
            "fn_b64": base64.b64encode(bytes(get_fn(i))).decode(),
            "macro_b64": get_macro(i)}


def cmd_backup(a):
    if not a: sys.exit("用法: backup <file> [ID]")
    f = a[0]; i = pick_id(a, 1)
    json.dump(_backup_obj(i), open(f, "w"), ensure_ascii=False, indent=2)
    print(f"已备份 keymap+fn+macro 到 {f}")


def cmd_restore(a):
    if not a: sys.exit("用法: restore <file> [ID]")
    obj = json.load(open(a[0])); i = pick_id(a, 1)
    set_keymap(i, base64.b64decode(obj["keymap_b64"]))
    if obj.get("fn_b64"): set_fn(i, base64.b64decode(obj["fn_b64"]))
    if obj.get("macro_b64"): set_macro(i, obj["macro_b64"])
    print(f"已从 {a[0]} 还原 keymap+fn+macro 到设备 {i}")


def cmd_getkey(a):
    if len(a) < 3: sys.exit("用法: getkey L R C [ID]")
    L, R, C = int(a[0]), int(a[1]), int(a[2]); i = pick_id(a, 3)
    code = cdc.expand(get_keymap(i), get_fn(i))[L][R][C]
    print(f"层{L} 行{R} 列{C} = 0x{code:04X} ({cdc.decode_code(code)})")


def cmd_setkey(a):
    if len(a) < 4: sys.exit("用法: setkey L R C <KEY> [ID]")
    L, R, C = int(a[0]), int(a[1]), int(a[2]); code = cdc.parse(a[3]); i = pick_id(a, 4)
    # 自动安全备份
    bdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backups")
    os.makedirs(bdir, exist_ok=True)
    bf = os.path.join(bdir, f"auto-{i}-{int(time.time())}.json")
    cmd_backup([bf, i])
    old = cdc.expand(get_keymap(i), get_fn(i))[L][R][C]
    if not set_one(i, L, R, C, code):
        sys.exit("写入校验失败!请用 restore 还原备份")
    print(f"层{L} 行{R} 列{C}: {cdc.decode_code(old)} -> {cdc.decode_code(code)}  ✓ (备份 {bf})")


def cmd_serve(a):
    port = int(a[0]) if a and a[0].isdigit() else 8770
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import urlparse, parse_qs
    here = os.path.dirname(os.path.abspath(__file__))
    editor_path = os.path.join(here, "editor.html")

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def _send(self, body, ctype="application/json", code=200):
            if isinstance(body, (dict, list)): body = json.dumps(body, ensure_ascii=False)
            if isinstance(body, str): body = body.encode("utf-8")
            self.send_response(code); self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body))); self.end_headers()
            self.wfile.write(body)
        def _body(self):
            n = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(n) or b"{}")
        def do_GET(self):
            p = urlparse(self.path); q = parse_qs(p.query)
            try:
                if p.path == "/":
                    self._send(open(editor_path, encoding="utf-8").read(), "text/html; charset=utf-8")
                elif p.path == "/api/devices": self._send(devices())
                elif p.path == "/api/catalog": self._send(catalog())
                elif p.path == "/api/grid": self._send(grid_payload(q["id"][0]))
                elif p.path == "/api/backup": self._send(_backup_obj(q["id"][0]))
                else: self._send({"error": "not found"}, code=404)
            except Exception as e:
                self._send({"error": str(e)}, code=500)
        def do_POST(self):
            p = urlparse(self.path)
            try:
                d = self._body()
                if p.path == "/api/setkey":
                    code = cdc.parse(d["key"])
                    ok = set_one(d["id"], int(d["L"]), int(d["R"]), int(d["C"]), code)
                    self._send({"ok": ok, "code": code, "label": cdc.decode_code(code)})
                elif p.path == "/api/restore":
                    o = d["data"]; i = d["id"]
                    set_keymap(i, base64.b64decode(o["keymap_b64"]))
                    if o.get("fn_b64"): set_fn(i, base64.b64decode(o["fn_b64"]))
                    if o.get("macro_b64"): set_macro(i, o["macro_b64"])
                    self._send({"ok": True})
                else: self._send({"error": "not found"}, code=404)
            except Exception as e:
                self._send({"error": str(e)}, code=500)

    srv = ThreadingHTTPServer((HOST, port), H)
    print(f"BBQ10 编辑器: http://127.0.0.1:{port}   (Ctrl-C 退出)")
    try: srv.serve_forever()
    except KeyboardInterrupt: print("\n已退出")


CMDS = {"list": cmd_list, "info": cmd_info, "dump": cmd_dump, "backup": cmd_backup,
        "restore": cmd_restore, "getkey": cmd_getkey, "setkey": cmd_setkey, "serve": cmd_serve}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        print(__doc__); print("命令:", " ".join(CMDS)); sys.exit(0 if len(sys.argv) < 2 else 1)
    CMDS[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()
