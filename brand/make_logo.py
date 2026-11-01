"""Логотип SolUP в стиле Solutions Design.

Слово «solup» строчными, одним цветом, шрифтом Lilita One (как «Solutions» в Mirrows).
Буква «o» заменена знаком — синей монетой с вырезанной галочкой вверх: это и «o»,
и наша валюта, и «up» без отдельной стрелки. Под словом рукописное «gifts» (Caveat)
с наклоном — так же, как «Design» в Solutions Design.

Запуск: .venv/Scripts/python brand/make_logo.py
Результат: brand/out/*.svg, *.png; копии для Mini App — в webapp/public/brand/.
"""

import math
import shutil
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
WEB = ROOT.parent / "webapp" / "public" / "brand"
LILITA = TTFont(ROOT / "fonts" / "LilitaOne.ttf")
CAVEAT = instantiateVariableFont(TTFont(ROOT / "fonts" / "Caveat.ttf"), {"wght": 700})

THEMES = {
    "light": {"text": "#1D1D1F", "brand": "#0071E3", "hand": "#0071E3"},
    "dark": {"text": "#F5F5F7", "brand": "#2997FF", "hand": "#64B2FF"},
}

# Геометрия в единицах шрифта Lilita (1000 на кегль), базовая линия y=0, ось y вверх
COIN_R = 262          # радиус монеты: чуть больше «o», чтобы читалась как знак
COIN_CY = 250         # центр по высоте строчных
HAND_SIZE = 0.62      # кегль «gifts» относительно основного
HAND_ANGLE = -6       # наклон рукописной подписи, градусы


def glyph_path(font: TTFont, text: str, x: float, y: float, k: float, rot: float = 0, origin=(0, 0)) -> tuple[str, float]:
    """Контур строки в координатах SVG (ось y вниз). Возвращает (d, ширина в единицах SVG)."""
    gs, cmap = font.getGlyphSet(), font.getBestCmap()
    pen = SVGPathPen(gs)
    a = math.radians(rot)
    ca, sa = math.cos(a), math.sin(a)
    cursor = 0.0
    for ch in text:
        name = cmap[ord(ch)]
        # масштаб с переворотом оси y, затем поворот вокруг origin
        gx, gy = x + cursor * k - origin[0], y - origin[1]
        t = (k * ca, k * sa, k * sa, -k * ca, origin[0] + gx * ca - gy * sa, origin[1] + gx * sa + gy * ca)
        gs[name].draw(TransformPen(pen, t))
        cursor += gs[name].width
    return pen.getCommands(), cursor * k


def coin_svg(cx: float, cy: float, r: float, color: str, mask_id: str) -> str:
    """Монета с вырезанной галочкой вверх (вырез — через маску, фон просвечивает)."""
    w = r * 0.62
    chevron = f"M{cx - w:.1f},{cy + r * 0.2:.1f} L{cx:.1f},{cy - r * 0.32:.1f} L{cx + w:.1f},{cy + r * 0.2:.1f}"
    return (f'<mask id="{mask_id}"><rect x="{cx - r - 1:.1f}" y="{cy - r - 1:.1f}" width="{2 * r + 2:.1f}" '
            f'height="{2 * r + 2:.1f}" fill="#fff"/><path d="{chevron}" fill="none" stroke="#000" '
            f'stroke-width="{r * 0.26:.1f}" stroke-linecap="round" stroke-linejoin="round"/></mask>'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{color}" mask="url(#{mask_id})"/>')


def layout(size: float = 100):
    """Раскладка «s ● lup» + «gifts» под концом слова. Координаты SVG, базовая линия на y=size."""
    k = size / 1000
    base = size
    gs, cmap = LILITA.getGlyphSet(), LILITA.getBestCmap()
    w_s = gs[cmap[ord("s")]].width * k
    w_o = gs[cmap[ord("o")]].width * k
    d_s, _ = glyph_path(LILITA, "s", 0, base, k)
    coin = (w_s + w_o / 2 + 4 * k, base - COIN_CY * k, COIN_R * k)
    d_lup, w_lup = glyph_path(LILITA, "lup", w_s + w_o + 8 * k, base, k)
    word_w = w_s + w_o + 8 * k + w_lup
    # «gifts»: правым краем под концом слова, чуть заходит на нижний вынос «p»
    hk = size * HAND_SIZE / CAVEAT["head"].unitsPerEm
    _, w_hand = glyph_path(CAVEAT, "gifts", 0, 0, hk)
    hx, hy = word_w - w_hand + size * 0.05, base + size * 0.5
    d_hand, _ = glyph_path(CAVEAT, "gifts", hx, hy, hk, rot=HAND_ANGLE, origin=(hx + w_hand / 2, hy))
    box = (-size * 0.04, base - 0.74 * size, word_w + size * 0.1, hy + size * 0.2)
    return {"s": d_s, "lup": d_lup, "coin": coin, "hand": d_hand, "box": box}


def svg_logo(theme: str, with_hand: bool = True) -> str:
    c = THEMES[theme]
    L = layout()
    x0, y0, x1, y1 = L["box"]
    if not with_hand:
        y1 = 100 + 0.22 * 100
    cx, cy, r = L["coin"]
    hand = f'<path fill="{c["hand"]}" d="{L["hand"]}"/>' if with_hand else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0:.1f} {y0:.1f} {x1 - x0:.1f} {y1 - y0:.1f}">'
            f'<path fill="{c["text"]}" d="{L["s"]}"/>{coin_svg(cx, cy, r, c["brand"], "cut-" + theme)}'
            f'<path fill="{c["text"]}" d="{L["lup"]}"/>{hand}</svg>\n')


