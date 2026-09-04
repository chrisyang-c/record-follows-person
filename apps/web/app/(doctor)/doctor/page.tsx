"use client";

import Link from "next/link";
import type { RoundPage } from "@schema";
import { ConfirmedChip } from "@/components/confirmed-chip";
import { Card } from "@/components/ui/card";
import { useApi, type Resident } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";

function Row({ r }: { r: Resident }) {
  const { data, error, status, loading } = useApi<RoundPage>(`/round-pages/${r.patient_id}`);
  return (
    <Card title={`${r.code_name} · ${r.room}`} headingLevel={2} meta={<span translate="no">{r.patient_id}</span>}>
      {data && (
        <>
          <p className="flex flex-wrap items-center gap-2 text-sm text-ink-2">
            RoundPage {fmtDateTime(data.generated_at)} <ConfirmedChip by={data.confirmed_by} />
          </p>
          <p className="mt-1 line-clamp-2 text-sm">{data.changes[0]?.summary ?? "—"}</p>
          <Link href={`/doctor/round/${r.patient_id}`} className="mt-3 inline-flex min-h-11 items-center rounded-[10px] bg-primary px-4 text-white hover:bg-primary-hover">看這一頁 →</Link>
        </>
      )}
      {loading && <p className="text-sm text-ink-2">Loading…</p>}
      {/* 404 = 還沒發布（正常）；其他 = API 沒開 */}
      {error && status === 404 && <p className="text-sm text-ink-2">尚未發布 RoundPage（護理師端執行巡診準備）</p>}
      {error && status !== 404 && (
        <p role="alert" className="text-sm text-danger-ink">
          無法連線到 API，請確認 make api 已啟動。
          <span className="block text-xs text-ink-2" translate="no">{error}</span>
        </p>
      )}
    </Card>
  );
}

export default function DoctorHome() {
  const { data: residents, error, loading } = useApi<Resident[]>("/residents");
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-medium">巡診名單（唯讀）</h1>
      <p className="text-sm text-ink-2">每人一頁：這是誰、變了什麼、上次醫囑做了沒、請你確認什麼。可列印 A4。</p>
      {loading && <p className="text-ink-2">Loading…</p>}
      {error && (
        <p role="alert" className="text-danger-ink">
          無法連線到 API，請確認 make api 已啟動。<span className="block text-xs text-ink-2" translate="no">{error}</span>
        </p>
      )}
      {residents && residents.length === 0 && (
        <p className="text-ink-2">
          還沒有住民資料，先跑 <code>make seed</code>。
        </p>
      )}
      {residents && residents.length > 0 && (
        <ul className="grid gap-4 md:grid-cols-3">
          {residents.map((r) => (
            <li key={r.patient_id}><Row r={r} /></li>
          ))}
        </ul>
      )}
    </div>
  );
}
