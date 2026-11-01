// Мини-движок анимации: вся картинка — функция времени renderAt(t).
// В браузере ролик проигрывается по кругу; render.py открывает страницу с ?capture
// и вызывает renderAt(t) покадрово, поэтому запись получается без рывков.

const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, k) => a + (b - a) * k;
const seg = (t, a, b) => clamp((t - a) / (b - a));
const ease = {
  out3: (k) => 1 - Math.pow(1 - k, 3),
  out5: (k) => 1 - Math.pow(1 - k, 5),
  inOut: (k) => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2),
  back: (k) => { const c = 1.7; return 1 + (c + 1) * Math.pow(k - 1, 3) + c * Math.pow(k - 1, 2); },
};
const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];

function css(el, props) {
  for (const k in props) el.style[k] = props[k];
}

// Видимость сцены [a, b] с плавным входом/выходом
function sceneVis(t, a, b, fin = 0.35, fout = 0.35) {
  if (t < a || t > b) return 0;
  return Math.min(fin ? seg(t, a, a + fin) : 1, fout ? 1 - seg(t, b - fout, b) : 1);
}

// Появление элемента: сдвиг снизу + прозрачность
function rise(el, t, start, dur = 0.5, dy = 24) {
  const k = ease.out3(seg(t, start, start + dur));
  css(el, { opacity: k, transform: `translateY(${(1 - k) * dy}px)` });
}

// Детерминированный «случайный» генератор, чтобы кадры совпадали при каждом рендере
function rand(seed) {
  let s = seed >>> 0;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}

// Фон: свечение, узор, пылинки — одинаковый во всех роликах
function buildBackground(stage, n = 46) {
  stage.insertAdjacentHTML("afterbegin", '<div class="bg-glow"></div><div class="bg-pattern"></div><div class="dust-layer"></div>');
  const layer = $(".dust-layer", stage);
  const r = rand(5);
  const dust = [];
  for (let i = 0; i < n; i++) {
    const d = document.createElement("i");
    d.className = "dust";
    const size = 1.5 + r() * 3;
    css(d, { width: size + "px", height: size + "px", filter: `blur(${r() * 1.2}px)` });
    layer.appendChild(d);
    dust.push({ el: d, x: r() * 1280, y: r() * 720, sp: 8 + r() * 22, ph: r() * 6.28, a: 0.25 + r() * 0.6 });
  }
  stage.insertAdjacentHTML("beforeend", '<div class="vignette"></div>');
  return (t, loop = 0) => {
    // при loop>0 пылинки движутся с периодом loop секунд — бесшовный цикл
    const T = loop || 1e9;
    for (const p of dust) {
      const k = (t % T) / T;
      const y = loop ? (p.y - k * 720 * Math.round(p.sp / 10 + 1) + 7200) % 720 : (p.y - t * p.sp + 7200) % 720;
      const x = p.x + Math.sin(t * 0.6 + p.ph) * 10;
      css(p.el, { transform: `translate(${x}px, ${y}px)`, opacity: p.a * (0.6 + 0.4 * Math.sin(t * 2 + p.ph)) });
    }
    css($(".bg-pattern", stage), { transform: `translateY(${-((t * 6) % 300)}px)` });
  };
}

function boot(duration, render) {
  window.DURATION = duration;
  window.renderAt = render;
  render(0);
  if (new URLSearchParams(location.search).has("capture")) return;
  const t0 = performance.now();
  const loop = () => {
    render(((performance.now() - t0) / 1000) % duration);
    requestAnimationFrame(loop);
  };
  document.fonts.ready.then(loop);
}

const GIFT = (name) => `../webapp/public/gifts/${name}.webp`;
