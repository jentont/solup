import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, authHeader, fmt, haptic, isDemo, Me, setDemoMode, tg } from "./api";
import { Home } from "./pages/Home";
import { Cases } from "./pages/Cases";
import { Upgrade } from "./pages/Upgrade";
import { Crash } from "./pages/Crash";
import { Mines } from "./pages/Mines";
import { Tower } from "./pages/Tower";
import { Wheel } from "./pages/Wheel";
import { Plinko } from "./pages/Plinko";
import { Dice } from "./pages/Dice";
import { Limbo } from "./pages/Limbo";
import { Coinflip } from "./pages/Coinflip";
import { Roulette } from "./pages/Roulette";
import { HiLo } from "./pages/HiLo";
import { Blackjack } from "./pages/Blackjack";
import { Slots } from "./pages/Slots";
import { Keno } from "./pages/Keno";
import { Rps } from "./pages/Rps";
import { Profile } from "./pages/Profile";
import { Deposit } from "./components/Deposit";
import { Wallet } from "./components/Wallet";
import { LiveFeed } from "./components/LiveFeed";
import { Avatar, Icon } from "./components/ui";

type Ctx = {
  me: Me | null;
  refresh: () => Promise<void>;
  setBalance: (b: number) => void;
  toast: (text: string, kind?: "ok" | "err") => void;
  openDeposit: () => void;
  demo: boolean;
  go: (tab: string) => void;
  dark: boolean;
  toggleTheme: () => void;
};

const AppCtx = createContext<Ctx>(null as any);
export const useApp = () => useContext(AppCtx);

// В меню три раздела; экраны игр открываются с главной и подсвечивают «Игры»
const TABS = [
  { id: "home", label: "Игры", icon: "games" },
  { id: "cases", label: "Кейсы", icon: "box" },
  { id: "profile", label: "Профиль", icon: "user" },
] as const;
const GAME_TABS = ["upgrade", "crash", "mines", "tower", "wheel", "plinko", "dice", "limbo", "coinflip", "roulette", "hilo", "blackjack", "slots", "keno", "rps"] as const;
type Tab = (typeof TABS)[number]["id"] | (typeof GAME_TABS)[number];

