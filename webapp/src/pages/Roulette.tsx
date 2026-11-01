import { useRef, useState } from "react";
import { useApp } from "../App";
import { usePlay, wait } from "../components/arcade";
import { BetPanel, GameHead } from "../components/ui";

// Порядок чисел на европейском колесе — лента крутится в нём
const WHEEL = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26];
const RED = new Set([1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]);
const color = (n: number) => (n === 0 ? "green" : RED.has(n) ? "red" : "black");
const BETS = [
  { id: "red", label: "Красное", x: 2 }, { id: "black", label: "Чёрное", x: 2 }, { id: "zero", label: "Зеро", x: 36 },
  { id: "even", label: "Чёт", x: 2 }, { id: "odd", label: "Нечёт", x: 2 }, { id: "low", label: "1–18", x: 2 }, { id: "high", label: "19–36", x: 2 },
];
const CELL = 62; // ширина ячейки ленты + отступ
const LAPS = 5;
const STRIP = Array.from({ length: LAPS + 2 }, () => WHEEL).flat();
const SPIN_MS = 3600;

export function Roulette() {
  const { me, go } = useApp();
  const { play, finish, busy } = usePlay<{ number: number; color: string }>("roulette");
  const [bet, setBet] = useState("10");
  const [pick, setPick] = useState("red");
  const [offset, setOffset] = useState(0);
  const [anim, setAnim] = useState(false);
  const [history, setHistory] = useState<number[]>([]);
  const [won, setWon] = useState<boolean | null>(null);
  const track = useRef<HTMLDivElement>(null);

  const spin = async () => {
    setWon(null);
    const r = await play(bet, { bet: pick });
    if (!r) return;
    const w = track.current?.clientWidth ?? 340;
    setAnim(false);
    setOffset(WHEEL.indexOf(0) * CELL);
    await wait(30);
    const idx = LAPS * WHEEL.length + WHEEL.indexOf(r.detail.number);
    setAnim(true);
    setOffset(idx * CELL - w / 2 + CELL / 2 + (Math.random() - 0.5) * 30);
    await wait(SPIN_MS + 100);
    setHistory((h) => [r.detail.number, ...h].slice(0, 12));
    setWon(r.payout > 0);
    finish(r);
  };

  return (
    <div className="game-page">
      <GameHead hand="красное или чёрное" title="Рулетка" onBack={() => go("home")} />
      <div className={`stage hue-roulette ${won === null ? "" : won ? "win" : "lose"}`}>
        <div className="rl-track" ref={track}>
          <div className="rl-strip" style={{ transform: `translateX(${-offset}px)`, transition: anim ? `transform ${SPIN_MS}ms cubic-bezier(.12,.75,.15,1)` : "none" }}>
            {STRIP.map((n, i) => <span key={i} className={`rl-cell ${color(n)}`}>{n}</span>)}
          </div>
          <i className="rl-marker" />
        </div>
        <div className="rl-history">
          {history.length ? history.map((n, i) => <span key={i} className={`rl-cell sm ${color(n)}`}>{n}</span>) : <span className="hint">здесь будут последние числа</span>}
        </div>
      </div>
      <BetPanel bet={bet} setBet={setBet} balance={me?.balance ?? 0}
        action={<button className="btn wide" disabled={busy} onClick={spin}>Крутить</button>}>
        <div className="opts opts--rl">
          {BETS.map((b) => (
            <button key={b.id} className={`${pick === b.id ? "active" : ""} rl-bet-${b.id}`} onClick={() => setPick(b.id)}>
              {b.label} <small>×{b.x}</small>
            </button>
          ))}
        </div>
      </BetPanel>
    </div>
  );
}
