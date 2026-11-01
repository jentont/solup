import { useEffect, useState } from "react";
import { api, fmt, InvItem, Item, tg } from "../api";
import { useApp } from "../App";
import { Avatar, Icon } from "../components/ui";
import { ItemCard } from "../components/ItemCard";

type Withdrawal = { id: number; status: string; created_at: string; item: Item };
type Tx = { id: number; amount: number; kind: string; created_at: string; note: string | null };

const STATUS: Record<string, string> = {
  pending: "ожидает", processing: "отправляется", done: "отправлен", failed: "ошибка", rejected: "отклонён",
};
const KIND: Record<string, string> = {
  deposit_stars: "Пополнение Stars", deposit_crypto: "Пополнение крипто", deposit_gift: "Пополнение подарком",
  case_open: "Открытие кейса", item_sell: "Продажа", upgrade: "Апгрейд", crash_bet: "Ставка краш",
  crash_win: "Выигрыш краш", crash_refund: "Возврат ставки", upgrade_win: "Апгрейд удался", upgrade_lose: "Апгрейд не удался",
  deposit_bonus: "Бонус к пополнению", bonus: "Ежедневный кейс", referral: "Реферальные", admin: "Корректировка",
  mines_bet: "Ставка мины", mines_win: "Выигрыш мины", tower_bet: "Ставка башня", tower_win: "Выигрыш башня",
  wheel_bet: "Ставка колесо", wheel_win: "Выигрыш колесо",
  plinko_bet: "Ставка плинко", plinko_win: "Выигрыш плинко",
  dice_bet: "Ставка дайс", dice_win: "Выигрыш дайс",
  limbo_bet: "Ставка лимбо", limbo_win: "Выигрыш лимбо",
  coinflip_bet: "Ставка монетка", coinflip_win: "Выигрыш монетка",
  roulette_bet: "Ставка рулетка", roulette_win: "Выигрыш рулетка",
  hilo_bet: "Ставка Hi-Lo", hilo_win: "Выигрыш Hi-Lo",
  blackjack_bet: "Ставка блэкджек", blackjack_win: "Выигрыш блэкджек",
  slots_bet: "Ставка слоты", slots_win: "Выигрыш слоты",
  keno_bet: "Ставка кено", keno_win: "Выигрыш кено",
  rps_bet: "Ставка камень-ножницы", rps_win: "Выигрыш камень-ножницы",
};

