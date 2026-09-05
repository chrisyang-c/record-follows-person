"use client";

import { useState } from "react";
import { Chip } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api, useApi, type AccessLogEntry, type CareCircleMember } from "@/lib/api";
import { fmtDateTime, fmtDay } from "@/lib/format";
import { useMyPatientId } from "@/lib/me";
import { IDENTITIES, ROLE_LABEL, TAB_LABEL, type Role, type Tab } from "@/lib/role";

type CircleData = { health_id: string; members: CareCircleMember[]; identities: Record<string, { role: Role; name: string }> };
const ALL: Tab[] = ["who", "timeline", "docs", "talk"];

/** Care Circle：誰能看我、看什麼、到什麼時候；本人可授權與撤銷；下面是「誰看過我的紀錄」。 */
export default function MeCirclePage() {
  const pid = useMyPatientId();
  const { data, error, reload } = useApi<CircleData>(pid ? `/patients/${pid}/care-circle` : null, [pid]);
  const { data: log, reload: reloadLog } = useApi<{ items: AccessLogEntry[] }>(pid ? `/patients/${pid}/access-log?limit=30` : null, [pid]);
  const [who, setWho] = useState("nurse_huang");
  const [scopes, setScopes] = useState<Tab[]>(["who", "timeline"]);
  const [days, setDays] = useState(30);
  const [busy, setBusy] = useState(false);
  if (pid === undefined || (!data && !error)) return <p className="text-ink-2">Loading…</p>;
  if (error) return <p role="alert" className="text-danger-ink">{error}</p>;
  const active = data!.members.filter((m) => !m.revoked_at && (!m.valid_to || m.valid_to > new Date().toISOString()));
  const revoke = async (memberId: string) => {
    if (!window.confirm(`撤銷 ${IDENTITIES[memberId]?.name ?? memberId} 的存取？撤銷後對方立刻看不到你的紀錄。`)) return;
    setBusy(true);
    try {
      await api(`/patients/${pid}/care-circle/${memberId}/revoke`, { method: "POST", json: {} });
      reload();
      reloadLog();
    } finally {
      setBusy(false);
    }
  };
  const grant = async () => {
    setBusy(true);
    try {
      const role = IDENTITIES[who]?.role ?? "nurse";
      await api(`/patients/${pid}/care-circle`, { method: "POST", json: { member_id: who, role, scopes, valid_days: days || null, granted_by: pid } });
      reload();
      reloadLog();
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-medium">Care Circle</h1>
      <p className="text-sm text-ink-2">誰能看我的紀錄，由我決定。<span className="num" translate="no">Health ID {data!.health_id}</span></p>
      <Card title="目前可以看我的人" headingLevel={2}>
        <ul className="divide-y divide-line">
          {active.map((m) => (
            <li key={m.member_id} className="flex flex-wrap items-center gap-2 py-2">
              <span className="font-medium">{m.name || IDENTITIES[m.member_id]?.name || m.member_id}</span>
              <Chip>{ROLE_LABEL[m.role as Role]}</Chip>
              <span className="text-xs text-ink-2">{m.scopes.map((s) => TAB_LABEL[s as Tab]).join("、")}{m.valid_to ? ` · 到 ${fmtDay(m.valid_to)}` : ""}</span>
              {m.role !== "patient" && (
                <Button variant="outline" className="ml-auto min-h-11" disabled={busy} onClick={() => void revoke(m.member_id)}>撤銷</Button>
              )}
            </li>
          ))}
        </ul>
      </Card>
      <Card title="授權新的人" headingLevel={2}>
        <div className="space-y-3 text-sm">
          <label className="block">
            <span className="text-ink-2">誰</span>
            <select name="who" value={who} onChange={(e) => setWho(e.target.value)} className="mt-1 min-h-11 w-full rounded-[10px] border border-line bg-bg px-3 text-ink focus-visible:ring-2 focus-visible:ring-primary">
              {Object.entries(IDENTITIES).filter(([k, v]) => v.role !== "patient" && k !== `fam_${pid}`).map(([k, v]) => (
                <option key={k} value={k}>{v.name}（{ROLE_LABEL[v.role]}）</option>
              ))}
            </select>
          </label>
          <fieldset>
            <legend className="text-ink-2">可以看</legend>
            <div className="mt-1 flex flex-wrap gap-2">
              {ALL.map((t) => (
                <label key={t} className="inline-flex min-h-11 items-center gap-1 rounded-full border border-line px-3">
                  <input type="checkbox" checked={scopes.includes(t)} onChange={(e) => setScopes((s) => (e.target.checked ? [...s, t] : s.filter((x) => x !== t)))} className="size-4 accent-[var(--primary)]" />
                  {TAB_LABEL[t]}
                </label>
              ))}
            </div>
          </fieldset>
          <label className="block">
            <span className="text-ink-2">有效天數（0＝不限）</span>
            <input type="number" name="valid_days" inputMode="numeric" min={0} value={days} onChange={(e) => setDays(Number(e.target.value))} className="num mt-1 min-h-11 w-full rounded-[10px] border border-line bg-bg px-3" />
          </label>
          <Button size="lg" className="w-full" disabled={busy || scopes.length === 0} onClick={() => void grant()}>授權</Button>
        </div>
      </Card>
      <Card title="誰看過我的紀錄" headingLevel={2}>
        {log && log.items.length === 0 && <p className="text-sm text-ink-2">還沒有人看過。</p>}
        <ul className="divide-y divide-line text-sm">
          {(log?.items ?? []).map((e, i) => (
            <li key={i} className="flex flex-wrap items-center gap-2 py-1.5">
              <span className="font-medium">{IDENTITIES[e.who]?.name ?? e.who}</span>
              <span className="text-ink-2">{e.what}</span>
              <span className="ml-auto text-xs text-ink-2">{fmtDateTime(e.ts)}</span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