def svg_mark(theme: str) -> str:
    """Отдельный знак-монета: иконка, фавикон, эмодзи."""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
            f'{coin_svg(50, 50, 48, THEMES[theme]["brand"], "cut-mark")}</svg>\n')


def draw_coin(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float, color: str, bg) -> None:
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
    w = r * 0.62
    pts = [(cx - w, cy + r * 0.2), (cx, cy - r * 0.32), (cx + w, cy + r * 0.2)]
    sw = int(r * 0.26)
    d.line(pts, fill=bg, width=sw, joint="curve")
    for x, y in (pts[0], pts[-1]):
        d.ellipse((x - sw / 2, y - sw / 2, x + sw / 2, y + sw / 2), fill=bg)


def png_avatar(px: int = 640) -> Image.Image:
    """Аватарка бота: тёмная, с узором стикеров Solutions; монета-знак и подпись."""
    c = THEMES["dark"]
    ss = 3
    w = h = px * ss
    bg = (29, 29, 31, 255)
    img = Image.new("RGBA", (w, h), bg)
    pat = Image.open(WEB / "pattern.png").convert("RGBA").resize((w // 2, h // 2))
    layer = Image.new("RGBA", pat.size, (255, 255, 255, 255))
    layer.putalpha(pat.getchannel("A").point(lambda a: int(a * 0.07)))
    for ty in range(0, h, pat.size[1]):
        for tx in range(0, w, pat.size[0]):
            img.alpha_composite(layer, (tx, ty))
    d = ImageDraw.Draw(img)
    # монета крупно по центру (Telegram обрежет аватарку в круг)
    r = w * 0.19
    cx, cy = w / 2, h * 0.37
    draw_coin(d, cx, cy, r, c["brand"], bg)
    f_word = ImageFont.truetype(str(ROOT / "fonts" / "LilitaOne.ttf"), int(w * 0.18))
    f_hand = ImageFont.truetype(str(ROOT / "fonts" / "Caveat.ttf"), int(w * 0.105))
    f_hand.set_variation_by_axes([700])
    word = "solup"
    bw = d.textbbox((0, 0), word, font=f_word)
    d.text(((w - (bw[2] - bw[0])) / 2 - bw[0], h * 0.6 - bw[1]), word, font=f_word, fill=c["text"])
    # рукописная подпись — отдельным слоем с наклоном
    hb = d.textbbox((0, 0), "gifts", font=f_hand)
    tag = Image.new("RGBA", (hb[2] + 20, hb[3] + 20), (0, 0, 0, 0))
    ImageDraw.Draw(tag).text((10 - hb[0], 10 - hb[1]), "gifts", font=f_hand, fill=c["hand"])
    tag = tag.rotate(-HAND_ANGLE, resample=Image.BICUBIC, expand=True)
    img.alpha_composite(tag, (int(w / 2 + (bw[2] - bw[0]) / 2 - tag.width * 0.8), int(h * 0.6 + (bw[3] - bw[1]) * 0.78)))
    return img.resize((px, px), Image.LANCZOS)


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    for theme in THEMES:
        (OUT / f"solup-{theme}.svg").write_text(svg_logo(theme), encoding="utf-8")
        (OUT / f"solup-word-{theme}.svg").write_text(svg_logo(theme, with_hand=False), encoding="utf-8")
        (OUT / f"solup-mark-{theme}.svg").write_text(svg_mark(theme), encoding="utf-8")
    png_avatar().save(OUT / "solup-avatar.png")
    WEB.mkdir(parents=True, exist_ok=True)
    for old in WEB.glob("solup-inline-*.svg"):
        old.unlink()
    for name in ("solup-light.svg", "solup-dark.svg", "solup-word-light.svg", "solup-word-dark.svg", "solup-mark-light.svg"):
        shutil.copy(OUT / name, WEB / name)
    print("ok:", ", ".join(sorted(p.name for p in OUT.iterdir())))


if __name__ == "__main__":
    main()
