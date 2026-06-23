# weather.py  (Pico 2W / MicroPython)
# Open-Meteo (APIキー不要) から現在＋本日＋明日の天気を取得する。

import json
import netlib

# 緯度経度はお好みで。既定=東京駅付近。
URL = ("https://api.open-meteo.com/v1/forecast"
       "?latitude=%s&longitude=%s"
       "&current=temperature_2m,weather_code"
       "&daily=weather_code,temperature_2m_max,temperature_2m_min"
       "&timezone=%s&forecast_days=2")


def _r(x):
    try:
        return int(round(x))
    except Exception:
        return 0


def fetch(lat=35.681, lon=139.767, tz="Asia/Tokyo"):
    url = URL % (lat, lon, tz.replace("/", "%2F"))
    code, body = netlib.get(url, max_bytes=8000)
    if code != 200:
        raise OSError("weather HTTP %d" % code)
    j = json.loads(body)
    cur = j["current"]
    da = j["daily"]
    return {
        "temp": _r(cur["temperature_2m"]),
        "code": int(cur["weather_code"]),
        "hi": _r(da["temperature_2m_max"][0]),
        "lo": _r(da["temperature_2m_min"][0]),
        "tmr_code": int(da["weather_code"][1]),
        "tmr_hi": _r(da["temperature_2m_max"][1]),
        "tmr_lo": _r(da["temperature_2m_min"][1]),
    }


if __name__ == "__main__":
    print(fetch())
