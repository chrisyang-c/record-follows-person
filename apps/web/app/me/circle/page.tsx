"use client";

import { useState } from "react";
import { Chip } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api, useApi, type AccessLogEntry, type CareCircleMember } from "@/lib/api";
import { fmtDateTime, fmtDay } from "@/lib/format";
import { useAuthSession } from "@/components/auth/session-provider";
import { PURPOSE_LABEL, type AccessPurpose } from "@/lib/auth";
import { IDENTITIES, ROLE_LABEL, TAB_LABEL, type Role, type Tab } from "@/lib/role";

type ManagedMember = CareCircleMember & { allowed_purposes?: AccessPurpose[]; can_manage?: boolean };
type CircleData = { health_id: string; members: ManagedMember[]; identities: Record<string, { role: Role; name: string }> };
const ALL: Tab[] = ["who", "timeline", "docs", "talk"];

/** Care Circle：誰能看我、看什麼、到什麼時候；本人可授權與撤銷；下面是「誰看過我的紀錄」。 */
export default function MeCirclePage() {
  const session = useAuthSession();
  const pid = session?.patient_id;
  const isOwner = session?.who === pid;
  const { data, error, reload } = useApi<CircleData>(pid ? `/patients/${pid}/care-circle` : null, [pid]);
  const { data: log, reload: reloadLog } = useApi<{ items: AccessLogEntry[] }>(pid ? `/patients/${pid}/access-log?limit=30` : null, [pid]);
  const [who, setWho] = useState("nurse_huang");
  const [scopes, setScopes] = useState<Tab[]>(["who", "timeline"]);
  const [days, setDays] = useState(30);
  const [purpose, setPurpose] = useState("護理評估與確認");
  const [allowedPurposes, setAllowedPurposes] = useState<AccessPurpose[]>(["treatment"]);
  const [canManage, setCanManage] = useState(false);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  if (!pid) return <p className="text-ink-2">請先登入並選擇要管理授權的住民。</p>;
  if (!data && !error) return <p className="text-ink-2">Loading…</p>;
  if (error) return <p role="alert" className="text-danger-ink">{error}</p>;
  const active = data!.members.filter((m) => !m.revoked_at && (!m.valid_to || m.valid_to > new Date().toISOString()));
  const revoke = async (memberId: string) => {
    if (!window.confirm(`撤銷 ${data!.identities[memberId]?.name ?? memberId} 的存取？撤銷後對方的新請求將無法讀取你的紀錄；已讀取的資料不會被遠端刪除。`)) return;
    setBusy(true);
    setActionError(null);
    try {
      await api(`/patients/${pid}/care-circle/${memberId}/revoke`, { method: "POST", json: {} });
      reload();
      reloadLog();
    } catch (err) {
      setActionError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const grant = async () => {
    if (!purpose.trim() || !scopes.length || !allowedPurposes.length) {
      setActionError("請填寫授權說明，並至少選擇一個資料範圍與一個使用目的。");
      return;
    }
    setBusy(true);
    setActionError(null);
    try {
      const role = data!.identities[who]?.role;
      if (!role) throw new Error("請選擇已註冊的帳號。");
      await api(`/patients/${pid}/care-circle`, { method: "POST", json: { member_id: who, role, scopes, valid_days: days || null, purpose, allowed_purposes: allowedPurposes, can_manage: isOwner && canManage } });
      reload();
      reloadLog();
    } catch (err) {
      setActionError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="space-y-4">
      <h1 className="text-balance text-2xl font-medium">Care Circle</h1>
      <p className="text-sm text-ink-2">{isOwner ? "誰能看我的紀錄，由我決定。" : "依本人委任管理授權；可授予的範圍由系統查證。"}<span className="num" translate="no">Health ID {data!.health_id}</span></p>
      {actionError && <p role="alert" className="rounded-lg border border-danger bg-danger-fill p-3 text-sm text-danger-ink">{actionError}</p>}
      <Card title="目前可以看我的人" headingLevel={2}>
        <ul className="divide-y divide-line">
          {active.map((m) => (
            <li key={m.member_id} className="flex flex-wrap items-center gap-2 py-2">
              <span className="font-medium">{m.name || IDENTITIES[m.member_id]?.name || m.member_id}</span>
              <Chip>{ROLE_LABEL[m.role as Role]}</Chip>
              <span className="text-xs text-ink-2">{m.scopes.map((s) => TAB_LABEL[s as Tab]).join("、")}{m.valid_to ? ` · 到 ${fmtDay(m.valid_to)}` : ""}{m.purpose ? ` · 為了${m.purpose}` : ""}</span>
              {m.allowed_purposes?.length ? <span className="text-xs text-ink-2">用途：{m.allowed_purposes.map((p) => PURPOSE_LABEL[p] ?? p).join("、")}</span> : null}
              {m.can_manage && <Chip>受委任管理授權</Chip>}
              {m.role !== "patient" && (
                <Button variant="outline" className="ml-auto min-h-11" disabled={busy} onClick={() => void revoke(m.member_id)}>撤銷</Button>
              )}
            </li>
          ))}
        </ul>
      </Card>
      <Card title="授權新的人" headingLevel={2}>
        <form className="space-y-3 text-sm" onSubmit={(e) => { e.preventDefault(); void grant(); }}>
          <label className="block">
            <span className="text-ink-2">誰</span>
            <select name="who" autoComplete="off" disabled={busy} value={who} onChange={(e) => setWho(e.target.value)} className="mt-1 min-h-14 w-full rounded-[10px] border border-line bg-bg px-3 text-ink focus-visible:ring-2 focus-visible:ring-primary">
              {Object.entries(data!.identities).filter(([k, v]) => v.role !== "patient" && k !== `fam_${pid}`).map(([k, v]) => (
                <option key={k} value={k}>{v.name}（{ROLE_LABEL[v.role]}）</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-ink-2">授權說明（必填）</span>
            <input name="purpose" autoComplete="off" required disabled={busy} value={purpose} onChange={(e) => setPurpose(e.target.value)} placeholder="例如：夜班交接、陪同就醫…" className="mt-1 min-h-14 w-full rounded-[10px] border border-line bg-bg px-3 text-ink placeholder:text-ink-2 focus-visible:ring-2 focus-visible:ring-primary" />
          </label>
          <fieldset>
            <legend className="text-ink-2">可以看</legend>
            <div className="mt-1 flex flex-wrap gap-2">
              {ALL.map((t) => (
                <label key={t} className="inline-flex min-h-14 items-center gap-1 rounded-full border border-line px-3">
                  <input type="checkbox" name="scopes" disabled={busy} checked={scopes.includes(t)} onChange={(e) => setScopes((s) => (e.target.checked ? [...s, t] : s.filter((x) => x !== t)))} className="size-4 accent-[var(--primary)]" />
                  {TAB_LABEL[t]}
                </label>
              ))}
            </div>
          </fieldset>
          <fieldset>
            <legend className="text-ink-2">允許的使用目的（至少一項）</legend>
            <div className="mt-1 flex flex-wrap gap-2">
              {(Object.keys(PURPOSE_LABEL) as AccessPurpose[]).map((p) => (
                <label key={p} className="inline-flex min-h-14 items-center gap-2 rounded-full border border-line px-3">
                  <input type="checkbox" name="allowed_purposes" disabled={busy} checked={allowedPurposes.includes(p)} onChange={(e) => setAllowedPurposes((prev) => e.target.checked ? [...prev, p] : prev.filter((v) => v !== p))} className="size-4 accent-[var(--primary)]" />
                  {PURPOSE_LABEL[p]}
                </label>
              ))}
            </div>
          </fieldset>
          {isOwner && <label className="flex min-h-14 items-center gap-2">
            <input type="checkbox" name="can_manage" disabled={busy} checked={canManage} onChange={(e) => setCanManage(e.target.checked)} className="size-4 accent-[var(--primary)]" />
            委任此人管理授權
          </label>}
          <label className="block">
            <span className="text-ink-2">有效天數（0＝不限）</span>
            <input type="number" name="valid_days" autoComplete="off" inputMode="numeric" min={0} disabled={busy} value={days} onChange={(e) => setDays(Number(e.target.value))} className="num mt-1 min-h-14 w-full rounded-[10px] border border-line bg-bg px-3 text-ink focus-visible:ring-2 focus-visible:ring-primary" />
          </label>
          <Button type="submit" size="lg" className="w-full" disabled={busy} aria-busy={busy}>{busy ? "送出中…" : "授權"}</Button>
        </form>
      </Card>
      <Card title="誰看過我的紀錄" headingLevel={2}>
        {log && log.items.length === 0 && <p className="text-sm text-ink-2">還沒有人看過。</p>}
        <ul className="divide-y divide-line text-sm">
          {(log?.items ?? []).map((e, i) => (
            <li key={i} className="flex flex-wrap items-center gap-2 py-1.5">
              <span className="font-medium">{IDENTITIES[e.who]?.name ?? e.who}</span>
              <span className="text-ink-2">{e.what}</span>
              {e.outcome && <Chip tone={e.outcome === "denied" || e.outcome === "failed" ? "warn" : "neutral"}>{e.outcome === "denied" ? "拒絕" : e.outcome === "failed" ? "操作失敗" : "允許"}</Chip>}
              {e.purpose && <span className="text-xs text-ink-2">用途：{PURPOSE_LABEL[e.purpose as AccessPurpose] ?? e.purpose}</span>}
              {e.reason && <span className="break-all text-xs text-ink-2" translate="no">{e.reason}</span>}
              <span className="ml-auto text-xs text-ink-2">{fmtDateTime(e.ts)}</span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
