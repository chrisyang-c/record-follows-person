"use client";

import { Printer } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import type { RoundPage } from "@schema";
import { RoundPageView } from "@/components/round-page-view";
import { Button } from "@/components/ui/button";
import { useApi } from "@/lib/api";

export default function DoctorRoundPage() {
  const { patientId } = useParams<{ patientId: string }>();
  const { data, error, status, loading } = useApi<RoundPage>(`/round-pages/${patientId}`);
  return (
    <div className="space-y-3">
      <div className="no-print flex flex-wrap items-center gap-2">
        <Link href="/doctor" className="inline-flex min-h-11 items-center text-sm text-primary hover:underline">← 名單</Link>
        <span className="ml-auto" />
        <Button variant="outline" onClick={() => window.print()} aria-label="列印 A4">
          <Printer className="size-4" aria-hidden="true" /> 列印 A4
        </Button>
      </div>
      {loading && <p className="text-ink-2">Loading…</p>}
      {error && status === 404 && (
        <p role="alert" className="text-ink-2">尚未發布 RoundPage：請護理師在「巡診準備」發布後再看。</p>
      )}
      {error && status !== 404 && (
        <p role="alert" className="text-danger-ink">
          無法連線到 API，請確認 make api 已啟動。<span className="block text-xs text-ink-2" translate="no">{error}</span>
        </p>
      )}
      {data && <RoundPageView page={data} />}
    </div>
  );
}
