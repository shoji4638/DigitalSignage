# news.py  (Pico 2W / MicroPython)
# RSS フィードから見出しを取得してティッカー用の文字列を作る。
# 8x8内蔵フォントはASCIIのみなので、非ASCII文字は除去/置換する。
# 日本語見出しを出すには日本語ビットマップフォントの導入が別途必要(Phase 2b)。

import netlib

# 既定は英語フィード(ASCIIで内蔵フォントに乗る)。任意のRSSに変更可。
DEFAULT_RSS = "https://feeds.bbci.co.uk/news/world/rss.xml"

_ENT = {"&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"',
        "&#39;": "'", "&apos;": "'", "&#x27;": "'", "&nbsp;": " "}


def _unescape(s):
    for k, v in _ENT.items():
        s = s.replace(k, v)
    return s


def _ascii_only(s):
    out = []
    for ch in s:
        o = ord(ch)
        if 32 <= o < 127:
            out.append(ch)
        elif ch in "“”":
            out.append('"')
        elif ch in "‘’":
            out.append("'")
        elif ch in "–—":
            out.append("-")
        else:
            pass  # その他の非ASCIIは捨てる
    return "".join(out)


def _titles(xml, maxn):
    titles = []
    pos = xml.find("<item")
    if pos < 0:
        pos = xml.find("<entry")   # Atom
    if pos < 0:
        pos = 0
    while len(titles) < maxn:
        t0 = xml.find("<title", pos)
        if t0 < 0:
            break
        s = xml.find(">", t0) + 1
        e = xml.find("</title>", s)
        if e < 0:
            break
        t = xml[s:e].replace("<![CDATA[", "").replace("]]>", "")
        t = _ascii_only(_unescape(t)).strip()
        if t:
            titles.append(t)
        pos = e + 8
    return titles


def fetch(rss=DEFAULT_RSS, maxn=8, sep="   ***   "):
    code, text = netlib.get_text(rss, max_bytes=60000)
    if code != 200:
        raise OSError("news HTTP %d" % code)
    titles = _titles(text, maxn)
    if not titles:
        return ""
    return (sep.join(titles) + sep).upper()


if __name__ == "__main__":
    print(fetch())
