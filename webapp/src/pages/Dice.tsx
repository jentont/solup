import { useState } from "react";
import { useApp } from "../App";
import { usePlay, wait } from "../components/arcade";
import { BetPanel, GameHead } from "../components/ui";

export function Dice() {
  const { me, go } = useApp();
  const { play, finish, busy } = usePlay<{ value: number }>("dice");
  const [bet, setBet] = useState("10");
  const [target, setTarget] = useState(50);
  const [over, setOver] = useState(true);
  const [value, setValue] = useState<number | null>(null);
  const [won, setWon] = useState<boolean | null>(null);

  const chance = over ? 100 - target : target;
  const mult = (0.95 * 100) / chance;

  const roll = async () => {
    setWon(null);
    const r = await play(bet, { target, over });
    if (!r) return;
    setValue(r.detail.value);
    await wait(650);
    setWon(r.payout > 0);
    finish(r);
  };

  return (
    <div className="game-page">
      <GameHead hand="больше или меньше" title="Дайс" onBack={() => go("home")} />
      <div className={`stage hue-dice ${won === null ? "" : won ? "win" : "lose"}`}>
        <div className={`dice-value ${won === null ? "" : won ? "pos" : "neg"}`}>{value === null ? "50.00" : value.toFixed(2)}</div>
        <div className="dice-track">
          <div className="dice-zone" style={over ? { left: `${target}%`, right: 0 } : { left: 0, right: `${100 - target}%` }} />
          {value !== null && <i className="dice-mark" style={{ left: `${value}%` }} />}
          <input type="range" min={2} max={98} value={target} disabled={busy} onChange={(e) => setTarget(+e.target.value)} />
        </div>
        <div className="stats">
          <div><span>{over ? "больше" : "меньше"}</span><b>{target}</b></div>
          <div><span>шанс</span><b>{chance}%</b></div>
          <div><span>выплата</span><b>×{mult.toFixed(2)}</b></div>
        </div>
      </div>
      <BetPanel bet={bet} setBet={setBet} balance={me?.balance ?? 0}
        action={<button className="btn wide" disabled={busy} onClick={roll}>Бросить</button>}>
        <div className="opts opts--2">
          <button className={!over ? "active" : ""} onClick={() => setOver(false)}>Меньше {target}</button>
          <button className={over ? "active" : ""} onClick={() => setOver(true)}>Больше {target}</button>
        </div>
      </BetPanel>
    </div>
  );
}
