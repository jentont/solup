import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useApp } from "../App";
import { Footer } from "../components/Footer";
import { GameArt } from "../components/GameArt";
import { SecTitle } from "../components/ui";

// Баннеры: у каждого свой цвет, как у карточек игр
type Slide = { hand: string; title: string; text: string; imgs: string[]; tab: string; cta: string; hue: string };

const SLIDES: Slide[] = [
  { hand: "10 новых игр", title: "Плинко", text: "Брось шарик — до ×27 к ставке", imgs: ["hangingstar", "stellarrocket"], tab: "plinko", cta: "Играть", hue: "plinko" },
  { hand: "новинка", title: "Колесо", text: "Один спин — до ×8 к ставке", imgs: ["recordplayer", "partysparkler"], tab: "wheel", cta: "Крутить", hue: "wheel" },
  { hand: "новинка", title: "Башня", text: "8 этажей, до ×6000 на вершине", imgs: ["witchhat", "spyagaric"], tab: "tower", cta: "Играть", hue: "tower" },
  { hand: "бесплатно", title: "Кейс дня", text: "Открывай раз в сутки — до 500 монет", imgs: ["lootbag", "lolpop"], tab: "bonus", cta: "Открыть", hue: "cases" },
  { hand: "навсегда", title: "Зови друзей", text: "Процент с каждого их пополнения", imgs: ["preciouspeach", "heartlocket"], tab: "ref", cta: "Позвать", hue: "upgrade" },
];

// Обложка каждой игры — компонент GameArt: предмет игры и NFT-подарки вокруг
type Game = { tab: string; title: string; tag?: string };

const GAMES: Game[] = [
  { tab: "crash", title: "Краш" },
  { tab: "cases", title: "Кейсы" },
  { tab: "upgrade", title: "Апгрейд" },
  { tab: "slots", title: "Слоты", tag: "NEW" },
  { tab: "mines", title: "Мины" },
  { tab: "wheel", title: "Колесо", tag: "NEW" },
  { tab: "tower", title: "Башня", tag: "NEW" },
  { tab: "blackjack", title: "Блэкджек", tag: "NEW" },
  { tab: "plinko", title: "Плинко", tag: "NEW" },
  { tab: "roulette", title: "Рулетка", tag: "NEW" },
  { tab: "dice", title: "Дайс", tag: "NEW" },
  { tab: "limbo", title: "Лимбо", tag: "NEW" },
  { tab: "hilo", title: "Hi-Lo", tag: "NEW" },
  { tab: "keno", title: "Кено", tag: "NEW" },
  { tab: "coinflip", title: "Монетка", tag: "NEW" },
  { tab: "rps", title: "Камень-ножницы", tag: "NEW" },
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
          <div className={`hero-slide hue-${s.hue}`} key={s.title} onClick={() => go(s.tab)}>
            <span className="rays" />
            <img className="hero-img back" src={`/gifts/${s.imgs[1]}.webp`} alt="" />
            <img className="hero-img" src={`/gifts/${s.imgs[0]}.webp`} alt="" />
            <div className="hero-body">
              <span className="hero-hand">{s.hand}</span>
              <div className="hero-title">{s.title}</div>
              <div className="hero-text">{s.text}</div>
            </div>
            <button className="hero-btn">{s.cta}</button>
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

      <SecTitle title="Игры" />
      <div className="games">
        {GAMES.map((g) => (
          <button key={g.tab} className={`gtile hue-${g.tab}`} onClick={() => go(g.tab)}>
            <span className="rays" />
            <span className="gtile-floor" />
            <GameArt id={g.tab} />
            {(online[g.tab] ?? 0) > 0 ? (
              <span className="online"><i />{online[g.tab]} играют</span>
            ) : g.tag ? <span className="gtile-tag">{g.tag}</span> : null}
            <span className="gtile-title">{g.title}</span>
          </button>
        ))}
      </div>

      <SecTitle title="Бонусы" />
      <div className="list">
        <button className="card row-card" onClick={() => go("bonus")}>
          <span className="row-art hue-cases"><img src="/gifts/lootbag.webp" alt="" /></span>
          <div className="row-card-body">
            <b>Ежедневный кейс</b>
            <span className="hint">бесплатно раз в 24 часа</span>
          </div>
          <span className="pill">Открыть</span>
        </button>
        <button className="card row-card" onClick={() => go("ref")}>
          <span className="row-art hue-upgrade"><img src="/gifts/preciouspeach.webp" alt="" /></span>
          <div className="row-card-body">
            <b>Приглашай друзей</b>
            <span className="hint">{me?.referral_percent ?? 5}% с каждого их пополнения</span>
          </div>
          <span className="pill pill--ghost">Позвать</span>
        </button>
        <button className="card row-card" onClick={() => go("profile")}>
          <span className="row-art hue-mines"><img src="/gifts/toybear.webp" alt="" /></span>
          <div className="row-card-body">
            <b>Инвентарь</b>
            <span className="hint">продать или вывести подарки</span>
          </div>
          <span className="pill pill--ghost">Открыть</span>
        </button>
      </div>

      <Footer go={go} />
    </div>
  );
}