export function Profile({ initialView = "inv" }: { initialView?: "inv" | "fair" }) {
  const { me, refresh, setBalance, toast, openDeposit, demo, dark, toggleTheme } = useApp();
  const [inv, setInv] = useState<InvItem[]>([]);
  const [wds, setWds] = useState<Withdrawal[]>([]);
  const [txs, setTxs] = useState<Tx[]>([]);
  const [sel, setSel] = useState<InvItem | null>(null);
  const [view, setView] = useState<"inv" | "wd" | "tx" | "fair">(initialView);
  const [revealed, setRevealed] = useState<any>(null);
  const [clientSeed, setClientSeed] = useState("");

  const load = () => {
    api<InvItem[]>("/inventory").then(setInv);
    api<Withdrawal[]>("/withdrawals").then(setWds);
    api<Tx[]>("/history").then(setTxs);
  };
  useEffect(load, []);

  const sell = async (ids: number[]) => {
    try {
      const r = await api("/inventory/sell", { ids });
      setBalance(r.balance);
      toast(`Продано за ${fmt(r.sold)}`);
      setSel(null);
      load();
    } catch (e: any) {
      toast(e.message, "err");
    }
  };

  const withdraw = async (i: InvItem) => {
    try {
      const r = await api(`/inventory/${i.id}/withdraw`, {});
      toast(r.status === "done" ? "Подарок отправлен!" : r.status === "pending" ? "Заявка создана" : "Не удалось, предмет возвращён", r.status === "failed" ? "err" : "ok");
      setSel(null);
      load();
    } catch (e: any) {
      toast(e.message, "err");
    }
  };

  const rotate = async () => {
    const r = await api("/fair/rotate", { client_seed: clientSeed || null });
    setRevealed(r);
    refresh();
  };

  const share = () => {
    if (!me?.ref_link) return;
    const text = "Открывай кейсы с подарками Telegram!";
    if (tg) tg.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(me.ref_link)}&text=${encodeURIComponent(text)}`);
    else navigator.clipboard?.writeText(me.ref_link).then(() => toast("Ссылка скопирована"));
  };

  const copy = () => me?.ref_link && navigator.clipboard?.writeText(me.ref_link).then(() => toast("Ссылка скопирована"));

  const owned = inv.filter((i) => i.status === "owned");
  const total = owned.reduce((a, i) => a + i.item.value, 0);

  return (
    <div>
      <div className="pcard">
        <span className="rays" />
        <div className="pcard-top">
          <Avatar id={me?.id} name={me?.first_name} className="pavatar" />
          <div className="pcard-who">
            <div className="pcard-name">{me?.first_name}</div>
            <div className="pcard-id">{me?.username ? `@${me.username}` : `ID ${me?.id}`}</div>
          </div>
          {demo && <span className="pcard-demo">демо</span>}
          <button className="pcard-theme" onClick={toggleTheme} aria-label={dark ? "Светлая тема" : "Тёмная тема"}>
            <Icon name={dark ? "sun" : "moon"} size={18} />
          </button>
        </div>
        <div className="pcard-bal">
          <span>Баланс</span>
          <b>{fmt(me?.balance ?? 0)} <i className="coin" /></b>
        </div>
        <div className="pcard-acts">
          <button className="pact pact--main" onClick={openDeposit}><Icon name="plus" size={18} />Пополнить</button>
          <button className="pact" onClick={() => setView("inv")}><Icon name="gift" size={18} />Вывести</button>
        </div>
      </div>

      <div className="pstats">
        <div><b>{owned.length}</b><span>предметов</span></div>
        <div><b>{fmt(total)} <i className="coin" /></b><span>в инвентаре</span></div>
        <div><b>{me?.referrals ?? 0}</b><span>друзей</span></div>
      </div>

      <div className="pref hue-upgrade">
        <span className="rays" />
        <img className="pref-img" src="/gifts/preciouspeach.webp" alt="" />
        <div className="pref-body">
          <b>Зови друзей — {me?.referral_percent}%</b>
          <span>с каждого их пополнения · заработано {fmt(me?.ref_earned ?? 0)}</span>
          <div className="pref-acts">
            <button className="hero-btn daily-btn" onClick={share} disabled={!me?.ref_link}>Пригласить</button>
            <button className="pref-copy" onClick={copy} disabled={!me?.ref_link} aria-label="Скопировать ссылку">Копировать</button>
          </div>
        </div>
      </div>

      <div className="pill-tabs seg-profile">
        {([["inv", "Инвентарь"], ["wd", "Выводы"], ["tx", "История"], ["fair", "Честность"]] as const).map(([k, l]) => (
          <button key={k} className={view === k ? "active" : ""} onClick={() => setView(k)}>{l}</button>
        ))}
      </div>

      {view === "inv" && (
        <>
          <div className="row between">
            <span className="muted">{owned.length} предметов · {fmt(total)} <i className="coin" /></span>
            {owned.length > 0 && <button className="link" onClick={() => sell(owned.map((i) => i.id))}>Продать всё</button>}
          </div>
          {inv.length === 0 && <div className="empty">Пока пусто — открой кейс</div>}
          <div className="item-grid">
            {inv.map((i) => (
              <ItemCard key={i.id} item={i.item} size="sm" onClick={() => i.status === "owned" && setSel(i)}
                footer={i.status === "withdrawing" ? <div className="badge">вывод…</div> : null} />
            ))}
          </div>
        </>
      )}

      {view === "wd" && (
        <div className="list">
          {wds.length === 0 && <div className="empty">Выводов пока нет</div>}
          {wds.map((w) => (
            <div key={w.id} className="list-row">
              <span>{w.item.emoji} {w.item.name}</span>
              <span>{STATUS[w.status] ?? w.status}</span>
            </div>
          ))}
        </div>
      )}

      {view === "tx" && (
        <div className="list">
          {txs.map((t) => (
            <div key={t.id} className="list-row">
              <span>{KIND[t.kind] ?? t.kind}<br />
                {t.note && <small className="muted">{t.note}<br /></small>}
                <small className="muted">{new Date(t.created_at + "Z").toLocaleString("ru-RU")}</small></span>
              {t.amount === 0 ? <span className={t.kind === "upgrade_win" ? "pos" : "neg"}>{t.kind === "upgrade_win" ? "удался" : "мимо"}</span> : <span className={t.amount > 0 ? "pos" : "neg"}>{t.amount > 0 ? "+" : ""}{fmt(t.amount)}</span>}
            </div>
          ))}
        </div>
      )}

      {view === "fair" && me && (
        <div className="fair">
          <p className="muted">
            Результат каждой игры = HMAC-SHA256(server_seed, "client_seed:nonce"). Хэш server seed известен заранее,
            сам seed раскрывается при смене — так можно проверить, что результаты не подменялись.
          </p>
          <div className="kv"><span>Server seed hash</span><code>{me.fair.server_seed_hash}</code></div>
          <div className="kv"><span>Client seed</span><code>{me.fair.client_seed}</code></div>
          <div className="kv"><span>Nonce</span><code>{me.fair.nonce}</code></div>
          <input placeholder="Новый client seed (необязательно)" value={clientSeed} onChange={(e) => setClientSeed(e.target.value)} />
          <button className="btn wide" onClick={rotate}>Сменить seed и раскрыть текущий</button>
          {revealed && (
            <div className="kv"><span>Раскрытый server seed</span><code>{revealed.server_seed}</code></div>
          )}
        </div>
      )}

      {sel && (
        <div className="sheet-bg" onClick={() => setSel(null)}>
          <div className="sheet" onClick={(e) => e.stopPropagation()}>
            <ItemCard item={sel.item} />
            <button className="btn wide" onClick={() => sell([sel.id])}>Продать за {fmt(sel.item.value)} <i className="coin" /></button>
            {sel.item.withdrawable && !sel.demo && (
              <button className="btn wide ghost" onClick={() => withdraw(sel)}>Вывести подарок в Telegram</button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
