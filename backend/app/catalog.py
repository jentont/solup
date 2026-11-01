"""Стартовый каталог предметов и кейсов. Цены — примерные, в монетах (1 монета = 1 ⭐ по умолчанию).
Актуализируйте их под рынок командой /setprice в боте."""

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Case, CaseItem, Item

# Все коллекционные (NFT) подарки Telegram: название, эмодзи, редкость, цена в монетах.
# Цены новых коллекций — floor на Fragment × 85 монет за TON (как у стартового набора); правьте /setprice.
ITEMS: list[tuple[str, str, str, int]] = [
    ("B-Day Candle", "🕯️", "common", 350),
    ("Desk Calendar", "📅", "common", 350),
    ("Lunar Snake", "🐍", "common", 380),
    ("Homemade Cake", "🎂", "common", 400),
    ("Lol Pop", "🍭", "common", 400),
    ("Party Sparkler", "🎇", "common", 400),
    ("Big Year", "🎁", "common", 420),
    ("Candy Cane", "🎁", "common", 420),
    ("Chill Flame", "🎁", "common", 420),
    ("Easter Egg", "🎁", "common", 420),
    ("Fresh Socks", "🎁", "common", 420),
    ("Happy Brownie", "🎁", "common", 420),
    ("Holiday Drink", "🎁", "common", 420),
    ("Ice Cream", "🎁", "common", 420),
    ("Instant Ramen", "🎁", "common", 420),
    ("Mirage Lamp", "🎁", "common", 420),
    ("Mood Pack", "🎁", "common", 420),
    ("Pet Snake", "🎁", "common", 420),
    ("Pool Float", "🎁", "common", 420),
    ("Snake Box", "🎁", "common", 420),
    ("Star Notepad", "🎁", "common", 420),
    ("Tama Gadget", "🎁", "common", 420),
    ("Timeless Book", "🎁", "common", 420),
    ("Vice Cream", "🎁", "common", 420),
    ("Whip Cupcake", "🎁", "common", 420),
    ("Xmas Stocking", "🎁", "common", 420),
    ("Jester Hat", "🃏", "common", 450),
    ("Clover Pin", "🎁", "common", 510),
    ("Cookie Heart", "🎁", "common", 510),
    ("Ginger Cookie", "🎁", "common", 510),
    ("Hypno Lollipop", "🎁", "common", 510),
    ("Jack-in-the-Box", "🎁", "common", 510),
    ("Liberty Figure", "🎁", "common", 510),
    ("Money Pot", "🎁", "common", 510),
    ("Mousse Cake", "🎁", "common", 510),
    ("Pretty Posy", "🎁", "common", 510),
    ("Restless Jar", "🎁", "common", 510),
    ("Snoop Dogg", "🎁", "common", 510),
    ("Spiced Wine", "🎁", "common", 510),
    ("Stellar Rocket", "🎁", "common", 510),
    ("Swag Bag", "🎁", "common", 510),
    ("Victory Medal", "🎁", "common", 510),
    ("Winter Wreath", "🎁", "common", 510),
    ("Hex Pot", "🧪", "uncommon", 550),
    ("Bow Tie", "🎁", "uncommon", 600),
    ("Eternal Candle", "🎁", "uncommon", 600),
    ("Faith Amulet", "🎁", "uncommon", 600),
    ("Light Sword", "🎁", "uncommon", 600),
    ("Lush Bouquet", "🎁", "uncommon", 600),
    ("Moon Pendant", "🎁", "uncommon", 600),
    ("Santa Hat", "🎁", "uncommon", 600),
    ("Spring Basket", "🎁", "uncommon", 600),
    ("Spy Agaric", "🍄", "uncommon", 600),
    ("Input Key", "🎁", "uncommon", 680),
    ("Jolly Chimp", "🎁", "uncommon", 680),
    ("Snow Globe", "🎁", "uncommon", 680),
    ("Surge Board", "🎁", "uncommon", 680),
    ("Witch Hat", "🧙", "uncommon", 700),
    ("Bunny Muffin", "🎁", "uncommon", 760),
    ("Evil Eye", "🎁", "uncommon", 760),
    ("Fine Pen", "🎁", "uncommon", 760),
    ("Berry Box", "🎁", "uncommon", 850),
    ("Snow Mittens", "🎁", "uncommon", 850),
    ("Jelly Bunny", "🐰", "uncommon", 900),
    ("Hanging Star", "🎁", "uncommon", 940),
    ("Joyful Bundle", "🎁", "uncommon", 940),
    ("Jingle Bells", "🎁", "rare", 1000),
    ("Sakura Flower", "🎁", "rare", 1000),
    ("Top Hat", "🎁", "rare", 1000),
    ("Love Candle", "🎁", "rare", 1100),
    ("Valentine Box", "🎁", "rare", 1100),
    ("Crystal Ball", "🔮", "rare", 1200),
    ("Skull Flower", "🎁", "rare", 1200),
    ("Sleigh Bell", "🎁", "rare", 1200),
    ("Flying Broom", "🎁", "rare", 1300),
    ("Love Potion", "💘", "rare", 1300),
    ("Record Player", "📻", "rare", 1400),
    ("Ionic Dryer", "🎁", "rare", 1450),
    ("Lucky Locket", "🎁", "rare", 1450),
    ("Mad Pumpkin", "🎁", "rare", 1450),
    ("Trapped Heart", "💔", "rare", 1500),
    ("Snoop Cigar", "🎁", "rare", 1550),
    ("UFC Strike", "🎁", "rare", 1600),
    ("Sky Stilettos", "🎁", "rare", 1700),
    ("Eternal Rose", "🌹", "rare", 2000),
    ("Cupid Charm", "🎁", "rare", 2300),
    ("Khabib's Papakha", "🎁", "rare", 2300),
    ("Bling Binky", "🎁", "rare", 2450),
    ("Rare Bird", "🎁", "epic", 2550),
    ("Electric Skull", "🎁", "epic", 3000),
    ("Toy Bear", "🧸", "epic", 3000),
    ("Diamond Ring", "💍", "epic", 3500),
    ("Voodoo Doll", "🎁", "epic", 3650),
    ("Bonded Ring", "🎁", "epic", 4000),
    ("Vintage Cigar", "🚬", "epic", 4000),
    ("Neko Helmet", "🐱", "epic", 4500),
    ("Sharp Tongue", "🎁", "epic", 4700),
    ("Kissed Frog", "🎁", "epic", 5350),
    ("Signet Ring", "💎", "epic", 5500),
    ("Low Rider", "🎁", "epic", 5950),
    ("Swiss Watch", "⌚", "epic", 6000),
    ("Gem Signet", "🎁", "epic", 6100),
    ("Magic Potion", "🎁", "epic", 6400),
    ("Genie Lamp", "🪔", "epic", 6500),
    ("Artisan Brick", "🎁", "epic", 7200),
    ("Ion Gem", "🎁", "epic", 7200),
    ("Mini Oscar", "🎁", "epic", 8900),
    ("Perfume Bottle", "🎁", "epic", 9200),
    ("Westside Sign", "🎁", "legendary", 11000),
    ("Myth Mask", "🎁", "legendary", 11500),
    ("Mighty Arm", "🎁", "legendary", 12000),
    ("Astral Shard", "🎁", "legendary", 12500),
    ("Nail Bracelet", "🎁", "legendary", 12500),
    ("Durov's Glasses", "🎁", "legendary", 13000),
    ("Loot Bag", "💰", "legendary", 15000),
    ("Heroic Helmet", "🎁", "legendary", 17000),
    ("Scared Cat", "🎁", "legendary", 25500),
    ("Heart Locket", "💝", "legendary", 30000),
    ("Resistance Dog", "🎁", "legendary", 41000),
    ("Precious Peach", "🍑", "legendary", 50000),
    ("Durov's Cap", "🧢", "legendary", 120000),
    ("Intelligence Cup", "🎁", "legendary", 265000),
    ("Algorithm Cup", "🎁", "legendary", 295000),
    ("Plush Pepe", "🐸", "legendary", 600000),
]

