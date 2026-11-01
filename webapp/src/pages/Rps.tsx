import { useState } from "react";
import { useApp } from "../App";
import { usePlay, wait } from "../components/arcade";
import { BetPanel, GameHead } from "../components/ui";

const MOVES = [
  { id: "rock", label: "Камень", icon: "✊" },
  { id: "paper", label: "Бумага", icon: "✋" },
  { id: "scissors", label: "Ножницы", icon: "✌️" },
];
const icon = (id: string) => MOVES.find((m) => m.id === id)!.icon;
const OUTCOME: Record<string, string> = { win: "Победа ×1.9", draw: "Ничья ×0.95", lose: "Поражение" };

export function Rps() {
  const { me, go } = useApp();
  const { play, finish, busy } = usePlay<{ house: string; outcome: string }>("rps");
  const [bet, setBet] = useState("10");
  const [move, setMove] = useState("rock");
  const [house, setHouse] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<string | null>(null);

  const fight = async () => {
    setOutcome(null);
    const r = await play(bet, { move });
    if (!r) return;
    for (let i = 0; i < 8; i++) {  // перебор вариантов, пока «думает» соперник
      setHouse(MOVES[i % 3].id);
      await wait(90);
    }
    setHouse(r.detail.house);
    setOutcome(r.detail.outcome);
    finish(r);
  };

  return (
    <div className="game-page">
      <GameHead hand="сыграем на троих?" title="Камень-ножницы" onBack={() => go("home")} />
      <div className={`stage hue-rps ${outcome === "win" ? "win" : outcome === "lose" ? "lose" : ""}`}>
        <div className="rps-duel">
          <div className="rps-side"><span>вы</span><b>{icon(move)}</b></div>
          <i>vs</i>
          <div className="rps-side"><span>SolUP</span><b className={busy && !outcome ? "rps-shake" : ""}>{house ? icon(house) : "❔"}</b></div>
        </div>
        <div className={`rps-outcome ${outcome ?? ""}`}>{outcome ? OUTCOME[outcome] : "Победа ×1.9 · ничья ×0.95"}</div>
      </div>
      <BetPanel bet={bet} setBet={setBet} balance={me?.balance ?? 0}
        action={<button className="btn wide" disabled={busy} onClick={fight}>Играть</button>}>
        <div className="opts opts--3">
          {MOVES.map((m) => (
            <button key={m.id} className={move === m.id ? "active" : ""} onClick={() => setMove(m.id)}>{m.icon} {m.label}</button>
          ))}
        </div>
      </BetPanel>
    </div>
  );
}
