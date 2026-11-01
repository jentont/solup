import { useEffect, useRef, useState } from "react";
import { api, fmt, haptic, wsUrl } from "../api";
import { useApp } from "../App";
import { SecTitle } from "../components/ui";

const GROWTH = 0.07; // должно совпадать с backend/app/crash.py
const multAt = (ms: number) => Math.floor(100 * Math.exp((GROWTH * Math.max(ms, 0)) / 1000)) / 100;

type Bet = { user_id: number; name: string; amount: number; auto_cashout: number | null; cashout_at: number | null; payout: number };
type State = {
  phase: "idle" | "betting" | "running" | "crashed";
  round_id: number;
  seed_hash: string;
  betting_ends_at: number;
  started_at: number;
  crash_point: number | null;
  history: number[];
  bets: Bet[];
  seed?: string;
};

export function Crash() {
  const { me, refresh, toast } = useApp();
  const [st, setSt] = useState<State | null>(null);
  const [amount, setAmount] = useState("10");
  const [auto, setAuto] = useState("");
  const [, force] = useState(0);
  const offset = useRef(0); // серверное время - локальное
  const canvas = useRef<HTMLCanvasElement>(null);
  const stRef = useRef<State | null>(null);
  stRef.current = st;

  useEffect(() => {
    let ws: WebSocket;
    let stopped = false;
    const connect = () => {
      ws = new WebSocket(wsUrl("/crash/ws"));
      ws.onmessage = (m) => {
        const e = JSON.parse(m.data);
        offset.current = e.now - Date.now();
        setSt((s) => {
          if (e.type === "state") return e;
          if (!s) return s;
          switch (e.type) {
            case "start":
              return { ...s, phase: "running", started_at: e.started_at };
            case "crash":
              return { ...s, phase: "crashed", crash_point: e.crash_point, seed: e.seed, history: [...s.history, e.crash_point].slice(-20) };
            case "bet":
              return { ...s, bets: [...s.bets.filter((b) => b.user_id !== e.user_id), e] };
            case "cashout":
              return { ...s, bets: s.bets.map((b) => (b.user_id === e.user_id ? { ...b, cashout_at: e.cashout_at, payout: e.payout } : b)) };
          }
          return s;
        });
        if (e.type === "crash" || e.type === "cashout") refresh();
      };
      ws.onclose = () => !stopped && setTimeout(connect, 2000);
    };
    connect();
    return () => {
      stopped = true;
      ws?.close();
    };
  }, [refresh]);

  // Отрисовка графика
  useEffect(() => {
    let raf = 0;
    const draw = () => {
      raf = requestAnimationFrame(draw);
      force((x) => (x + 1) % 1000);
      const c = canvas.current;
      const s = stRef.current;
      if (!c || !s) return;
      const dpr = window.devicePixelRatio || 1;
      const w = c.clientWidth, h = c.clientHeight;
      if (c.width !== w * dpr) { c.width = w * dpr; c.height = h * dpr; }
      const ctx = c.getContext("2d")!;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      if (s.phase !== "running" && s.phase !== "crashed") return;
      const now = Date.now() + offset.current;
      const end = s.phase === "crashed" && s.crash_point ? Math.log(s.crash_point / 100) / GROWTH * 1000 : now - s.started_at;
      const tMax = Math.max(end, 8000);
      const mMax = Math.max(multAt(end), 2);
      const pts: [number, number][] = [];
      for (let i = 0; i <= 60; i++) {
        const t = (end * i) / 60;
        pts.push([(t / tMax) * (w - 20) + 10, h - 10 - ((multAt(t) - 1) / (mMax - 1)) * (h - 30)]);
      }
      const color = s.phase === "crashed" ? "#ffd0d8" : "#ffffff";
      const grad = ctx.createLinearGradient(0, 0, 0, h);
      grad.addColorStop(0, color + "66");
      grad.addColorStop(1, color + "00");
      ctx.beginPath();
      ctx.moveTo(pts[0][0], h - 10);
      pts.forEach(([x, y]) => ctx.lineTo(x, y));
      ctx.lineTo(pts[pts.length - 1][0], h - 10);
      ctx.fillStyle = grad;
      ctx.fill();
      ctx.beginPath();
      pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
      ctx.strokeStyle = color;
      ctx.lineWidth = 3;
      ctx.stroke();
      const [lx, ly] = pts[pts.length - 1];
      ctx.beginPath();
      ctx.arc(lx, ly, 6, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
    };
    draw();
    return () => cancelAnimationFrame(raf);
  }, []);

  const now = Date.now() + offset.current;
  const myBet = st?.bets.find((b) => b.user_id === me?.id);
  let big = "";
  let sub = "";
  if (st?.phase === "betting") {
    big = `${Math.max(0, (st.betting_ends_at - now) / 1000).toFixed(1)}с`;
    sub = "Приём ставок";
  } else if (st?.phase === "running") {
    big = `${multAt(now - st.started_at).toFixed(2)}x`;
  } else if (st?.phase === "crashed" && st.crash_point) {
    big = `${(st.crash_point / 100).toFixed(2)}x`;
    sub = "Краш!";
  }

  const bet = async () => {
    try {
      const a = Math.round(parseFloat(amount.replace(",", ".")) * 100);
      const ac = auto ? Math.round(parseFloat(auto.replace(",", ".")) * 100) : null;
      await api("/crash/bet", { amount: a, auto_cashout: ac });
      haptic();
      refresh();
    } catch (e: any) {
      toast(e.message, "err");
    }
  };
  const cashout = async () => {
    try {
      const r = await api("/crash/cashout", {});
      haptic("success");
      toast(`Забрали ${fmt(r.payout)}`);
    } catch (e: any) {
      toast(e.message, "err");
    }
  };

  const canCashout = st?.phase === "running" && myBet && myBet.cashout_at === null;
  const potential = canCashout && st ? Math.floor(myBet!.amount * multAt(now - st.started_at)) : 0;

  return (
    <div>
      <div className="crash-history">
        {st?.history.slice().reverse().map((p, i) => (
          <span key={i} className={p >= 200 ? "hi" : "lo"}>{(p / 100).toFixed(2)}x</span>
        ))}
      </div>
      <div className={`crash-board ${st?.phase ?? ""}`}>
        <canvas ref={canvas} />
        <div className="crash-mult">
          <div className="big">{big}</div>
          <div className="muted">{sub}</div>
        </div>
      </div>

      <div className="crash-controls">
        <div className="field">
          <label className="muted">Ставка</label>
          <input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />
          <div className="quick">
            {["10", "50", "100", "500"].map((v) => (
              <button key={v} onClick={() => setAmount(v)}>{v}</button>
            ))}
            <button onClick={() => setAmount(String(Math.floor((me?.balance ?? 0) / 100)))}>MAX</button>
          </div>
        </div>
        <div className="field">
          <label className="muted">Автовывод, x</label>
          <input inputMode="decimal" placeholder="—" value={auto} onChange={(e) => setAuto(e.target.value)} />
        </div>
        {canCashout ? (
          <button className="btn wide cash" onClick={cashout}>Забрать {fmt(potential)} <i className="coin" /></button>
        ) : (
          <button className="btn wide" disabled={st?.phase !== "betting" || !!myBet} onClick={bet}>
            {myBet ? (myBet.cashout_at ? `Выигрыш ${fmt(myBet.payout)}` : "Ставка принята") : st?.phase === "betting" ? "Поставить" : "Ждём следующий раунд"}
          </button>
        )}
      </div>

      <SecTitle hand="в этом раунде" title={`Игроки · ${st?.bets.length ?? 0}`} small />
      <div className="bets">
        {st?.bets.map((b) => (
          <div key={b.user_id} className={`bet-row ${b.cashout_at ? "won" : st.phase === "crashed" ? "lost" : ""}`}>
            <span>{b.name}</span>
            <span>{fmt(b.amount)}</span>
            <span>{b.cashout_at ? `${(b.cashout_at / 100).toFixed(2)}x · +${fmt(b.payout)}` : "—"}</span>
          </div>
        ))}
      </div>
      {st && (
        <div className="fair-note muted">
          Раунд #{st.round_id} · hash {st.seed_hash.slice(0, 16)}…{st.seed ? ` · seed ${st.seed.slice(0, 16)}…` : ""}
        </div>
      )}
    </div>
  );
}
