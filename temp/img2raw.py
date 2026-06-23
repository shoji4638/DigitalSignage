#!/usr/bin/env python3
# img2raw.py  (PC側 / CPython)
# 任意の画像(PNG/JPG等) -> ST7789V3 表示用の生 RGB565 raw へ変換する。
#
#   出力フォーマット: 1ピクセル2バイト, ビッグエンディアン(高位バイト先)。
#   Pico側は readinto() でこの raw をフレームバッファへ直読みして show() するだけ。
#   バイト順は st7789v3.py の show()(=SPI素通し) と一致させてある。
#
# 使い方:
#   python3 img2raw.py input1.png input2.jpg ... -o out_dir
#   python3 img2raw.py "ads/*.png" -o images --fit cover
#
# オプション:
#   --width / --height   既定 172x320 (ポートレート)
#   --fit cover|contain  cover=全面を埋めて中央切抜き(既定) / contain=全体を収め余白
#   --bg R,G,B           contain時の余白色 (既定 0,0,0)

import argparse
import glob
import os
import sys

import numpy as np
from PIL import Image, ImageOps


def to_rgb565_be(img):
    """PIL RGB Image -> ビッグエンディアン RGB565 の bytes。"""
    a = np.asarray(img.convert("RGB"), dtype=np.uint16)  # (H, W, 3)
    r = (a[:, :, 0] >> 3) & 0x1F
    g = (a[:, :, 1] >> 2) & 0x3F
    b = (a[:, :, 2] >> 3) & 0x1F
    rgb565 = (r << 11) | (g << 5) | b           # uint16, ネイティブ
    return rgb565.astype(">u2").tobytes()        # ">u2" でビッグエンディアン化


def fit_image(img, w, h, mode, bg):
    img = img.convert("RGB")
    if mode == "cover":
        # 全面を埋めて中央クロップ
        return ImageOps.fit(img, (w, h), method=Image.LANCZOS)
    else:  # contain
        im = img.copy()
        im.thumbnail((w, h), Image.LANCZOS)
        canvas = Image.new("RGB", (w, h), bg)
        canvas.paste(im, ((w - im.width) // 2, (h - im.height) // 2))
        return canvas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+", help="入力画像 (glob可)")
    ap.add_argument("-o", "--out", default="images", help="出力ディレクトリ")
    ap.add_argument("--width", type=int, default=172)
    ap.add_argument("--height", type=int, default=320)
    ap.add_argument("--orient", choices=["portrait", "landscape"], default=None,
                    help="指定すると寸法を自動設定 (portrait=172x320 / landscape=320x172)")
    ap.add_argument("--fit", choices=["cover", "contain"], default="cover")
    ap.add_argument("--bg", default="0,0,0")
    args = ap.parse_args()

    if args.orient == "portrait":
        args.width, args.height = 172, 320
    elif args.orient == "landscape":
        args.width, args.height = 320, 172

    bg = tuple(int(x) for x in args.bg.split(","))
    os.makedirs(args.out, exist_ok=True)

    # glob 展開
    paths = []
    for pat in args.inputs:
        hit = glob.glob(pat)
        paths.extend(hit if hit else [pat])

    expect = args.width * args.height * 2
    n = 0
    for p in paths:
        if not os.path.isfile(p):
            print("skip (not found):", p, file=sys.stderr)
            continue
        img = Image.open(p)
        img = fit_image(img, args.width, args.height, args.fit, bg)
        data = to_rgb565_be(img)
        assert len(data) == expect, (len(data), expect)
        stem = os.path.splitext(os.path.basename(p))[0]
        outp = os.path.join(args.out, stem + ".raw")
        with open(outp, "wb") as f:
            f.write(data)
        print("%s -> %s  (%d bytes)" % (p, outp, len(data)))
        n += 1
    print("done: %d file(s), %dx%d, %d bytes each" % (n, args.width, args.height, expect))


if __name__ == "__main__":
    main()
