/**
 * Indian localized formatters for currency, dates, and times (CODE-11, HUM-26).
 */

export function formatInr(amount: number | null | undefined): string {
  if (amount === null || amount === undefined) return "-";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatDateIst(isoString: string | null | undefined): string {
  if (!isoString) return "-";
  const d = new Date(isoString);
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "Asia/Kolkata",
  }).format(d);
}

export function formatDateTimeIst(isoString: string | null | undefined): string {
  if (!isoString) return "-";
  const d = new Date(isoString);
  const datePart = new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "Asia/Kolkata",
  }).format(d);
  const timePart = new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Kolkata",
  }).format(d);
  return `${datePart}, ${timePart} IST`;
}
