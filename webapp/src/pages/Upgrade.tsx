import { useEffect, useMemo, useState } from "react";
import { api, fmt, haptic, InvItem, Item } from "../api";
import { useApp } from "../App";
import { SecTitle } from "../components/ui";
import { ItemCard } from "../components/ItemCard";

export function Upgrade() {
  const { me, setBalance, toast } = useApp();
  const [inv, setInv] = useState<InvItem[]>([]);
  const [items, setItems] = useState<Item[]>([]);
  const [picked, setPicked] = useState<number[]>([]);
  const [extra, setExtra] = useState("");
  const [target, setTarget] = useState<Item | null>(null);
  const [chance, setChance] = useState(0);
  const [angle, setAngle] = useState(0);
  const [spinning, setSpinning] = useState(false);
  const [result, setResult] = useState<"win" | "lose" | null>(null);
  const [burning, setBurning] = useState<string[] | null>(null);

  const load = () => api<InvItem[]>("/inventory").then((r) => setInv(r.filter((i) => i.status === "owned")));
  useEffect(() => {
    load();
    api<Item[]>("/items").then(setItems);
  }, []);

  const extraValue = Math.max(0, Math.round((parseFloat(extra) || 0) * 100));
  const inputValue = useMemo(
    () => inv.filter((i) => picked.includes(i.id)).reduce((a, i) => a + i.item.value, 0) + extraValue,
    [inv, picked, extraValue],
  );
  const targets = items.filter((i) => i.value > inputValue * 1.2);

  useEffect(() => {
    if (!target || !inputValue) return setChance(0);
    const t = setTimeout(() => {
      api(`/upgrade/chance?input_value=${inputValue}&target_value=${target.value}`).then((r) => setChance(r.chance));
    }, 150);
    return () => clearTimeout(t);
  }, [inputValue, target]);

  const toggle = (id: number) =>
    setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : p.length < 10 ? [...p, id] : p));

  const run = async () => {
    if (!target || spinning) return;
    setResult(null);
    setBurning(null);
    // что ставим — запоминаем заранее, чтобы при проигрыше показать, как оно сгорает
    const stake = inv.filter((i) => picked.includes(i.id)).map((i) => i.item.image_url).filter(Boolean) as string[];
    try {
      const r = await api("/upgrade", { inventory_ids: picked, extra: extraValue, target_item_id: target.id });
      setSpinning(true);
      haptic();
      // Стрелка останавливается на значении броска: зелёный сектор [0, chance) — победа
      setAngle((a) => a - (a % 360) + 360 * 5 + r.roll * 360);
      setTimeout(() => {
        setSpinning(false);
        setResult(r.win ? "win" : "lose");
        haptic(r.win ? "success" : "error");
        if (!r.win) setBurning(stake.length ? stake.slice(0, 3) : ["/brand/coin.svg"]);
        setBalance(r.balance);
        setPicked([]);
        setExtra("");
        load();
      }, 4200);
    } catch (e: any) {
      toast(e.message, "err");
    }
  };

  const deg = chance * 360;
  return (
    <div>
      <SecTitle hand="рискнём?" title="Апгрейд." />
      <div className={`upgrade-stage ${result ?? ""}`}>
        <div className="gauge">
          <div className="gauge-ring" style={{ background: `conic-gradient(var(--brand) 0deg ${deg}deg, var(--card-2) ${deg}deg 360deg)` }} />
          <div className="gauge-inner">
            {burning ? (
              <Burn key={burning.join()} imgs={burning} onDone={() => setBurning(null)} />
            ) : target?.image_url ? (
              <img className="gauge-img" src={target.image_url} alt="" />
            ) : (
              <div className="gauge-q">?</div>
            )}
            <div className="gauge-pct">{(chance * 100).toFixed(2)}%</div>
            {result && <div className="gauge-res">{result === "win" ? "ПОБЕДА!" : "МИМО"}</div>}
          </div>
          <div
            className="gauge-needle"
            style={{ transform: `rotate(${angle}deg)`, transition: spinning ? "transform 4s cubic-bezier(0.15,0.85,0.25,1)" : "none" }}
          />
        </div>
        <div className="upgrade-boxes">
          <div className="upgrade-box">
            <div className="upgrade-box-title">Ставка</div>
            <div className="upgrade-thumbs">
              {inv.filter((i) => picked.includes(i.id)).slice(0, 4).map((i) =>
                i.item.image_url ? <img key={i.id} src={i.item.image_url} alt="" /> : <span key={i.id}>{i.item.emoji}</span>,
              )}
            </div>
            <div className="upgrade-value">{fmt(inputValue)} <i className="coin" /></div>
          </div>
          <div className="upgrade-arrow">➜</div>
          <div className="upgrade-box">
            <div className="upgrade-box-title">Цель</div>
            <div className="upgrade-thumbs">
              {target && (target.image_url ? <img src={target.image_url} alt="" /> : <span>{target.emoji}</span>)}
            </div>
            <div className="upgrade-value">{target ? <>{fmt(target.value)} <i className="coin" /></> : "не выбрана"}</div>
          </div>
        </div>
      </div>

      <button className="btn wide" disabled={!target || !inputValue || !chance || spinning} onClick={run}>
        {spinning ? "…" : "Улучшить"}
      </button>

      <SecTitle hand="ставка" title="Ваши предметы." small />
      {inv.length === 0 && <div className="muted">Инвентарь пуст — откройте кейс или поставьте баланс</div>}
      <div className="item-grid">
        {inv.map((i) => (
          <ItemCard key={i.id} item={i.item} size="sm" selected={picked.includes(i.id)} onClick={() => toggle(i.id)} />
        ))}
      </div>
      <div className="extra">
        <label className="muted">+ с баланса (у вас {fmt(me?.balance ?? 0)})</label>
        <input inputMode="decimal" placeholder="0" value={extra} onChange={(e) => setExtra(e.target.value.replace(",", "."))} />
      </div>

      <SecTitle hand="цель" title="Что хотим." small />
      <div className="item-grid">
        {targets.map((i) => (
          <ItemCard key={i.id} item={i} size="sm" selected={target?.id === i.id} onClick={() => setTarget(i)} />
        ))}
      </div>
    </div>
  );
}

