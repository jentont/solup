"""Стартовый каталог предметов и кейсов. Цены — примерные, в монетах (1 монета = 1 ⭐ по умолчанию).
Актуализируйте их под рынок командой /setprice в боте."""

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Case, CaseItem, Item

# (название коллекционного подарка, эмодзи, редкость, цена в монетах)
ITEMS: list[tuple[str, str, str, int]] = [
    ("Lol Pop", "🍭", "common", 400),
    ("Desk Calendar", "📅", "common", 350),
    ("B-Day Candle", "🕯️", "common", 350),
    ("Homemade Cake", "🎂", "common", 400),
    ("Lunar Snake", "🐍", "common", 380),
    ("Party Sparkler", "🎇", "common", 400),
    ("Jester Hat", "🃏", "common", 450),
    ("Hex Pot", "🧪", "uncommon", 550),
    ("Spy Agaric", "🍄", "uncommon", 600),
    ("Witch Hat", "🧙", "uncommon", 700),
    ("Jelly Bunny", "🐰", "uncommon", 900),
    ("Crystal Ball", "🔮", "rare", 1200),
    ("Love Potion", "💘", "rare", 1300),
    ("Record Player", "📻", "rare", 1400),
    ("Trapped Heart", "💔", "rare", 1500),
    ("Eternal Rose", "🌹", "rare", 2000),
    ("Toy Bear", "🧸", "epic", 3000),
    ("Diamond Ring", "💍", "epic", 3500),
    ("Vintage Cigar", "🚬", "epic", 4000),
    ("Neko Helmet", "🐱", "epic", 4500),
    ("Signet Ring", "💎", "epic", 5500),
    ("Swiss Watch", "⌚", "epic", 6000),
    ("Genie Lamp", "🪔", "epic", 6500),
    ("Loot Bag", "💰", "legendary", 15000),
    ("Heart Locket", "💝", "legendary", 30000),
    ("Precious Peach", "🍑", "legendary", 50000),
    ("Durov's Cap", "🧢", "legendary", 120000),
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
        await s.commit()
        return
    by_name: dict[str, Item] = {}
    for name, emoji, rarity, value in ITEMS:
        item = Item(name=name, gift_name=name, emoji=emoji, rarity=rarity, value=value * 100,
                    image_url=gift_image(name))
        s.add(item)
        by_name[name] = item
    await s.flush()
    for sort, (slug, name, emoji, price, rtp, names) in enumerate(CASES):
        items = [by_name[n] for n in names]
        weights = weights_for_rtp([i.value for i in items], price * 100, rtp)
        case = Case(slug=slug, name=name, emoji=emoji, price=price * 100, sort=sort)
        case.items = [CaseItem(item_id=i.id, weight=w) for i, w in zip(items, weights)]
        s.add(case)
    await s.commit()
