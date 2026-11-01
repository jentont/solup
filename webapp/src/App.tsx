import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, authHeader, fmt, haptic, isDemo, Me, setDemoMode, tg } from "./api";
import { Home } from "./pages/Home";
import { Cases } from "./pages/Cases";
import { Upgrade } from "./pages/Upgrade";
import { Crash } from "./pages/Crash";
import { Profile } from "./pages/Profile";
import { Deposit } from "./components/Deposit";
import { Wallet } from "./components/Wallet";
import { LiveFeed } from "./components/LiveFeed";
import { Icon } from "./components/ui";

type Ctx = {
  me: Me | null;
  refresh: () => Promise<void>;
  setBalance: (b: number) => void;
  toast: (text: string, kind?: "ok" | "err") => void;
  openDeposit: () => void;
  demo: boolean;
};

const AppCtx = createContext<Ctx>(null as any);
export const useApp = () => useContext(AppCtx);

const TABS = [
  { id: "home", label: "Главная", icon: "home" },
  { id: "cases", label: "Кейсы", icon: "box" },
  { id: "upgrade", label: "Апгрейд", icon: "bolt" },
  { id: "crash", label: "Краш", icon: "rocket" },
  { id: "profile", label: "Профиль", icon: "user" },
] as const;
type Tab = (typeof TABS)[number]["id"];

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
      const bg = d ? "#000000" : "#F5F5F7";
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
      <div className="splash">
        <img className="logo logo--light" src="/brand/solup-light.svg" alt="SolUP" />
        <img className="logo logo--dark" src="/brand/solup-dark.svg" alt="SolUP" />
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
  };

  return (
    <AppCtx.Provider value={ctx}>
      <div className="app">
        <header className="topbar">
          <button className="brand" onClick={() => go("home")} aria-label="SolUP">
            <span className="brand-mark"><img src="/brand/cat.png" alt="" /></span>
            <img className="logo logo--light" src="/brand/solup-word-light.svg" alt="SolUP" />
            <img className="logo logo--dark" src="/brand/solup-word-dark.svg" alt="SolUP" />
          </button>
          <div className="top-right">
          <button className="icon-btn" onClick={toggleTheme} aria-label={dark ? "Светлая тема" : "Тёмная тема"}>
            <Icon name={dark ? "sun" : "moon"} size={20} />
          </button>
          <button className="balance" onClick={() => setWallet(true)}>
            {demo && <span className="balance-tag">демо</span>}
            <span className="balance-value">{shownMe ? fmt(shownMe.balance) : "—"}</span>
            <i className="coin" />
            <span className="balance-plus"><Icon name="plus" size={14} /></span>
          </button>
          </div>
        </header>
        <LiveFeed />
        <main className="content" key={demo ? "demo" : "real"}>
          {tab === "home" && <Home go={go} />}
          {tab === "cases" && <Cases />}
          {tab === "upgrade" && <Upgrade />}
          {tab === "crash" && <Crash />}
          {tab === "profile" && <Profile key={profileView} initialView={profileView} />}
        </main>
        <nav className="tabbar">
          {TABS.map((t) => (
            <button key={t.id} className={`tab ${tab === t.id ? "tab--on" : ""}`} onClick={() => go(t.id)}>
              <Icon name={t.icon} />
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
