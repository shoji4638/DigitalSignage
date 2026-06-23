# board_render.py
# Phase2 情報ボードの「描画ロジックのみ」。machine等のハード依存importは無し。
# framebuf 互換の canvas 描画メソッドだけを使う:
#   fill(c) fill_rect(x,y,w,h,c) rect(x,y,w,h,c) hline(x,y,w,c) vline(x,y,h,c)
#   line(x1,y1,x2,y2,c) ellipse(x,y,xr,yr,c[,f]) text(s,x,y,c) pixel(x,y,c)
# 実機では lcd(framebuf) を、PCモックでは PIL ラッパを渡す(同一コードで動く)。
#
# 色は呼び出し側が palette(dict) で渡す。実機=color565値 / モック=RGBタプル。

# WMO weather code -> 種別/ラベル
def wmo_kind(code):
    if code == 0:                      return "clear"
    if code in (1, 2):                 return "pcloudy"
    if code == 3:                      return "cloudy"
    if code in (45, 48):               return "fog"
    if code in (51, 53, 55, 56, 57):   return "drizzle"
    if code in (61, 63, 65, 66, 67):   return "rain"
    if code in (80, 81, 82):           return "showers"
    if code in (71, 73, 75, 77, 85, 86): return "snow"
    if code in (95, 96, 99):           return "storm"
    return "cloudy"

def wmo_label(code):
    return {
        "clear": "CLEAR", "pcloudy": "P.CLOUDY", "cloudy": "CLOUDY",
        "fog": "FOG", "drizzle": "DRIZZLE", "rain": "RAIN",
        "showers": "SHOWERS", "snow": "SNOW", "storm": "STORM",
    }[wmo_kind(code)]


def ctext(cv, cx, y, s, c):
    cv.text(s, cx - len(s) * 4, y, c)   # 8x8等幅前提で中央寄せ


# ---- 7セグ大型数字 -------------------------------------------------
_SEG = {  # a b c d e f g
    "0": (1,1,1,1,1,1,0), "1": (0,1,1,0,0,0,0), "2": (1,1,0,1,1,0,1),
    "3": (1,1,1,1,0,0,1), "4": (0,1,1,0,0,1,1), "5": (1,0,1,1,0,1,1),
    "6": (1,0,1,1,1,1,1), "7": (1,1,1,0,0,0,0), "8": (1,1,1,1,1,1,1),
    "9": (1,1,1,1,0,1,1), "-": (0,0,0,0,0,0,1),
}

