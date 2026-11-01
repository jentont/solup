import { useEffect, useState } from "react";
import { api, fmt, Item, wsUrl } from "../api";

type LiveEvent = { user: string; item: Item; source: string };

export function LiveFeed() {
  const [events, setEvents] = useState<LiveEvent[]>([]);

  useEffect(() => {
    api<LiveEvent[]>("/live").then(setEvents).catch(() => {});
    let ws: WebSocket | null = null;
    let stopped = false;
    const connect = () => {
      ws = new WebSocket(wsUrl("/ws"));
      ws.onmessage = (m) => {
        const e = JSON.parse(m.data);
        if (e.type === "live") setEvents((prev) => [e, ...prev].slice(0, 30));
      };
      ws.onclose = () => !stopped && setTimeout(connect, 3000);
    };
    connect();
    return () => {
      stopped = true;
      ws?.close();
    };
  }, []);

  if (!events.length) return null;
  return (
    <div className="live">
      <div className="live-dot">live</div>
      <div className="live-track">
        {events.map((e, i) => (
          <div key={i} className={`live-item r-${e.item.rarity}`} title={e.user}>
            <span className="live-emoji">{e.item.image_url ? <img src={e.item.image_url} alt="" /> : e.item.emoji}</span>
            <span className="live-info"><span className="live-user">{e.user}</span><span className="live-val">{fmt(e.item.value)}</span></span>
            {e.source === "upgrade" && <span className="live-tag">ап</span>}
          </div>
        ))}
      </div>
    </div>
  );
}
