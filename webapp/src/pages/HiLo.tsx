import { useState } from "react";
import { fmt, haptic } from "../api";
import { useApp } from "../App";
import { PlayCard, useRound } from "../components/arcade";
import { BetPanel, GameHead } from "../components/ui";

type G = {
  bet: number; status: "active" | "cashed" | "lost"; payout: number; cards: number[]; steps: number; multiplier: number;
  hi: { chance: number; multiplier: number }; lo: { chance: number; multiplier: number };
};

export function HiLo() {
  const { me, go, toast } = useApp();
  const { g, act, busy } = useRound<G>("hilo");
  const [bet, setBet] = useState("10");
  const active = g?.status === "active";

  const move = async (a: string) => {
    const r = await act(a, bet);
    if (!r) return;
    if (r.status === "lost") { haptic("error"); toast("Мимо! Ставка сгорела", "err"); }
    else if (r.status === "cashed") { haptic("success"); toast(`Забрали ×${(r.payout / r.bet).toFixed(2)} · +${fmt(r.payout)}`); }
    else haptic();
  };

  const cur = g?.cards[g.cards.length - 1];
  const pct = (p: number) => `${Math.round(p * 100)}%`;
  return (
    <div className="game-page">
      <GameHead hand="старше или младше" title="Hi-Lo" onBack={() => go("home")} />
      <div className={`stage hue-hilo ${g?.status === "lost" ? "lose" : g?.status === "cashed" ? "win" : ""}`}>
        <div className="hilo-main">
          <PlayCard key={g?.cards.length} rank={cur} i={g?.cards.length ?? 0} hidden={!g} />
        </div>
        <div className="hilo-trail">
          {g?.cards.slice(0, -1).slice(-8).map((c, i) => <PlayCard key={i} rank={c} i={i} />)}
        </div>
        <div className="stats">
          <div><span>множитель</span><b>×{(g?.multiplier || 0).toFixed(2)}</b></div>
          <div><span>угадано</span><b>{g?.steps ?? 0}</b></div>
          <div><span>ставка</span><b>{g ? fmt(g.bet) : "—"}</b></div>
        </div>
      </div>
      {active ? (
        <div className="bet-panel">
          <div className="opts opts--2 hilo-acts">
            <button disabled={busy || g!.hi.chance === 0} onClick={() => move("hi")}>▲ Старше или равно<small>{pct(g!.hi.chance)} · ×{g!.hi.multiplier.toFixed(2)}</small></button>
            <button disabled={busy || g!.lo.chance === 0} onClick={() => move("lo")}>▼ Младше или равно<small>{pct(g!.lo.chance)} · ×{g!.lo.multiplier.toFixed(2)}</small></button>
          </div>
          <div className="opts opts--2">
            <button disabled={busy} onClick={() => move("skip")}>Пропустить карту</button>
            <button className="cash-opt" disabled={busy || !g!.steps} onClick={() => move("cashout")}>
              Забрать {g!.steps ? fmt(Math.floor(g!.bet * g!.multiplier)) : ""}
            </button>
          </div>
        </div>
      ) : (
        <BetPanel bet={bet} setBet={setBet} balance={me?.balance ?? 0}
          action={<button className="btn wide" disabled={busy} onClick={() => move("start")}>{g ? "Ещё раз" : "Играть"}</button>} />
      )}
    </div>
  );
}
