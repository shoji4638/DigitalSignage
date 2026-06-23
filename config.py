# config.py  (Pico 2W / MicroPython, CPythonでも動く)
# 起動時に /config.json を読み込み、欠けたキーは既定値で補う。
# wifi   : [{ssid,password},...] / 単一 {ssid,password} / 最上位ssid を (ssid,pw) リストへ正規化
# weather: locations(都市リスト)へ正規化。旧形式(単一都市)も受ける。
# display.orientation: portrait/landscape。 geometry()で回転・サイズ・画像サブフォルダを得る。

import json

_DEFAULT_LOCATIONS = [
    {"city": "OSAKA",     "lat": 34.6937, "lon": 135.5023, "tz": "Asia/Tokyo",       "tz_offset": 32400},
    {"city": "TOKYO",     "lat": 35.6895, "lon": 139.6917, "tz": "Asia/Tokyo",       "tz_offset": 32400},
    {"city": "GOPPINGEN", "lat": 48.7036, "lon": 9.6526,   "tz": "Europe/Berlin",    "tz_offset": 3600},
    {"city": "NEW YORK",  "lat": 40.7128, "lon": -74.0060, "tz": "America/New_York", "tz_offset": -18000},
    {"city": "PARIS",     "lat": 48.8566, "lon": 2.3522,   "tz": "Europe/Paris",     "tz_offset": 3600},
]

_DEFAULTS = {
    "force_dns": "",
    "github": {
        "raw_base": "https://raw.githubusercontent.com/USER/REPO/main/images",
        "manifest": "manifest.txt",
    },
    "news_rss": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "display": {"orientation": "portrait"},
    "cycle": {"weather_sec": 20, "signage_sec": 30, "image_sec": 6, "datetime_sec": 15},
    "clock": {"tz_offset": 32400, "label": "JAPAN"},
}

_cache = None


def _norm_wifi(raw):
    nets = []
    w = raw.get("wifi")
    if isinstance(w, list):
        for n in w:
            if isinstance(n, dict) and n.get("ssid"):
                nets.append((n["ssid"], n.get("password", "")))
    elif isinstance(w, dict) and w.get("ssid"):
        nets.append((w["ssid"], w.get("password", "")))
    if raw.get("ssid"):
        nets.append((raw["ssid"], raw.get("password", "")))
    return [(s, p) for (s, p) in nets if s and not s.startswith("YOUR_SSID")]


def _norm_locations(raw):
    w = raw.get("weather")
    src = None
    if isinstance(w, dict) and isinstance(w.get("locations"), list):
        src = w["locations"]
    elif isinstance(raw.get("locations"), list):
        src = raw["locations"]
    elif isinstance(w, dict) and w.get("city"):
        src = [w]                      # 旧形式: 単一都市
    if not src:
        src = _DEFAULT_LOCATIONS
    out = []
    for loc in src:
        if isinstance(loc, dict) and loc.get("city"):
            out.append({
                "city": loc["city"],
                "lat": loc.get("lat", 0), "lon": loc.get("lon", 0),
                "tz": loc.get("tz", "UTC"),
                "tz_offset": loc.get("tz_offset", 0),
            })
    return out or list(_DEFAULT_LOCATIONS)


def _norm_orient(v):
    s = str(v).lower()
    if s.startswith("l") or s in ("\u6a2a", "\u6a2a\u9577"):
        return "landscape"
    return "portrait"


def geometry(orientation):
    if _norm_orient(orientation) == "landscape":
        return {"rotation": 1, "w": 320, "h": 172, "subdir": "landscape",
                "landscape": True, "ticker_h": 24}
    return {"rotation": 0, "w": 172, "h": 320, "subdir": "portrait",
            "landscape": False, "ticker_h": 28}


def load(path="/config.json", reload=False):
    global _cache
    if _cache is not None and not reload:
        return _cache
    try:
        with open(path) as f:
            raw = json.load(f)
    except OSError:
        raise OSError("config not found: " + path)

    gh = raw.get("github", {}) or {}
    disp = raw.get("display", {}) or {}
    cyc = raw.get("cycle", {}) or {}
    dcy = _DEFAULTS["cycle"]
    clk = raw.get("clock", {}) or {}
    dclk = _DEFAULTS["clock"]

    cfg = {
        "wifi": _norm_wifi(raw),
        "force_dns": raw.get("force_dns", _DEFAULTS["force_dns"]),
        "github": {
            "raw_base": gh.get("raw_base", _DEFAULTS["github"]["raw_base"]),
            "manifest": gh.get("manifest", _DEFAULTS["github"]["manifest"]),
        },
        "locations": _norm_locations(raw),
        "news_rss": raw.get("news_rss", _DEFAULTS["news_rss"]),
        "orientation": _norm_orient(disp.get("orientation", "portrait")),
        "cycle": {
            "weather_sec": cyc.get("weather_sec", dcy["weather_sec"]),
            "signage_sec": cyc.get("signage_sec", dcy["signage_sec"]),
            "image_sec": cyc.get("image_sec", dcy["image_sec"]),
            "datetime_sec": cyc.get("datetime_sec", dcy["datetime_sec"]),
        },
        "clock": {
            "tz_offset": clk.get("tz_offset", dclk["tz_offset"]),
            "label": clk.get("label", dclk["label"]),
        },
    }
    _cache = cfg
    return cfg