export function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [tab, setTab] = useState<Tab>("home");
  const [profileView, setProfileView] = useState<"inv" | "fair">("inv");
  const [splash, setSplash] = useState(true);
  const [demo, setDemo] = useState(isDemo());
  // заставка с логотипом держится не меньше 0,9 с, даже если данные пришли сразу
  useEffect(() => {
    const t = setTimeout(() => setSplash(false), 900);
    return () => clearTimeout(t);
  }, []);
  const [deposit, setDeposit] = useState(false);
  const [wallet, setWallet] = useState(false);
  const [toastMsg, setToastMsg] = useState<{ text: string; kind: string } | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setMe(await api<Me>("/me"));
    } catch (e: any) {
      setAuthError(e.message);
    }
  }, []);

  const toast = useCallback((text: string, kind: "ok" | "err" = "ok") => {
    setToastMsg({ text, kind });
    setTimeout(() => setToastMsg(null), 2800);
  }, []);

  useEffect(() => {
    tg?.ready();
    tg?.expand();
    // На телефоне — на весь экран, без шапки Telegram; свайп вниз не закрывает приложение
    if (["ios", "android"].includes(tg?.platform) && tg?.isVersionAtLeast?.("8.0")) {
      try { tg.requestFullscreen(); } catch { /* старый клиент */ }
    }
    if (tg?.isVersionAtLeast?.("7.7")) tg.disableVerticalSwipes();
    refresh();
  }, [refresh]);

  // Тема: «auto» — как в Telegram (или в системе), иначе выбор игрока из шапки
  const [theme, setTheme] = useState<string>(() => {
    try {
      return localStorage.getItem("theme") || "auto";
    } catch {
      return "auto";
    }
  });
  const [dark, setDark] = useState(false);
  useEffect(() => {
    const apply = () => {
      // telegram-web-app.js есть и в обычном браузере, поэтому смотрим на initData
      const system = tg?.initData ? tg.colorScheme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
      const d = theme === "auto" ? system : theme === "dark";
      document.body.classList.toggle("dark", d);
      setDark(d);
      const bg = d ? "#090A16" : "#F3F4FA";
      tg?.setHeaderColor?.(bg);
      tg?.setBackgroundColor?.(bg);
    };
    apply();
    tg?.onEvent?.("themeChanged", apply);
    return () => tg?.offEvent?.("themeChanged", apply);
  }, [theme]);
  const toggleTheme = () => {
    const next = dark ? "light" : "dark";
    setTheme(next);
    haptic();
    try {
      localStorage.setItem("theme", next);
    } catch {
      /* приватный режим браузера */
    }
  };

  // Кнопка «Назад» Telegram возвращает на главную
  useEffect(() => {
    const back = tg?.BackButton;
    if (!back) return;
    const onBack = () => setTab("home");
    if (tab === "home") back.hide();
    else back.show();
    back.onClick(onBack);
    return () => back.offClick(onBack);
  }, [tab]);

  if (!authHeader) {
    return <div className="center-msg">Откройте приложение через Telegram-бота</div>;
  }
  if (authError && !me) {
    return <div className="center-msg">{authError}</div>;
  }
  if (!me || splash) {
    return (
      <div className="boot">
        <img className="boot-logo" src="/brand/solup-word-dark.svg" alt="SolUP" />
        <div className="boot-hand">загружаем подарки…</div>
        <div className="boot-bar"><i /></div>
      </div>
    );
  }

  const go = (t: string) => {
    setProfileView(t === "fair" ? "fair" : "inv");
    if (t === "bonus") setTab("cases");
    else if (t === "ref" || t === "fair") setTab("profile");
    else setTab(t as Tab);
    window.scrollTo(0, 0);
  };

  const switchDemo = (on: boolean) => {
    if (on === demo) return;
    setDemoMode(on);
    setDemo(on);
    haptic();
  };
  const refillDemo = async () => {
    const r = await api("/demo/refill", {});
    setMe((m) => (m ? { ...m, demo_balance: r.balance } : m));
    haptic("success");
    toast("Демо-баланс пополнен");
  };

  // Страницы видят баланс текущего режима в me.balance и ничего не знают о демо
  const shownMe = me && demo ? { ...me, balance: me.demo_balance } : me;
  const ctx: Ctx = {
    me: shownMe,
    refresh,
    setBalance: (b) => setMe((m) => (m ? (demo ? { ...m, demo_balance: b } : { ...m, balance: b }) : m)),
    toast,
    openDeposit: () => (demo ? refillDemo() : setDeposit(true)),
    demo,
    go,
    dark,
    toggleTheme,
  };
  const navTab = (GAME_TABS as readonly string[]).includes(tab) ? "home" : tab;
  const bonusReady = !me.bonus_available_at || Date.parse(me.bonus_available_at) <= Date.now();

  return (
    <AppCtx.Provider value={ctx}>
      <div className="app">
        <header className="topbar">
          <button className="brand" onClick={() => go("home")} aria-label="SolUP">
            <img className="logo logo--light" src="/brand/solup-word-light.svg" alt="SolUP" />
            <img className="logo logo--dark" src="/brand/solup-word-dark.svg" alt="SolUP" />
          </button>
          <div className="top-right">
          <button className="balance" onClick={() => setWallet(true)}>
            <i className="coin" />
            <span className="balance-value">{shownMe ? fmt(shownMe.balance) : "—"}</span>
            {demo && <span className="balance-tag">демо</span>}
          </button>
          <button className="topup" onClick={ctx.openDeposit}>Пополнить</button>
          <button className="top-avatar" onClick={() => go("profile")} aria-label="Профиль">
            <Avatar id={me.id} name={me.first_name} />
          </button>
          </div>
        </header>
        {tab === "home" && <LiveFeed />}
        <main className="content" key={demo ? "demo" : "real"}>
          {tab === "home" && <Home go={go} />}
          {tab === "cases" && <Cases />}
          {tab === "upgrade" && <Upgrade />}
          {tab === "crash" && <Crash />}
          {tab === "mines" && <Mines />}
          {tab === "tower" && <Tower />}
          {tab === "wheel" && <Wheel />}
          {tab === "plinko" && <Plinko />}
          {tab === "dice" && <Dice />}
          {tab === "limbo" && <Limbo />}
          {tab === "coinflip" && <Coinflip />}
          {tab === "roulette" && <Roulette />}
          {tab === "hilo" && <HiLo />}
          {tab === "blackjack" && <Blackjack />}
          {tab === "slots" && <Slots />}
          {tab === "keno" && <Keno />}
          {tab === "rps" && <Rps />}
          {tab === "profile" && <Profile key={profileView} initialView={profileView} />}
        </main>
        <nav className="tabbar">
          {TABS.map((t) => (
            <button key={t.id} className={`tab ${navTab === t.id ? "tab--on" : ""}`} onClick={() => go(t.id)}>
              {t.id === "cases" && bonusReady && <span className="tab-free">FREE</span>}
              <Icon name={t.icon} size={18} />
              <span className="tab-label">{t.label}</span>
            </button>
          ))}
        </nav>
        {deposit && <Deposit onClose={() => setDeposit(false)} />}
        {wallet && me && (
          <Wallet
            me={me}
            demo={demo}
            onDemo={switchDemo}
            onDeposit={() => { setWallet(false); setDeposit(true); }}
            onRefill={refillDemo}
            onClose={() => setWallet(false)}
          />
        )}
        {toastMsg && <div className={`toast ${toastMsg.kind}`}>{toastMsg.text}</div>}
      </div>
    </AppCtx.Provider>
  );
}
