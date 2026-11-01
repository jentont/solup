import { useState } from "react";
import { fmt, haptic } from "../api";
import { useApp } from "../App";
import { PlayCard, useRound } from "../components/arcade";
import { BetPanel, GameHead } from "../components/ui";

type G = {
  bet: number; status: "active" | "cashed" | "lost"; payout: number; player: number[]; dealer: number[];
  player_value: number; dealer_value: number; can_double: boolean; outcome: string | null;
};
const OUTCOME: Record<string, string> = {
  blackjack: "Блэкджек! ×2.2", win: "Победа ×2", push: "Ничья — ставка вернулась", lose: "Дилер выиграл", bust: "Перебор",
};

export function Blackjack() {
  const { me, go, toast } = useApp();
  const { g, act, busy } = useRound<G>("blackjack");
  const [bet, setBet] = useState("10");
  const active = g?.status === "active";

  const move = async (a: string) => {
    const r = await act(a, bet);
    if (!r) return;
    if (r.status === "active") return haptic();
    haptic(r.payout ? "success" : "error");
    if (r.outcome) toast(r.payout ? `${OUTCOME[r.outcome]} · +${fmt(r.payout)}` : OUTCOME[r.outcome], r.payout ? "ok" : "err");
  };

  return (
    <div className="game-page">
      <GameHead hand="набери 21" title="Блэкджек" onBack={() => go("home")} />
      <div className={`stage hue-blackjack bj-table ${g?.status === "lost" ? "lose" : g?.status === "cashed" ? "win" : ""}`}>
        <div className="bj-hand">
          <span className="bj-label">Дилер {g && <b>{g.dealer_value}</b>}</span>
          <div className="bj-cards">
            {g ? <>{g.dealer.map((c, i) => <PlayCard key={i} rank={c} i={i} />)}{active && <PlayCard hidden i={1} />}</>
              : <><PlayCard hidden /><PlayCard hidden i={1} /></>}
          </div>
        </div>
        <div className="bj-mid">{g?.outcome ? OUTCOME[g.outcome] : "Блэкджек платит 6:5 · дилер берёт до 17"}</div>
        <div className="bj-hand">
          <div className="bj-cards">
            {g ? g.player.map((c, i) => <PlayCard key={i} rank={c} i={i + 2} />) : <><PlayCard hidden /><PlayCard hidden i={1} /></>}
          </div>
          <span className="bj-label">Вы {g && <b>{g.player_value}</b>}</span>
        </div>
      </div>
      {active ? (
        <div className="bet-panel">
          <div className="opts opts--3">
            <button disabled={busy} onClick={() => move("hit")}>Ещё</button>
            <button disabled={busy} onClick={() => move("stand")}>Хватит</button>
            <button disabled={busy || !g!.can_double} onClick={() => move("double")}>Удвоить</button>
          </div>
        </div>
      ) : (
        <BetPanel bet={bet} setBet={setBet} balance={me?.balance ?? 0}
          action={<button className="btn wide" disabled={busy} onClick={() => move("start")}>{g ? "Новая раздача" : "Раздать"}</button>} />
      )}
    </div>
  );
}
