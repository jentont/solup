"""Аватарка бота SolUP в серии Solutions (см. «аватарки_промт_и_правила.md»).

Кот Solutions выглядывает из-за хромовой надписи SOLUP и кладёт лапы на буквы,
хромовое кольцо-орбита (задняя половина за котом, передняя — перед текстом),
акцент — синяя монета SolUP, по углам размытые подарки, тёмная студия, частицы, зерно.

Использует исходники серии из папки «аватарки» (кот, шрифт Anton, title2d.py, текстура хрома),
поэтому запускается только на машине, где эта папка есть:
    .venv/Scripts/python brand/make_avatar.py
Результат: brand/out/avatar/solup_avatar_{2048,1024,640}.png
"""

import math
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out" / "avatar"
AV = Path("G:/боты для тг общее/аватарки")
SRC = AV / "аватарка solutions shop" / "исходники"
sys.path.insert(0, str(SRC))
from title2d import title3d  # noqa: E402  (заголовок серии: хром, фаска, выдавка, блик)

ANTON = str(AV / "аватарка nakrut partners" / "исходники" / "fonts" / "AntonSC-Regular.ttf")
OSWALD = str(AV / "аватарка nakrut partners" / "исходники" / "fonts" / "Oswald.ttf")
CHROME_TEX = str(AV / "для аватарок конструктор" / "текстуры" / "жидкий_хром_01.jpg")
GIFTS = ROOT.parent / "webapp" / "public" / "gifts"

S = 2048
BRAND = np.array([0x29, 0x97, 0xFF], np.float32) / 255  # синий SolUP (тёмная тема)
rng = np.random.default_rng(7)


# ---------- композитинг (float RGB 0..1, прямая альфа) ----------
def over(dst, rgb, a, x=0, y=0):
    """Кладёт слой rgb/a на dst в точку (x, y) с обрезкой по краям."""
    h, w = a.shape
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, S), min(y + h, S)
    if x0 >= x1 or y0 >= y1:
        return
    sa = a[y0 - y:y1 - y, x0 - x:x1 - x, None]
    dst[y0:y1, x0:x1] = rgb[y0 - y:y1 - y, x0 - x:x1 - x] * sa + dst[y0:y1, x0:x1] * (1 - sa)


def screen(dst, rgb, x=0, y=0):
    h, w = rgb.shape[:2]
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, S), min(y + h, S)
    src = rgb[y0 - y:y1 - y, x0 - x:x1 - x]
    dst[y0:y1, x0:x1] = 1 - (1 - dst[y0:y1, x0:x1]) * (1 - src)


def gauss(sigma_x, cx, cy, sigma_y=None):
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    sy = sigma_y or sigma_x
    return np.exp(-(((xx - cx) / sigma_x) ** 2 + ((yy - cy) / sy) ** 2) / 2)


