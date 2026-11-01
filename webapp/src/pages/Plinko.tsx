import { useState } from "react";
import { useApp } from "../App";
import { usePlay, useTables, wait } from "../components/arcade";
import { BetPanel, GameHead } from "../components/ui";

const ROWS = 8;
const W = 300;
const GAP = W / (ROWS + 2);
const TOP = 22;
// Колышек ряда r номер i (в ряду r + 3 колышка), по центру поля
const peg = (r: number, i: number) => ({ x: W / 2 + (i - (r + 2) / 2) * GAP, y: TOP + r * GAP });

export function Plinko() {
  const { me, go } = useApp();
  const tables = useTables();
  const { play, finish, busy } = usePlay<{ path: number[]; slot: number }>("plinko");
  const [bet, setBet] = useState("10");
  const [risk, setRisk] = useState("low");
  const [ball, setBall] = useState<{ x: number; y: number } | null>(null);
  const [hit, setHit] = useState<number | null>(null);
  const mults: number[] = tables?.plinko?.[risk] ?? [];

  const drop = async () => {
    setHit(null);
    const r = await play(bet, { risk });
    if (!r) return;
    // шарик идёт между колышками: смещение вправо на полшага за каждый «1»
    let x = W / 2;
    setBall({ x, y: TOP - GAP * 0.7 });
    for (let row = 0; row < ROWS; row++) {
      await wait(150);
      x += (r.detail.path[row] ? 0.5 : -0.5) * GAP;
      setBall({ x, y: TOP + row * GAP + GAP * 0.5 });
    }
    await wait(170);
    setBall(null);
    setHit(r.detail.slot);
    finish(r);
  };

  const slotW = GAP;
  return (
    <div className="game-page">
      <GameHead hand="куда упадёт?" title="Плинко" onBack={() => go("home")} />
      <div className={`stage hue-plinko ${hit === null ? "" : (mults[hit] ?? 0) >= 1 ? "win" : "lose"}`}>
        <svg className="plinko" viewBox={`0 0 ${W} ${TOP + ROWS * GAP + 34}`}>
          {Array.from({ length: ROWS }, (_, r) =>
            Array.from({ length: r + 3 }, (_, i) => {
              const p = peg(r, i);
              return <circle key={`${r}-${i}`} cx={p.x} cy={p.y} r={3.2} className="peg" />;
            }),
          )}
          {mults.map((m, i) => {
            const x = W / 2 + (i - ROWS / 2) * slotW;
            const y = TOP + ROWS * GAP - 6;
            const tier = m >= 5 ? "t3" : m >= 1.5 ? "t2" : m >= 1 ? "t1" : "t0";
            return (
              <g key={i} className={`pslot ${tier} ${hit === i ? "hit" : ""}`}>
                <rect x={x - slotW / 2 + 1.5} y={y} width={slotW - 3} height={24} rx={6} />
                <text x={x} y={y + 12.5}>{m}</text>
              </g>
            );
          })}
          {ball && <circle cx={ball.x} cy={ball.y} r={6.5} className="pball" />}
        </svg>
      </div>
      <BetPanel bet={bet} setBet={setBet} balance={me?.balance ?? 0}
        action={<button className="btn wide" disabled={busy || !mults.length} onClick={drop}>Бросить шарик</button>}>
        <div className="opts opts--2">
          <button className={risk === "low" ? "active" : ""} disabled={busy} onClick={() => setRisk("low")}>Спокойно · до ×5.4</button>
          <button className={risk === "high" ? "active" : ""} disabled={busy} onClick={() => setRisk("high")}>Риск · до ×27</button>
        </div>
      </BetPanel>
    </div>
  );
}
