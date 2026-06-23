# netlib.py  (Pico 2W / MicroPython)
# 共通ネットワーク層: WiFi / NTP / 堅牢HTTP(S)。
#   get(url)         -> (code, body_bytes)        小さいAPI/RSS向け(メモリ取得)
#   get_text(url)    -> (code, text)
#   get_to_file(u,p) -> 書込みバイト数            画像など向け(ファイルへストリーム)
# Content-Length・チャンク転送・リダイレクトに対応。証明書検証は省略(公開取得)。

import os
import time
import socket

try:
    import ssl
except ImportError:
    import ussl as ssl

FORCE_DNS = ""   # DNS不調時に config から "8.8.8.8" 等を設定


def connect_wifi(ssid, pw, timeout=20):
    import network
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(ssid, pw)
        t0 = time.ticks_ms()
        while not wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), t0) > timeout * 1000:
                raise OSError("wifi timeout")
            time.sleep_ms(200)
    cfg = wlan.ifconfig()
    if FORCE_DNS and cfg[3] != FORCE_DNS:
        wlan.ifconfig((cfg[0], cfg[1], cfg[2], FORCE_DNS))
    time.sleep_ms(800)
    return wlan.ifconfig()[0]


def sync_time():
    try:
        import ntptime
        ntptime.settime()
        return True
    except Exception as e:
        print("ntp fail", e)
        return False


def _resolve(host, port, tries=5):
    last = None
    for _ in range(tries):
        try:
            return socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)[0][-1]
        except OSError as e:
            last = e
            time.sleep_ms(600)
    raise last


def _split(url):
    if url.startswith("https://"):
        sec, rest, port = True, url[8:], 443
    elif url.startswith("http://"):
        sec, rest, port = False, url[7:], 80
    else:
        raise ValueError("bad url")
    i = rest.find("/")
    host, path = (rest[:i], rest[i:]) if i >= 0 else (rest, "/")
    if ":" in host:
        host, p = host.split(":")
        port = int(p)
    return sec, host, port, path


def _readline(s):
    buf = b""
    while True:
        c = s.read(1)
        if not c:
            break
        buf += c
        if c == b"\n":
            break
    return buf


def _read_exact(s, n):
    got = b""
    while len(got) < n:
        d = s.read(n - len(got))
        if not d:
            break
        got += d
    return got


def _open(url, hops):
    """接続->リクエスト送信->ヘッダ解析(リダイレクト追従)。(s, code, clen, chunked)。"""
    sec, host, port, path = _split(url)
    addr = _resolve(host, port)
    sock = socket.socket()
    sock.connect(addr)
    if sec:
        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.verify_mode = ssl.CERT_NONE
            s = ctx.wrap_socket(sock, server_hostname=host)
        except AttributeError:
            s = ssl.wrap_socket(sock, server_hostname=host)
    else:
        s = sock

    req = ("GET %s HTTP/1.1\r\nHost: %s\r\nUser-Agent: pico\r\n"
           "Accept: */*\r\nConnection: close\r\n\r\n" % (path, host))
    s.write(req.encode())

    parts = _readline(s).decode().strip().split(" ")
    code = int(parts[1]) if len(parts) > 1 else 0

    clen = -1
    chunked = False
    loc = None
    while True:
        line = _readline(s)
        if line in (b"\r\n", b"\n", b""):
            break
        t = line.decode("ascii", "replace").strip()
        low = t.lower()
        if low.startswith("content-length:"):
            try:
                clen = int(t.split(":", 1)[1])
            except Exception:
                pass
        elif low.startswith("transfer-encoding:") and "chunked" in low:
            chunked = True
        elif low.startswith("location:"):
            loc = t.split(":", 1)[1].strip()

    if code in (301, 302, 303, 307, 308) and loc:
        try:
            s.close()
        except Exception:
            pass
        if hops <= 0:
            raise OSError("too many redirects")
        if loc.startswith("/"):
            loc = "%s://%s%s" % ("https" if sec else "http", host, loc)
        return _open(loc, hops - 1)
    return s, code, clen, chunked


def _pump(s, clen, chunked, write, max_bytes):
    total = 0
    if chunked:
        while total < max_bytes:
            size_line = _readline(s).strip()
            if not size_line:
                continue
            try:
                n = int(size_line.split(b";")[0], 16)
            except Exception:
                break
            if n == 0:
                break
            d = _read_exact(s, n)
            write(d)
            total += len(d)
            _readline(s)
    elif clen >= 0:
        remaining = min(clen, max_bytes)
        while remaining > 0:
            d = s.read(min(1024, remaining))
            if not d:
                break
            write(d)
            total += len(d)
            remaining -= len(d)
    else:
        while total < max_bytes:
            d = s.read(1024)
            if not d:
                break
            write(d)
            total += len(d)
    return total


def get(url, hops=4, max_bytes=200000):
    s, code, clen, chunked = _open(url, hops)
    chunks = []
    try:
        _pump(s, clen, chunked, chunks.append, max_bytes)
    finally:
        try:
            s.close()
        except Exception:
            pass
    return code, b"".join(chunks)


def get_text(url, **kw):
    code, body = get(url, **kw)
    return code, body.decode("utf-8", "replace")


def get_to_file(url, path, hops=4, max_bytes=2000000):
    s, code, clen, chunked = _open(url, hops)
    if code != 200:
        try:
            s.close()
        except Exception:
            pass
        raise OSError("HTTP %d" % code)
    tmp = path + ".part"
    try:
        with open(tmp, "wb") as f:
            n = _pump(s, clen, chunked, f.write, max_bytes)
    finally:
        try:
            s.close()
        except Exception:
            pass
    if clen >= 0 and n != min(clen, max_bytes):
        try:
            os.remove(tmp)
        except Exception:
            pass
        raise OSError("short read %d/%d" % (n, clen))
    try:
        os.remove(path)
    except Exception:
        pass
    os.rename(tmp, path)
    return n


def connect_any(networks, timeout=15):
    """networks: [(ssid, pw), ...] を上から順に試し、最初に繋がったIPを返す。"""
    import network
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if wlan.isconnected():
        cfg = wlan.ifconfig()
        if FORCE_DNS and cfg[3] != FORCE_DNS:
            wlan.ifconfig((cfg[0], cfg[1], cfg[2], FORCE_DNS))
        return wlan.ifconfig()[0]
    last = None
    for ssid, pw in networks:
        try:
            return connect_wifi(ssid, pw, timeout)
        except OSError as e:
            last = e
            try:
                wlan.disconnect()
            except Exception:
                pass
            time.sleep_ms(300)
    raise last or OSError("no wifi configured")
