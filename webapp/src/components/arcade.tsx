// Общее для мини-игр: ставка через /play, пошаговые раунды через /round, таблицы выплат и игральная карта.
import { useEffect, useState } from "react";
import { api, fmt, haptic } from "../api";
import { useApp } from "../App";
import { toCents } from "./ui";

export type PlayResult<D = any> = { multiplier: number; payout: number; detail: D; balance: number };

// Мгновенная игра: play() списывает ставку и возвращает результат; finish() — после анимации
export function usePlay<D = any>(game: string) {
  const { setBalance, toast } = useApp();
  const [busy, setBusy] = useState(false);
  const play = async (bet: string, params: object = {}): Promise<PlayResult<D> | null> => {
    if (busy) return null;
    setBusy(true);
    try {
      const r = await api<PlayResult<D>>(`/play/${game}`, { bet: toCents(bet), params });
      haptic();
      return r;
    } catch (e: any) {
      toast(e.message, "err");
      setBusy(false);
      return null;
    }
  };
  const finish = (r: PlayResult<D>) => {
    setBusy(false);
    setBalance(r.balance);
    if (r.payout) {
      haptic("success");
      toast(`×${+r.multiplier.toFixed(2)} · +${fmt(r.payout)}`);
    } else haptic("error");
  };
  return { play, finish, busy };
}

// Пошаговая игра (Hi-Lo, блэкджек): состояние раунда и ходы
export function useRound<G>(game: string) {
  const { setBalance, toast } = useApp();
  const [g, setG] = useState<G | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api(`/round/${game}`).then((r) => setG(r.game));
  }, [game]);
  const act = async (action: string, bet = "0") => {
    if (busy) return null;
    setBusy(true);
    try {
      const r = await api(`/round/${game}`, { action, bet: action === "start" ? toCents(bet) : 0 });
      setG(r.game);
      setBalance(r.balance);
      return r.game as G;
    } catch (e: any) {
      toast(e.message, "err");
      return null;
    } finally {
      setBusy(false);
    }
  };
  return { g, act, busy };
}

// Таблицы выплат с сервера — одни на все экраны
let tablesReq: Promise<any> | null = null;
export function useTables() {
  const [t, setT] = useState<any>(null);
  useEffect(() => {
    tablesReq ??= api("/arcade");
    tablesReq.then(setT);
  }, []);
  return t;
}

export const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

const RANKS = ["", "A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"];
const SUITS = ["♠", "♥", "♦", "♣"];

// Колода бесконечная, у карты есть только достоинство; масть — для вида, по позиции
export function PlayCard({ rank, i = 0, hidden }: { rank?: number; i?: number; hidden?: boolean }) {
  if (hidden || !rank) return <div className="pcard-x back" style={{ animationDelay: `${i * 0.08}s` }} />;
  const suit = SUITS[(rank + i) % 4];
  return (
    <div className={`pcard-x ${suit === "♥" || suit === "♦" ? "red" : ""}`} style={{ animationDelay: `${i * 0.08}s` }}>
      <span className="pc-r">{RANKS[rank]}</span>
      <span className="pc-s">{suit}</span>
      <span className="pc-r pc-r2">{RANKS[rank]}</span>
    </div>
  );
}
