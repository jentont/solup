// Обложка игры на главной: главный предмет игры в центре и NFT-подарки вокруг.
// Предмет — вырезанный из макетов объект (/art) или нарисованный стилями (слоты, рулетка, кости…).

type Art = { main?: string; obj?: string; gifts: string[] };

const ART: Record<string, Art> = {
  upgrade: { main: "upgrade", gifts: ["swisswatch", "diamondring", "signetring"] },
  crash: { main: "crash", gifts: ["durovscap", "plushpepe", "jellybunny"] },
  cases: { main: "cases", gifts: ["lootbag", "plushpepe", "heartlocket"] },
  mines: { main: "mines", gifts: ["crystalball", "iongem", "astralshard"] },
  tower: { main: "tower", gifts: ["witchhat", "spyagaric", "magicpotion"] },
  wheel: { main: "wheel", gifts: ["recordplayer", "partysparkler", "lolpop"] },
  blackjack: { main: "blackjack", gifts: ["tophat", "vintagecigar", "moneypot"] },
  slots: { obj: "slots", gifts: ["berrybox", "lolpop", "diamondring"] },
  plinko: { obj: "plinko", gifts: ["bunnymuffin", "stellarrocket", "jellybunny"] },
  dice: { obj: "dice", gifts: ["tamagadget", "jackinthebox", "astralshard"] },
  limbo: { obj: "limbo", gifts: ["astralshard", "starnotepad", "iongem"] },
  coinflip: { obj: "coin", gifts: ["moneypot", "swagbag", "cloverpin"] },
  roulette: { obj: "roulette", gifts: ["evileye", "faithamulet", "vintagecigar"] },
  hilo: { obj: "hilo", gifts: ["timelessbook", "inputkey", "starnotepad"] },
  keno: { obj: "keno", gifts: ["iongem", "crystalball", "gemsignet"] },
  rps: { obj: "rps", gifts: ["mightyarm", "ufcstrike", "heroichelmet"] },
};

const gift = (s: string) => `/gifts/${s}.webp`;

// Предметы, нарисованные стилями — для игр без вырезанного объекта
function Obj({ kind }: { kind: string }) {
  switch (kind) {
    case "slots":
      return (
        <div className="ga-slots">
          <span className="ga-slots-top">777</span>
          <div className="ga-slots-win">
            {["cookieheart", "cookieheart", "cookieheart"].map((s, i) => <img key={i} src={gift(s)} alt="" />)}
          </div>
          <i className="ga-slots-lever" />
        </div>
      );
    case "plinko":
      return (
        <div className="ga-plinko">
          {[3, 4, 5, 6].map((n, r) => (
            <div key={r}>{Array.from({ length: n }, (_, i) => <i key={i} />)}</div>
          ))}
          <b className="ga-ball" />
        </div>
      );
    case "dice":
      return (
        <div className="ga-dice">
          <i className="d5" /><i className="d3" />
        </div>
      );
    case "limbo":
      return (
        <div className="ga-limbo">
          <img src={gift("stellarrocket")} alt="" />
          <b>×100</b>
        </div>
      );
    case "coin":
      return (
        <div className="ga-coin">
          <img src="/brand/solup-mark-light.svg" alt="" />
        </div>
      );
    case "roulette":
      return <div className="ga-roulette"><i /></div>;
    case "hilo":
      return (
        <div className="ga-hilo">
          <span className="c1">A<small>♠</small></span>
          <span className="c2">K<small>♥</small></span>
          <b className="up">▲</b><b className="down">▼</b>
        </div>
      );
    case "keno":
      return (
        <div className="ga-keno">
          {[7, 12, 3, 21, 9, 33, 18, 5, 27].map((n, i) => <i key={i} className={[1, 3, 5, 7].includes(i) ? "on" : ""}>{n}</i>)}
        </div>
      );
    case "rps":
      return (
        <div className="ga-rps">
          <span>✊</span><span>✌️</span><span>✋</span>
        </div>
      );
  }
  return null;
}

export function GameArt({ id }: { id: string }) {
  const a = ART[id];
  if (!a) return null;
  return (
    <div className="ga">
      <img className="ga-g g1" src={gift(a.gifts[0])} alt="" />
      <img className="ga-g g2" src={gift(a.gifts[1])} alt="" />
      <div className="ga-main">
        {a.main ? <img src={`/art/${a.main}.webp`} alt="" /> : <Obj kind={a.obj!} />}
      </div>
      <img className="ga-g g3" src={gift(a.gifts[2])} alt="" />
      <i className="ga-spark s1" /><i className="ga-spark s2" />
    </div>
  );
}
