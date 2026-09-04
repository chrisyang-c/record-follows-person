"use client";

import type * as React from "react";
import type { ISBAR } from "@schema";
import { Card } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/field";

export interface OnsiteForm {
  temp_c: string;
  sbp: string;
  dbp: string;
  hr: string;
  rr: string;
  spo2: string;
  consciousness: string;
  wound: string;
  notes: string;
}

export const emptyOnsite: OnsiteForm = { temp_c: "", sbp: "", dbp: "", hr: "", rr: "", spo2: "", consciousness: "", wound: "", notes: "" };

export function onsitePayload(f: OnsiteForm) {
  const n = (s: string) => (s.trim() === "" ? null : Number(s));
  return {
    vitals: { temp_c: n(f.temp_c), sbp: n(f.sbp), dbp: n(f.dbp), hr: n(f.hr), rr: n(f.rr), spo2: n(f.spo2) },
    consciousness: f.consciousness,
    wound: f.wound || null,
    notes: f.notes || null,
  };
}

function VitalField({ id, label, unit, step, value, onChange }: { id: string; label: string; unit: string; step?: string; value: string; onChange: (v: string) => void }) {
  return (
    <div className="min-w-0">
      <Label htmlFor={id}>{label} <span className="text-ink-2">{unit}</span></Label>
      <Input id={id} name={id} type="number" inputMode="decimal" step={step ?? "1"} value={value} onChange={(e) => onChange(e.target.value)} className="num" autoComplete="off" />
    </div>
  );
}

const VITALS: { k: keyof OnsiteForm; label: string; unit: string; step?: string }[] = [
  { k: "temp_c", label: "體溫", unit: "°C", step: "0.1" },
  { k: "sbp", label: "收縮壓", unit: "mmHg" },
  { k: "dbp", label: "舒張壓", unit: "mmHg" },
  { k: "hr", label: "心率", unit: "/分" },
  { k: "rr", label: "呼吸", unit: "/分" },
  { k: "spo2", label: "SpO₂", unit: "%" },
];

export function OnsiteFields({ value, onChange, consciousnessRef }: { value: OnsiteForm; onChange: (v: OnsiteForm) => void; consciousnessRef?: React.Ref<HTMLInputElement> }) {
  const set = (k: keyof OnsiteForm) => (v: string) => onChange({ ...value, [k]: v });
  const setE = (k: keyof OnsiteForm) => (e: React.ChangeEvent<HTMLInputElement>) => onChange({ ...value, [k]: e.target.value });
  return (
    <fieldset className="rounded-[12px] border border-line p-3">
      <legend className="px-1 text-sm font-medium">現場評估（護理師）</legend>
      <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
        {VITALS.map((f) => (
          <VitalField key={f.k} id={`v-${f.k}`} label={f.label} unit={f.unit} step={f.step} value={value[f.k]} onChange={set(f.k)} />
        ))}
      </div>
      <div className="mt-2 grid gap-2 sm:grid-cols-3">
        <div>
          <Label htmlFor="consciousness">意識</Label>
          <Input ref={consciousnessRef} id="consciousness" name="consciousness" value={value.consciousness} onChange={setE("consciousness")} placeholder="可喚醒，對答清楚…" autoComplete="off" />
        </div>
        <div>
          <Label htmlFor="wound">傷口</Label>
          <Input id="wound" name="wound" value={value.wound} onChange={setE("wound")} placeholder="無／右額血腫 2 cm…" autoComplete="off" />
        </div>
        <div>
          <Label htmlFor="notes">備註</Label>
          <Input id="notes" name="notes" value={value.notes} onChange={setE("notes")} placeholder="其他現場觀察…" autoComplete="off" />
        </div>
      </div>
    </fieldset>
  );
}

