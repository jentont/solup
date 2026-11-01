import { useEffect, useState } from "react";
import { api, fmt, haptic } from "../api";
import { useApp } from "../App";
import { BetPanel, GameHead, toCents } from "../components/ui";

type Game = {
  id: number;
  bet: number;
  difficulty: string;
  cols: number;
  bombs: number;
  floors: number;
  picks: number[];
  status: "active" | "cashed" | "lost";
  payout: number;
  multiplier: number;
  next_multiplier: number | null;
  board: number[][] | null;
};

// Ширина ряда и бомбы на этаже — как tower.DIFFICULTIES на сервере
const DIFFS: Record<string, { label: string; cols: number; bombs: number }> = {
  easy: { label: "Легко", cols: 4, bombs: 1 },
  medium: { label: "Средне", cols: 3, bombs: 1 },
  hard: { label: "Сложно", cols: 2, bombs: 1 },
  extreme: { label: "Жесть", cols: 3, bombs: 2 },
};
const FLOORS = 8;
const mult = (d: string, k: number) => 0.95 * (DIFFS[d].cols / (DIFFS[d].cols - DIFFS[d].bombs)) ** k;
const short = (m: number) => (m >= 100 ? Math.round(m).toLocaleString("ru-RU") : m.toFixed(2));

export function Tower() {
  const { me, setBalance, toast, go } = useApp();
  const [game, setGame] = useState<Game | null>(null);
  const [bet, setBet] = useState("10");
  const [diff, setDiff] = useState("medium");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api("/tower").then((r) => setGame(r.game));
  }, []);

  const call = async (path: string, body: unknown = {}) => {
    if (busy) return null;
    setBusy(true);
    try {
      const r = await api(path, body);
      setGame(r.game);
      setBalance(r.balance);
      return r.game as Game;
    } catch (e: any) {
      toast(e.message, "err");
      return null;
    } finally {
      setBusy(false);
    }
  };

  const start = async () => {
    const g = await call("/tower/start", { bet: toCents(bet), difficulty: diff });
    if (g) haptic();
  };
  const pick = async (col: number) => {
    const g = await call("/tower/pick", { col });
    if (!g) return;
    if (g.status === "lost") {
      haptic("error");
      toast("Бомба! Ставка сгорела", "err");
    } else if (g.status === "cashed") {
      haptic("success");
      toast(`Вершина! +${fmt(g.payout)}`);
    } else haptic();
  };
  const cashout = async () => {
    const g = await call("/tower/cashout");
    if (g) {
      haptic("success");
      toast(`Забрали ×${g.multiplier.toFixed(2)} · +${fmt(g.payout)}`);
    }
  };

  const active = game?.status === "active";
  const over = !!game && !active;
  const d = active || over ? game!.difficulty : diff;
  const cols = DIFFS[d].cols;
  const current = active ? game!.picks.length : -1;

  return (
    <div className="game-page">
      <GameHead hand="не сорвись" title="Башня" onBack={() => go("home")} />

      <div className={`stage hue-tower ${game?.status === "lost" ? "lose" : game?.status === "cashed" ? "win" : ""}`}>
        <div className="tower">
          {Array.from({ length: FLOORS }, (_, f) => {
            const picked = (active || over) ? game!.picks[f] : undefined;
            const bombs = over ? game!.board![f] : [];
            const rowCls = f === current ? "now" : picked !== undefined ? "done" : "";
            return (
              <div key={f} className={`tower-row ${rowCls}`}>
                <span className="tower-mult">×{short(mult(d, f + 1))}</span>
                <div className="tower-cells" style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
                  {Array.from({ length: cols }, (_, c) => {
                    const isPick = picked === c;
                    const isBomb = bombs.includes(c);
                    const cls = isPick ? (isBomb ? "boom" : "safe") : over && isBomb ? "mine-shown" : "";
                    return (
                      <button key={c} className={`tcell ${cls}`} disabled={f !== current || busy} onClick={() => pick(c)}>
                        {isPick && !isBomb && <img src="/gifts/spyagaric.webp" alt="" />}
                        {isBomb && over && <i className="mine" />}
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {active ? (
        <button className="btn wide cash" disabled={busy || !game!.picks.length} onClick={cashout}>
          {game!.picks.length ? <>Забрать {fmt(Math.floor(game!.bet * game!.multiplier))} <i className="coin" /></> : "Выберите ячейку на 1 этаже"}
        </button>
      ) : (
        <BetPanel
          bet={bet}
          setBet={setBet}
          balance={me?.balance ?? 0}
          action={<button className="btn wide" disabled={busy} onClick={start}>{over ? "Ещё раз" : "Играть"}</button>}
        >
          <div className="opt-label">Сложность</div>
          <div className="opts opts--4">
            {Object.entries(DIFFS).map(([k, v]) => (
              <button key={k} className={k === diff ? "active" : ""} onClick={() => setDiff(k)}>{v.label}</button>
            ))}
          </div>
        </BetPanel>
      )}
    </div>
  );
}
