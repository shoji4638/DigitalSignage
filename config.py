# config.py  (Pico 2W / MicroPython, CPythonでも動く)
# 起動時に /config.json を読み込み、欠けたキーは既定値で補う。
# wifi は [{ssid,password},...] のリスト、または単一 {ssid,password}、
# または最上位の ssid/password のどれでも受け付けて (ssid,pw) のリストへ正規化する。

import json

_DEFAULTS = {
    "force_dns": "",
    "github": {
        "raw_base": "https://raw.githubusercontent.com/USER/REPO/main/images",
        "manifest": "manifest.txt",
    },
    "weather": {
        "city": "TOKYO", "lat": 35.681, "lon": 139.767,
        "tz": "Asia/Tokyo", "tz_offset": 32400,
    },
    "news_rss": "https://feeds.bbci.co.uk/news/world/rss.xml",
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
    if raw.get("ssid"):                      # 最上位 ssid/password も許容
        nets.append((raw["ssid"], raw.get("password", "")))
    # プレースホルダのまま(YOUR_SSID...)は無効として除外
    return [(s, p) for (s, p) in nets if s and not s.startswith("YOUR_SSID")]


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
    wx = raw.get("weather", {}) or {}
    dwx = _DEFAULTS["weather"]

    cfg = {
        "wifi": _norm_wifi(raw),
        "force_dns": raw.get("force_dns", _DEFAULTS["force_dns"]),
        "github": {
            "raw_base": gh.get("raw_base", _DEFAULTS["github"]["raw_base"]),
            "manifest": gh.get("manifest", _DEFAULTS["github"]["manifest"]),
        },
        "weather": {
            "city": wx.get("city", dwx["city"]),
            "lat": wx.get("lat", dwx["lat"]),
            "lon": wx.get("lon", dwx["lon"]),
            "tz": wx.get("tz", dwx["tz"]),
            "tz_offset": wx.get("tz_offset", dwx["tz_offset"]),
        },
        "news_rss": raw.get("news_rss", _DEFAULTS["news_rss"]),
    }
    _cache = cfg
    return cfg
