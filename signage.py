# signage.py  (Pico 2W / MicroPython)
# Phase 1: Pico に保存した RGB565 raw 画像を順次ローテーション表示する。
#
# 事前準備:
#   1) PC で  python3 img2raw.py your.png -o images
#   2) 生成された images/*.raw を Pico の /images/ にコピー
#   3) board_pins.py, st7789v3.py, signage.py を Pico ルートに置く
#   4) signage.py を実行 (main.py にすれば電源投入で自動起動)
#
# raw は 172x320 / 2byte-per-pixel / ビッグエンディアン (img2raw.py 出力と一致)。

import os
import time
import machine

import board_pins as bp
from st7789v3 import ST7789V3, color565

# ---- 設定 -------------------------------------------------------------
IMAGE_DIR   = "/images"   # raw 画像の置き場
INTERVAL_MS = 5000        # 1枚あたりの表示時間
TRANSITION  = "fade"      # "fade"(バックライト調光) または "cut"(瞬時切替)
FADE_STEP   = 5           # フェードの粗さ(%刻み)。小さいほど滑らか
FADE_WAIT   = 8           # 各ステップの待ち(ms)
# ----------------------------------------------------------------------


def list_raw(d):
    try:
        files = os.listdir(d)
    except OSError:
        return []
    return sorted(d + "/" + f for f in files if f.endswith(".raw"))


def show_raw(lcd, path):
    """raw を直接フレームバッファへ読み込んで表示。追加メモリ確保なし。"""
    expect = lcd.width * lcd.height * 2
    try:
        size = os.stat(path)[6]
    except OSError:
        size = -1
    if size != expect:
        # サイズ不一致は安全側に倒す: 一旦黒で埋めてから読める分だけ読む
        lcd.fill(0)
        print("warn: %s size=%d expected=%d" % (path, size, expect))
    with open(path, "rb") as f:
        f.readinto(lcd.buffer)
    lcd.show()


def fade_to(lcd, target, step=FADE_STEP, wait=FADE_WAIT):
    """現在のバックライトから target(%) まで滑らかに変化。"""
    cur = getattr(lcd, "_bl_pct", 0)
    rng = range(cur, target + 1, step) if target >= cur else range(cur, target - 1, -step)
    for p in rng:
        lcd.backlight(p)
        time.sleep_ms(wait)
    lcd.backlight(target)
    lcd._bl_pct = target


def message(lcd, lines):
    lcd.fill(0)
    y = lcd.height // 2 - len(lines) * 6
    for s in lines:
        lcd.text(s, 8, y, color565(255, 255, 255))
        y += 14
    lcd.show()


def run(lcd, image_dir=IMAGE_DIR, interval_ms=INTERVAL_MS, transition=TRANSITION):
    lcd._bl_pct = 0
    lcd.backlight(0)
    i = 0
    imgs = list_raw(image_dir)
    if not imgs:
        message(lcd, ["no .raw images", "in " + image_dir])
        lcd.backlight(100)
        return

    while True:
        path = imgs[i]
        if transition == "fade":
            fade_to(lcd, 0)          # 暗転
            show_raw(lcd, path)      # 暗い間に差し替え
            fade_to(lcd, 100)        # 明転
        else:
            show_raw(lcd, path)
            lcd.backlight(100)
            lcd._bl_pct = 100

        time.sleep_ms(interval_ms)

        i += 1
        if i >= len(imgs):
            i = 0
            imgs = list_raw(image_dir)  # 1巡ごとに再スキャン(将来のDL追加に追従)
            if not imgs:
                message(lcd, ["no .raw images", "in " + image_dir])
                lcd.backlight(100)
                return


if __name__ == "__main__":
    spi = machine.SPI(bp.SPI_ID, baudrate=bp.SPI_BAUD,
                      sck=machine.Pin(bp.PIN_SCK), mosi=machine.Pin(bp.PIN_MOSI))
    lcd = ST7789V3(spi, cs=bp.PIN_CS, dc=bp.PIN_DC, rst=bp.PIN_RST,
                   bl=bp.PIN_BL, rotation=0)
    run(lcd)
