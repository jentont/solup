import { useEffect, useRef, useState } from "react";
import { api, Case, fmt, haptic, InvItem, Item } from "../api";
import { useApp } from "../App";
import { GameHead, Icon, SecTitle } from "../components/ui";
import { ItemCard } from "../components/ItemCard";

// Разделы витрины: кейсы по slug, остальные — в «Разное»
const GROUPS = [
  { id: "new", label: "Новинки", slugs: ["new", "spooky", "halloween"] },
  { id: "cheap", label: "На сдачу", slugs: ["piggy", "starter", "sweet", "party"] },
  { id: "theme", label: "Тематические", slugs: ["love", "magic", "gentleman"] },
  { id: "rich", label: "Хайроллер", slugs: ["luxury", "durov", "legend", "pepe"] },
];
const groupOf = (slug: string) => GROUPS.find((g) => g.slugs.includes(slug))?.id ?? "other";

// Карточка кейса: коллаж из пяти самых дорогих подарков на свечении цвета главного
// Кейсы со своим объектом из /art (вырезан из макетов) — он вместо главного подарка коллажа
const CASE_ART: Record<string, string> = { spooky: "case-spooky", piggy: "case-piggy" };

export function CaseTile({ c, onClick }: { c: Case; onClick: () => void }) {
  const art = c.items.filter((i) => i.image_url).slice(0, 5);
  const pic = CASE_ART[c.slug];
  return (
    <button className={`case-tile r-${art[0]?.rarity ?? "common"}`} onClick={onClick}>
      <div className={`case-art ${pic ? "case-art--pic" : ""}`}>
        <i className="case-spark s1" /><i className="case-spark s2" /><i className="case-spark s3" />
        {/* у кейса со своим объектом он в центре, а подарки — по углам */}
        {pic && <img className="case-obj" src={`/art/${pic}.webp`} alt="" />}
        {(pic ? art.slice(1, 5) : art).map((i, n) => <img key={i.id} className={`case-art-${pic ? n + 1 : n}`} src={i.image_url!} alt="" />)}
      </div>
      <div className="case-foot">
        <span className="case-name">{c.name}</span>
        <span className="case-price">{fmt(c.price)} <i className="coin" /></span>
      </div>
    </button>
  );
}

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
  const shown = cases
    .filter((c) => !q || c.name.toLowerCase().includes(q) || c.items.some((i) => i.name.toLowerCase().includes(q)))
    .sort((a, b) => (asc ? a.price - b.price : b.price - a.price));
  const sections = [...GROUPS, { id: "other", label: "Разное", slugs: [] }]
    .filter((g) => filter === "all" || filter === g.id)
    .map((g) => ({ ...g, cases: shown.filter((c) => groupOf(c.slug) === g.id) }))
    .filter((g) => g.cases.length);
  const plural = (n: number) => (n % 10 === 1 && n % 100 !== 11 ? "кейс" : [2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100) ? "кейса" : "кейсов");

  return (
    <div>
      <SecTitle hand="раз в сутки" title="Бесплатный кейс." />
      <DailyCase />

      <div className="case-tools case-tools--sticky">
        <input className="search" placeholder="Кейс или подарок" value={query} onChange={(e) => setQuery(e.target.value)} />
        <button className="sort" onClick={() => setAsc(!asc)} aria-label="Сортировка">{asc ? "↑ цена" : "↓ цена"}</button>
      </div>
      <div className="chips">
        {[{ id: "all", label: "Все" }, ...GROUPS].map((f) => (
          <button key={f.id} className={`chip-f ${filter === f.id ? "on" : ""}`} onClick={() => setFilter(f.id)}>
            {f.label}
          </button>
        ))}
      </div>
      {sections.length === 0 && <div className="empty">Ничего не нашлось</div>}
      {sections.map((g) => (
        <section key={g.id}>
          <div className="case-sec">
            <h2>{g.label}</h2>
            <span>{g.cases.length} {plural(g.cases.length)}</span>
          </div>
          <div className="case-grid">
            {g.cases.map((c) => <CaseTile key={c.id} c={c} onClick={() => setOpen(c)} />)}
          </div>
        </section>
      ))}
    </div>
  );
}

