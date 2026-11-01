import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useApp } from "../App";
import { Footer } from "../components/Footer";
import { SecTitle } from "../components/ui";

type Slide = { hand: string; title: string; text: string; img: string; tab: string; cta: string };

const SLIDES: Slide[] = [
  { hand: "бесплатно", title: "Подарок дня.", text: "Заходи раз в сутки и забирай монеты", img: "homemadecake", tab: "bonus", cta: "Забрать" },
  { hand: "рискнёшь?", title: "Апгрейд до ×20.", text: "Меняй дешёвые подарки на дорогие", img: "swisswatch", tab: "upgrade", cta: "Играть" },
  { hand: "навсегда", title: "Зови друзей.", text: "Процент с каждого их пополнения", img: "preciouspeach", tab: "ref", cta: "Позвать" },
];

type Game = { tab: string; key?: string; title: string; hint: string; imgs: string[] };

const GAMES: Game[] = [
  { tab: "upgrade", key: "upgrade", title: "Апгрейд", hint: "дешёвое в дорогое", imgs: ["swisswatch", "diamondring"] },
  { tab: "crash", key: "crash", title: "Краш", hint: "успей забрать", imgs: ["durovscap", "jellybunny"] },
  { tab: "cases", key: "cases", title: "Кейсы", hint: "5 кейсов с подарками", imgs: ["lootbag", "plushpepe"] },
  { tab: "profile", title: "Инвентарь", hint: "продать или вывести", imgs: ["toybear", "heartlocket"] },
];

function Hero({ go }: { go: (tab: string) => void }) {
  const [i, setI] = useState(0);
  const track = useRef<HTMLDivElement>(null);
  const paused = useRef(false);

  useEffect(() => {
    const t = setInterval(() => {
      if (paused.current || !track.current) return;
      const next = (Math.round(track.current.scrollLeft / track.current.clientWidth) + 1) % SLIDES.length;
      track.current.scrollTo({ left: next * track.current.clientWidth, behavior: "smooth" });
    }, 5000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="hero">
      <div
        className="hero-track"
        ref={track}
        onScroll={(e) => setI(Math.round(e.currentTarget.scrollLeft / e.currentTarget.clientWidth))}
        onTouchStart={() => (paused.current = true)}
        onTouchEnd={() => setTimeout(() => (paused.current = false), 4000)}
      >
        {SLIDES.map((s) => (
          <div className="hero-slide" key={s.title}>
            <div className="hero-body">
              <span className="hero-hand">{s.hand}</span>
              <div className="hero-title">{s.title}</div>
              <div className="hero-text">{s.text}</div>
              <button className="hero-btn" onClick={() => go(s.tab)}>{s.cta}</button>
            </div>
            <img className="hero-img" src={`/gifts/${s.img}.webp`} alt="" />
          </div>
        ))}
      </div>
      <div className="hero-dots">
        {SLIDES.map((_, n) => <i key={n} className={n === i ? "on" : ""} />)}
      </div>
    </div>
  );
}

export function Home({ go }: { go: (tab: string) => void }) {
  const { me } = useApp();
  const [online, setOnline] = useState<Record<string, number>>({});

  useEffect(() => {
    const load = () => api("/online").then(setOnline).catch(() => {});
    load();
    const t = setInterval(load, 20000);
    return () => clearInterval(t);
  }, []);

  return (
    <div>
      <Hero go={go} />

      <SecTitle hand="сыграем?" title="Игры." />
      <div className="games">
        {GAMES.map((g) => (
          <button key={g.tab} className="card game" onClick={() => go(g.tab)}>
            <div className="game-art">
              {g.key && (online[g.key] ?? 0) > 0 && (
                <span className="online"><i />{online[g.key] ?? 0} играют</span>
              )}
              <img className="game-img back" src={`/gifts/${g.imgs[1]}.webp`} alt="" />
              <img className="game-img front" src={`/gifts/${g.imgs[0]}.webp`} alt="" />
            </div>
            <div className="game-title">{g.title}</div>
            <div className="hint">{g.hint}</div>
          </button>
        ))}
      </div>

      <SecTitle hand="бесплатно" title="Бонусы." />
      <div className="list">
        <button className="card row-card" onClick={() => go("bonus")}>
          <img src="/gifts/lolpop.webp" alt="" />
          <div className="row-card-body">
            <b>Подарок дня</b>
            <span className="hint">монеты раз в 24 часа</span>
          </div>
          <span className="pill">Забрать</span>
        </button>
        <button className="card row-card" onClick={() => go("ref")}>
          <img src="/gifts/preciouspeach.webp" alt="" />
          <div className="row-card-body">
            <b>Приглашай друзей</b>
            <span className="hint">{me?.referral_percent ?? 5}% с каждого их пополнения</span>
          </div>
          <span className="pill pill--ghost">Позвать</span>
        </button>
      </div>

      <Footer go={go} />
    </div>
  );
}