// Сгорание поставленного подарка при неудачном апгрейде: накаляется, прогорает
// сверху вниз рваным огненным краем, сыплет искрами и оставляет пепел.
const EMBERS = Array.from({ length: 16 }, (_, i) => ({
  left: 18 + ((i * 37) % 64),
  delay: 0.35 + ((i * 53) % 90) / 100,
  drift: ((i * 29) % 40) - 20,
  size: 3 + (i % 3) * 2,
}));

function Burn({ imgs, onDone }: { imgs: string[]; onDone: () => void }) {
  return (
    <div className="burn" onAnimationEnd={(e) => e.currentTarget === e.target && onDone()}>
      <svg width="0" height="0" aria-hidden="true">
        <filter id="burn-edge">
          <feTurbulence type="fractalNoise" baseFrequency="0.06" numOctaves="2" seed="7" />
          <feDisplacementMap in="SourceGraphic" scale="10" />
        </filter>
      </svg>
      <div className="burn-stack">
        {imgs.map((src, n) => (
          <img key={n} className={`burn-img burn-img-${n}`} src={src} alt="" />
        ))}
        <div className="burn-glow" />
      </div>
      {EMBERS.map((e, n) => (
        <i
          key={n}
          className="ember"
          style={{
            left: `${e.left}%`, width: e.size, height: e.size, animationDelay: `${e.delay}s`,
            ["--drift" as any]: `${e.drift}px`,
          }}
        />
      ))}
      <div className="ash" />
    </div>
  );
}