export function IsbarView({ isbar, headingLevel = 3 }: { isbar: ISBAR; headingLevel?: 3 | 4 }) {
  const ai = isbar.status !== "approved";
  const h = headingLevel;
  return (
    <div className="space-y-2 text-sm">
      <Card headingLevel={h} variant={ai ? "ai" : "confirmed"} title="I · 身分">
        <p>{isbar.identity}</p>
      </Card>
      <Card headingLevel={h} variant={ai ? "ai" : "confirmed"} title="S · 現況">
        <p>{isbar.situation}</p>
      </Card>
      <Card headingLevel={h} variant={ai ? "ai" : "confirmed"} title="B · 背景">
        <p>{isbar.background}</p>
      </Card>
      <Card headingLevel={h} variant="ai" title="A（AI）· 與基線比的變化">
        <p>{isbar.ai_change_vs_baseline}</p>
      </Card>
      <Card headingLevel={h} variant="ai" title="R（AI）· 請確認事項">
        <ul className="list-disc pl-5">
          {isbar.ai_questions_for_nurse.map((q, i) => (
            <li key={i}>{q}</li>
          ))}
        </ul>
      </Card>
      <Card headingLevel={h} variant={isbar.nurse_assessment ? "confirmed" : "default"} title="A · 護理師評估">
        <p className={isbar.nurse_assessment ? "" : "text-ink-2"}>{isbar.nurse_assessment ?? "（待護理師填寫）"}</p>
      </Card>
      <Card headingLevel={h} variant={isbar.nurse_recommendation ? "confirmed" : "default"} title="R · 護理師建議">
        <p className={isbar.nurse_recommendation ? "" : "text-ink-2"}>{isbar.nurse_recommendation ?? "（待護理師填寫）"}</p>
      </Card>
    </div>
  );
}

export function IsbarEditor({
  isbar,
  s,
  b,
  a,
  r,
  onS,
  onB,
  onA,
  onR,
  aRef,
  rRef,
}: {
  isbar: ISBAR | null;
  s: string;
  b: string;
  a: string;
  r: string;
  onS: (v: string) => void;
  onB: (v: string) => void;
  onA: (v: string) => void;
  onR: (v: string) => void;
  aRef?: React.Ref<HTMLTextAreaElement>;
  rRef?: React.Ref<HTMLTextAreaElement>;
}) {
  return (
    <div className="space-y-3">
      {isbar && (
        <Card variant="ai" title="I · 身分">
          <p className="text-sm">{isbar.identity}</p>
        </Card>
      )}
      <Card variant="ai" title="S · 現況（AI 預填，可改）">
        <Textarea id="s" name="situation" aria-label="S 現況" value={s} onChange={(e) => onS(e.target.value)} className="min-h-20 text-sm" autoComplete="off" />
      </Card>
      <Card variant="ai" title="B · 背景（AI 預填，可改）">
        <Textarea id="b" name="background" aria-label="B 背景" value={b} onChange={(e) => onB(e.target.value)} className="min-h-20 text-sm" autoComplete="off" />
      </Card>
      {isbar && (
        <>
          <Card variant="ai" title="A（AI）· 只寫與基線比的變化">
            <p className="text-sm">{isbar.ai_change_vs_baseline}</p>
          </Card>
          <Card variant="ai" title="R（AI）· 只提問，請確認">
            <ul className="list-disc pl-5 text-sm">
              {isbar.ai_questions_for_nurse.map((q, i) => (
                <li key={i}>{q}</li>
              ))}
            </ul>
          </Card>
        </>
      )}
      <Card title="A · 護理師評估（必填，由您撰寫）">
        <Textarea ref={aRef} id="a" name="nurse_assessment" aria-label="A 護理師評估" value={a} onChange={(e) => onA(e.target.value)} placeholder="現場評估後的專業判斷…" className="min-h-24" autoComplete="off" />
      </Card>
      <Card title="R · 護理師建議（必填，由您撰寫）">
        <Textarea ref={rRef} id="r" name="nurse_recommendation" aria-label="R 護理師建議" value={r} onChange={(e) => onR(e.target.value)} placeholder="您的建議與下一步…" className="min-h-24" autoComplete="off" />
      </Card>
    </div>
  );
}
