"""Запись HTML-анимаций SolUP в видео: страница рисует кадр по renderAt(t),
Edge в фоне снимает кадры, ffmpeg собирает видео и звук.

    .venv/Scripts/python promo/render.py insert            # вставка: тёмная, зелёная, прозрачная + звук
    .venv/Scripts/python promo/render.py promo             # промо-ролик
    .venv/Scripts/python promo/render.py insert --frames 0.7 2.6 4.6 6.3   # отдельные кадры для проверки

Результат — в promo/out/.
"""

import argparse
import math
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
SR = 48000

# страница, размер в CSS-пикселях, масштаб (итог = размер × масштаб), fps, версии
JOBS = {
    "insert": {"page": "insert.html", "size": (1280, 672), "scale": 1.5, "fps": 60, "variants": ["dark", "green", "alpha"]},
    "promo": {"page": "promo.html", "size": (1280, 720), "scale": 1.5, "fps": 30, "variants": ["dark"]},
}


# ---------- звук: короткие синтетические эффекты по меткам страницы ----------
def env(n, attack, decay):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(attack, 1e-4)) * np.exp(-t / decay)


def tone(freq, dur, attack=0.004, decay=0.12, kind="sine"):
    n = int(dur * SR)
    t = np.arange(n) / SR
    ph = 2 * np.pi * freq * t
    w = np.sin(ph) if kind == "sine" else np.sign(np.sin(ph)) * 0.4 + np.sin(ph) * 0.6
    return w * env(n, attack, decay)


def mix(*parts):
    """Складывает звуки разной длины."""
    out = np.zeros(max(len(x) for x in parts))
    for x in parts:
        out[: len(x)] += x
    return out


def sfx(kind, rng):
    if kind == "tick":  # щелчок рулетки
        n = int(0.03 * SR)
        click = rng.normal(0, 1, n) * env(n, 0.0005, 0.004)
        return mix(0.35 * click, 0.25 * tone(2400, 0.03, 0.0005, 0.006))
    if kind == "tap":
        return mix(0.5 * tone(900, 0.08, 0.001, 0.02), 0.2 * tone(1800, 0.05, 0.001, 0.01))
    if kind == "key":
        n = int(0.04 * SR)
        return mix(0.25 * rng.normal(0, 1, n) * env(n, 0.0005, 0.008), 0.15 * tone(1300, 0.04, 0.001, 0.01))
    if kind == "pop":
        n = int(0.18 * SR)
        f = np.linspace(300, 900, n)
        return 0.45 * np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.002, 0.06)
    if kind == "whoosh":
        n = int(0.7 * SR)
        noise = rng.normal(0, 1, n)
        k = np.convolve(noise, np.ones(40) / 40, mode="same")  # мягкий шум
        shape = np.sin(np.linspace(0, np.pi, n)) ** 2
        return 0.5 * k * shape
    if kind in ("win", "win2"):  # «дзынь»: мажорное арпеджио
        notes = [784, 988, 1175, 1568] if kind == "win2" else [659, 831, 988]
        out = np.zeros(int(0.9 * SR))
        for i, f in enumerate(notes):
            s = int(i * 0.06 * SR)
            n = mix(tone(f, 0.8, 0.003, 0.35), 0.3 * tone(f * 2, 0.6, 0.003, 0.2))
            out[s:s + len(n)] += n[: len(out) - s] * 0.35
        return out
    return np.zeros(1)


def build_audio(cues, duration, path):
    rng = np.random.default_rng(3)
    mix = np.zeros(int((duration + 1) * SR))
    for c in cues:
        s = sfx(c["k"], rng)
        i = int(c["t"] * SR)
        mix[i:i + len(s)] += s[: len(mix) - i]
    mix = mix[: int(duration * SR)]
    mix = np.tanh(mix * 1.2) * 0.8  # мягкий лимитер
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())


# ---------- кадры ----------
def open_page(p, job, bg):
    b = p.chromium.launch(channel="msedge", headless=True)
    w, h = job["size"]
    pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=job["scale"])
    pg.goto((HERE / job["page"]).as_uri() + f"?capture&bg={bg}")
    pg.evaluate("document.fonts.ready")
    pg.wait_for_function("[...document.images].every(i => i.complete)")
    pg.wait_for_timeout(500)
    return b, pg


