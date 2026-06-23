# gh_sync.py  (Pico 2W / MicroPython)
# Phase 1(サーバー対応): GitHub raw の画像を取得して signage に流す。
# config.json の display.orientation に応じて、参照フォルダ・保存先・回転を切替える。
#
#   raw_base/<orient>/manifest.txt と raw_base/<orient>/<file> を読む。
#   Pico内は /images/<orient>/ に保存。 orient = portrait | landscape
#
# 動作: WiFi -> manifest取得 -> 各 .raw をDL(一時->rename) -> signage.run()
#       失敗時も保存済み画像でオフライン継続。

import os
import time
import machine

import netlib
import config


def _ensure_dir(d):
    try:
        os.mkdir(d)
    except OSError:
        pass


def sync(cfg, geom):
    sub = geom["subdir"]
    base = cfg["github"]["raw_base"] + "/" + sub
    manifest = cfg["github"]["manifest"]
    image_dir = "/images/" + sub
    _ensure_dir("/images")
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
    return count, image_dir


def boot():
    import board_pins as bp
    from st7789v3 import ST7789V3
    from signage import run, message

    cfg = config.load()
    netlib.FORCE_DNS = cfg["force_dns"]
    geom = config.geometry(cfg["orientation"])

    spi = machine.SPI(bp.SPI_ID, baudrate=bp.SPI_BAUD,
                      sck=machine.Pin(bp.PIN_SCK), mosi=machine.Pin(bp.PIN_MOSI))
    lcd = ST7789V3(spi, cs=bp.PIN_CS, dc=bp.PIN_DC, rst=bp.PIN_RST,
                   bl=bp.PIN_BL, rotation=geom["rotation"])
    lcd.backlight(100)

    image_dir = "/images/" + geom["subdir"]
    try:
        message(lcd, ["WiFi connecting", "%d network(s)" % len(cfg["wifi"])])
        ip = netlib.connect_any(cfg["wifi"])
        message(lcd, ["WiFi OK", ip, "", "Sync " + geom["subdir"]])
        n, image_dir = sync(cfg, geom)
        message(lcd, ["Sync done", "%d image(s)" % n])
        time.sleep_ms(900)
    except Exception as e:
        message(lcd, ["offline mode", str(e)[:22]])
        time.sleep_ms(1400)

    run(lcd, image_dir=image_dir)


if __name__ == "__main__":
    boot()
