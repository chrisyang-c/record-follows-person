"use client";

import Link from "next/link";
import { Chip } from "@/components/ui/badge";
import { useApi, type MeTimeline } from "@/lib/api";
import { fmtDay } from "@/lib/format";
import { LIFE_EVENT_LABEL } from "@/lib/labels";
import { useMyPatientId } from "@/lib/me";

/** 事件：所有大事件（確診／住院／手術／跌倒／急症）一列一件。 */
export default function MeEventsPage() {
  const pid = useMyPatientId();
  const { data, error } = useApi<MeTimeline>(pid ? `/me/${pid}/timeline` : null, [pid]);
  if (pid === undefined || (!data && !error)) return <p className="text-ink-2">Loading…</p>;
  if (error) return <p role="alert" className="text-danger-ink">{error}</p>;
  const events = data!.years.flatMap((y) => y.major);
  return (
    <div>
      <h1 className="text-2xl font-medium">事件</h1>
      <ul className="mt-3 divide-y divide-line">
        {events.map((e) => (
          <li key={e.id} className="py-3">
            <div className="flex items-center gap-2">
              <Chip tone={e.type === "fall" || e.type === "acute" ? "danger" : "neutral"}>{LIFE_EVENT_LABEL[e.type as keyof typeof LIFE_EVENT_LABEL] ?? "事件"}</Chip>
              <Link href={`/p/${pid}?tab=timeline#${e.id}`} className="font-medium hover:text-primary">{e.title}</Link>
              <span className="ml-auto text-xs text-ink-2">{fmtDay(e.ts)}</span>
            </div>
            {e.summary && <p className="mt-1 text-sm text-ink-2">{e.summary}{e.facility ? `（${e.facility}）` : ""}</p>}
          </li>
        ))}
      </ul>
    </div>
  );
}
