const dt = new Intl.DateTimeFormat("zh-TW", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Taipei" });
const d = new Intl.DateTimeFormat("zh-TW", { month: "numeric", day: "numeric", timeZone: "Asia/Taipei" });
const num = new Intl.NumberFormat("zh-TW", { maximumFractionDigits: 1 });

export function fmtDateTime(iso?: string | null) {
  if (!iso) return "—";
  try {
    return dt.format(new Date(iso));
  } catch {
    return iso;
  }
}
export function fmtDay(iso?: string | null) {
  if (!iso) return "—";
  try {
    return d.format(new Date(iso));
  } catch {
    return iso;
  }
}
export function fmtNum(n?: number | null) {
  return n == null ? "—" : num.format(n);
}
export function fmtPct(n?: number | null) {
  return n == null ? "—" : `${Math.round(n * 100)}%`;
}
