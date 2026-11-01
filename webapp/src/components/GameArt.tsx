// Обложка игры на главной: крупный NFT-подарок спереди и второй — за ним, под углом.

const ART: Record<string, [front: string, back: string]> = {
  crash: ["durovscap", "jellybunny"],
  cases: ["lootbag", "plushpepe"],
  upgrade: ["swisswatch", "diamondring"],
  slots: ["berrybox", "cookieheart"],
  mines: ["crystalball", "lunarsnake"],
  wheel: ["recordplayer", "partysparkler"],
  tower: ["witchhat", "spyagaric"],
  blackjack: ["tophat", "vintagecigar"],
  plinko: ["hangingstar", "bunnymuffin"],
  roulette: ["evileye", "faithamulet"],
  dice: ["tamagadget", "jackinthebox"],
  limbo: ["stellarrocket", "astralshard"],
  hilo: ["timelessbook", "starnotepad"],
  keno: ["iongem", "gemsignet"],
  coinflip: ["moneypot", "swagbag"],
  rps: ["mightyarm", "ufcstrike"],
};

export function GameArt({ id }: { id: string }) {
  const a = ART[id];
  if (!a) return null;
  return (
    <>
      <img className="gtile-img back" src={`/gifts/${a[1]}.webp`} alt="" />
      <img className="gtile-img" src={`/gifts/${a[0]}.webp`} alt="" />
    </>
  );
}
