// Клиент API. В Telegram авторизуемся через initData, в браузере при DEV_AUTH — через ?dev=<user_id>.

export const tg = (window as any).Telegram?.WebApp;

const devId = new URLSearchParams(location.search).get("dev");
export const authHeader: string = tg?.initData ? `tma ${tg.initData}` : devId ? `dev ${devId}` : "";

// Демо-режим: игра на демо-баланс. Выбор помнит браузер игрока.
let demoMode = (() => {
  try {
    return localStorage.getItem("demo") === "1";
  } catch {
    return false;
  }
})();
export const isDemo = () => demoMode;
export function setDemoMode(on: boolean) {
  demoMode = on;
  try {
    localStorage.setItem("demo", on ? "1" : "0");
  } catch {
    /* приватный режим браузера */
  }
}

export class ApiError extends Error {}

export async function api<T = any>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: { Authorization: authHeader, "Content-Type": "application/json", "X-Demo": demoMode ? "1" : "0" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(typeof data.detail === "string" ? data.detail : "Ошибка запроса");
  return data as T;
}

export function wsUrl(path: string): string {
  return `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api${path}`;
}

export type Item = {
  id: number;
  name: string;
  emoji: string;
  image_url: string | null;
  rarity: "common" | "uncommon" | "rare" | "epic" | "legendary";
  value: number;
  withdrawable: boolean;
  chance?: number;
};

export type Case = { id: number; slug: string; name: string; emoji: string; price: number; items: Item[] };

export type InvItem = { id: number; status: string; source: string; created_at: string; demo: boolean; item: Item };

export type Me = {
  id: number;
  first_name: string;
  username: string | null;
  balance: number;
  demo_balance: number;
  ref_link: string | null;
  referrals: number;
  ref_earned: number;
  referral_percent: number;
  bonus_available_at: string | null;
  fair: { server_seed_hash: string; client_seed: string; nonce: number };
};

// Суммы приходят в сотых монеты
export function fmt(v: number): string {
  const n = v / 100;
  return n.toLocaleString("ru-RU", { maximumFractionDigits: n >= 100 ? 0 : 2 });
}

export function haptic(kind: "light" | "success" | "error" = "light") {
  const h = tg?.HapticFeedback;
  if (!h) return;
  if (kind === "light") h.impactOccurred("light");
  else h.notificationOccurred(kind);
}
