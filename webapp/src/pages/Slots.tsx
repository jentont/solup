import { useState } from "react";
import { useApp } from "../App";
import { usePlay, useTables, wait } from "../components/arcade";
import { BetPanel, GameHead } from "../components/ui";

// Символы барабанов — подарки; порядок от дорогого к дешёвому, как в таблице выплат
const SYMBOLS: Record<string, string> = {
  seven: "plushpepe", diamond: "diamondring", bell: "jinglebells", grape: "berrybox", lemon: "lolpop", cherry: "cookieheart",
};
const NAMES = Object.keys(SYMBOLS);
const H = 84; // высота символа на барабане
const REEL = 24; // символов на ленте барабана

const img = (s: string) => `/gifts/${SYMBOLS[s]}.webp`;

export function Slots() {
  const { me, go } = useApp();
  const tables = useTables();
  const { play, finish, busy } = usePlay<{ reels: string[] }>("slots");
  const [bet, setBet] = useState("10");
  const [reels, setReels] = useState<string[][]>(() => [0, 1, 2].map((k) => Array.from({ length: REEL }, (_, i) => NAMES[(i + k * 2) % 6])));
  const [spin, setSpin] = useState(0);
  const [won, setWon] = useState<boolean | null>(null);

  const go2 = async () => {
    setWon(null);
    const r = await play(bet);
    if (!r) return;
    // новые ленты: случайные символы, последний — выпавший; барабаны останавливаются по очереди
    setReels(r.detail.reels.map((s) => [...Array.from({ length: REEL - 1 }, () => NAMES[Math.floor(Math.random() * 6)]), s]));
    setSpin((n) => n + 1);
    await wait(2300);
    setWon(r.payout > 0);
    finish(r);
  };

  const three = tables?.slots?.three ?? {};
  return (
    <div className="game-page">
      <GameHead hand="три в ряд" title="Слоты" onBack={() => go("home")} />
      <div className={`stage hue-slots ${won === null ? "" : won ? "win" : "lose"}`}>
        <div className="slots">
          {reels.map((strip, k) => (
            <div key={k} className="reel">
              <div key={spin} className={`reel-strip ${spin ? "spin" : ""}`}
                style={{ transform: `translateY(${-(REEL - 1) * H}px)`, animationDuration: `${1.3 + k * 0.45}s` }}>
                {strip.map((s, i) => <img key={i} src={img(s)} alt="" />)}
              </div>
            </div>
          ))}
          <i className="slots-line" />
        </div>
        <div className="slot-pays">
          {NAMES.map((s) => (
            <span key={s}><img src={img(s)} alt="" />×3 = <b>×{three[s] ?? "…"}</b></span>
          ))}
          <span><img src={img("cherry")} alt="" />×2 = <b>×{tables?.slots?.cherry?.[2] ?? "…"}</b></span>
          <span><img src={img("cherry")} alt="" />×1 = <b>×{tables?.slots?.cherry?.[1] ?? "…"}</b></span>
        </div>
      </div>
      <BetPanel bet={bet} setBet={setBet} balance={me?.balance ?? 0}
        action={<button className="btn wide" disabled={busy} onClick={go2}>Крутить</button>} />
    </div>
  );
}