type Prize = { amount: number; chance: number };
const PRIZE_RARITY: Item["rarity"][] = ["common", "common", "common", "uncommon", "rare", "epic", "legendary", "legendary"];

function PrizeCard({ p, i }: { p: Prize; i: number }) {
  return (
    <div className={`item-card sm prize r-${PRIZE_RARITY[i]}`}>
      <div className="item-emoji"><i className="coin prize-coin" style={{ fontSize: 30 + i * 4 }} /></div>
      <div className="item-value">{fmt(p.amount)}</div>
    </div>
  );
}

// Ежедневный кейс: призы в монетах, своя рулетка, открывается раз в 24 часа
function DailyCase() {
  const { me, setBalance, toast, refresh } = useApp();
  const [now, setNow] = useState(Date.now());
  const [prizes, setPrizes] = useState<Prize[]>([]);
  const [strip, setStrip] = useState<number[]>([]);
  const [offset, setOffset] = useState(0);
  const [spinning, setSpinning] = useState(false);
  const trackRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    api("/bonus").then((r) => setPrizes(r.prizes));
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const at = me?.bonus_available_at ? Date.parse(me.bonus_available_at) : 0;
  const left = at - now;

  const pick = () => {
    let r = Math.random();
    for (let i = 0; i < prizes.length; i++) if ((r -= prizes[i].chance) <= 0) return i;
    return 0;
  };
  const open = async () => {
    if (spinning) return;
    try {
      const r = await api("/bonus", {});
      const s = Array.from({ length: STRIP }, pick);
      s[WIN_INDEX] = r.index;
      setStrip(s);
      setOffset(0);
      setSpinning(true);
      haptic();
      const width = trackRef.current?.clientWidth ?? 360;
      requestAnimationFrame(() =>
        requestAnimationFrame(() => setOffset(WIN_INDEX * ITEM_W - width / 2 + ITEM_W / 2 + (Math.random() - 0.5) * 36)),
      );
      setTimeout(async () => {
        setSpinning(false);
        setBalance(r.balance);
        haptic("success");
        toast(`Бесплатный кейс: +${fmt(r.amount)}`);
        await refresh();
      }, 4600);
    } catch (e: any) {
      toast(e.message, "err");
      await refresh();
    }
  };

  return (
    <div className="daily-case hue-cases">
      <span className="rays" />
      <img className="daily-case-img" src="/gifts/lootbag.webp" alt="" />
      <div className="daily-case-body">
        <b>Ежедневный кейс</b>
        <span>до {prizes.length ? fmt(prizes[prizes.length - 1].amount) : "500"} монет, бесплатно</span>
        {left > 0 && !spinning ? (
          <div className="daily-timer">через {new Date(left).toISOString().slice(11, 19)}</div>
        ) : (
          <button className="hero-btn daily-btn" disabled={spinning || !prizes.length} onClick={open}>
            {spinning ? "Крутим…" : "Открыть"}
          </button>
        )}
      </div>
      {prizes.length > 0 && (
        <div className="roulette daily-roulette" ref={trackRef}>
          <div className="roulette-row">
            <div
              className="roulette-strip"
              style={{
                transform: `translateX(${-offset}px)`,
                transition: spinning && offset ? "transform 4400ms cubic-bezier(0.12, 0.8, 0.2, 1)" : "none",
              }}
            >
              {(strip.length ? strip : prizes.map((_, i) => i).concat(prizes.map((_, i) => i))).map((pi, i) => (
                <PrizeCard key={i} p={prizes[pi]} i={pi} />
              ))}
            </div>
          </div>
          <div className="roulette-marker" />
        </div>
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
      <GameHead hand="кейс" title={c.name} onBack={onBack} />
      <div className={`case-head r-${c.items[0]?.rarity ?? "common"}`}>
        <div className="case-art big">
          <i className="case-spark s1" /><i className="case-spark s2" /><i className="case-spark s3" />
          {c.items.filter((i) => i.image_url).slice(0, 5).map((i, n) => <img key={i.id} className={`case-art-${n}`} src={i.image_url!} alt="" />)}
        </div>
        <div className="case-head-sub">до {fmt(c.items[0]?.value ?? 0)} <i className="coin" /> · {c.items.length} подарков</div>
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
