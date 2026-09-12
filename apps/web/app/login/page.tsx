"use client";

import { Activity, KeyRound, Lock } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { PURPOSE_LABEL, ROLE_PURPOSES, type AccessPurpose, type AuthSession } from "@/lib/auth";
import { IDENTITIES, ROLE_LABEL, type Role } from "@/lib/role";
import { cn } from "@/lib/utils";

const ROLES: Role[] = ["patient", "family", "caregiver", "nurse", "doctor"];
const HINT: Record<Role, string> = {
  patient: "01 活體數位孿生、我的時間軸、問我的紀錄、Care Circle",
  family: "家屬艙：我的家人、對話、四鍵驗證",
  caregiver: "家屬艙：我照顧的人、講一句今天怎麼樣",
  nurse: "護理站：Clinical Queue、事件資訊包、審核",
  doctor: "醫師艙：巡診名單、RoundPage、縱向摘要",
};
const PATIENTS = ["P001", "P002", "P003"];

/** Every person signs in with their own account. Existing consent grants determine access. */
function LoginInner() {
  const sp = useSearchParams();
  const next = sp.get("next") ?? "";
  const [role, setRole] = useState<Role>("patient");
  const ids = useMemo(() => Object.entries(IDENTITIES).filter(([, v]) => v.role === role), [role]);
  const [who, setWho] = useState<string>("P001");
  const [pid, setPid] = useState<string>("P001");
  const [password, setPassword] = useState("");
  const [purpose, setPurpose] = useState<AccessPurpose>("self-care");
  const passwordRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(sp.get("error") === "unavailable" ? "登入服務暫時無法連線，請稍後重試。" : null);
  const pickRole = (r: Role) => {
    setRole(r);
    const first = Object.entries(IDENTITIES).find(([, v]) => v.role === r)?.[0] ?? "";
    setWho(first);
    setPid(IDENTITIES[first]?.patient_id ?? "P001");
    setPurpose(ROLE_PURPOSES[r][0]);
    setPassword("");
    setErr(null);
  };
  const identity = IDENTITIES[who];
  const targetPid = identity?.patient_id ?? pid;
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setErr(null);
    try {
      await api<AuthSession>("/login", { method: "POST", json: { who, patient_id: targetPid, password, purpose } });
      // A full navigation discards the previous account's client state and rechecks the session.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- discard all prior account state after authentication
      window.location.assign(`/role${next ? `?next=${encodeURIComponent(next)}` : ""}`);
    } catch (e2) {
      setErr((e2 as Error).message);
      passwordRef.current?.focus();
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="mx-auto w-full max-w-[420px] space-y-5 py-4">
      <header className="text-center">
        <span className="mx-auto inline-flex size-14 items-center justify-center rounded-full border border-accent/60 text-accent"><Activity className="size-7" aria-hidden="true" /></span>
        <p className="label-caps mt-3">OMNI-TWIN · Sign in</p>
        <h1 className="text-balance text-2xl font-medium">登入</h1>
        <p className="mt-1 text-sm text-ink-2">請使用你自己的帳號與密碼。能查看哪些紀錄，由本人既有的 Care Circle 授權決定。</p>
      </header>

      <form onSubmit={submit} className="space-y-4 rounded-[12px] border border-line bg-surface p-5">
        <fieldset>
          <legend className="label-caps mb-2">我是</legend>
          <ul className="grid grid-cols-2 gap-2">
            {ROLES.map((r) => (
              <li key={r}>
                <button type="button" disabled={busy} aria-pressed={role === r} onClick={() => pickRole(r)} className={cn("flex min-h-14 w-full items-center justify-center rounded-[10px] border px-3 text-base focus-visible:ring-2 focus-visible:ring-accent hover:bg-surface-2 disabled:opacity-50", role === r ? "border-accent bg-surface-2 text-ink" : "border-line text-ink-2 hover:text-ink")}>
                  {ROLE_LABEL[r]}
                </button>
              </li>
            ))}
          </ul>
          <p className="mt-1 text-xs text-ink-2">{HINT[role]}</p>
        </fieldset>

        <label className="block">
          <span className="label-caps">個人帳號</span>
          <select name="who" autoComplete="username" disabled={busy} value={who} onChange={(e) => { setWho(e.target.value); setPassword(""); setErr(null); const p = IDENTITIES[e.target.value]?.patient_id; if (p) setPid(p); }} className="mt-1 min-h-14 w-full rounded-[10px] border border-line bg-bg px-3 text-ink focus-visible:ring-2 focus-visible:ring-accent">
            {ids.map(([k, v]) => (
              <option key={k} value={k}>{v.name} · {k}</option>
            ))}
          </select>
        </label>

        {!identity?.patient_id && (
          <label className="block">
            <span className="label-caps">要看的住民</span>
            <select name="patient_id" autoComplete="off" disabled={busy} value={pid} onChange={(e) => setPid(e.target.value)} className="mt-1 min-h-14 w-full rounded-[10px] border border-line bg-bg px-3 text-ink focus-visible:ring-2 focus-visible:ring-accent">
              {PATIENTS.map((p) => (
                <option key={p} value={p}>{IDENTITIES[p].name} · {p}</option>
              ))}
            </select>
          </label>
        )}

        <label className="block">
          <span className="label-caps">這次使用目的</span>
          <select name="purpose" autoComplete="off" disabled={busy} value={purpose} onChange={(e) => setPurpose(e.target.value as AccessPurpose)} className="mt-1 min-h-14 w-full rounded-[10px] border border-line bg-bg px-3 text-ink focus-visible:ring-2 focus-visible:ring-accent">
            {ROLE_PURPOSES[role].map((p) => <option key={p} value={p}>{PURPOSE_LABEL[p]}</option>)}
          </select>
        </label>

        <label className="block">
          <span className="label-caps inline-flex items-center gap-1"><KeyRound className="size-3" aria-hidden="true" />我的帳號密碼</span>
          <input ref={passwordRef} name="password" type="password" autoComplete="current-password" spellCheck={false} required disabled={busy} aria-invalid={err ? true : undefined} aria-describedby={err ? "login-error" : "password-help"} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="輸入你自己的密碼…" className="num mt-1 min-h-14 w-full rounded-[10px] border border-line bg-bg px-3 text-ink placeholder:text-ink-2 focus-visible:border-accent focus-visible:ring-2 focus-visible:ring-accent" />
          <span id="password-help" className="mt-1 block text-xs text-ink-2">登入不會新增或擴大授權。未獲授權時，請向本人申請。</span>
        </label>

        {err && <p id="login-error" role="alert" className="rounded-[10px] border border-danger bg-danger-fill p-3 text-sm text-danger-ink">{err}</p>}
        <Button type="submit" size="lg" className="w-full" disabled={busy} aria-busy={busy}>
          {busy ? "驗證中…" : <><Lock className="size-5" aria-hidden="true" />登入帳號</>}
        </Button>
      </form>
      <p className="break-words text-center text-xs text-ink-2">合成資料示範帳號的公開密碼：<span className="num" translate="no">demo-{who}-2026!</span>。僅供測試，正式帳號應使用各自設定的密碼。</p>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<p className="text-ink-2">Loading…</p>}>
      <LoginInner />
    </Suspense>
  );
}
