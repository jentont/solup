import { fmt, Me } from "../api";

type Props = {
  me: Me;
  demo: boolean;
  onDemo: (on: boolean) => void;
  onDeposit: () => void;
  onRefill: () => void;
  onClose: () => void;
};

// Кошелёк: какой баланс в игре — настоящий или демо — и как его пополнить.
export function Wallet({ me, demo, onDemo, onDeposit, onRefill, onClose }: Props) {
  return (
    <div className="sheet-bg" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <div className="grabber" />
        <div className="row between">
          <h2 className="sheet-title">Кошелёк.</h2>
          <button className="close" onClick={onClose}>✕</button>
        </div>

        <div className="pill-tabs">
          <button className={!demo ? "active" : ""} onClick={() => onDemo(false)}>Реальный</button>
          <button className={demo ? "active" : ""} onClick={() => onDemo(true)}>Демо</button>
        </div>

        <div className="wcard wallet-card">
          <div className="wcard-label">{demo ? "демо-баланс" : "баланс"}</div>
          <div className="wcard-num">
            {fmt(demo ? me.demo_balance : me.balance)} <i className="coin coin--big" />
          </div>
          {demo ? (
            <div className="wallet-note">Тренируйся без риска: монеты ненастоящие, выигрыши не выводятся.</div>
          ) : (
            <div className="wallet-note">Пополняй звёздами, криптой или подарками, выводи подарками.</div>
          )}
        </div>

        {demo ? (
          <button className="btn wide" onClick={onRefill}>Вернуть демо-баланс до 10 000</button>
        ) : (
          <button className="btn wide" onClick={onDeposit}>Пополнить</button>
        )}
        <button className="btn ghost wide" onClick={onClose}>Играть</button>
      </div>
    </div>
  );
}
