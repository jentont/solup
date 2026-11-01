import { useState } from "react";
import { useApp } from "../App";
import { usePlay } from "../components/arcade";
import { BetPanel, GameHead } from "../components/ui";

const TARGETS = [1.5, 2, 5, 10, 100];

export function Limbo() {
  const { me, go } = useApp();
  const { play, finish, busy } = usePlay<{ result: number }>("limbo");
  const [bet, setBet] = useState("10");
  const [target, setTarget] = useState("2");
  const [shown, setShown] = useState(1);
  const [won, setWon] = useState<boolean | null>(null);
  const t = Math.max(1.01, parseFloat(target.replace(",", ".")) || 1.01);

  const go2 = async () => {
    setWon(null);
    const r = await play(bet, { target: t });
    if (!r) return;
    // множитель «взлетает» от 1.00 до результата
    const end = r.detail.result;
    const start = performance.now();
    const dur = 700;
    await new Promise<void>((done) => {
      const step = (now: number) => {
        const k = Math.min(1, (now - start) / dur);
        setShown(1 + (end - 1) * (1 - (1 - k) ** 3));
        if (k < 1) requestAnimationFrame(step);
        else done();
      };
      requestAnimationFrame(step);
    });
    setWon(r.payout > 0);
    finish(r);
  };

  return (
    <div className="game-page">
      <GameHead hand="выше цели" title="Лимбо" onBack={() => go("home")} />
      <div className={`stage hue-limbo ${won === null ? "" : won ? "win" : "lose"}`}>
        <div className={`limbo-num ${won === null ? "" : won ? "pos" : "neg"}`}>×{shown.toFixed(2)}</div>
        <div className="limbo-goal">цель ×{t.toFixed(2)} · шанс {(95 / t).toFixed(2)}%</div>
      </div>
      <BetPanel bet={bet} setBet={setBet} balance={me?.balance ?? 0}
        action={<button className="btn wide" disabled={busy} onClick={go2}>Играть</button>}>
        <div className="opt-label">Цель — множитель выигрыша</div>
        <div className="bet-input">
          <span className="bet-x">×</span>
          <input inputMode="decimal" value={target} onChange={(e) => setTarget(e.target.value)} aria-label="Цель" />
        </div>
        <div className="opts">
          {TARGETS.map((v) => (
            <button key={v} className={t === v ? "active" : ""} onClick={() => setTarget(String(v))}>×{v}</button>
          ))}
        </div>
      </BetPanel>
    </div>
  );
}
