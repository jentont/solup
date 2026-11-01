// Общие элементы Solutions Design: заголовок раздела с рукописной подписью и иконки.
import { useState, type ReactNode } from "react";
import { tg } from "../api";

export function SecTitle({ hand, title, small }: { hand?: string; title: string; small?: boolean }) {
  return (
    <div className={`sec ${small ? "sec--small" : ""}`}>
      {hand && <span className="sec-hand">{hand}</span>}
      <h2 className="sec-title">{title}</h2>
    </div>
  );
}

// Фото профиля: из Telegram (своё), иначе через бота с сервера, иначе первая буква имени
export function Avatar({ id, name, className = "" }: { id?: number; name?: string; className?: string }) {
  const own = tg?.initDataUnsafe?.user;
  const [src, setSrc] = useState<string | null>(
    own?.id === id && own?.photo_url ? own.photo_url : id ? `/api/avatar/${id}` : null,
  );
  return (
    <span className={`avatar-x ${className}`}>
      {src ? <img src={src} alt="" onError={() => setSrc(src.startsWith("/api/") || !id ? null : `/api/avatar/${id}`)} />
        : <b>{name?.[0]?.toUpperCase() ?? "?"}</b>}
    </span>
  );
}

// Шапка экрана игры: кнопка назад к играм и заголовок
export function GameHead({ hand, title, onBack }: { hand: string; title: string; onBack: () => void }) {
  return (
    <div className="game-head">
      <button className="game-back" onClick={onBack} aria-label="К играм"><Icon name="back" size={20} /></button>
      <div>
        <span className="sec-hand">{hand}</span>
        <h2 className="game-head-title">{title}</h2>
      </div>
    </div>
  );
}

// Панель ставки для игр: сумма с быстрыми кнопками, опции игры и главная кнопка
export function BetPanel({ bet, setBet, balance, children, action }: {
  bet: string; setBet: (v: string) => void; balance: number; children?: ReactNode; action: ReactNode;
}) {
  const num = parseFloat(bet.replace(",", ".")) || 0;
  const set = (v: number) => setBet(String(Math.max(1, Math.floor(v * 100) / 100)));
  return (
    <div className="bet-panel">
      <div className="bet-row-in">
        <div className="bet-input">
          <i className="coin" />
          <input inputMode="decimal" value={bet} onChange={(e) => setBet(e.target.value)} aria-label="Ставка" />
        </div>
        <button className="bet-q" onClick={() => set(num / 2)}>½</button>
        <button className="bet-q" onClick={() => set(num * 2)}>×2</button>
        <button className="bet-q" onClick={() => set(balance / 100)}>MAX</button>
      </div>
      {children}
      {action}
    </div>
  );
}

export const toCents = (bet: string) => Math.round(parseFloat(bet.replace(",", ".")) * 100);

const PATHS: Record<string, string> = {
  home: "M4 11.2 12 4l8 7.2V20a1 1 0 0 1-1 1h-4.5v-5.5h-5V21H5a1 1 0 0 1-1-1z",
  box: "M12 2.5 3.5 7v10L12 21.5 20.5 17V7zm0 2.3 5.9 3.1L12 11 6.1 7.9zM5.5 9.6l5.5 2.9v6.4l-5.5-2.9zm7.5 9.3v-6.4l5.5-2.9v6.4z",
  bolt: "M13.5 2 5 13.5h6L9.5 22 19 9.8h-6.2z",
  rocket:
    "M14.5 3.2c3.2-.9 5.6-.7 6.3 0s.9 3.1 0 6.3c-.8 2.8-2.9 5.3-5.6 7.2l.3 3.1-3.3 2-1.2-3.4-3.4-3.4-3.4-1.2 2-3.3 3.1.3c1.9-2.7 4.4-4.8 7.2-5.6zM15 7.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3zM5.6 15.8c-1.5.6-2.4 2.8-2.6 5.2 2.4-.2 4.6-1.1 5.2-2.6z",
  user: "M12 3a4.5 4.5 0 1 1 0 9 4.5 4.5 0 0 1 0-9zm0 10.5c4.4 0 8 2.3 8 5.3V21H4v-2.2c0-3 3.6-5.3 8-5.3z",
  plus: "M11 4h2v7h7v2h-7v7h-2v-7H4v-2h7z",
  gift: "M20 8h-2.2A3 3 0 0 0 12 4.8 3 3 0 0 0 6.2 8H4a1 1 0 0 0-1 1v3h8V8h2v4h8V9a1 1 0 0 0-1-1zM9 8a1 1 0 1 1 1-1v1zm5 0V7a1 1 0 1 1 1 1zM4 13.5V20a1 1 0 0 0 1 1h6v-7.5zm9 0V21h6a1 1 0 0 0 1-1v-6.5z",
  users: "M9 4a4 4 0 1 1 0 8 4 4 0 0 1 0-8zm7.5 1.5a3 3 0 1 1 0 6 3 3 0 0 1 0-6zM9 13.5c4 0 7 2 7 4.6V20H2v-1.9c0-2.6 3-4.6 7-4.6zm8.5.4c2.6.3 4.5 1.9 4.5 3.8V20h-4v-1.9c0-1.6-.2-3-.5-4.2z",
  shield: "M12 2.5 4 5.6v6.1c0 4.9 3.4 8.9 8 9.8 4.6-.9 8-4.9 8-9.8V5.6zm-1.2 13.4-3.6-3.6 1.4-1.4 2.2 2.2 4.8-4.8 1.4 1.4z",
  sun: "M12 7a5 5 0 1 1 0 10 5 5 0 0 1 0-10zm-1-5h2v3h-2zm0 17h2v3h-2zM2 11h3v2H2zm17 0h3v2h-3zM4.2 5.6l1.4-1.4 2.1 2.1-1.4 1.4zm12.1 12.1 1.4-1.4 2.1 2.1-1.4 1.4zM4.2 18.4l2.1-2.1 1.4 1.4-2.1 2.1zM16.3 6.3l2.1-2.1 1.4 1.4-2.1 2.1z",
  moon: "M20.5 14.6A8.5 8.5 0 0 1 9.4 3.5a8.5 8.5 0 1 0 11.1 11.1z",
  arrow: "M5 11h11.2l-4.6-4.6L13 5l7 7-7 7-1.4-1.4 4.6-4.6H5z",
  back: "M19 11H7.8l4.6-4.6L11 5l-7 7 7 7 1.4-1.4L7.8 13H19z",
  games: "M7.5 6h9a5.5 5.5 0 0 1 5.3 7l-1.3 4.6a2.6 2.6 0 0 1-4.5 1L13.9 16h-3.8l-2.1 2.6a2.6 2.6 0 0 1-4.5-1L2.2 13A5.5 5.5 0 0 1 7.5 6zM7 9v1.5H5.5v1.5H7v1.5h1.5V12H10v-1.5H8.5V9zm9.5 0a1 1 0 1 0 0 2 1 1 0 0 0 0-2zm-2 2a1 1 0 1 0 0 2 1 1 0 0 0 0-2zm4 0a1 1 0 1 0 0 2 1 1 0 0 0 0-2z",
};

export function Icon({ name, size = 22 }: { name: keyof typeof PATHS | string; size?: number }) {
  return (
    <svg className="ic" width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <path d={PATHS[name]} fill="currentColor" />
    </svg>
  );
}

export const Star = () => <i className="ic-star" />;
