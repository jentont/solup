import { fmt, Item } from "../api";

type Props = {
  item: Item;
  selected?: boolean;
  onClick?: () => void;
  footer?: React.ReactNode;
  size?: "sm" | "md";
};

export function ItemCard({ item, selected, onClick, footer, size = "md" }: Props) {
  return (
    <div className={`item-card r-${item.rarity} ${size} ${selected ? "selected" : ""}`} onClick={onClick}>
      <div className="item-emoji">
        {item.image_url ? <img src={item.image_url} alt="" /> : item.emoji}
      </div>
      <div className="item-name">{item.name}</div>
      <div className="item-value">{fmt(item.value)} <i className="coin" /></div>
      {item.chance !== undefined && <div className="item-chance">{(item.chance * 100).toFixed(item.chance < 0.01 ? 3 : 1)}%</div>}
      {footer}
    </div>
  );
}
