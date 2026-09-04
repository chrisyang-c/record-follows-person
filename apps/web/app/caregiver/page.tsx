"use client";

import { Check } from "lucide-react";
import Link from "next/link";
import { useApi, type PatientSummary, type Resident } from "@/lib/api";

function ResidentCard({ r }: { r: Resident }) {
  const { data } = useApi<PatientSummary>(`/patients/${r.patient_id}/summary`);
  const recorded = data?.recorded_today ?? false;
  const notes = data?.notes_count ?? 0;
  const red = data?.session?.phase === "red";
  return (
    <Link href={`/p/${r.patient_id}?tab=talk`} className="flex min-h-[88px] items-center gap-4 rounded-[12px] border border-line bg-bg px-4 shadow-[var(--shadow-card)] hover:border-primary hover:bg-surface">
      <div className="min-w-0 flex-1">
        <p className="text-xl font-medium">{r.code_name} <span className="text-sm font-normal text-ink-2">{r.room}</span></p>
        <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-ink-2">
          {data ? (
            recorded ? (
              <span className="inline-flex items-center gap-1 text-ok-ink"><Check className="size-4" aria-hidden="true" />今天記了</span>
            ) : (
              <span>今天還沒記</span>
            )
          ) : (
            <span>…</span>
          )}
          {notes > 0 && <span>注意事項 <span className="num">{notes}</span> 件</span>}
          {red && <span className="text-danger-ink">護理師已收到通知</span>}
        </p>
      </div>
      <span className="text-primary" aria-hidden="true">→</span>
    </Link>
  );
}

/** 照護者首頁：三張住民大卡（≥88px），點進去就是對話。 */
export default function CaregiverHome() {
  const { data: residents, error } = useApi<Resident[]>("/residents");
  return (
    <div className="mx-auto max-w-[390px] space-y-4">
      <h1 className="text-2xl font-medium">今天照顧誰？</h1>
      {error && <p role="alert" className="text-danger-ink">無法連線到 API，請確認 make api 已啟動。</p>}
      {residents && residents.length === 0 && <p className="text-ink-2">還沒有住民資料，先跑 <code>make seed</code>。</p>}
      <ul className="grid gap-3">
        {(residents ?? []).map((r) => (
          <li key={r.patient_id}><ResidentCard r={r} /></li>
        ))}
      </ul>
      <p className="pt-4 text-center text-sm"><Link href="/" className="inline-flex min-h-11 items-center text-ink-2 hover:text-ink">切換角色</Link></p>
    </div>
  );
}
