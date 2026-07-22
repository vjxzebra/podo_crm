import type { PaymentMethod } from "./financeTypes";

const moneyFormatter = new Intl.NumberFormat("uk-UA", {
  style: "currency",
  currency: "UAH",
  maximumFractionDigits: 2,
});

export const dateTimeFormatter = new Intl.DateTimeFormat("uk-UA", {
  timeZone: "Europe/Kyiv",
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

export const shortDateTimeFormatter = new Intl.DateTimeFormat("uk-UA", {
  timeZone: "Europe/Kyiv",
  day: "2-digit",
  month: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

export const methodLabels: Readonly<Record<PaymentMethod, string>> = {
  CASH: "Готівка",
  CARD: "Картка",
  TRANSFER: "Переказ",
};

export function money(value: number): string {
  return moneyFormatter.format(value / 100);
}

export function parseMoneyToMinor(value: string): number | null {
  const normalized = value.trim().replace(/[\s\u00a0\u202f]/g, "").replace(",", ".");
  if (!/^\d+(?:\.\d{0,2})?$/.test(normalized)) return null;
  const [whole = "0", fraction = ""] = normalized.split(".");
  const minor = (BigInt(whole) * 100n) + BigInt(fraction.padEnd(2, "0") || "0");
  if (minor <= 0n || minor > BigInt(Number.MAX_SAFE_INTEGER)) return null;
  return Number(minor);
}

export function parseNonNegativeMoneyToMinor(value: string): number | null {
  const normalized = value.trim().replace(/[\s\u00a0\u202f]/g, "").replace(",", ".");
  if (!/^\d+(?:\.\d{0,2})?$/.test(normalized)) return null;
  const [whole = "0", fraction = ""] = normalized.split(".");
  const minor = (BigInt(whole) * 100n) + BigInt(fraction.padEnd(2, "0") || "0");
  if (minor < 0n || minor > BigInt(Number.MAX_SAFE_INTEGER)) return null;
  return Number(minor);
}