# (slug, название, эмодзи, цена в монетах, RTP, предметы)
CASES: list[tuple[str, str, str, int, float, list[str]]] = [
    ("starter", "Новичок", "📦", 500, 0.9,
     ["Desk Calendar", "B-Day Candle", "Lunar Snake", "Lol Pop", "Hex Pot", "Witch Hat", "Crystal Ball", "Toy Bear"]),
    ("sweet", "Сладкий", "🍬", 700, 0.9,
     ["Lol Pop", "Homemade Cake", "Party Sparkler", "Jelly Bunny", "Love Potion", "Eternal Rose", "Diamond Ring", "Loot Bag"]),
    ("magic", "Магия", "🔮", 1500, 0.9,
     ["Jester Hat", "Hex Pot", "Witch Hat", "Crystal Ball", "Record Player", "Genie Lamp", "Heart Locket"]),
    ("luxury", "Роскошь", "💎", 5000, 0.9,
     ["Crystal Ball", "Eternal Rose", "Toy Bear", "Vintage Cigar", "Signet Ring", "Swiss Watch", "Loot Bag", "Precious Peach"]),
    ("legend", "Легенда", "👑", 25000, 0.88,
     ["Swiss Watch", "Genie Lamp", "Loot Bag", "Heart Locket", "Precious Peach", "Durov's Cap", "Plush Pepe"]),
    ("piggy", "Копилка", "🐷", 400, 0.9,
     ["Desk Calendar", "B-Day Candle", "Lunar Snake", "Lol Pop", "Jester Hat", "Hex Pot", "Jelly Bunny"]),
    ("party", "Вечеринка", "🎉", 800, 0.9,
     ["B-Day Candle", "Homemade Cake", "Party Sparkler", "Jelly Bunny", "Record Player", "Vintage Cigar"]),
    ("halloween", "Хэллоуин", "🎃", 900, 0.9,
     ["Lunar Snake", "Jester Hat", "Hex Pot", "Spy Agaric", "Witch Hat", "Crystal Ball", "Genie Lamp"]),
    ("love", "Любовь", "💘", 2000, 0.9,
     ["Lol Pop", "Love Potion", "Trapped Heart", "Eternal Rose", "Diamond Ring", "Heart Locket"]),
    ("gentleman", "Джентльмен", "🎩", 3500, 0.9,
     ["Record Player", "Vintage Cigar", "Signet Ring", "Swiss Watch", "Neko Helmet", "Durov's Cap"]),
    ("durov", "Дуров", "🧢", 12000, 0.88,
     ["Genie Lamp", "Neko Helmet", "Loot Bag", "Heart Locket", "Precious Peach", "Durov's Cap"]),
    ("pepe", "Пепе", "🐸", 50000, 0.88,
     ["Loot Bag", "Heart Locket", "Precious Peach", "Durov's Cap", "Plush Pepe"]),
    ("new", "Новинки", "✨", 2500, 0.9,
     ["Mirage Lamp", "Fine Pen", "Lucky Locket", "Electric Skull", "Myth Mask", "Durov's Glasses", "Resistance Dog"]),
    ("spooky", "Жуть", "💀", 1800, 0.9,
     ["Evil Eye", "Skull Flower", "Flying Broom", "Mad Pumpkin", "Electric Skull", "Voodoo Doll", "Myth Mask", "Scared Cat"]),
]


