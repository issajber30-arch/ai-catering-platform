// Currency is a placeholder until OPEN_DECISIONS #17 is answered: change CURRENCY in one place.
const CURRENCY = "ILS";

const money = new Intl.NumberFormat("he-IL", { style: "currency", currency: CURRENCY, maximumFractionDigits: 2 });
const moneyWhole = new Intl.NumberFormat("he-IL", { style: "currency", currency: CURRENCY, maximumFractionDigits: 0 });
const number = new Intl.NumberFormat("he-IL", { maximumFractionDigits: 2 });
const dateLong = new Intl.DateTimeFormat("he-IL", { weekday: "long", day: "numeric", month: "long", year: "numeric" });

export function fmtMoney(value) {
  const n = Number(value);
  return Number.isInteger(n) ? moneyWhole.format(n) : money.format(n);
}

export function fmtSignedMoney(value) {
  const n = Number(value);
  if (n === 0) return fmtMoney(0);
  // Used inside a dir="ltr" span; strip the RLM marks Intl adds so the sign sits next to the number.
  return `${n > 0 ? "+" : "-"}${fmtMoney(Math.abs(n)).replace(/‏/g, "")}`;
}

export function fmtNumber(value) {
  return number.format(Number(value));
}

export function fmtDate(isoDate) {
  if (!isoDate) return "";
  const [y, m, d] = isoDate.split("-").map(Number);
  return dateLong.format(new Date(y, m - 1, d));
}

export function toIsoDate(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function addDays(date, days) {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}
