# gh_sync.py  (Pico 2W / MicroPython)
# Phase 1(サーバー対応): GitHub raw の画像を /images へDLして signage に流す。
# 設定は /config.json (config.load) から読む。通信は共通 netlib を使用。
#
# 動作: WiFi接続 -> manifest取得 -> 各 .raw をDL(一時ファイル->rename) -> signage.run()
#       WiFi/DL失敗時も /images の既存画像でそのまま動く(オフライン継続)。

import os
import time
import machine

import netlib
import config

IMAGE_DIR = "/images"


def _ensure_dir(d):
    try:
        os.mkdir(d)
    except OSError:
        pass


def sync(cfg, image_dir=IMAGE_DIR):
    base = cfg["github"]["raw_base"]
    manifest = cfg["github"]["manifest"]
    _ensure_dir(image_dir)
    code, text = netlib.get_text(base + "/" + manifest, max_bytes=8000)
    if code != 200:
        raise OSError("manifest HTTP %d" % code)
    names = []
    for line in text.replace("\r", "\n").split("\n"):
        n = line.strip()
        if n and not n.startswith("#"):
            names.append(n)
    count = 0
    for name in names:
        try:
            netlib.get_to_file(base + "/" + name, image_dir + "/" + name)
            print("got", name)
            count += 1
        except Exception as e:
            print("skip", name, e)
    return count


def boot():
    import board_pins as bp
    from st7789v3 import ST7789V3
    from signage import run, message

    spi = machine.SPI(bp.SPI_ID, baudrate=bp.SPI_BAUD,
                      sck=machine.Pin(bp.PIN_SCK), mosi=machine.Pin(bp.PIN_MOSI))
    lcd = ST7789V3(spi, cs=bp.PIN_CS, dc=bp.PIN_DC, rst=bp.PIN_RST,
                   bl=bp.PIN_BL, rotation=0)
    lcd.backlight(100)

    try:
        cfg = config.load()
        netlib.FORCE_DNS = cfg["force_dns"]
    except Exception as e:
        message(lcd, ["config.json", "missing/invalid", str(e)[:20]])
        time.sleep_ms(1500)
        run(lcd)   # 設定なしでも既存 /images で表示は続ける
        return

    try:
        message(lcd, ["WiFi connecting", "%d network(s)" % len(cfg["wifi"])])
        ip = netlib.connect_any(cfg["wifi"])
        message(lcd, ["WiFi OK", ip, "", "Sync GitHub..."])
        n = sync(cfg)
        message(lcd, ["Sync done", "%d image(s)" % n])
        time.sleep_ms(900)
    except Exception as e:
        message(lcd, ["offline mode", str(e)[:22]])
        time.sleep_ms(1400)

    run(lcd)


if __name__ == "__main__":
    boot()
