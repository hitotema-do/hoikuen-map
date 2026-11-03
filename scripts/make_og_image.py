"""LINE や X でリンクを送ったときに出るカード画像（web/og.png, 1200x630）を作る。

    python scripts/make_og_image.py

右側は地図の「絵」で、本物の地図ではない（地図データの出典表示が要らないように）。
画像は固定なので、月の名前などすぐ古くなる情報は入れない。
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "og.png"
ICON = ROOT / "web" / "icon-512.png"
FONT_R = "C:/Windows/Fonts/BIZ-UDGothicR.ttc"
FONT_B = "C:/Windows/Fonts/BIZ-UDGothicB.ttc"

S = 2  # 2倍で描いて縮小（線をなめらかにするため）
W, H = 1200 * S, 630 * S

BG = "#F6F7F9"
INK = "#1F2933"
SUB = "#52606D"
LINE = "#D9E2EC"
ACCENT = "#2563EB"
# ピンの色はアプリと同じ（1〜2人は黄色に黒い字、3人以上は緑に白い字、0は灰色）
FEW = "#FBBF24"
MANY = "#15803D"
ZERO = "#7B8794"
# 地図の絵の色
LAND = "#EEF0EC"
RIVER = "#CFE3F1"
ROAD = "#FFFFFF"
PARK = "#DCEBD5"


def font(path, size):
    return ImageFont.truetype(path, size * S)


def px(*v):
    return [x * S for x in v]


img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

# ---- 左：アイコン・名前・説明 ----
ix, iy, isz = 80, 82, 112
icon = Image.open(ICON).convert("RGB").resize((isz * S, isz * S), Image.LANCZOS)
mask = Image.new("L", icon.size, 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, isz * S - 1, isz * S - 1], radius=26 * S, fill=255)
img.paste(icon, (ix * S, iy * S), mask)
d.rounded_rectangle(px(ix, iy, ix + isz, iy + isz), radius=26 * S, outline=LINE, width=2 * S)

d.text(px(80, 232), "広島市", font=font(FONT_B, 44), fill=INK)
d.text(px(78, 286), "保育園空きマップ", font=font(FONT_B, 66), fill=INK)
d.text(px(82, 380), "保育園の空き状況が、", font=font(FONT_R, 36), fill=INK)
d.text(px(82, 428), "地図でひと目でわかる。", font=font(FONT_R, 36), fill=INK)

# 特徴のタグ
tx = 82
for label in ("全8区対応", "毎月更新", "無料", "登録不要"):
    f = font(FONT_B, 22)
    w = d.textlength(label, font=f) / S
    d.rounded_rectangle(px(tx, 498, tx + w + 30, 542), radius=22 * S, fill="white", outline=LINE, width=2 * S)
    d.text(px(tx + 15, 508), label, font=f, fill=ACCENT)
    tx += w + 30 + 10

d.text(px(82, 570), "非公式アプリ ／ 広島市の公開資料をもとに作成", font=font(FONT_R, 20), fill=SUB)

# ---- 右：アプリ画面の見本（地図の絵） ----
cx, cy, cw, ch = 690, 56, 440, 518
card = Image.new("RGB", (cw * S, ch * S), LAND)
c = ImageDraw.Draw(card)


def cp(*v):
    return [x * S for x in v]


# 公園
c.rounded_rectangle(cp(300, 330, 400, 420), radius=18 * S, fill=PARK)
c.rounded_rectangle(cp(30, 420, 130, 500), radius=18 * S, fill=PARK)
# 川（広島らしく、何本も南へ流れる）
for pts in ([(70, 120), (95, 260), (80, 400), (110, 540)],
            [(210, 120), (190, 280), (225, 420), (205, 540)],
            [(350, 120), (375, 250), (340, 380), (370, 540)]):
    c.line([(x * S, y * S) for x, y in pts], fill=RIVER, width=26 * S, joint="curve")
# 道
for y in (180, 300, 460):
    c.line(cp(0, y, cw, y + 14), fill=ROAD, width=9 * S)
for x in (140, 290):
    c.line(cp(x, 120, x - 18, ch), fill=ROAD, width=9 * S)

# 上：検索窓とボタン
c.rectangle(cp(0, 0, cw, 122), fill="white")
c.rounded_rectangle(cp(18, 18, cw - 18, 64), radius=23 * S, fill="white", outline=LINE, width=2 * S)
c.ellipse(cp(36, 32, 52, 48), outline=SUB, width=3 * S)
c.line(cp(50, 46, 57, 53), fill=SUB, width=3 * S)
c.text(cp(68, 30), "園の名前・地域で探す", font=font(FONT_R, 18), fill=SUB)
chip_x = 18
for label, on in (("1歳", True), ("空き状況", False), ("区・種類", False)):
    # ▾ はこの書体に無いので三角を描く
    f = font(FONT_B if on else FONT_R, 17)
    w = c.textlength(label, font=f) / S + 18
    col = "white" if on else INK
    c.rounded_rectangle(cp(chip_x, 76, chip_x + w + 28, 110), radius=17 * S,
                        fill=INK if on else "white", outline=None if on else LINE, width=2 * S)
    c.text(cp(chip_x + 14, 83), label, font=f, fill=col)
    tri_x = chip_x + 14 + w - 10
    c.polygon(cp(tri_x - 5, 90, tri_x + 5, 90, tri_x, 97), fill=col)
    chip_x += w + 28 + 8
c.line(cp(0, 122, cw, 122), fill=LINE, width=2 * S)

# ピン（影を付けてから丸と数字）
pins = [(118, 170, 3), (255, 205, 1), (60, 300, 0), (170, 345, 5), (318, 290, 2),
        (390, 200, 0), (250, 420, 0), (95, 470, 2), (395, 470, 4), (300, 490, 0), (160, 255, 0)]
shadow = Image.new("L", card.size, 0)
sd = ImageDraw.Draw(shadow)
for x, y, n in pins:
    r = 21 if n else 13
    sd.ellipse(cp(x - r, y - r + 3, x + r, y + r + 3), fill=110)
shadow = shadow.filter(ImageFilter.GaussianBlur(4 * S))
card.paste(Image.new("RGB", card.size, "#000000"), (0, 0), shadow)
for x, y, n in pins:
    r = 21 if n else 13
    fill = MANY if n >= 3 else FEW if n >= 1 else ZERO
    c.ellipse(cp(x - r, y - r, x + r, y + r), fill="white")
    c.ellipse(cp(x - r + 3, y - r + 3, x + r - 3, y + r - 3), fill=fill)
    c.text((x * S, y * S), str(n), font=font(FONT_B, 20 if n else 13),
           fill="white" if n >= 3 or n == 0 else INK, anchor="mm")

cmask = Image.new("L", card.size, 0)
ImageDraw.Draw(cmask).rounded_rectangle([0, 0, cw * S - 1, ch * S - 1], radius=28 * S, fill=255)
img.paste(card, (cx * S, cy * S), cmask)
d.rounded_rectangle(px(cx, cy, cx + cw, cy + ch), radius=28 * S, outline=LINE, width=2 * S)

img.resize((1200, 630), Image.LANCZOS).save(OUT, optimize=True)
print(f"→ {OUT}")
