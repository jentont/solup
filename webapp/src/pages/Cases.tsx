import { useEffect, useRef, useState } from "react";
import { api, Case, fmt, haptic, InvItem, Item } from "../api";
import { useApp } from "../App";
import { Icon, SecTitle } from "../components/ui";
import { ItemCard } from "../components/ItemCard";

const PRICE_FILTERS = [
  { id: "all", label: "Все", test: () => true },
  { id: "cheap", label: "до 1 000", test: (p: number) => p < 100_000 },
  { id: "mid", label: "1 000 – 5 000", test: (p: number) => p >= 100_000 && p <= 500_000 },
  { id: "rich", label: "от 5 000", test: (p: number) => p > 500_000 },
];

export function Cases() {
  const [cases, setCases] = useState<Case[]>([]);
  const [open, setOpen] = useState<Case | null>(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [asc, setAsc] = useState(true);

  useEffect(() => {
    api<Case[]>("/cases").then(setCases);
  }, []);

  if (open) return <CaseView c={open} onBack={() => setOpen(null)} />;

  // Поиск и по названию кейса, и по подаркам внутри
  const q = query.trim().toLowerCase();
  const test = PRICE_FILTERS.find((f) => f.id === filter)!.test;
  const shown = cases
    .filter((c) => test(c.price))
    .filter((c) => !q || c.name.toLowerCase().includes(q) || c.items.some((i) => i.name.toLowerCase().includes(q)))
    .sort((a, b) => (asc ? a.price - b.price : b.price - a.price));

  return (
    <div>
      <SecTitle hand="бесплатно" title="Подарок дня." />
      <DailyGift />

      <SecTitle hand="что внутри?" title="Кейсы." />
      <div className="case-tools">
        <input className="search" placeholder="Кейс или подарок" value={query} onChange={(e) => setQuery(e.target.value)} />
        <button className="sort" onClick={() => setAsc(!asc)}>{asc ? "Дешевле" : "Дороже"}</button>
      </div>
      <div className="chips">
        {PRICE_FILTERS.map((f) => (
          <button key={f.id} className={`chip-f ${filter === f.id ? "on" : ""}`} onClick={() => setFilter(f.id)}>
            {f.label}
          </button>
        ))}
      </div>
      {shown.length === 0 && <div className="empty">Ничего не нашлось</div>}
      <div className="case-grid">
        {shown.map((c) => (
          <button key={c.id} className="case-tile" onClick={() => setOpen(c)}>
            <div className="case-art">
              {c.items.slice(0, 3).map((i, n) =>
                i.image_url ? <img key={i.id} className={`case-art-${n}`} src={i.image_url} alt="" /> : null,
              )}
            </div>
            <div className="case-name">{c.name}</div>
            <div className="case-top">до {fmt(c.items[0]?.value ?? 0)} <i className="coin" /></div>
            <div className="case-price">{fmt(c.price)} <i className="coin" /></div>
          </button>
        ))}
      </div>
    </div>
  );
}

function DailyGift() {
  const { me, setBalance, toast, refresh } = useApp();
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const at = me?.bonus_available_at ? Date.parse(me.bonus_available_at) : 0;
  const left = at - now;
  const claim = async () => {
    try {
      const r = await api("/bonus", {});
      setBalance(r.balance);
      haptic("success");
      toast(`Подарок дня: +${fmt(r.amount)}`);
    } catch (e: any) {
      toast(e.message, "err");
    }
    await refresh();
  };
  return (
    <div className="card daily">
      <div className="daily-art">
        <img src="/gifts/homemadecake.webp" alt="" />
      </div>
      <div className="daily-body">
        <b>Монеты каждый день</b>
        <span className="hint">заходи раз в 24 часа и забирай</span>
      </div>
      {left > 0 ? (
        <div className="timer">{new Date(left).toISOString().slice(11, 19)}</div>
      ) : (
        <button className="pill" onClick={claim}>Забрать</button>
      )}
    </div>
  );
}

const ITEM_W = 104; // ширина ячейки рулетки + отступ
const STRIP = 50;
const WIN_INDEX = 42;

function pickByChance(items: Item[]): Item {
  let r = Math.random();
  for (const i of items) {
    r -= i.chance ?? 0;
    if (r <= 0) return i;
  }
  return items[0];
}

function CaseView({ c, onBack }: { c: Case; onBack: () => void }) {
  const { me, setBalance, toast } = useApp();
  const [count, setCount] = useState(1);
  const [spinning, setSpinning] = useState(false);
  const [strips, setStrips] = useState<Item[][]>([]);
  const [drops, setDrops] = useState<InvItem[] | null>(null);
  const [offsets, setOffsets] = useState<number[]>([]);
  const trackRef = useRef<HTMLDivElement>(null);
  // Быстрое открытие запоминаем в браузере, как удобство конкретного игрока
  const [fast, setFast] = useState(() => {
    try { return localStorage.getItem("fastOpen") === "1"; } catch { return false; }
  });
  const toggleFast = () => {
    setFast(!fast);
    try { localStorage.setItem("fastOpen", fast ? "0" : "1"); } catch { /* приватный режим */ }
  };
  const spinMs = fast ? 1200 : 5400;

  const openCase = async () => {
    if (spinning) return;
    setDrops(null);
    try {
      const res = await api<{ drops: InvItem[]; balance: number }>(`/cases/${c.id}/open`, { count });
      const newStrips = res.drops.map((d) => {
        const s = Array.from({ length: STRIP }, () => pickByChance(c.items));
        s[WIN_INDEX] = d.item;
        return s;
      });
      setStrips(newStrips);
      setOffsets(newStrips.map(() => 0));
      setSpinning(true);
      haptic();
      const width = trackRef.current?.clientWidth ?? 360;
      requestAnimationFrame(() =>
        requestAnimationFrame(() =>
          setOffsets(newStrips.map(() => WIN_INDEX * ITEM_W - width / 2 + ITEM_W / 2 + (Math.random() - 0.5) * 60)),
        ),
      );
      setTimeout(() => {
        setSpinning(false);
        setDrops(res.drops);
        setBalance(res.balance);
        haptic("success");
      }, spinMs + 200);
    } catch (e: any) {
      toast(e.message, "err");
    }
  };

  const sellAll = async () => {
    if (!drops) return;
    try {
      const r = await api("/inventory/sell", { ids: drops.map((d) => d.id) });
      setBalance(r.balance);
      toast(`Продано за ${fmt(r.sold)}`);
      setDrops(null);
      setStrips([]);
    } catch (e: any) {
      toast(e.message, "err");
    }
  };

  const enough = (me?.balance ?? 0) >= c.price * count;
  const showFair = () =>
    toast(`Честная игра: хэш сида ${me?.fair.server_seed_hash.slice(0, 12)}…, ход №${me?.fair.nonce}. Проверка — в Профиле.`);

  return (
    <div>
      <button className="back" onClick={onBack}>← Назад</button>
      <div className="case-head">
        <div className="case-art big">{c.items.slice(0, 3).map((i, n) => i.image_url ? <img key={i.id} className={`case-art-${n}`} src={i.image_url} alt="" /> : null)}</div>
        <h2 className="sec-title">{c.name}.</h2>
      </div>

      <div className="roulette" ref={trackRef}>
        {(strips.length ? strips : [c.items.concat(c.items).slice(0, 8)]).map((s, si) => (
          <div className="roulette-row" key={si}>
            <div
              className="roulette-strip"
              style={{
                transform: `translateX(${-(offsets[si] ?? 0)}px)`,
                transition: spinning && offsets[si] ? `transform ${spinMs}ms cubic-bezier(0.12, 0.8, 0.2, 1)` : "none",
              }}
            >
              {s.map((it, i) => (
                <ItemCard key={i} item={{ ...it, chance: undefined }} size="sm" />
              ))}
            </div>
          </div>
        ))}
        <div className="roulette-marker" />
      </div>

      {drops ? (
        <div className="drops">
          <div className="drops-title">Выпало на {fmt(drops.reduce((a, d) => a + d.item.value, 0))} <i className="coin" /></div>
          <div className="row gap">
            <button className="btn" onClick={sellAll}>Продать всё</button>
            <button className="btn ghost" onClick={() => { setDrops(null); setStrips([]); }}>
              В инвентарь
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className="count-picker">
            {[1, 2, 3, 4, 5].map((n) => (
              <button key={n} className={n === count ? "active" : ""} disabled={spinning} onClick={() => setCount(n)}>
                x{n}
              </button>
            ))}
          </div>
          <div className="open-row">
            <button className="btn" disabled={spinning || !enough} onClick={openCase}>
              {spinning ? "Крутим…" : enough ? <>Открыть за {fmt(c.price * count)} <i className="coin" /></> : "Недостаточно средств"}
            </button>
            <button className={`tool ${fast ? "on" : ""}`} onClick={toggleFast} aria-label="Быстрое открытие" title="Быстрое открытие">
              <Icon name="bolt" size={20} />
            </button>
            <button className="tool" onClick={showFair} aria-label="Честная игра" title="Честная игра">
              <Icon name="shield" size={20} />
            </button>
          </div>
        </>
      )}

      <SecTitle hand="может выпасть" title="Содержимое." small />
      <div className="item-grid">
        {c.items.map((i) => (
          <ItemCard key={i.id} item={i} size="sm" />
        ))}
      </div>
    </div>
  );
}
