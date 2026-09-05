"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useSyncExternalStore } from "react";
import { DocsTab } from "@/components/patient/docs-tab";
import { TalkTab } from "@/components/patient/talk-tab";
import { TimelineTab } from "@/components/patient/timeline-tab";
import { WhoTab } from "@/components/patient/who-tab";
import { Chip } from "@/components/ui/badge";
import { useApi, type PatientSummary } from "@/lib/api";
import { setPatientTitle } from "@/lib/patient-title";
import { AccessDenied } from "@/components/patient/access-denied";
import { isTab, readMe, readRole, ROLE_TABS, TAB_LABEL, type Role, type Tab } from "@/lib/role";
import { cn } from "@/lib/utils";

/**
 * 病人頁 = 單一入口：/p/{id}?tab=who|timeline|docs|talk。
 * 預設 tab：照護者 talk；護理師 有紅燈／草稿 → docs，否則 timeline；醫師 docs（proxy.ts 先給角色第一個 tab，這裡再依資料調整）。
 */
function PatientInner() {
  const { id } = useParams<{ id: string }>();
  const params = useSearchParams();
  const router = useRouter();
  // cookie 只在瀏覽器讀得到：伺服器先給 null，hydrate 後換成真正角色（避免 SSR/CSR 不一致）
  const roleCookie = useSyncExternalStore(() => () => {}, () => readRole(), () => null);
  const me = useSyncExternalStore(() => () => {}, () => readMe(), () => null);
  const role: Role = roleCookie ?? "nurse";
  const tabParam = params.get("tab");
  const requested: Tab = isTab(tabParam) ? tabParam : ROLE_TABS[role][0];
  const onlyIds = useMemo(() => (params.get("ids") ?? "").split(",").filter(Boolean), [params]);
  // ?tab= 也送給 API：access log 記「看了哪個 tab」
  const { data, error, status, reload } = useApi<PatientSummary>(`/patients/${id}/summary?tab=${requested}`, [me]);
  const allowed: Tab[] = data?.allowed_tabs ?? ROLE_TABS[role];
  const tab: Tab = requested;
  const name = data?.profile.code_name ?? "";
  useEffect(() => {
    setPatientTitle(name);
    return () => setPatientTitle("");
  }, [name]);
  // 護理師沒指定 tab 且沒有紅燈／草稿 → timeline
  useEffect(() => {
    if (role === "nurse" && data && !isTab(tabParam) && data.pending.length === 0) router.replace(`/p/${id}?tab=timeline`);
  }, [role, data, tabParam, id, router]);

  if (roleCookie === null) return <p className="text-ink-2">Loading…</p>;
  if (error && status === 404) return <p role="alert" className="text-danger-ink">找不到這位住民。</p>;
  if (error && status === 403) return <AccessDenied what="這份紀錄" />;
  if (error) return <p role="alert" className="text-danger-ink">無法連線到 API，請確認 make api 已啟動。<span className="block text-xs text-ink-2" translate="no">{error}</span></p>;
  if (!data) return <p className="text-ink-2">Loading…</p>;
  const red = data.pending.some((p) => p.red_flag);
  const drafts = data.pending.length;
  return (
    <div className="space-y-4">
      <header className="no-print flex flex-wrap items-baseline gap-2">
        <h1 className="text-2xl font-medium">{data.profile.code_name}</h1>
        <span className="text-sm text-ink-2">{data.profile.room}</span>
        <span className="num w-full text-xs text-ink-2 sm:w-auto" translate="no">Health ID {data.profile.health_id}</span>
        {red && <Chip tone="danger">紅燈</Chip>}
        {!red && drafts > 0 && role !== "caregiver" && <Chip tone="primary">待確認 {drafts}</Chip>}
        {data.session?.phase === "red" && role === "caregiver" && <Chip tone="danger">護理師已收到通知</Chip>}
      </header>
      <nav aria-label="分頁" className="no-print -mx-4 overflow-x-auto border-b border-line px-4">
        <ul className="flex gap-1">
          {[...allowed, ...ROLE_TABS[role].filter((t) => !allowed.includes(t))].map((t) => (
            <li key={t}>
              <Link
                href={`/p/${id}?tab=${t}`}
                aria-current={t === tab ? "page" : undefined}
                className={cn("inline-flex min-h-12 items-center border-b-2 px-3 text-base", t === tab ? "border-primary font-medium text-ink" : "border-transparent text-ink-2 hover:text-ink", !allowed.includes(t) && "text-ink-2/60")}
                aria-disabled={!allowed.includes(t) || undefined}
              >
                {TAB_LABEL[t]}
                {t === "docs" && drafts > 0 && role === "nurse" && <span className="num ml-1 rounded-full bg-ai-fill px-1.5 text-xs">{drafts}</span>}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
      {!allowed.includes(tab) && <AccessDenied what={`「${TAB_LABEL[tab]}」`} />}
      {allowed.includes(tab) && tab === "who" && <WhoTab summary={data} />}
      {allowed.includes(tab) && tab === "timeline" && <TimelineTab summary={data} role={role} onlyIds={onlyIds} />}
      {allowed.includes(tab) && tab === "docs" && <DocsTab summary={data} role={role} onChanged={reload} />}
      {allowed.includes(tab) && tab === "talk" && <TalkTab key={id} summary={data} role={role} onChanged={reload} />}
    </div>
  );
}

export default function PatientPage() {
  return (
    <Suspense fallback={<p className="text-ink-2">Loading…</p>}>
      <PatientInner />
    </Suspense>
  );
}
