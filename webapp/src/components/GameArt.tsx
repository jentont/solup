// Обложка игры на главной: силуэт игры на фоне (башня, поле мин, пирамида плинко…),
// чтобы игру узнавали с первого взгляда, и два NFT-подарка поверх.

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

const range = (n: number) => Array.from({ length: n }, (_, i) => i);

// Силуэты в координатах плитки 100×128; рисуются белым, прозрачность задаёт CSS
const SCENES: Record<string, JSX.Element> = {
  tower: (
    <g>
      <path d="M22 16h12v8h8v-8h16v8h8v-8h12v22l-6 4v70H28V42l-6-4z" />
      <path className="cut" d="M42 112V88a8 8 0 0 1 16 0v24z" />
      {range(6).map((i) => <rect key={i} className="cut" x="28" y={46 + i * 11} width="44" height="1.6" />)}
    </g>
  ),
  mines: (
    <g>
      {range(16).map((i) => <rect key={i} x={8 + (i % 4) * 22} y={14 + Math.floor(i / 4) * 22} width="18" height="18" rx="4" opacity={i === 5 || i === 10 ? 1 : 0.55} />)}
      <circle cx="39" cy="45" r="5" className="cut" />
      <path className="cut" d="M61 62l4 5-4 5-4-5z" />
    </g>
  ),
  plinko: (
    <g>
      {range(7).map((r) => range(r + 3).map((i) => <circle key={`${r}-${i}`} cx={50 + (i - (r + 2) / 2) * 11} cy={14 + r * 11} r="2.4" />))}
      {range(9).map((i) => <rect key={i} x={6 + i * 10} y="94" width="8" height="10" rx="2" opacity={0.4 + Math.abs(i - 4) * 0.15} />)}
    </g>
  ),
  roulette: (
    <g transform="translate(50 52)">
      <circle r="44" />
      {range(18).map((i) => (
        <path key={i} className="cut" opacity={i % 2 ? 0.5 : 0.9} d={`M0 0L${44 * Math.sin((i * 20 * Math.PI) / 180)} ${-44 * Math.cos((i * 20 * Math.PI) / 180)}A44 44 0 0 1 ${44 * Math.sin(((i * 20 + 10) * Math.PI) / 180)} ${-44 * Math.cos(((i * 20 + 10) * Math.PI) / 180)}z`} />
      ))}
      <circle r="14" />
    </g>
  ),
  wheel: (
    <g transform="translate(50 56)">
      <circle r="42" opacity="0.5" />
      {range(8).map((i) => (
        <path key={i} opacity={i % 2 ? 0.55 : 1} d={`M0 0L${40 * Math.sin((i * 45 * Math.PI) / 180)} ${-40 * Math.cos((i * 45 * Math.PI) / 180)}A40 40 0 0 1 ${40 * Math.sin(((i + 1) * 45 * Math.PI) / 180)} ${-40 * Math.cos(((i + 1) * 45 * Math.PI) / 180)}z`} />
      ))}
      <path d="M-7 -50h14l-7 12z" />
    </g>
  ),
  slots: (
    <g>
      <rect x="8" y="18" width="84" height="74" rx="10" />
      <rect className="cut" x="14" y="34" width="72" height="34" rx="5" />
      {range(3).map((i) => <text key={i} x={26 + i * 24} y="60" className="glyph">7</text>)}
      <rect x="93" y="30" width="3" height="28" rx="1.5" />
      <circle cx="94.5" cy="28" r="4" />
    </g>
  ),
  dice: (
    <g>
      <g transform="rotate(-14 32 44)"><rect x="10" y="22" width="44" height="44" rx="9" />{[[22, 34], [42, 34], [32, 44], [22, 54], [42, 54]].map(([x, y], i) => <circle key={i} className="cut" cx={x} cy={y} r="4" />)}</g>
      <g transform="rotate(12 68 72)"><rect x="46" y="50" width="44" height="44" rx="9" opacity="0.7" />{[[58, 62], [68, 72], [78, 82]].map(([x, y], i) => <circle key={i} className="cut" cx={x} cy={y} r="4" />)}</g>
    </g>
  ),
  crash: (
    <g>
      {range(5).map((i) => <rect key={i} x="8" y={20 + i * 18} width="84" height="0.8" opacity="0.5" />)}
      <path d="M8 104C40 100 62 80 86 22" fill="none" stroke="#fff" strokeWidth="5" strokeLinecap="round" />
      <path d="M78 22l10-6 2 12z" />
    </g>
  ),
  blackjack: (
    <g>
      <g transform="rotate(-12 38 60)"><rect x="16" y="26" width="42" height="60" rx="6" /><text x="25" y="44" className="glyph cut">A</text></g>
      <g transform="rotate(10 62 60)"><rect x="42" y="28" width="42" height="60" rx="6" opacity="0.8" /><text x="51" y="46" className="glyph cut">K</text></g>
    </g>
  ),
  cases: (
    <g>
      <path d="M14 46h72v50H14z" />
      <path d="M12 30l76 0 0 14H12z" opacity="0.7" />
      <rect className="cut" x="44" y="50" width="12" height="16" rx="3" />
    </g>
  ),
  upgrade: (
    <g>
      <path d="M50 10l34 34H64v58H36V44H16z" />
      <path className="cut" d="M50 30l18 18H58v46H42V48H32z" opacity="0.6" />
    </g>
  ),
  hilo: (
    <g>
      <rect x="28" y="26" width="44" height="64" rx="7" />
      <text x="40" y="66" className="glyph cut big">?</text>
      <path d="M50 4l12 14H38z" />
      <path d="M50 112l12-14H38z" opacity="0.7" />
    </g>
  ),
  keno: (
    <g>
      {range(16).map((i) => <circle key={i} cx={20 + (i % 4) * 20} cy={22 + Math.floor(i / 4) * 20} r="8" opacity={[1, 6, 9, 14].includes(i) ? 1 : 0.45} />)}
    </g>
  ),
  coinflip: (
    <g transform="translate(50 54)">
      <circle r="40" />
      <circle r="31" className="cut" />
      <circle r="26" />
      <path className="cut" d="M0 -14l4 9 10 1-7 7 2 10-9-5-9 5 2-10-7-7 10-1z" />
    </g>
  ),
  limbo: (
    <g>
      <text x="50" y="58" className="glyph huge" textAnchor="middle">×100</text>
      <path d="M50 76l12 14H54v14h-8V90h-8z" opacity="0.7" />
    </g>
  ),
  rps: (
    <g>
      <rect x="10" y="30" width="30" height="40" rx="6" opacity="0.8" />
      <circle cx="74" cy="44" r="18" />
      <circle cx="34" cy="96" r="8" opacity="0.7" /><circle cx="56" cy="96" r="8" opacity="0.7" />
      <path d="M38 90l22-26M58 90L36 64" stroke="#fff" strokeWidth="5" strokeLinecap="round" opacity="0.7" />
    </g>
  ),
};

export function GameArt({ id }: { id: string }) {
  const a = ART[id];
  if (!a) return null;
  return (
    <>
      {SCENES[id] && (
        <svg className="gtile-scene" viewBox="0 0 100 128" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
          {SCENES[id]}
        </svg>
      )}
      <img className="gtile-img back" src={`/gifts/${a[1]}.webp`} alt="" />
      <img className="gtile-img" src={`/gifts/${a[0]}.webp`} alt="" />
    </>
  );
}
