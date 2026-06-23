# infoboard.py  (Pico 2W / MicroPython)
# 天気予報パネル(複数都市を順次表示) + ニュース横スクロールティッカー。
# 単体でも動くが、app.py から weather_phase / fetch_all を再利用する想定。
#
# 必要: config.json, config.py, board_pins.py, st7789v3.py, board_render.py,
#       netlib.py, weather.py, news.py, signage.py

import time
import machine

import board_pins as bp
from st7789v3 import ST7789V3, color565
import board_render as br
import netlib
import weather
import news
import signage
import config

SCROLL_PX = 2
FRAME_MS = 30
REFRESH_MIN = 15
_NEWS_NONE = "NO NEWS FEED   ***   CHECK NETWORK / RSS URL   ***   "

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
    return time.localtime(time.time() + (tz_offset or 0))


def _clock_str(t):
    return "%02d:%02d" % (t[3], t[4])


def _date_str(t):
    return "%s %02d %s" % (_WD[t[6]], t[2], _MON[t[1] - 1])


def _msg(lcd, lines):
    lcd.fill(PALETTE["BG"])
    y = lcd.height // 2 - len(lines) * 7
    for s in lines:
        br.ctext(lcd, lcd.width // 2, y, s, PALETTE["FG"])
        y += 14
    lcd.show()


def _blit_rows(lcd, y0, y1):
    w = lcd.width
    lcd._set_window(0, y0, w - 1, y1)
    mv = memoryview(lcd.buffer)
    lcd._wdata(mv[y0 * w * 2:(y1 + 1) * w * 2])


def setup_lcd(rotation):
    spi = machine.SPI(bp.SPI_ID, baudrate=bp.SPI_BAUD,
                      sck=machine.Pin(bp.PIN_SCK), mosi=machine.Pin(bp.PIN_MOSI))
    lcd = ST7789V3(spi, cs=bp.PIN_CS, dc=bp.PIN_DC, rst=bp.PIN_RST,
                   bl=bp.PIN_BL, rotation=rotation)
    lcd.backlight(100)
    return lcd


# ---- データ取得(都市ごと/ニュース)。失敗時は前回値を保持 -----------
def fetch_weather(loc, prev=None):
    if prev:
        d = dict(prev)
    else:
        d = {"city": loc["city"], "code": None, "temp": None, "hi": None, "lo": None,
             "tmr_code": None, "tmr_hi": None, "tmr_lo": None,
             "weather_ok": False, "utc_offset": None, "tz_offset": loc.get("tz_offset", 0)}
    d["city"] = loc["city"]
    d["tz_offset"] = loc.get("tz_offset", 0)
    try:
        d.update(weather.fetch(loc["lat"], loc["lon"], loc["tz"]))
        d["city"] = loc["city"]
        d["weather_ok"] = True
    except Exception as e:
        print("weather fail", loc["city"], e)
    return d


def fetch_news(cfg, prev=""):
    try:
        t = news.fetch(cfg["news_rss"])
        if t:
            return t
    except Exception as e:
        print("news fail", e)
    return prev or _NEWS_NONE


def fetch_all(cfg, prev_cities=None, prev_ticker=""):
    """全都市の天気 + ニュースを取得。失敗項目は前回値を保持。(cities, ticker)。"""
    locs = cfg["locations"]
    cities = []
    for i, loc in enumerate(locs):
        prev = prev_cities[i] if (prev_cities and i < len(prev_cities)) else None
        cities.append(fetch_weather(loc, prev))
    ticker = fetch_news(cfg, prev_ticker)
    return cities, ticker


def all_ok(cities):
    return all(c.get("weather_ok") for c in cities) if cities else False


# ---- 1都市分の天気フェーズ(指定時間、ティッカー流しながら) ----------
def weather_phase(lcd, geom, city, ticker, dur_ms):
    W, H = geom["w"], geom["h"]
    th = geom["ticker_h"]
    ls = geom["landscape"]
    header_h = 20 if ls else 24
    header_ty = 6 if ls else 8

    off = city.get("utc_offset")
    if off is None:
        off = city.get("tz_offset", 0)
    t = _now(off)
    city["clock"] = _clock_str(t)
    city["date"] = _date_str(t)

    signage.fade_to(lcd, 0)
    br.render_board(lcd, PALETTE, city, W, H, th, ls)
    lcd.show()
    signage.fade_to(lcd, 100)

    scroll = 0
    last_min = -1
    deadline = time.ticks_add(time.ticks_ms(), dur_ms)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        br.render_ticker(lcd, PALETTE, ticker, scroll, W, H, th)
        _blit_rows(lcd, H - th, H - 1)
        scroll += SCROLL_PX

        t = _now(off)
        if t[4] != last_min:
            last_min = t[4]
            city["clock"] = _clock_str(t)
            lcd.fill_rect(0, 0, W, header_h, PALETTE["PANEL"])
            lcd.text(city["city"], 6, header_ty, PALETTE["FG"])
            clk = city["clock"]
            lcd.text(clk, W - len(clk) * 8 - 6, header_ty, PALETTE["ACCENT"])
            _blit_rows(lcd, 0, header_h - 1)

        time.sleep_ms(FRAME_MS)


# ---- 日時フェーズ(デジタル/アナログ、毎秒更新) --------------------
def datetime_phase(lcd, geom, style, label, tz_off, dur_ms):
    W, H = geom["w"], geom["h"]
    ls = geom["landscape"]

    def draw():
        t = _now(tz_off)
        if style == "analog":
            br.render_analog(lcd, PALETTE, t, label, W, H, ls)
        else:
            br.render_digital(lcd, PALETTE, t, label, W, H, ls)
        return t

    signage.fade_to(lcd, 0)
    t = draw()
    lcd.show()
    signage.fade_to(lcd, 100)

    last_sec = t[5]
    deadline = time.ticks_add(time.ticks_ms(), dur_ms)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        t = _now(tz_off)
        if t[5] != last_sec:     # 秒が変わったら描き直し
            last_sec = t[5]
            draw()
            lcd.show()
        time.sleep_ms(80)


# ---- 単体実行: 天気のみ複数都市を巡回 ------------------------------
def run():
    cfg = config.load()
    netlib.FORCE_DNS = cfg["force_dns"]
    geom = config.geometry(cfg["orientation"])
    lcd = setup_lcd(geom["rotation"])
    lcd._bl_pct = 100

    _msg(lcd, ["WiFi connecting", "%d network(s)" % len(cfg["wifi"])])
    try:
        ip = netlib.connect_any(cfg["wifi"])
        _msg(lcd, ["WiFi OK", ip, "", "sync time + data"])
        netlib.sync_time()
    except Exception as e:
        _msg(lcd, ["network error", str(e)[:22]])
        time.sleep_ms(1500)

    cities, ticker = fetch_all(cfg)
    idx = 0
    last_refresh = time.ticks_ms()
    ok_ms = REFRESH_MIN * 60 * 1000
    retry_ms = 60 * 1000
    dur = cfg["cycle"]["weather_sec"] * 1000

    while True:
        weather_phase(lcd, geom, cities[idx], ticker, dur)
        idx = (idx + 1) % len(cities)

        interval = ok_ms if all_ok(cities) else retry_ms
        if time.ticks_diff(time.ticks_ms(), last_refresh) > interval:
            last_refresh = time.ticks_ms()
            try:
                netlib.connect_any(cfg["wifi"])
            except Exception as e:
                print("wifi reconnect fail", e)
            cities, ticker = fetch_all(cfg, cities, ticker)


if __name__ == "__main__":
    run()
