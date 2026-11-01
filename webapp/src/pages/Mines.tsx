import { useEffect, useState } from "react";
import { api, fmt, haptic } from "../api";
import { useApp } from "../App";
import { BetPanel, GameHead, toCents } from "../components/ui";

type Game = {
  id: number;
  bet: number;
  mines: number;
  opened: number[];
  status: "active" | "cashed" | "lost";
  payout: number;
  multiplier: number;
  next_multiplier: number | null;
  mine_cells: number[] | null;
};

const MINES = [1, 3, 5, 10, 24];
// Множитель первого хода — для подсказки до старта (как в mines.multiplier на сервере)
const firstMult = (m: number) => (0.95 * 25) / (25 - m);

export function Mines() {
  const { me, setBalance, toast, go } = useApp();
  const [game, setGame] = useState<Game | null>(null);
  const [bet, setBet] = useState("10");
  const [mines, setMines] = useState(3);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api("/mines").then((r) => setGame(r.game));
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
    const g = await call("/mines/start", { bet: toCents(bet), mines });
    if (g) haptic();
  };
  const open = async (cell: number) => {
    if (game?.status !== "active" || game.opened.includes(cell)) return;
    const g = await call("/mines/open", { cell });
    if (!g) return;
    if (g.status === "lost") {
      haptic("error");
      toast("Мина! Ставка сгорела", "err");
    } else if (g.status === "cashed") {
      haptic("success");
      toast(`Все клетки открыты: +${fmt(g.payout)}`);
    } else haptic();
  };
  const cashout = async () => {
    const g = await call("/mines/cashout");
    if (g) {
      haptic("success");
      toast(`Забрали ×${g.multiplier.toFixed(2)} · +${fmt(g.payout)}`);
    }
  };

  const active = game?.status === "active";
  const over = game && game.status !== "active";
  const shownMines = active ? game!.mines : mines;
  const next = active ? game!.next_multiplier : firstMult(mines);

  return (
    <div className="game-page">
      <GameHead hand="не наступи" title="Мины" onBack={() => go("home")} />

      <div className={`stage hue-mines ${game?.status === "lost" ? "lose" : game?.status === "cashed" ? "win" : ""}`}>
        <div className="stats">
          <div><span>множитель</span><b>×{(active || over ? game!.multiplier : 1).toFixed(2)}</b></div>
          <div><span>следующая</span><b>{next ? `×${next.toFixed(2)}` : "—"}</b></div>
          <div><span>мин</span><b>{shownMines}</b></div>
        </div>
        <div className="mines-grid">
          {Array.from({ length: 25 }, (_, i) => {
            const isOpen = game?.opened.includes(i);
            const isMine = game?.mine_cells?.includes(i);
            const cls = isOpen ? (isMine ? "boom" : "safe") : over && isMine ? "mine-shown" : over ? "dim" : active ? "live" : "";
            return (
              <button key={i} className={`mcell ${cls}`} disabled={!active || isOpen || busy} onClick={() => open(i)}>
                {isOpen && !isMine && <img src="/gifts/crystalball.webp" alt="" />}
                {isMine && (isOpen || over) && <i className="mine" />}
              </button>
            );
          })}
        </div>
      </div>

      {active ? (
        <button className="btn wide cash" disabled={busy || !game!.opened.length} onClick={cashout}>
          {game!.opened.length ? <>Забрать {fmt(Math.floor(game!.bet * game!.multiplier))} <i className="coin" /></> : "Откройте клетку"}
        </button>
      ) : (
        <BetPanel
          bet={bet}
          setBet={setBet}
          balance={me?.balance ?? 0}
          action={<button className="btn wide" disabled={busy} onClick={start}>{over ? "Ещё раз" : "Играть"}</button>}
        >
          <div className="opt-label">Мин на поле</div>
          <div className="opts">
            {MINES.map((m) => (
              <button key={m} className={m === mines ? "active" : ""} onClick={() => setMines(m)}>{m}</button>
            ))}
          </div>
        </BetPanel>
      )}
    </div>
  );
}
