# st7789v3.py
# Waveshare 1.47inch LCD Module (ST7789V3, 172x320) 用 MicroPython ドライバ
# - framebuf ベース(フルバッファ合成 -> 一括転送)。RP2350なら 172*320*2=約107KB で余裕。
# - 172x320 パネル特有の 34px カラムオフセットを内蔵処理。
# - framebuf RGB565(リトルエンディアン) と ST7789(ビッグエンディアン) の差は
#   color565() でバイトスワップ済みの値を返すことで吸収する。
#
# 単体テスト: このファイルを直接 main.py として実行(または import 後 __main__)すると
#            オフセット/色順/向き/文字 を一度に確認できるブリングアップ画面を表示する。

import machine
import framebuf
import time

# ST7789 コマンド
_SWRESET = 0x01
_SLPOUT  = 0x11
_NORON   = 0x13
_INVON   = 0x21
_DISPON  = 0x29
_CASET   = 0x2A
_RASET   = 0x2B
_RAMWR   = 0x2C
_COLMOD  = 0x3A
_MADCTL  = 0x36

# MADCTL ビット
_MADCTL_MY  = 0x80
_MADCTL_MX  = 0x40
_MADCTL_MV  = 0x20
_MADCTL_BGR = 0x08   # 立てるとBGR。Waveshareパネルは通常RGB(=0)

# rotation -> (madctl, width, height, xstart, ystart)
# 172幅は内蔵RAM240に対し中央寄せ(両側34px)。landscapeでは34がrow側に回る。
_ROTATIONS = {
    0: (0x00,               172, 320, 34, 0),   # portrait
    1: (_MADCTL_MV | _MADCTL_MX, 320, 172, 0, 34),  # landscape
    2: (_MADCTL_MY | _MADCTL_MX, 172, 320, 34, 0),   # portrait flip
    3: (_MADCTL_MV | _MADCTL_MY, 320, 172, 0, 34),  # landscape flip
}


def color565(r, g, b):
    """RGB(0-255) -> framebuf格納用にバイトスワップした16bit値。"""
    c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return ((c & 0xFF) << 8) | (c >> 8)


class ST7789V3(framebuf.FrameBuffer):
    def __init__(self, spi, cs, dc, rst, bl=None, rotation=0, bgr=False):
        self.spi = spi
        self.cs = machine.Pin(cs, machine.Pin.OUT, value=1)
        self.dc = machine.Pin(dc, machine.Pin.OUT, value=0)
        self.rst = machine.Pin(rst, machine.Pin.OUT, value=1)
        self.bl = machine.PWM(machine.Pin(bl)) if bl is not None else None
        if self.bl:
            self.bl.freq(1000)
            self.bl.duty_u16(0)  # 初期化が終わるまで消灯

        madctl, w, h, xs, ys = _ROTATIONS[rotation]
        if bgr:
            madctl |= _MADCTL_BGR
        self._madctl = madctl
        self.width = w
        self.height = h
        self._xs = xs
        self._ys = ys

        self.buffer = bytearray(w * h * 2)
        super().__init__(self.buffer, w, h, framebuf.RGB565)

        self._reset()
        self._init()

    # --- 低レベル ---
    def _wcmd(self, cmd):
        self.dc(0)
        self.cs(0)
        self.spi.write(bytes([cmd]))
        self.cs(1)

    def _wdata(self, data):
        self.dc(1)
        self.cs(0)
        self.spi.write(data)
        self.cs(1)

    def _wcmd_data(self, cmd, data):
        self._wcmd(cmd)
        self._wdata(bytes(data))

    def _reset(self):
        self.rst(1); time.sleep_ms(5)
        self.rst(0); time.sleep_ms(20)
        self.rst(1); time.sleep_ms(150)

    def _init(self):
        self._wcmd(_SWRESET); time.sleep_ms(150)
        self._wcmd(_SLPOUT);  time.sleep_ms(120)
        self._wcmd_data(_COLMOD, [0x55])      # 16bit/pixel
        self._wcmd_data(_MADCTL, [self._madctl])
        # porch / gate / vcom (既知良好値。画質安定用)
        self._wcmd_data(0xB2, [0x0C, 0x0C, 0x00, 0x33, 0x33])
        self._wcmd_data(0xB7, [0x35])
        self._wcmd_data(0xBB, [0x19])
        self._wcmd_data(0xC0, [0x2C])
        self._wcmd_data(0xC2, [0x01])
        self._wcmd_data(0xC3, [0x12])
        self._wcmd_data(0xC4, [0x20])
        self._wcmd_data(0xC6, [0x0F])
        self._wcmd_data(0xD0, [0xA4, 0xA1])
        self._wcmd_data(0xE0, [0xD0, 0x04, 0x0D, 0x11, 0x13, 0x2B, 0x3F,
                               0x54, 0x4C, 0x18, 0x0D, 0x0B, 0x1F, 0x23])
        self._wcmd_data(0xE1, [0xD0, 0x04, 0x0C, 0x11, 0x13, 0x2C, 0x3F,
                               0x44, 0x51, 0x2F, 0x1F, 0x1F, 0x20, 0x23])
        self._wcmd(_INVON);  time.sleep_ms(10)   # IPSパネルは反転ON
        self._wcmd(_NORON);  time.sleep_ms(10)
        self._wcmd(_DISPON); time.sleep_ms(120)

    def _set_window(self, x0, y0, x1, y1):
        x0 += self._xs; x1 += self._xs
        y0 += self._ys; y1 += self._ys
        self._wcmd_data(_CASET, [x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF])
        self._wcmd_data(_RASET, [y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF])
        self._wcmd(_RAMWR)

    def show(self):
        """framebuf 全体をパネルへ転送。"""
        self._set_window(0, 0, self.width - 1, self.height - 1)
        self._wdata(self.buffer)

    def backlight(self, percent):
        """0-100 でバックライト調光。"""
        if self.bl:
            percent = 0 if percent < 0 else 100 if percent > 100 else percent
            self.bl.duty_u16(int(percent * 65535 / 100))


