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


def _n(v):
    """数値を文字列化。未取得(None)は '--'。"""
    return "--" if v is None else "%d" % v


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
    """7セグで s を描く。h=数字高さ。':' '.' '-' 対応。末尾に度記号(deg)も可。戻り=右端x。"""
    w = int(h * 0.56)
    t = max(2, h // 8)
    cx = x
    for ch in s:
        if ch == ".":
            cv.fill_rect(cx, y + h - t, t, t, c); cx += t + 3
        elif ch == ":":
            cv.fill_rect(cx, y + h // 3 - t // 2, t, t, c)
            cv.fill_rect(cx, y + 2 * h // 3 - t // 2, t, t, c)
            cx += t + 5
        elif ch in _SEG:
            _seg7(cv, cx, y, w, h, t, _SEG[ch], c); cx += w + max(3, t)
        else:
            cx += w + max(3, t)
    if deg:
        r = max(3, h // 10)
        cv.ellipse(cx + r + 1, y + r + 1, r, r, c)   # 度記号(輪郭)
        cx += 2 * r + 4
    return cx


def bignum_width(s, h, deg=False):
    """draw_bignum の描画幅(px)。中央寄せ計算用。"""
    w = int(h * 0.56)
    t = max(2, h // 8)
    cx = 0
    for ch in s:
        if ch == ".":
            cx += t + 3
        elif ch == ":":
            cx += t + 5
        else:
            cx += w + max(3, t)
    if deg:
        cx += 2 * max(3, h // 10) + 4
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
    temp = _n(d.get("temp"))
    th = 56
    tw = int(th * 0.56)
    total = len(temp) * (tw + 4) + 2 * max(3, th // 10) + 4
    draw_bignum(cv, (W - total) // 2, 108, temp, th, P["FG"], deg=True)

    # 状態ラベル
    ctext(cv, W // 2, 176, wmo_label(d.get("code", 3)), P["ACCENT"])

    # 本日 Hi/Lo
    ctext(cv, W // 2, 196, "H%s   L%s" % (_n(d.get("hi")), _n(d.get("lo"))), P["FG"])

    if d.get("date"):
        ctext(cv, W // 2, 208, d["date"], P["DIM"])

    cv.hline(8, 220, W - 16, P["LINE"])

    # 明日
    ctext(cv, W // 2, 228, "TOMORROW", P["DIM"])
    draw_icon(cv, 38, 262, wmo_kind(d.get("tmr_code", 3)), P, 0.8)
    cv.text("H%s" % _n(d.get("tmr_hi")), 86, 250, P["FG"])
    cv.text("L%s" % _n(d.get("tmr_lo")), 86, 266, P["DIM"])

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


# ---- 横長(320x172)用の静的レイアウト -------------------------------
def render_static_landscape(cv, P, d, W, H, ticker_h):
    cv.fill(P["BG"])
    # ヘッダ(全幅)
    cv.fill_rect(0, 0, W, 20, P["PANEL"])
    cv.text(d.get("city", ""), 6, 6, P["FG"])
    clk = d.get("clock", "")
    cv.text(clk, W - len(clk) * 8 - 6, 6, P["ACCENT"])
    cv.hline(0, 20, W, P["LINE"])

    # 左ゾーン: アイコン + 大型気温
    draw_icon(cv, 56, 82, wmo_kind(d.get("code", 3)), P, 1.1)
    temp = "%d" % d.get("temp", 0)
    draw_bignum(cv, 104, 44, temp, 58, P["FG"], deg=True)
    ctext(cv, 104, 122, wmo_label(d.get("code", 3)), P["ACCENT"])

    # 縦の区切り
    cv.vline(206, 26, (H - ticker_h) - 30, P["LINE"])

    # 右ゾーン: 本日 / 明日 / 日付
    rx = 262
    ctext(cv, rx, 30, "TODAY", P["DIM"])
    ctext(cv, rx, 44, "H%d  L%d" % (d.get("hi", 0), d.get("lo", 0)), P["FG"])
    ctext(cv, rx, 72, "TOMORROW", P["DIM"])
    draw_icon(cv, 234, 104, wmo_kind(d.get("tmr_code", 3)), P, 0.7)
    cv.text("H%d" % d.get("tmr_hi", 0), 274, 96, P["FG"])
    cv.text("L%d" % d.get("tmr_lo", 0), 274, 112, P["DIM"])
    if d.get("date"):
        ctext(cv, rx, 132, d["date"], P["DIM"])

    # ティッカー背景(全幅)
    ty = H - ticker_h
    cv.fill_rect(0, ty, W, ticker_h, P["TBG"])
    cv.hline(0, ty, W, P["ACCENT"])


# ---- 横長(320x172)レイアウト --------------------------------------
def render_static_land(cv, P, d, W, H, ticker_h):
    cv.fill(P["BG"])
    # ヘッダ(全幅)
    cv.fill_rect(0, 0, W, 20, P["PANEL"])
    cv.text(d.get("city", ""), 6, 6, P["FG"])
    clk = d.get("clock", "")
    cv.text(clk, W - len(clk) * 8 - 6, 6, P["ACCENT"])
    cv.hline(0, 20, W, P["LINE"])

    # 左: アイコン + 大型気温
    draw_icon(cv, 54, 78, wmo_kind(d.get("code", 3)), P)
    temp = _n(d.get("temp"))
    th = 46
    draw_bignum(cv, 104, 50, temp, th, P["FG"], deg=True)
    ctext(cv, 112, 110, wmo_label(d.get("code", 3)), P["ACCENT"])
    ctext(cv, 112, 130, "H%s   L%s" % (_n(d.get("hi")), _n(d.get("lo"))), P["FG"])

    # 縦の区切り
    ty = H - ticker_h
    cv.vline(208, 28, ty - 30, P["LINE"])

    # 右: 明日 + 日付
    ctext(cv, 264, 30, "TOMORROW", P["DIM"])
    draw_icon(cv, 242, 80, wmo_kind(d.get("tmr_code", 3)), P, 0.8)
    cv.text("H%s" % _n(d.get("tmr_hi")), 282, 70, P["FG"])
    cv.text("L%s" % _n(d.get("tmr_lo")), 282, 88, P["DIM"])
    if d.get("date"):
        ctext(cv, 264, 124, d["date"], P["DIM"])

    # ティッカー背景(全幅)
    cv.fill_rect(0, ty, W, ticker_h, P["TBG"])
    cv.hline(0, ty, W, P["ACCENT"])


def render_board(cv, P, d, W, H, ticker_h, landscape=False):
    if landscape:
        render_static_land(cv, P, d, W, H, ticker_h)
    else:
        render_static(cv, P, d, W, H, ticker_h)


# ---- 日時画面 ------------------------------------------------------
import math as _math

_WD3 = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
_MON3 = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN",
         "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")


def _thick_line(cv, x0, y0, x1, y1, c, th):
    dx = x1 - x0
    dy = y1 - y0
    L = _math.sqrt(dx * dx + dy * dy) or 1
    px = -dy / L
    py = dx / L
    for k in range(-th, th + 1):
        cv.line(int(x0 + px * k), int(y0 + py * k),
                int(x1 + px * k), int(y1 + py * k), c)


def _datetime_header(cv, P, label, W, ls):
    hh = 20 if ls else 24
    ty = 6 if ls else 8
    cv.fill_rect(0, 0, W, hh, P["PANEL"])
    cv.text(label, 6, ty, P["FG"])
    cv.text("JST", W - 3 * 8 - 6, ty, P["ACCENT"])
    cv.hline(0, hh, W, P["LINE"])
    return hh


def render_digital(cv, P, t, label, W, H, ls):
    """年月日 + 大型デジタル時計。 t=time.localtime tuple。"""
    cv.fill(P["BG"])
    _datetime_header(cv, P, label, W, ls)

    ymd = "%04d-%02d-%02d" % (t[0], t[1], t[2])
    wd = _WD3[t[6]]
    hm = "%02d:%02d" % (t[3], t[4])
    ss = "%02d" % t[5]

    if ls:
        ctext(cv, W // 2, 36, ymd + "  " + wd, P["FG"])
        bigh, smh = 64, 30
        gap = 10
        total = bignum_width(hm, bigh) + gap + bignum_width(ss, smh)
        x0 = (W - total) // 2
        ay = 80
        xend = draw_bignum(cv, x0, ay, hm, bigh, P["FG"])
        draw_bignum(cv, xend + gap, ay + bigh - smh, ss, smh, P["ACCENT"])
    else:
        ctext(cv, W // 2, 60, ymd, P["FG"])
        ctext(cv, W // 2, 78, wd, P["DIM"])
        bigh, smh = 46, 22
        gap = 8
        total = bignum_width(hm, bigh) + gap + bignum_width(ss, smh)
        x0 = (W - total) // 2
        ay = 150
        xend = draw_bignum(cv, x0, ay, hm, bigh, P["FG"])
        draw_bignum(cv, xend + gap, ay + bigh - smh, ss, smh, P["ACCENT"])


def render_analog(cv, P, t, label, W, H, ls):
    """アナログ時計 + 日付。"""
    cv.fill(P["BG"])
    hh = _datetime_header(cv, P, label, W, ls)

    cx = W // 2
    cy = (hh + H) // 2 - (6 if ls else 12)
    r = (min(W, H - hh) // 2) - (10 if ls else 8)

    # 文字盤
    cv.ellipse(cx, cy, r, r, P["LINE"])
    cv.ellipse(cx, cy, r - 1, r - 1, P["DIM"])
    for i in range(12):
        a = _math.radians(i * 30)
        sx, sy = _math.sin(a), -_math.cos(a)
        inner = r - (10 if i % 3 == 0 else 6)
        col = P["ACCENT"] if i % 3 == 0 else P["DIM"]
        cv.line(int(cx + sx * inner), int(cy + sy * inner),
                int(cx + sx * (r - 2)), int(cy + sy * (r - 2)), col)

    h, m, s = t[3] % 12, t[4], t[5]
    a_h = _math.radians((h + m / 60.0) * 30)
    a_m = _math.radians(m * 6)
    a_s = _math.radians(s * 6)

    def tip(ang, length):
        return cx + _math.sin(ang) * length, cy - _math.cos(ang) * length

    hx, hy = tip(a_h, r * 0.52)
    mx, my = tip(a_m, r * 0.78)
    sx, sy = tip(a_s, r * 0.86)
    _thick_line(cv, cx, cy, hx, hy, P["FG"], 2)
    _thick_line(cv, cx, cy, mx, my, P["ACCENT"], 1)
    cv.line(cx, cy, int(sx), int(sy), P["TBG"])     # 秒針(赤)
    cv.ellipse(cx, cy, 3, 3, P["FG"], True)         # 中心ハブ

    # 日付
    ymd = "%04d-%02d-%02d %s" % (t[0], t[1], t[2], _WD3[t[6]])
    ctext(cv, W // 2, H - (16 if ls else 22), ymd, P["DIM"])
