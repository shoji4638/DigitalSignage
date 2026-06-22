# board_pins.py
# Pico 2W (RP2350) + Waveshare 1.47inch LCD Module (ST7789V3, 172x320)
#
# ※ ILI9341 からの置き換え試作。既存スロットルのピン配置をそのまま流用。
#   ILI9341 と ST7789V3 はどちらも「DC/RST/CS + MOSI のみ(MISO不要)」の
#   4線SPI構成なので、配線変更なしで載せ替え可能。
#
# 配線 (ILI9341 と同一):
#   LCD VCC  -> 3V3
#   LCD GND  -> GND
#   LCD DIN  -> GP7   (SPI0 TX / MOSI)   ※ILI9341 の LCD_SDI と同じ
#   LCD CLK  -> GP6   (SPI0 SCK)
#   LCD CS   -> GP13
#   LCD DC   -> GP15
#   LCD RST  -> GP14
#   LCD BL   -> GP9   (バックライト, High=点灯)

# --- SPI ---
SPI_ID   = 0
SPI_BAUD = 40_000_000   # 不安定なら 20_000_000 へ。ST7789は高速SPI可
PIN_SCK  = 6            # LCD_SCK  (SPI0 SCK)
PIN_MOSI = 7            # LCD_SDI  (SPI0 TX) ※MISOは基板上未接続

# --- LCD control ---
PIN_CS  = 13           # LCD_CS
PIN_DC  = 15           # LCD_DC
PIN_RST = 14           # LCD_RESET
PIN_BL  = 9            # LCD_LED (バックライト, High=点灯)

# --- パネル諸元 (ST7789V3 / 172x320) ---
LCD_NATIVE_W = 172     # 物理ピクセル(横) ※ポートレート時
LCD_NATIVE_H = 320     # 物理ピクセル(縦)
LCD_COL_OFFSET = 34    # (240 - 172) / 2  内蔵RAM240幅に対する中央寄せ
LCD_ROW_OFFSET = 0
