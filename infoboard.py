# infoboard.py  (Pico 2W / MicroPython)
# Phase 2: 天気予報パネル + ニュース横スクロールティッカー。
# 設定は /config.json (config.load) から読む。
#
# 必要ファイル: config.json, config.py, board_pins.py, st7789v3.py,
#               board_render.py, netlib.py, weather.py, news.py

import time
import machine

import board_pins as bp
from st7789v3 import ST7789V3, color565
import board_render as br
import netlib
import weather
import news
import config

# ===== 表示チューニング(コード側) ====================================
TICKER_H = 28
SCROLL_PX = 2          # 1フレームの移動量(大=速い)
FRAME_MS = 30          # フレーム間隔
REFRESH_MIN = 15       # 天気・ニュースの再取得間隔(分)
# =====================================================================

W, H = 172, 320

PALETTE = {
    "BG":     color565(8, 12, 22),
    "PANEL":  color565(20, 30, 52),
    "FG":     color565(235, 240, 250),
    "DIM":    color565(120, 140, 170),
    "ACCENT": color565(90, 200, 255),
    "LINE":   color565(40, 55, 85),
    "SUN":    color565(255, 205, 60),
    "CLOUD":  color565(170, 185, 205),
    "RAIN":   color565(90, 170, 255),
    "SNOW":   color565(235, 245, 255),
    "WARN":   color565(255, 210, 70),
    "TBG":    color565(160, 30, 30),
    "TFG":    color565(255, 245, 235),
}

_WD = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
_MON = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN",
        "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")


def _now(tz_offset):
    return time.localtime(time.time() + tz_offset)


def _clock_str(t):
    return "%02d:%02d" % (t[3], t[4])


def _date_str(t):
    return "%s %02d %s" % (_WD[t[6]], t[2], _MON[t[1] - 1])


def _msg(lcd, lines):
    lcd.fill(PALETTE["BG"])
    y = 130
    for s in lines:
        br.ctext(lcd, W // 2, y, s, PALETTE["FG"])
        y += 14
    lcd.show()


def _blit_rows(lcd, y0, y1):
    """フレームバッファの水平帯(y0..y1)だけ転送(全面転送より高速)。"""
    lcd._set_window(0, y0, W - 1, y1)
    mv = memoryview(lcd.buffer)
    lcd._wdata(mv[y0 * W * 2:(y1 + 1) * W * 2])


def setup_lcd():
    spi = machine.SPI(bp.SPI_ID, baudrate=bp.SPI_BAUD,
                      sck=machine.Pin(bp.PIN_SCK), mosi=machine.Pin(bp.PIN_MOSI))
    lcd = ST7789V3(spi, cs=bp.PIN_CS, dc=bp.PIN_DC, rst=bp.PIN_RST,
                   bl=bp.PIN_BL, rotation=0)
    lcd.backlight(100)
    return lcd


def fetch_data(cfg):
    wx = cfg["weather"]
    d = {"city": wx["city"], "code": 3, "temp": 0, "hi": 0, "lo": 0,
         "tmr_code": 3, "tmr_hi": 0, "tmr_lo": 0, "ticker": ""}
    try:
        d.update(weather.fetch(wx["lat"], wx["lon"], wx["tz"]))
        d["city"] = wx["city"]
    except Exception as e:
        print("weather fail", e)
    try:
        t = news.fetch(cfg["news_rss"])
        if t:
            d["ticker"] = t
    except Exception as e:
        print("news fail", e)
    if not d["ticker"]:
        d["ticker"] = "NO NEWS FEED   ***   CHECK NETWORK / RSS URL   ***   "
    return d


def run():
    lcd = setup_lcd()
    try:
        cfg = config.load()
        netlib.FORCE_DNS = cfg["force_dns"]
    except Exception as e:
        _msg(lcd, ["config.json", "missing/invalid", str(e)[:20]])
        return

    tz_off = cfg["weather"]["tz_offset"]
    city = cfg["weather"]["city"]

    _msg(lcd, ["WiFi connecting", "%d network(s)" % len(cfg["wifi"])])
    try:
        ip = netlib.connect_any(cfg["wifi"])
        _msg(lcd, ["WiFi OK", ip, "", "sync time + data"])
        netlib.sync_time()
    except Exception as e:
        _msg(lcd, ["network error", str(e)[:22]])
        time.sleep_ms(1500)

    data = fetch_data(cfg)
    t = _now(tz_off)
    data["clock"] = _clock_str(t)
    data["date"] = _date_str(t)
    br.render_static(lcd, PALETTE, data, W, H, TICKER_H)
    lcd.show()

    scroll = 0
    last_min = -1
    last_refresh = time.ticks_ms()
    refresh_ms = REFRESH_MIN * 60 * 1000

    while True:
        br.render_ticker(lcd, PALETTE, data["ticker"], scroll, W, H, TICKER_H)
        _blit_rows(lcd, H - TICKER_H, H - 1)
        scroll += SCROLL_PX

        t = _now(tz_off)
        if t[4] != last_min:
            last_min = t[4]
            data["clock"] = _clock_str(t)
            lcd.fill_rect(0, 0, W, 24, PALETTE["PANEL"])
            lcd.text(city, 6, 8, PALETTE["FG"])
            clk = data["clock"]
            lcd.text(clk, W - len(clk) * 8 - 6, 8, PALETTE["ACCENT"])
            _blit_rows(lcd, 0, 23)

        if time.ticks_diff(time.ticks_ms(), last_refresh) > refresh_ms:
            last_refresh = time.ticks_ms()
            data = fetch_data(cfg)
            tt = _now(tz_off)
            data["clock"] = _clock_str(tt)
            data["date"] = _date_str(tt)
            br.render_static(lcd, PALETTE, data, W, H, TICKER_H)
            lcd.show()
            scroll = 0

        time.sleep_ms(FRAME_MS)


if __name__ == "__main__":
    run()
