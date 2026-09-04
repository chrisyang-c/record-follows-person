"use client";

import Link from "next/link";
import type { RoundPage } from "@schema";
import { ConfirmedChip } from "@/components/confirmed-chip";
import { Chip } from "@/components/ui/badge";
import { useApi, type Resident } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";

function Row({ r }: { r: Resident }) {
  const { data, error, status } = useApi<RoundPage>(`/round-pages/${r.patient_id}`);
  const first = data?.changes[0]?.summary ?? (data ? "本期八維度皆與基線一致" : "");
  return (
    <li className="flex min-h-16 flex-wrap items-center gap-3 border-t border-line py-3">
      <div className="min-w-0 flex-1">
        <p className="text-lg font-medium">{r.code_name} <span className="text-sm font-normal text-ink-2">{r.room}</span></p>
        {data && (
          <p className="mt-0.5 flex flex-wrap items-center gap-2 text-sm text-ink-2">
            <span className="truncate">{first}</span>
            <span>· {fmtDateTime(data.generated_at)}</span>
            {data.status === "approved" ? <ConfirmedChip by={data.confirmed_by} /> : <Chip tone="primary">草稿</Chip>}
          </p>
        )}
        {error && status === 404 && <p className="text-sm text-ink-2">尚未發布 RoundPage</p>}
        {error && status !== 404 && <p role="alert" className="text-sm text-danger-ink">無法連線到 API</p>}
      </div>
      <Link href={`/p/${r.patient_id}?tab=docs`} className="inline-flex min-h-12 items-center rounded-[10px] bg-primary px-4 text-white hover:bg-primary-hover">看一頁 →</Link>
    </li>
  );
}

/** 醫師首頁：今天的巡診名單，一列一人，「看一頁」進 RoundPage（可列印 A4）。 */
export default function DoctorHome() {
  const { data: residents, error } = useApi<Resident[]>("/residents");
  return (
    <div className="space-y-3">
      <h1 className="text-2xl font-medium">今天巡診</h1>
      <p className="text-sm text-ink-2">每人一頁：這是誰、變了什麼、上次醫囑做了沒、請你確認什麼。</p>
      {error && <p role="alert" className="text-danger-ink">無法連線到 API，請確認 make api 已啟動。</p>}
      <ul>
        {(residents ?? []).map((r) => (
          <Row key={r.patient_id} r={r} />
        ))}
      </ul>
    </div>
  );
}
