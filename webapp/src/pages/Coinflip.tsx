import { useState } from "react";
import { useApp } from "../App";
import { usePlay, wait } from "../components/arcade";
import { BetPanel, GameHead } from "../components/ui";

export function Coinflip() {
  const { me, go } = useApp();
  const { play, finish, busy } = usePlay<{ landed: "heads" | "tails" }>("coinflip");
  const [bet, setBet] = useState("10");
  const [side, setSide] = useState<"heads" | "tails">("heads");
  const [turns, setTurns] = useState(0); // в полуоборотах: чётное — орёл сверху
  const [won, setWon] = useState<boolean | null>(null);

  const flip = async () => {
    setWon(null);
    const r = await play(bet, { side });
    if (!r) return;
    const now = turns % 2 === 0 ? "heads" : "tails";
    setTurns(turns + 10 + (r.detail.landed === now ? 0 : 1));
    await wait(1500);
    setWon(r.payout > 0);
    finish(r);
  };

  return (
    <div className="game-page">
      <GameHead hand="орёл или решка" title="Монетка" onBack={() => go("home")} />
      <div className={`stage hue-coinflip ${won === null ? "" : won ? "win" : "lose"}`}>
        <div className="coin3d-wrap">
          <div className="coin3d" style={{ transform: `rotateY(${turns * 180}deg)` }}>
            <div className="coin3d-face heads"><img src="/brand/solup-mark-light.svg" alt="" /><span>орёл</span></div>
            <div className="coin3d-face tails"><b>×1.9</b><span>решка</span></div>
          </div>
        </div>
      </div>
      <BetPanel bet={bet} setBet={setBet} balance={me?.balance ?? 0}
        action={<button className="btn wide" disabled={busy} onClick={flip}>Подбросить · ×1.9</button>}>
        <div className="opts opts--2">
          <button className={side === "heads" ? "active" : ""} onClick={() => setSide("heads")}>Орёл</button>
          <button className={side === "tails" ? "active" : ""} onClick={() => setSide("tails")}>Решка</button>
        </div>
      </BetPanel>
    </div>
  );
}
