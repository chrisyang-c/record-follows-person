"use client";

import { Activity, KeyRound, Lock } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
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

/**
 * 登入（以病人為核心）：選角色 → 選身份 → 選住民 → 輸入「病人的密碼」。
 * 本人用自己的密碼；家屬、照護者、護理師、醫師都要病人密碼才進 Care Circle（API POST /login，密碼只存 hash）。
 * cookie 只存「我是誰」；能看什麼仍由 Care Circle 決定。
 */
function LoginInner() {
  const router = useRouter();
  const sp = useSearchParams();
  const next = sp.get("next") ?? "";
  const [role, setRole] = useState<Role>("patient");
  const ids = useMemo(() => Object.entries(IDENTITIES).filter(([, v]) => v.role === role), [role]);
  const [who, setWho] = useState<string>("P001");
  const [pid, setPid] = useState<string>("P001");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const pickRole = (r: Role) => {
    setRole(r);
    const first = Object.entries(IDENTITIES).find(([, v]) => v.role === r)?.[0] ?? "";
    setWho(first);
    setPid(IDENTITIES[first]?.patient_id ?? "P001");
    setErr(null);
  };
  const identity = IDENTITIES[who];
  const targetPid = identity?.patient_id ?? pid;
  const targetName = IDENTITIES[targetPid]?.name ?? targetPid;
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setErr(null);
    try {
      await api("/login", { method: "POST", json: { who, patient_id: targetPid, code } });
      router.push(`/role?set=${who}${next ? `&next=${encodeURIComponent(next)}` : ""}`);
    } catch (e2) {
      setErr((e2 as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="mx-auto w-full max-w-[420px] space-y-5 py-4">
      <header className="text-center">
        <span className="glow mx-auto inline-flex size-14 items-center justify-center rounded-full border border-accent/60 text-accent"><Activity className="size-7" aria-hidden="true" /></span>
        <p className="label-caps mt-3">OMNI-TWIN · Sign in</p>
        <h1 className="text-2xl font-medium">登入</h1>
        <p className="mt-1 text-sm text-ink-2">紀錄屬於本人。本人用自己的密碼；其他人要有病人的密碼才看得到。</p>
      </header>

      <form onSubmit={submit} className="space-y-4 rounded-[12px] border border-line bg-surface p-5">
        <fieldset>
          <legend className="label-caps mb-2">我是</legend>
          <ul className="grid grid-cols-2 gap-2">
            {ROLES.map((r) => (
              <li key={r}>
                <button type="button" aria-pressed={role === r} onClick={() => pickRole(r)} className={cn("flex min-h-12 w-full items-center justify-center rounded-[10px] border px-3 text-base focus-visible:ring-2 focus-visible:ring-accent", role === r ? "border-accent bg-surface-2 text-ink" : "border-line text-ink-2 hover:text-ink")}>
                  {ROLE_LABEL[r]}
                </button>
              </li>
            ))}
          </ul>
          <p className="mt-1 text-xs text-ink-2">{HINT[role]}</p>
        </fieldset>

        <label className="block">
          <span className="label-caps">身份</span>
          <select name="who" value={who} onChange={(e) => { setWho(e.target.value); const p = IDENTITIES[e.target.value]?.patient_id; if (p) setPid(p); }} className="mt-1 min-h-12 w-full rounded-[10px] border border-line bg-bg px-3 text-ink focus-visible:ring-2 focus-visible:ring-accent">
            {ids.map(([k, v]) => (
              <option key={k} value={k}>{v.name}</option>
            ))}
          </select>
        </label>

        {!identity?.patient_id && (
          <label className="block">
            <span className="label-caps">要看的住民</span>
            <select name="patient_id" value={pid} onChange={(e) => setPid(e.target.value)} className="mt-1 min-h-12 w-full rounded-[10px] border border-line bg-bg px-3 text-ink focus-visible:ring-2 focus-visible:ring-accent">
              {PATIENTS.map((p) => (
                <option key={p} value={p}>{IDENTITIES[p].name} · {p}</option>
              ))}
            </select>
          </label>
        )}

        <label className="block">
          <span className="label-caps inline-flex items-center gap-1"><KeyRound className="size-3" aria-hidden="true" />{role === "patient" ? "我的密碼" : `${targetName}的密碼`}</span>
          <input name="code" type="password" inputMode="numeric" autoComplete="off" value={code} onChange={(e) => setCode(e.target.value)} placeholder="示範：出生年（4 碼）…" className="num mt-1 min-h-12 w-full rounded-[10px] border border-line bg-bg px-3 text-ink placeholder:text-ink-2 focus-visible:border-accent focus-visible:ring-2 focus-visible:ring-accent" />
          <span className="mt-1 block text-xs text-ink-2">{role === "patient" ? "只有本人知道；忘記請找家屬重設。" : "由本人或家屬告知。通過後你會以這個角色的預設範圍與目的進入 Care Circle（一天），每次查看都記在「誰看過我的紀錄」。"}</span>
        </label>

        {err && <p role="alert" className="rounded-[10px] border border-danger bg-danger-fill p-3 text-sm text-danger-ink">{err}</p>}
        <Button type="submit" size="lg" className="w-full" disabled={busy || !code}>
          {busy ? "驗證中…" : <><Lock className="size-5" aria-hidden="true" />進入</>}
        </Button>
      </form>
      <p className="text-center text-xs text-ink-2">示範密碼＝住民出生年：王伯 1940 · 陳奶奶 1936 · 李阿公 1943。密碼只以 hash 儲存。</p>
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