def _seg7(cv, x, y, w, h, t, segs, c):
    a,b,cc,d,e,f,g = segs
    if a: cv.fill_rect(x+t, y, w-2*t, t, c)
    if g: cv.fill_rect(x+t, y+h//2 - t//2, w-2*t, t, c)
    if d: cv.fill_rect(x+t, y+h-t, w-2*t, t, c)
    if f: cv.fill_rect(x, y+t, t, h//2 - t, c)
    if b: cv.fill_rect(x+w-t, y+t, t, h//2 - t, c)
    if e: cv.fill_rect(x, y+h//2, t, h//2 - t, c)
    if cc: cv.fill_rect(x+w-t, y+h//2, t, h//2 - t, c)

def draw_bignum(cv, x, y, s, h, c, deg=False):
    """7セグで s を描く。h=数字高さ。末尾に度記号(deg)を付けられる。戻り=右端x。"""
    w = int(h * 0.56)
    t = max(2, h // 8)
    cx = x
    for ch in s:
        if ch == ".":
            cv.fill_rect(cx, y + h - t, t, t, c); cx += t + 3
        elif ch in _SEG:
            _seg7(cv, cx, y, w, h, t, _SEG[ch], c); cx += w + max(3, t)
        else:
            cx += w + max(3, t)
    if deg:
        r = max(3, h // 10)
        cv.ellipse(cx + r + 1, y + r + 1, r, r, c)   # 度記号(輪郭)
        cx += 2 * r + 4
    return cx


# ---- 天気アイコン (作図) -------------------------------------------
def draw_icon(cv, cx, cy, kind, P, scale=1.0):
    R = int(20 * scale)
    sun = P["SUN"]; cl = P["CLOUD"]; rn = P["RAIN"]; sn = P["SNOW"]; wn = P["WARN"]

    def cloud(ox, oy, col):
        cv.ellipse(ox-12, oy, 11, 9, col, True)
        cv.ellipse(ox+12, oy, 11, 9, col, True)
        cv.ellipse(ox, oy-6, 13, 11, col, True)
        cv.fill_rect(ox-22, oy, 44, 11, col)

    if kind == "clear":
        cv.ellipse(cx, cy, R, R, sun, True)
        for a in range(0, 360, 45):
            import math
            dx = math.cos(a*3.14159/180); dy = math.sin(a*3.14159/180)
            cv.line(int(cx+dx*(R+4)), int(cy+dy*(R+4)),
                    int(cx+dx*(R+12)), int(cy+dy*(R+12)), sun)
    elif kind == "pcloudy":
        cv.ellipse(cx+10, cy-10, R-4, R-4, sun, True)
        cloud(cx-4, cy+6, cl)
    elif kind in ("cloudy", "fog"):
        cloud(cx, cy, cl)
        if kind == "fog":
            for i in range(3):
                cv.hline(cx-22, cy+16+i*6, 44, P["DIM"])
    elif kind in ("rain", "drizzle", "showers"):
        cloud(cx, cy-6, cl)
        for i in range(-1, 2):
            cv.line(cx+i*14, cy+12, cx+i*14-4, cy+24, rn)
    elif kind == "snow":
        cloud(cx, cy-6, cl)
        for i in range(-1, 2):
            cv.text("*", cx+i*14-4, cy+14, sn)
    elif kind == "storm":
        cloud(cx, cy-6, cl)
        cv.line(cx, cy+12, cx-6, cy+22, wn)
        cv.line(cx-6, cy+22, cx+4, cy+22, wn)
        cv.line(cx+4, cy+22, cx-2, cy+34, wn)


# ---- 静的部(天気/ヘッダ)。ティッカー帯は背景だけ描く ---------------
def render_static(cv, P, d, W, H, ticker_h):
    cv.fill(P["BG"])
    # ヘッダ
    cv.fill_rect(0, 0, W, 24, P["PANEL"])
    cv.text(d.get("city", ""), 6, 8, P["FG"])
    clk = d.get("clock", "")
    cv.text(clk, W - len(clk) * 8 - 6, 8, P["ACCENT"])
    cv.hline(0, 24, W, P["LINE"])

    # 天気アイコン
    draw_icon(cv, W // 2, 70, wmo_kind(d.get("code", 3)), P)

    # 大型気温
    temp = "%d" % d.get("temp", 0)
    th = 56
    tw = int(th * 0.56)
    total = len(temp) * (tw + 4) + 2 * max(3, th // 10) + 4
    draw_bignum(cv, (W - total) // 2, 108, temp, th, P["FG"], deg=True)

    # 状態ラベル
    ctext(cv, W // 2, 176, wmo_label(d.get("code", 3)), P["ACCENT"])

    # 本日 Hi/Lo
    ctext(cv, W // 2, 196, "H%d   L%d" % (d.get("hi", 0), d.get("lo", 0)), P["FG"])

    if d.get("date"):
        ctext(cv, W // 2, 208, d["date"], P["DIM"])

    cv.hline(8, 220, W - 16, P["LINE"])

    # 明日
    ctext(cv, W // 2, 228, "TOMORROW", P["DIM"])
    draw_icon(cv, 38, 262, wmo_kind(d.get("tmr_code", 3)), P, 0.8)
    cv.text("H%d" % d.get("tmr_hi", 0), 86, 250, P["FG"])
    cv.text("L%d" % d.get("tmr_lo", 0), 86, 266, P["DIM"])

    # ティッカー背景
    ty = H - ticker_h
    cv.fill_rect(0, ty, W, ticker_h, P["TBG"])
    cv.hline(0, ty, W, P["ACCENT"])


# ---- ティッカー帯のみ(毎フレーム更新) -----------------------------
def render_ticker(cv, P, text, scroll_px, W, H, ticker_h):
    ty = H - ticker_h
    cv.fill_rect(0, ty + 1, W, ticker_h - 1, P["TBG"])
    if not text:
        return
    n = len(text)
    total = n * 8
    sp = scroll_px % total
    first = sp // 8
    off = -(sp % 8)
    cols = W // 8 + 2
    buf = ""
    for k in range(cols):
        buf += text[(first + k) % n]
    cv.text(buf, off, ty + (ticker_h - 8) // 2, P["TFG"])
