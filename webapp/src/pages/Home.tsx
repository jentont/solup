import { useEffect, useState } from "react";
import { api } from "../api";
import { useApp } from "../App";
import { Footer } from "../components/Footer";
import { GameArt } from "../components/GameArt";
import { SecTitle } from "../components/ui";

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

// Баннер: ролик «рулетка → апгрейд» без звука по кругу; нажатие открывает апгрейд
function PromoVideo({ go }: { go: (tab: string) => void }) {
  return (
    <button className="promo-video" onClick={() => go("upgrade")} aria-label="Апгрейд">
      <video src="/promo/upgrade.mp4" poster="/promo/upgrade.jpg" autoPlay muted loop playsInline preload="auto" />
    </button>
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
      <PromoVideo go={go} />

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
