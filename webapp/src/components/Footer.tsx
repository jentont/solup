import { useEffect, useState } from "react";
import { api, tg } from "../api";

type Config = { bot_username: string | null; support: string | null; news: string | null };

function openTg(username: string) {
  const url = `https://t.me/${username}`;
  if (tg?.openTelegramLink) tg.openTelegramLink(url);
  else window.open(url, "_blank");
}

export function Footer({ go }: { go: (tab: string) => void }) {
  const [cfg, setCfg] = useState<Config | null>(null);
  useEffect(() => {
    api<Config>("/config").then(setCfg).catch(() => {});
  }, []);

  return (
    <footer className="footer">
      <div className="footer-top">
        <img className="logo logo--light" src="/brand/solup-light.svg" alt="SolUP" />
        <img className="logo logo--dark" src="/brand/solup-dark.svg" alt="SolUP" />
        <span className="age">18+</span>
      </div>
      <div className="footer-links">
        <button onClick={() => go("fair")}>Честная игра</button>
        {cfg?.news && <button onClick={() => openTg(cfg.news!)}>Новости</button>}
        {cfg?.support && <button onClick={() => openTg(cfg.support!)}>Поддержка</button>}
      </div>
      <div className="footer-note">
        Игра для совершеннолетних. Играйте в меру: ставьте только то, что готовы потерять.
      </div>
      <div className="hint">© {new Date().getFullYear()} SolUP · Solutions</div>
    </footer>
  );
}