# ----------------------------------------------------------------------------
# 単体ブリングアップテスト
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    import board_pins as bp

    spi = machine.SPI(bp.SPI_ID, baudrate=bp.SPI_BAUD,
                      sck=machine.Pin(bp.PIN_SCK), mosi=machine.Pin(bp.PIN_MOSI))
    lcd = ST7789V3(spi, cs=bp.PIN_CS, dc=bp.PIN_DC, rst=bp.PIN_RST,
                   bl=bp.PIN_BL, rotation=0)

    WHITE = color565(255, 255, 255)
    RED   = color565(255, 0, 0)
    GREEN = color565(0, 255, 0)
    BLUE  = color565(0, 0, 255)
    BLACK = color565(0, 0, 0)
    YELLOW = color565(255, 255, 0)
    CYAN   = color565(0, 255, 255)

    W, H = lcd.width, lcd.height

    lcd.fill(BLACK)

    # (1) 最外周ぴったりに1px白枠。オフセットが狂っていると枠が欠ける/色帯が出る。
    lcd.rect(0, 0, W, H, WHITE)

    # (2) 色順チェック: 上から R / G / B の帯。赤青が入れ替わるならBGR=Trueに。
    bar = 28
    lcd.fill_rect(4, 8, W - 8, bar, RED)
    lcd.fill_rect(4, 8 + bar, W - 8, bar, GREEN)
    lcd.fill_rect(4, 8 + bar * 2, W - 8, bar, BLUE)

    # (3) 向きチェック: 4隅に別色マーカー。どの隅が原点(0,0)か一目で分かる。
    m = 12
    lcd.fill_rect(0, 0, m, m, RED)             # 左上 = 原点
    lcd.fill_rect(W - m, 0, m, m, GREEN)       # 右上
    lcd.fill_rect(0, H - m, m, m, BLUE)        # 左下
    lcd.fill_rect(W - m, H - m, m, m, YELLOW)  # 右下

    # (4) 文字
    lcd.text("ST7789V3 OK", 20, 130, WHITE)
    lcd.text("172 x 320", 20, 145, CYAN)
    lcd.text("origin=TL/RED", 20, 165, WHITE)
    lcd.text("R G B bars", 20, 180, WHITE)

    lcd.show()
    lcd.backlight(100)

    print("bring-up displayed: W=%d H=%d xoff=%d yoff=%d" % (W, H, lcd._xs, lcd._ys))
