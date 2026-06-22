# gh_sync.py  (Pico 2W / MicroPython)
# GitHub の raw 画像を /images へダウンロードして signage に流す。
#
# 動作: WiFi接続 -> マニフェスト取得 -> 各 .raw をDL(一時ファイル->rename) -> signage.run()
#       WiFi/DL が失敗しても、既に /images にある画像でそのまま動く(オフライン継続)。
#
# GitHub 側の準備 (公開リポジトリ):
#   リポジトリ例:  github.com/<USER>/<REPO>   ブランチ main
#   配置:
#     images/manifest.txt        <- 表示したい .raw のファイル名を1行ずつ
#     images/sample_coffee.raw
#     images/sample_beer.raw
#     ...
#   raw URL は  https://raw.githubusercontent.com/<USER>/<REPO>/main/images/<file>
#   -> 下の GITHUB_RAW_BASE をそのフォルダまでに設定する。

import os
import time
import socket
import machine

# ===== 設定 (自分の値に変更) =========================================
WIFI_SSID = "SANTA_2F"
WIFI_PASS = "s8nidedxcaid7"

# images フォルダまでの raw ベースURL (末尾スラッシュ無し)
GITHUB_RAW_BASE = "https://github.com/shoji4638/DigitalSignage.git/main/images"
MANIFEST = "manifest.txt"     # ベースURL直下に置くファイル名一覧
IMAGE_DIR = "/images"
# =====================================================================

try:
    import ssl
except ImportError:
    import ussl as ssl


# ---- WiFi ----------------------------------------------------------
def wifi_connect(ssid=WIFI_SSID, pw=WIFI_PASS, timeout=20):
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
    return wlan.ifconfig()[0]


# ---- HTTP(S) GET ---------------------------------------------------
def _url_split(url):
    if url.startswith("https://"):
        secure = True; rest = url[8:]; port = 443
    elif url.startswith("http://"):
        secure = False; rest = url[7:]; port = 80
    else:
        raise ValueError("bad url: " + url)
    i = rest.find("/")
    if i < 0:
        host, path = rest, "/"
    else:
        host, path = rest[:i], rest[i:]
    if ":" in host:
        host, p = host.split(":"); port = int(p)
    return secure, host, port, path


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


def _open_body(url):
    """ヘッダまで読み進め、(socket, content_length) を返す。本文はこの後から。"""
    secure, host, port, path = _url_split(url)
    addr = socket.getaddrinfo(host, port)[0][-1]
    sock = socket.socket()
    sock.connect(addr)
    if secure:
        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.verify_mode = ssl.CERT_NONE      # 公開ファイルなので証明書検証は省略
            s = ctx.wrap_socket(sock, server_hostname=host)
        except AttributeError:
            s = ssl.wrap_socket(sock, server_hostname=host)
    else:
        s = sock

    req = "GET %s HTTP/1.1\r\nHost: %s\r\nUser-Agent: pico\r\nConnection: close\r\n\r\n" % (path, host)
    s.write(req.encode())

    status = _readline(s).decode().strip()
    parts = status.split(" ")
    code = int(parts[1]) if len(parts) > 1 else 0

    clen = -1
    while True:
        line = _readline(s)
        if line in (b"\r\n", b"\n", b""):
            break
        ls = line.decode().strip().lower()
        if ls.startswith("content-length:"):
            clen = int(ls.split(":", 1)[1])

    if code != 200:
        try:
            s.close()
        except Exception:
            pass
        raise OSError("HTTP %d" % code)
    return s, clen


def download(url, path):
    """url のファイルを path へ保存(一時ファイル->rename)。書き込みバイト数を返す。"""
    s, clen = _open_body(url)
    tmp = path + ".part"
    written = 0
    try:
        with open(tmp, "wb") as f:
            remaining = clen
            while remaining != 0:
                n = 512 if remaining < 0 else min(512, remaining)
                chunk = s.read(n)
                if not chunk:
                    break
                f.write(chunk)
                written += len(chunk)
                if remaining > 0:
                    remaining -= len(chunk)
    finally:
        try:
            s.close()
        except Exception:
            pass
    if clen >= 0 and written != clen:
        try:
            os.remove(tmp)
        except Exception:
            pass
        raise OSError("short read %d/%d" % (written, clen))
    # MicroPython の rename は既存先で失敗することがあるので先に消す
    try:
        os.remove(path)
    except Exception:
        pass
    os.rename(tmp, path)
    return written


def fetch_text(url, limit=4096):
    s, clen = _open_body(url)
    try:
        data = b""
        remaining = clen if clen >= 0 else limit
        while remaining > 0 and len(data) < limit:
            chunk = s.read(min(256, remaining))
            if not chunk:
                break
            data += chunk
            if clen >= 0:
                remaining -= len(chunk)
    finally:
        try:
            s.close()
        except Exception:
            pass
    return data.decode()


# ---- 同期 ----------------------------------------------------------
def _ensure_dir(d):
    try:
        os.mkdir(d)
    except OSError:
        pass  # 既存ならOK


def sync(base=GITHUB_RAW_BASE, manifest=MANIFEST, image_dir=IMAGE_DIR):
    """マニフェストに載った .raw を全部DL。成功した件数を返す。"""
    _ensure_dir(image_dir)
    text = fetch_text(base + "/" + manifest)
    names = []
    for line in text.replace("\r", "\n").split("\n"):
        name = line.strip()
        if name and not name.startswith("#"):
            names.append(name)
    count = 0
    for name in names:
        try:
            download(base + "/" + name, image_dir + "/" + name)
            print("got", name)
            count += 1
        except Exception as e:
            print("skip", name, e)
    return count


# ---- 起動: WiFi -> 同期 -> ローテーション --------------------------
def boot():
    import board_pins as bp
    from st7789v3 import ST7789V3
    from signage import run, message

    spi = machine.SPI(bp.SPI_ID, baudrate=bp.SPI_BAUD,
                      sck=machine.Pin(bp.PIN_SCK), mosi=machine.Pin(bp.PIN_MOSI))
    lcd = ST7789V3(spi, cs=bp.PIN_CS, dc=bp.PIN_DC, rst=bp.PIN_RST,
                   bl=bp.PIN_BL, rotation=0)
    lcd._bl_pct = 100
    lcd.backlight(100)

    try:
        message(lcd, ["WiFi connecting", WIFI_SSID])
        ip = wifi_connect()
        message(lcd, ["WiFi OK", ip, "", "Sync GitHub..."])
        n = sync()
        message(lcd, ["Sync done", "%d image(s)" % n])
        time.sleep_ms(900)
    except Exception as e:
        # WiFi/DL失敗でも既存画像で続行
        message(lcd, ["offline mode", str(e)[:22]])
        time.sleep_ms(1400)

    run(lcd)


if __name__ == "__main__":
    boot()
