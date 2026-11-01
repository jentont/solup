import { useState } from "react";
import { useApp } from "../App";
import { usePlay, useTables, wait } from "../components/arcade";
import { BetPanel, GameHead } from "../components/ui";

const CELLS = 40;
const MAX_PICKS = 5;

export function Keno() {
  const { me, go, toast } = useApp();
  const tables = useTables();
  const { play, finish, busy } = usePlay<{ drawn: number[]; hits: number }>("keno");
  const [bet, setBet] = useState("10");
  const [picks, setPicks] = useState<number[]>([3, 11, 19, 27]);
  const [drawn, setDrawn] = useState<number[]>([]);
  const [hits, setHits] = useState<number | null>(null);
  const pays: number[] = tables?.keno?.[picks.length] ?? [];

  const toggle = (n: number) => {
    if (busy) return;
    setDrawn([]);
    setHits(null);
    if (picks.includes(n)) setPicks(picks.filter((x) => x !== n));
    else if (picks.length < MAX_PICKS) setPicks([...picks, n]);
    else toast(`Не больше ${MAX_PICKS} чисел`, "err");
  };
  const auto = () => {
    const all = Array.from({ length: CELLS }, (_, i) => i + 1).sort(() => Math.random() - 0.5);
    setPicks(all.slice(0, MAX_PICKS));
    setDrawn([]);
    setHits(null);
  };

  const draw = async () => {
    setDrawn([]);
    setHits(null);
    const r = await play(bet, { picks });
    if (!r) return;
    for (let i = 1; i <= r.detail.drawn.length; i++) {  // числа выпадают по одному
      setDrawn(r.detail.drawn.slice(0, i));
      await wait(110);
    }
    setHits(r.detail.hits);
    finish(r);
  };

  return (
    <div className="game-page">
      <GameHead hand={`выбери до ${MAX_PICKS} чисел`} title="Кено" onBack={() => go("home")} />
      <div className={`stage hue-keno ${hits === null ? "" : (pays[hits] ?? 0) > 0 ? "win" : "lose"}`}>
        <div className="keno-grid">
          {Array.from({ length: CELLS }, (_, i) => i + 1).map((n) => {
            const p = picks.includes(n), d = drawn.includes(n);
            return (
              <button key={n} className={`kcell ${p ? "pick" : ""} ${d ? "drawn" : ""} ${p && d ? "hit" : ""}`} onClick={() => toggle(n)}>
                {n}
              </button>
            );
          })}
        </div>
        <div className="keno-pays">
          {pays.map((m, h) => (
            <span key={h} className={hits === h ? "on" : ""}><small>{h}</small>{m ? `×${m}` : "—"}</span>
          ))}
        </div>
      </div>
      <BetPanel bet={bet} setBet={setBet} balance={me?.balance ?? 0}
        action={<button className="btn wide" disabled={busy || !picks.length} onClick={draw}>Играть · {picks.length} из {MAX_PICKS}</button>}>
        <div className="opts opts--2">
          <button disabled={busy} onClick={auto}>Случайные</button>
          <button disabled={busy} onClick={() => { setPicks([]); setDrawn([]); setHits(null); }}>Очистить</button>
        </div>
      </BetPanel>
    </div>
  );
}
