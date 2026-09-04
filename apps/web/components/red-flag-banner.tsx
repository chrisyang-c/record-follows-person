import { AlertTriangle } from "lucide-react";

export function RedFlagBanner({ lines, title = "紅燈：觀察到的事實 → 建議聯絡護理師" }: { lines: string[]; title?: string }) {
  if (!lines.length) return null;
  return (
    <div role="alert" aria-live="assertive" className="red-flag sticky top-0 z-20 mb-4 p-4 text-ink">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 size-6 shrink-0 text-danger" aria-hidden="true" />
        <div className="min-w-0">
          <p className="font-medium text-danger-ink">{title}</p>
          <ul className="mt-1 space-y-1 text-sm">
            {lines.map((l, i) => (
              <li key={i} className="break-words">{l}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
