import { useEffect, useState } from "react";
import { api, fmt, haptic } from "../api";
import { useApp } from "../App";
import { BetPanel, GameHead, toCents } from "../components/ui";

const COLORS: Record<string, string> = {
  "0": "#262a52", "1.2": "#3d7bff", "1.5": "#22c08a", "2": "#a35cff", "3": "#ffb020", "5": "#ff5a4f", "8": "#ff4fb8",
};
const RISKS = [{ id: "low", label: "Спокойное" }, { id: "high", label: "Рисковое" }];
const R = 140;
const SPIN_MS = 4200;

// Точка на окружности: угол по часовой стрелке от верха
const pt = (deg: number, r: number) => {
  const a = (deg * Math.PI) / 180;
  return `${(r * Math.sin(a)).toFixed(2)} ${(-r * Math.cos(a)).toFixed(2)}`;
};

function WheelSvg({ segments, rotation, won }: { segments: number[]; rotation: number; won: number | null }) {
  const step = 360 / segments.length;
  return (
    <svg className="wheel-svg" viewBox="-150 -150 300 300" aria-hidden="true">
      <circle r="148" fill="none" stroke="rgba(255,255,255,.14)" strokeWidth="4" />
      <g style={{ transform: `rotate(${rotation}deg)`, transition: `transform ${SPIN_MS}ms cubic-bezier(.12,.72,.14,1)` }}>
        {segments.map((m, i) => {
          const a0 = i * step - step / 2;
          const a1 = a0 + step;
          return (
            <g key={i} className={won === i ? "seg won" : "seg"}>
              <path d={`M0 0 L${pt(a0, R)} A${R} ${R} 0 0 1 ${pt(a1, R)} Z`} fill={COLORS[String(m)]} stroke="#0d0f22" strokeWidth="1.5" />
              {m > 0 && (
                <text transform={`rotate(${i * step}) translate(0 ${-R * 0.74}) rotate(90)`} className="seg-label">
                  ×{m}
                </text>
              )}
            </g>
          );
        })}
      </g>
      <circle r="40" fill="#0d0f22" stroke="rgba(255,255,255,.12)" strokeWidth="2" />
    </svg>
  );
}

export function Wheel() {
  const { me, setBalance, toast, go } = useApp();
  const [wheels, setWheels] = useState<Record<string, number[]> | null>(null);
  const [risk, setRisk] = useState("low");
  const [bet, setBet] = useState("10");
  const [rotation, setRotation] = useState(0);
  const [spinning, setSpinning] = useState(false);
  const [result, setResult] = useState<{ index: number; multiplier: number; payout: number } | null>(null);

  useEffect(() => {
    api("/wheel").then((r) => setWheels(r.wheels));
  }, []);

  const segments = wheels?.[risk] ?? [];
  const legend = [...new Set(segments)].sort((a, b) => a - b);

  const spin = async () => {
    if (spinning) return;
    setSpinning(true);
    setResult(null);
    try {
      const r = await api("/wheel/spin", { bet: toCents(bet), risk });
      haptic();
      const step = 360 / segments.length;
      // докручиваем так, чтобы центр выпавшего сектора встал под стрелку, плюс 5 полных оборотов
      const target = (((-r.index * step - rotation) % 360) + 360) % 360;
      setRotation(rotation + 360 * 5 + target);
      setTimeout(() => {
        setResult(r);
        setBalance(r.balance);
        setSpinning(false);
        if (r.payout) {
          haptic("success");
          toast(`×${r.multiplier} · +${fmt(r.payout)}`);
        } else haptic("error");
      }, SPIN_MS);
    } catch (e: any) {
      toast(e.message, "err");
      setSpinning(false);
    }
  };

  return (
    <div className="game-page">
      <GameHead hand="испытай удачу" title="Колесо" onBack={() => go("home")} />

      <div className={`stage hue-wheel ${result ? (result.payout ? "win" : "lose") : ""}`}>
        <div className="wheel">
          <i className="wheel-pointer" />
          <WheelSvg segments={segments} rotation={rotation} won={spinning ? null : result?.index ?? null} />
          <div className="wheel-center">
            {result ? <b className={result.payout ? "pos" : "neg"}>×{result.multiplier}</b> : <img src="/gifts/recordplayer.webp" alt="" />}
          </div>
        </div>
        <div className="wheel-legend">
          {legend.map((m) => (
            <span key={m} className={result?.multiplier === m && !spinning ? "on" : ""}>
              <i style={{ background: COLORS[String(m)] }} />×{m}
            </span>
          ))}
        </div>
      </div>

      <BetPanel
        bet={bet}
        setBet={setBet}
        balance={me?.balance ?? 0}
        action={<button className="btn wide" disabled={spinning || !wheels} onClick={spin}>{spinning ? "Крутится…" : "Крутить"}</button>}
      >
        <div className="opts opts--2">
          {RISKS.map((r) => (
            <button key={r.id} className={r.id === risk ? "active" : ""} disabled={spinning}
              onClick={() => { setRisk(r.id); setResult(null); }}>{r.label}</button>
          ))}
        </div>
      </BetPanel>
    </div>
  );
}