# ---------- фон: тёмная студия, луч сверху, пятно за заголовком, туман ----------
def background():
    bg = np.zeros((S, S, 3), np.float32) + np.array([0.022, 0.024, 0.032], np.float32)
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    shaft = np.exp(-((xx - S * 0.5) / (S * 0.13)) ** 2) * np.clip(1 - yy / (S * 0.95), 0, 1) ** 1.4
    bg += shaft[..., None] * np.array([0.16, 0.17, 0.2], np.float32)
    bg += gauss(S * 0.3, S * 0.5, S * 0.56, S * 0.17)[..., None] * np.array([0.13, 0.15, 0.2], np.float32)
    # мягкие горизонтальные «световые полосы» за заголовком, как в серии
    streak = gauss(S * 0.5, S * 0.5, S * 0.62, S * 0.035) * (0.6 + 0.4 * rng.random((1, S)).astype(np.float32))
    bg += cv2.GaussianBlur(streak, (0, 0), 3)[..., None] * np.array([0.1, 0.11, 0.13], np.float32)
    fog = cv2.GaussianBlur(rng.random((S // 16, S // 16)).astype(np.float32), (0, 0), 2)
    fog = cv2.resize(fog, (S, S), interpolation=cv2.INTER_CUBIC) * np.clip((yy - S * 0.62) / (S * 0.38), 0, 1)
    bg += fog[..., None] * 0.07
    return bg


# ---------- кот: силуэт по светящемуся контуру (как в wm.py серии) ----------
def load_cat():
    # cv2.imread не понимает кириллицу в пути, поэтому читаем байты
    raw = np.fromfile(str(SRC / "cat_gpt.png"), np.uint8)
    cat = cv2.imdecode(raw, cv2.IMREAD_COLOR).astype(np.float32)[..., ::-1] / 255
    lum = cat.mean(2)
    H0, W0 = lum.shape
    ledge = 862  # линия «полки», на которой лежат лапы
    rim = cv2.morphologyEx((lum > 0.18).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    rim[ledge - 2:ledge + 3, :] = 1
    ff = rim.copy()
    cv2.floodFill(ff, np.zeros((H0 + 2, W0 + 2), np.uint8), (5, 5), 2)
    sil = (ff != 2).astype(np.uint8)
    sil[ledge + 2:] = 0
    sil = sil.astype(np.float32)
    sil = cv2.GaussianBlur(sil, (0, 0), 1.2)
    halo = cat * (1 - sil[..., None])  # светящаяся кромка вокруг силуэта — кладём «экраном»
    halo[ledge - 6:] = 0
    # у полки светится её край — оставляем свечение только у лап
    shelf = np.ones(W0, bool)
    shelf[40:380] = shelf[880:1215] = False
    halo[790:, shelf] = 0
    return cat, sil, halo, ledge


# ---------- хромовое кольцо-орбита ----------
def ring_layers(cx, cy, rx, ry, angle):
    """Возвращает (задняя половина, передняя половина) как RGB-слои для screen-наложения."""
    def arc(a0, a1):
        lay = np.zeros((S, S), np.float32)
        for t, w in ((14, 0.25), (7, 0.6), (3, 1.0)):
            cv2.ellipse(lay, (int(cx * 16), int(cy * 16)), (int(rx * 16), int(ry * 16)), angle, a0, a1,
                        w, t, cv2.LINE_AA, 4)
        # ярче к боковым краям, как отражение в хроме
        yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
        side = 0.55 + 0.45 * np.clip(np.abs(xx - cx) / rx, 0, 1) ** 2
        lay = lay * side
        glow = cv2.GaussianBlur(lay, (0, 0), 18) * 0.7
        return np.clip(lay + glow, 0, 1)[..., None] * np.array([0.92, 0.95, 1.0], np.float32)
    # cv2: углы от оси x по часовой; верхняя (дальняя) половина — 180..360
    return arc(180, 360), arc(0, 180)


# ---------- синяя монета SolUP ----------
def coin_layer(d):
    """Монета с вырезанной галочкой вверх, с мягким объёмом и свечением. RGBA d×d."""
    ss = 4
    D = d * ss
    m = Image.new("L", (D, D), 0)
    dr = ImageDraw.Draw(m)
    dr.ellipse((0, 0, D - 1, D - 1), fill=255)
    r = D / 2
    w = r * 0.62
    pts = [(r - w, r + r * 0.2), (r, r - r * 0.32), (r + w, r + r * 0.2)]
    sw = int(r * 0.26)
    dr.line(pts, fill=0, width=sw, joint="curve")
    for x, y in (pts[0], pts[-1]):
        dr.ellipse((x - sw / 2, y - sw / 2, x + sw / 2, y + sw / 2), fill=0)
    a = np.asarray(m.resize((d, d), Image.LANCZOS), np.float32) / 255
    yy, xx = np.mgrid[0:d, 0:d].astype(np.float32) / d
    shade = 1.15 - 0.55 * np.sqrt((xx - 0.32) ** 2 + (yy - 0.28) ** 2)  # блик сверху-слева
    rgb = np.clip(BRAND[None, None] * shade[..., None], 0, 1)
    return rgb, a


# ---------- подарки по углам: размытые, приглушённые под палитру ----------
def blurred_gift(name, size, blur, sat=0.28, bright=0.5):
    im = Image.open(GIFTS / f"{name}.webp").convert("RGBA").resize((size, size), Image.LANCZOS)
    pad = int(blur * 4)  # поля, чтобы размытие не упиралось в край слоя
    canvas = Image.new("RGBA", (size + 2 * pad, size + 2 * pad), (0, 0, 0, 0))
    canvas.paste(im, (pad, pad))
    arr = np.asarray(canvas, np.float32) / 255
    rgb, a = arr[..., :3], arr[..., 3]
    grey = rgb.mean(2, keepdims=True)
    rgb = (grey + (rgb - grey) * sat) * bright
    rgb = cv2.GaussianBlur(rgb * a[..., None], (0, 0), blur)
    a = cv2.GaussianBlur(a, (0, 0), blur)
    rgb = np.where(a[..., None] > 1e-4, rgb / np.maximum(a[..., None], 1e-4), 0)
    return rgb, a, pad


def sparkle(dst, x, y, r, k=1.0):
    """Четырёхлучевая звёздочка-блик."""
    lay = np.zeros((S, S), np.float32)
    cv2.line(lay, (int(x - r), int(y)), (int(x + r), int(y)), 1.0, 3, cv2.LINE_AA)
    cv2.line(lay, (int(x), int(y - r)), (int(x), int(y + r)), 1.0, 3, cv2.LINE_AA)
    lay = cv2.GaussianBlur(lay, (0, 0), 1.2) + gauss(r * 0.18, x, y) * 1.2
    screen(dst, np.clip(lay * k, 0, 1)[..., None] * np.array([0.95, 0.97, 1.0], np.float32))


def main() -> None:
    img = background()

    # заголовок
    title_w = int(S * 0.78)
    T = title3d(["SOLUP"], ANTON, title_w, size=700, tex=CHROME_TEX, tex_amt=0.35, sweep=0.3)
    th, tw = T.shape[:2]
    tx, ty = (S - tw) // 2, int(S * 0.43)
    face_top = ty + int(title_w * 0.09)  # верх букв: в title3d холст имеет отступ P = 9% ширины

    # кольцо (задняя половина — до кота и текста)
    ring_back, ring_front = ring_layers(S * 0.5, S * 0.64, S * 0.47, S * 0.115, -7)
    screen(img, ring_back * 0.9)

    # кот за надписью
    cat, sil, halo, ledge = load_cat()
    k = 1.1
    cw = int(cat.shape[1] * k)
    cat_s = cv2.resize(cat, (cw, cw), interpolation=cv2.INTER_AREA)
    sil_s = cv2.resize(sil, (cw, cw), interpolation=cv2.INTER_AREA)
    halo_s = cv2.resize(halo, (cw, cw), interpolation=cv2.INTER_AREA)
    cx = (S - cw) // 2
    cy = face_top + int(S * 0.012) - int(ledge * k)  # полка чуть ниже верха букв: лапы лежат на буквах
    screen(img, halo_s, cx, cy)
    over(img, cat_s, sil_s, cx, cy)

    # сам заголовок
    over(img, T[..., :3], T[..., 3], tx, ty)

    # лапы поверх букв + мягкая тень от них на буквах.
    # Лапы вырезаются эллипсами с мягким краем (центр и радиусы — в координатах исходного кота)
    ch, cwid = sil_s.shape
    for (px, py, rx, ry) in ((212, 812, 168, 80), (1043, 812, 160, 80)):
        m = np.zeros((ch, cwid), np.float32)
        cv2.ellipse(m, (int(px * k), int(py * k)), (int(rx * k), int(ry * k)), 0, 0, 360, 1.0, -1, cv2.LINE_AA)
        m = cv2.GaussianBlur(m, (0, 0), 6) * sil_s
        m[int((ledge + 4) * k):] = 0
        shadow = cv2.GaussianBlur(m, (0, 0), 14) * 0.6
        over(img, np.zeros((ch, cwid, 3), np.float32), shadow, cx + 6, cy + 22)
        over(img, cat_s, m, cx, cy)
        # свечение кромки только вокруг лапы
        ring = cv2.GaussianBlur(m, (0, 0), 10)
        screen(img, halo_s * np.clip(ring * 2, 0, 1)[..., None], cx, cy)

    # подзаголовок: разрядка и тонкие линии по бокам
    sub = Image.new("L", (S, 200), 0)
    sd = ImageDraw.Draw(sub)
    f = ImageFont.truetype(OSWALD, 92)
    try:
        f.set_variation_by_name("SemiBold")
    except Exception:
        pass
    text = "G I F T S"
    w = sd.textlength(text, font=f)
    sd.text(((S - w) / 2, 30), text, font=f, fill=255)
    ly = 92
    sd.line([((S - w) / 2 - 200, ly), ((S - w) / 2 - 50, ly)], fill=255, width=6)
    sd.line([((S + w) / 2 + 50, ly), ((S + w) / 2 + 200, ly)], fill=255, width=6)
    sa = np.asarray(sub, np.float32) / 255
    sub_y = ty + th - int(th * 0.06)
    over(img, np.zeros((200, S, 3), np.float32), cv2.GaussianBlur(sa, (0, 0), 6) * 0.7, 0, sub_y + 10)
    over(img, np.full((200, S, 3), 0.9, np.float32), sa, 0, sub_y)

    # кольцо (передняя половина — поверх текста)
    screen(img, ring_front)

    # акцент: синяя монета у правого уха кота + свечение
    cd = int(S * 0.085)
    crgb, ca = coin_layer(cd)
    mx, my = int(S * 0.79), int(S * 0.2)
    screen(img, gauss(cd * 0.9, mx + cd / 2, my + cd / 2)[..., None] * BRAND * 0.55)
    over(img, crgb, ca, mx, my)

    # звёздочки-блики
    sparkle(img, S * 0.25, S * 0.4, 34)
    sparkle(img, S * 0.865, S * 0.375, 28, 0.9)
    sparkle(img, S * 0.955, S * 0.595, 40, 0.8)

    # передний план: размытые подарки по углам, частично срезаны рамкой
    for name, size, x, y, blur in (
        ("heartlocket", 640, -200, -170, 14),
        ("lootbag", 600, S - 380, -150, 12),
        ("durovscap", 700, -260, S - 440, 16),
        ("swisswatch", 640, S - 400, S - 400, 14),
    ):
        grgb, ga, pad = blurred_gift(name, size, blur)
        over(img, grgb, ga * 0.95, x - pad, y - pad)

    # частицы пыли
    lay = np.zeros((S, S), np.float32)
    for _ in range(260):
        x, y = rng.uniform(0, S), rng.uniform(0, S)
        r = rng.uniform(1.2, 4.5)
        cv2.circle(lay, (int(x), int(y)), int(r), float(rng.uniform(0.25, 1.0)), -1, cv2.LINE_AA)
    lay = cv2.GaussianBlur(lay, (0, 0), 1.6) * 0.55
    screen(img, lay[..., None] * np.array([0.9, 0.93, 1.0], np.float32))

    # мягкая виньетка, приподнятые средние тона, плёночное зерно
    vig = gauss(S * 0.62, S * 0.5, S * 0.48)
    img *= (0.55 + 0.45 * vig)[..., None]
    img = np.clip(img, 0, 1) ** 0.94
    img = np.clip(img + rng.normal(0, 0.018, (S, S, 1)).astype(np.float32), 0, 1)

    OUT.mkdir(parents=True, exist_ok=True)
    full = Image.fromarray((img * 255).astype(np.uint8))
    for px in (2048, 1024, 640):
        full.resize((px, px), Image.LANCZOS).save(OUT / f"solup_avatar_{px}.png", optimize=True)
    print("ok:", OUT)


if __name__ == "__main__":
    main()