def weights_for_rtp(values: list[int], price: int, rtp: float, scale: int = 1_000_000) -> list[int]:
    """Веса w_i ~ value_i^-a; показатель a подбирается так, чтобы ожидаемый выигрыш = rtp * price."""
    target = rtp * price
    if not min(values) < target < max(values):
        raise ValueError(f"RTP недостижим: цена {price}, предметы {min(values)}..{max(values)}")

    def ev(a: float) -> float:
        w = [v**-a for v in values]
        return sum(wi * v for wi, v in zip(w, values)) / sum(w)

    lo, hi = -10.0, 10.0  # ev убывает по a
    for _ in range(100):
        mid = (lo + hi) / 2
        if ev(mid) > target:
            lo = mid
        else:
            hi = mid
    raw = [v**-lo for v in values]
    total = sum(raw)
    return [max(1, round(r / total * scale)) for r in raw]


def gift_image(name: str) -> str:
    """Картинки лежат в webapp/public/gifts/<slug>.webp."""
    return f"/gifts/{re.sub(r'[^a-z0-9]', '', name.lower())}.webp"


async def seed_catalog(s: AsyncSession) -> None:
    if (await s.execute(select(Item.id).limit(1))).first():
        known = {name for name, *_ in ITEMS}
        for item in (await s.execute(select(Item).where(Item.image_url.is_(None)))).scalars():
            if item.gift_name in known:
                item.image_url = gift_image(item.gift_name)
    by_name = {i.gift_name: i for i in (await s.execute(select(Item))).scalars()}
    # Подарки из каталога, которых ещё нет в базе (новые коллекции добавляются и в старую базу)
    for name, emoji, rarity, value in ITEMS:
        if name not in by_name:
            item = Item(name=name, gift_name=name, emoji=emoji, rarity=rarity, value=value * 100,
                        image_url=gift_image(name))
            s.add(item)
            by_name[name] = item
    await s.flush()
    # Кейсы из каталога, которых ещё нет в базе (новые добавляются и в старую базу)
    existing = set((await s.execute(select(Case.slug))).scalars())
    for sort, (slug, name, emoji, price, rtp, names) in enumerate(CASES):
        if slug in existing or not all(n in by_name for n in names):
            continue
        items = [by_name[n] for n in names]
        weights = weights_for_rtp([i.value for i in items], price * 100, rtp)
        case = Case(slug=slug, name=name, emoji=emoji, price=price * 100, sort=sort)
        case.items = [CaseItem(item_id=i.id, weight=w) for i, w in zip(items, weights)]
        s.add(case)
    await s.commit()
