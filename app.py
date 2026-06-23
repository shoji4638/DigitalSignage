# app.py  (Pico 2W / MicroPython)
# 統合メイン: 天気予報(複数都市) / サイネージ(画像) / 日時(デジタル・アナログ) を巡回表示。
#   起動時: WiFi -> NTP -> GitHub画像同期 -> 全都市の天気/ニュース取得
#   以降  : 天気(都市を順送り) -> 画像 -> 日時(デジタル/アナログ交互, 日本時間) -> ... を巡回
#           天気/ニュースは定期再取得(失敗時は前回値保持、未取得は短間隔リトライ)。
#
# 設定 config.json:
#   display.orientation = portrait | landscape
#   cycle.weather_sec / signage_sec / image_sec / datetime_sec
#   weather.locations = 表示する都市の配列
#   clock.tz_offset / clock.label = 日時画面の時差(秒)と表示名 (既定 JST/JAPAN)
#
# 必要: config.json, config.py, board_pins.py, st7789v3.py, board_render.py,
#       netlib.py, weather.py, news.py, signage.py, infoboard.py, gh_sync.py

import time

import config
import netlib
import signage
import infoboard as ib


def signage_phase(lcd, image_dir, dur_ms, image_ms):
    imgs = signage.list_raw(image_dir)
    if not imgs:
        return   # 画像が無ければ天気のみ巡回
    deadline = time.ticks_add(time.ticks_ms(), dur_ms)
    i = 0
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        signage.fade_to(lcd, 0)
        signage.show_raw(lcd, imgs[i])
        signage.fade_to(lcd, 100)
        hold = time.ticks_add(time.ticks_ms(), image_ms)
        while (time.ticks_diff(hold, time.ticks_ms()) > 0 and
               time.ticks_diff(deadline, time.ticks_ms()) > 0):
            time.sleep_ms(50)
        i = (i + 1) % len(imgs)


def run():
    cfg = config.load()
    netlib.FORCE_DNS = cfg["force_dns"]
    geom = config.geometry(cfg["orientation"])
    cyc = cfg["cycle"]

    lcd = ib.setup_lcd(geom["rotation"])
    lcd._bl_pct = 100
    image_dir = "/images/" + geom["subdir"]

    ib._msg(lcd, ["WiFi connecting", "%d network(s)" % len(cfg["wifi"])])
    try:
        ip = netlib.connect_any(cfg["wifi"])
        ib._msg(lcd, ["WiFi OK", ip, "", "sync time/img/data"])
        netlib.sync_time()
        try:
            import gh_sync
            n, image_dir = gh_sync.sync(cfg, geom)
            print("synced %d images -> %s" % (n, image_dir))
        except Exception as e:
            print("image sync fail", e)
    except Exception as e:
        ib._msg(lcd, ["offline mode", str(e)[:22]])
        time.sleep_ms(1200)

    cities, ticker = ib.fetch_all(cfg)
    widx = 0
    didx = 0
    styles = ("digital", "analog")
    clk_off = cfg["clock"]["tz_offset"]
    clk_label = cfg["clock"]["label"]
    last_refresh = time.ticks_ms()
    ok_ms = ib.REFRESH_MIN * 60 * 1000
    retry_ms = 60 * 1000
    w_ms = cyc["weather_sec"] * 1000
    s_ms = cyc["signage_sec"] * 1000
    img_ms = cyc["image_sec"] * 1000
    dt_ms = cyc["datetime_sec"] * 1000

    while True:
        # 天気(都市を順送り)
        ib.weather_phase(lcd, geom, cities[widx], ticker, w_ms)
        widx = (widx + 1) % len(cities)
        # サイネージ(画像ローテーション)
        signage_phase(lcd, image_dir, s_ms, img_ms)
        # 日時(デジタル/アナログを順送り、日本時間)
        ib.datetime_phase(lcd, geom, styles[didx], clk_label, clk_off, dt_ms)
        didx = (didx + 1) % len(styles)

        interval = ok_ms if ib.all_ok(cities) else retry_ms
        if time.ticks_diff(time.ticks_ms(), last_refresh) > interval:
            last_refresh = time.ticks_ms()
            try:
                netlib.connect_any(cfg["wifi"])
            except Exception as e:
                print("wifi reconnect fail", e)
            cities, ticker = ib.fetch_all(cfg, cities, ticker)


if __name__ == "__main__":
    run()
