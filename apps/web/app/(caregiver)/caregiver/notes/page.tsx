"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import type { CaregiverNotes } from "@schema";
import { ProvenanceBadge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useApi, type Resident } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import { T } from "@/lib/i18n";

const t = T["zh-TW"];

function NotesInner() {
  const params = useSearchParams();
  const patient = params.get("patient") ?? "P001";
  const { data: residents } = useApi<Resident[]>("/residents");
  const resident = residents?.find((r) => r.patient_id === patient);
  const { data, error, status, loading } = useApi<CaregiverNotes>(`/caregiver-notes/${patient}`);

  return (
    <div className="mx-auto max-w-[390px] text-lg">
      <h1 className="mb-1 text-2xl font-medium">{t.notes}</h1>
      <p className="mb-4 text-sm text-ink-2">
        {resident?.code_name} · {resident?.room}
      </p>
      {loading && <p className="text-ink-2">Loading…</p>}
      {error && status === 404 && (
        <Card headingLevel={2}>
          <p className="text-ink-2">還沒有本月注意事項。護理師輸入醫囑後會出現在這裡。</p>
        </Card>
      )}
      {error && status !== 404 && (
        <p role="alert" className="rounded-[10px] bg-danger-fill p-3 text-sm text-danger-ink">
          無法連線到 API，請確認 make api 已啟動。（{error}）
        </p>
      )}
      {data && (
        <Card variant="confirmed" headingLevel={2} meta={fmtDateTime(data.generated_at)}>
          <ol className="list-decimal space-y-4 pl-6">
            {data.items.map((it, i) => (
              <li key={i}>
                <p className="font-medium">{it}</p>
              </li>
            ))}
          </ol>
          <div className="mt-4">
            <ProvenanceBadge source={data.provenance.source} author={data.provenance.author} />
          </div>
        </Card>
      )}
      <p className="mt-6 text-center text-sm">
        <Link href={`/caregiver?patient=${patient}`} className="inline-flex min-h-14 items-center text-primary hover:underline">
          ← {t.speak}
        </Link>
      </p>
    </div>
  );
}

export default function NotesPage() {
  return (
    <Suspense fallback={<p className="text-ink-2">Loading…</p>}>
      <NotesInner />
    </Suspense>
  );
}
