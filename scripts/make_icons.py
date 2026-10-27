"""ホーム画面用アイコン（にこにこ園舎）の PNG を web/ に書き出す。

web/icon.svg と同じ絵を Pillow で描く。座標は 100×100 の方眼で書いて、
大きく描いてから縮小し、ふちをなめらかにする。
"""
from pathlib import Path

from PIL import Image, ImageDraw

WEB = Path(__file__).resolve().parent.parent / "web"

BG = "#fff3d6"
ROOF = "#ff7a8a"
WALL = "#ffffff"
WALL_LINE = "#ffb3bd"
FACE = "#3b2a1a"
CHEEK = "#ffb3bd"
SUN = "#ffe066"


def draw_icon(size, content_scale=1.0):
    ss = 4  # 4倍で描いて縮小する
    big = size * ss
    img = Image.new("RGB", (big, big), BG)
    d = ImageDraw.Draw(img)

    def p(x, y):
        # 中心(50,50)を基準に縮める。マスク用アイコンは絵を小さめにして、丸く切られても欠けないように
        x = 50 + (x - 50) * content_scale
        y = 50 + (y - 50) * content_scale
        return (x * big / 100, y * big / 100)

    def u(v):
        return v * content_scale * big / 100

    def dot(x, y, r, fill):
        cx, cy = p(x, y)
        d.ellipse([cx - u(r), cy - u(r), cx + u(r), cy + u(r)], fill=fill)

    # 屋根（角を丸く見せるため、頂点に丸を置く）
    roof = [p(18, 50), p(50, 22), p(82, 50)]
    d.polygon(roof, fill=ROOF)
    d.line(roof + [roof[0]], fill=ROOF, width=round(u(6)))
    for x, y in [(18, 50), (50, 22), (82, 50)]:
        dot(x, y, 3, ROOF)

    # 屋根の丸窓
    dot(50, 38, 5, SUN)

    # 壁
    x0, y0 = p(27, 47)
    x1, y1 = p(73, 82)
    d.rounded_rectangle([x0, y0, x1, y1], radius=u(6), fill=WALL, outline=WALL_LINE, width=round(u(3)))

    # 顔
    dot(41, 60, 3.5, FACE)
    dot(59, 60, 3.5, FACE)
    dot(35, 67, 3.5, CHEEK)
    dot(65, 67, 3.5, CHEEK)
    smile = []
    for i in range(21):
        t = i / 20
        x = (1 - t) ** 2 * 44 + 2 * (1 - t) * t * 50 + t ** 2 * 56
        y = (1 - t) ** 2 * 67 + 2 * (1 - t) * t * 73 + t ** 2 * 67
        smile.append(p(x, y))
    d.line(smile, fill=FACE, width=round(u(3)), joint="curve")
    dot(44, 67, 1.5, FACE)
    dot(56, 67, 1.5, FACE)

    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    draw_icon(180).save(WEB / "icon-180.png")  # iPhone 用
    draw_icon(192).save(WEB / "icon-192.png")
    draw_icon(512).save(WEB / "icon-512.png")
    draw_icon(512, content_scale=0.8).save(WEB / "icon-maskable-512.png")  # Android の丸切り抜き用
    print("書き出しました:", WEB)
