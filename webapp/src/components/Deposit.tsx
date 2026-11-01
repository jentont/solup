import { useEffect, useState } from "react";
import { api, fmt, haptic, Item, tg } from "../api";
import { useApp } from "../App";
import { Star } from "./ui";

type Info = {
  stars: { enabled: boolean; coins_per_star: number; bonus_percent: number };
  crypto: { enabled: boolean; coins_per_unit: Record<string, number>; bonus_percent: number };
  gifts: { enabled: boolean; relayer: string };
};

const STAR_PACKS = [50, 100, 200, 500, 1000, 2500, 5000, 10000];
const CRYPTO_PACKS: Record<string, number[]> = { TON: [1, 3, 5, 10, 25, 50], USDT: [5, 10, 25, 50, 100, 250] };

function openLink(url: string) {
  if (tg?.openTelegramLink && url.startsWith("https://t.me/")) tg.openTelegramLink(url);
  else window.open(url, "_blank");
}

export function Deposit({ onClose }: { onClose: () => void }) {
  const { refresh, toast } = useApp();
  const [info, setInfo] = useState<Info | null>(null);
  const [gifts, setGifts] = useState<Item[]>([]);
  const [tab, setTab] = useState<"stars" | "crypto" | "gifts">("stars");
  const [asset, setAsset] = useState<"TON" | "USDT">("TON");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<Info>("/deposit/info").then(setInfo);
    api<Item[]>("/items").then((items) => setGifts(items.filter((i) => i.withdrawable).sort((a, b) => b.value - a.value)));
  }, []);

  const payStars = async (stars: number) => {
    if (busy) return;
    setBusy(true);
    try {
      const { link } = await api("/deposit/stars", { stars });
      if (!tg?.openInvoice) return openLink(link);
      tg.openInvoice(link, (status: string) => {
        if (status === "paid") {
          haptic("success");
          toast("Оплачено! Баланс обновится через пару секунд");
          setTimeout(refresh, 1500);
          onClose();
        }
      });
    } catch (e: any) {
      toast(e.message, "err");
    } finally {
      setBusy(false);
    }
  };

  const payCrypto = async (amount: number) => {
    if (busy) return;
    setBusy(true);
    try {
      const { url } = await api("/deposit/crypto", { asset, amount: String(amount) });
      openLink(url);
      toast("После оплаты баланс зачислится в течение ~15 секунд");
    } catch (e: any) {
      toast(e.message, "err");
    } finally {
      setBusy(false);
    }
  };

  const starRate = info?.stars.coins_per_star ?? 1;
  const starBonus = info?.stars.bonus_percent ?? 0;
  const cryptoRate = info?.crypto.coins_per_unit[asset] ?? 0;
  const cryptoBonus = info?.crypto.bonus_percent ?? 0;

  return (
    <div className="sheet-bg" onClick={onClose}>
      <div className="sheet deposit" onClick={(e) => e.stopPropagation()}>
        <div className="grabber" />
        <div className="row between">
          <h2 className="sheet-title">Пополнение.</h2>
          <button className="close" onClick={onClose}>✕</button>
        </div>
        <div className="pill-tabs">
          <button className={tab === "stars" ? "active" : ""} onClick={() => setTab("stars")}>
            <Star /> Stars{starBonus > 0 && <span className="bonus-tag">+{starBonus}%</span>}
          </button>
          <button className={tab === "crypto" ? "active" : ""} onClick={() => setTab("crypto")}>
            <img className="ic-img" src="/brand/ton.svg" alt="" /> Крипта{cryptoBonus > 0 && <span className="bonus-tag">+{cryptoBonus}%</span>}
          </button>
          <button className={tab === "gifts" ? "active" : ""} onClick={() => setTab("gifts")}>Подарки</button>
        </div>

        {tab === "stars" && (
          <div className="packs">
            {!info?.stars.enabled && <div className="note">Оплата звёздами появится после запуска бота</div>}
            {STAR_PACKS.map((s) => {
              const coins = Math.round(s * starRate * 100);
              return (
                <button key={s} className="pack" disabled={!info?.stars.enabled || busy} onClick={() => payStars(s)}>
                  <span className="pack-get">
                    <i className="coin" /> {fmt(coins)}
                    {starBonus > 0 && <span className="pack-bonus">+{fmt(Math.floor((coins * starBonus) / 100))}</span>}
                  </span>
                  <span className="pack-price">{s} <Star /></span>
                </button>
              );
            })}
          </div>
        )}

        {tab === "crypto" && (
          <div className="packs">
            <div className="pill-tabs small">
              {(["TON", "USDT"] as const).map((a) => (
                <button key={a} className={asset === a ? "active" : ""} onClick={() => setAsset(a)}>{a}</button>
              ))}
            </div>
            {!info?.crypto.enabled && <div className="note">Криптопополнение появится после подключения @CryptoBot</div>}
            {CRYPTO_PACKS[asset].map((a) => {
              const coins = Math.round(a * cryptoRate * 100);
              return (
                <button key={a} className="pack" disabled={!info?.crypto.enabled || busy} onClick={() => payCrypto(a)}>
                  <span className="pack-get">
                    <i className="coin" /> {cryptoRate ? fmt(coins) : "—"}
                    {cryptoBonus > 0 && cryptoRate > 0 && (
                      <span className="pack-bonus">+{fmt(Math.floor((coins * cryptoBonus) / 100))}</span>
                    )}
                  </span>
                  <span className="pack-price">{a} {asset}</span>
                </button>
              );
            })}
          </div>
        )}

        {tab === "gifts" && (
          <div className="packs">
            <button className="note link-note" disabled={!info?.gifts.enabled}
              onClick={() => openLink(`https://t.me/${info!.gifts.relayer}`)}>
              Отправь свой подарок <u>@{info?.gifts.relayer || "—"}</u> и получи <i className="coin" /> на баланс
            </button>
            <div className="sec sec--small"><span className="sec-hand">прайс</span><h2 className="sec-title">Сколько дадим.</h2></div>
            {gifts.map((g) => (
              <div key={g.id} className="pack gift-row">
                <span className="gift-name">
                  {g.image_url ? <img src={g.image_url} alt="" /> : g.emoji} {g.name}
                </span>
                <span className="gift-val">+{fmt(g.value)} <i className="coin" /></span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