def shot(pg, t, alpha):
    pg.evaluate(f"renderAt({t})")
    return pg.locator("#stage").screenshot(omit_background=alpha, animations="disabled")


def render(name, frames_only=None):
    job = JOBS[name]
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        if frames_only:
            b, pg = open_page(p, job, "dark")
            for t in frames_only:
                (OUT / f"{name}_frame_{t:.2f}.png").write_bytes(shot(pg, t, False))
            b.close()
            print("кадры:", OUT)
            return

        alpha = "alpha" in job["variants"]
        b, pg = open_page(p, job, "alpha" if alpha else "dark")
        duration = pg.evaluate("window.DURATION")
        cues = pg.evaluate("window.SFX || []")
        fps = job["fps"]
        n = int(round(duration * fps))
        tmp = OUT / f"_{name}_frames"
        # кадры с прошлого запуска переиспользуем, если их ровно столько, сколько нужно
        done = tmp.exists() and len(list(tmp.glob("*.png"))) == n
        if tmp.exists() and not done:
            shutil.rmtree(tmp)
        tmp.mkdir(exist_ok=True)
        for i in range(0 if not done else n, n):
            (tmp / f"{i:05d}.png").write_bytes(shot(pg, i / fps, alpha))
            if i % 60 == 0:
                print(f"{name}: кадр {i}/{n}")
        bg_png = None
        if alpha and "dark" in job["variants"]:
            # фон для тёмной версии: та же страница, панель скрыта
            pg.goto((HERE / job["page"]).as_uri() + "?capture&bg=dark")
            pg.evaluate("document.querySelector('.panel').style.visibility='hidden'")
            bg_png = OUT / f"_{name}_bg.png"
            bg_png.write_bytes(pg.locator("#stage").screenshot())
        b.close()

    wav = OUT / f"_{name}.wav"
    build_audio(cues, duration, wav)
    seq = str(tmp / "%05d.png")
    base = ["ffmpeg", "-v", "error", "-y", "-framerate", str(fps), "-i", seq]
    for v in job["variants"]:
        if v == "alpha":
            # ProRes 4444 с прозрачностью — открывается в Premiere, After Effects, DaVinci, CapCut
            subprocess.run(base + ["-i", str(wav), "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
                                   "-c:a", "pcm_s16le", "-shortest", str(OUT / f"solup-{name}-alpha.mov")], check=True)
            subprocess.run(base + ["-i", str(wav), "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "6M",
                                   "-c:a", "libopus", "-shortest", str(OUT / f"solup-{name}-alpha.webm")], check=True)
        else:
            if v == "green":
                under = ["-f", "lavfi", "-i", f"color=c=0x00FF00:s={int(job['size'][0] * job['scale'])}x{int(job['size'][1] * job['scale'])}:r={fps}"]
            elif bg_png:
                under = ["-loop", "1", "-framerate", str(fps), "-i", str(bg_png)]
            else:
                under = None
            if under:
                cmd = ["ffmpeg", "-v", "error", "-y"] + under + ["-framerate", str(fps), "-i", seq, "-i", str(wav),
                       "-filter_complex", "[0][1]overlay=shortest=1,format=yuv420p", "-map", "2:a"]
            else:
                cmd = base + ["-i", str(wav), "-pix_fmt", "yuv420p"]
            cmd += ["-c:v", "libx264", "-crf", "16", "-preset", "slow", "-c:a", "aac", "-b:a", "192k", "-shortest",
                    "-movflags", "+faststart", str(OUT / f"solup-{name}-{'green-screen' if v == 'green' else 'original'}.mp4")]
            subprocess.run(cmd, check=True)
    shutil.rmtree(tmp)
    for f in (wav, bg_png):
        if f and f.exists():
            f.unlink()
    print("готово:", OUT)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("name", choices=JOBS)
    ap.add_argument("--frames", nargs="*", type=float)
    a = ap.parse_args()
    render(a.name, a.frames)
