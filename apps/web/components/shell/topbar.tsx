"use client";

import { Activity, CloudSun, Droplets, Thermometer } from "lucide-react";
import Link from "next/link";
import { ROLE_HOME, ROLE_LABEL, type Identity } from "@/lib/role";
import { usePatientTitle } from "@/lib/patient-title";

/** 假資料：地點·天氣（規格 §3.1 允許假資料；不放任何健康數字） */
const WEATHER = { place: "台北 · 大安區", sky: "多雲短暫雨", temp: "24°C", humidity: "78%" };

/**
 * 頂欄 64px（桌機）／56px（手機）：品牌 ｜ 地點·天氣 ｜ 同步燈 ｜ 本人頭像（身份）。
 * 同步燈是全站兩個允許發光的元素之一（另一個是 01 熱點）。
 */
export function TopBar({ identity }: { identity: Identity | null }) {
  const patient = usePatientTitle();
  return (
    <header className="no-print sticky top-0 z-30 border-b border-line bg-bg/95 backdrop-blur">
      <div className="flex h-14 items-center gap-3 px-4 lg:h-16 lg:px-6">
        <Link href="/twin" className="flex min-h-11 items-center gap-3 rounded-lg px-1 hover:bg-surface" aria-label="OMNI-TWIN 首頁">
          <span className="inline-flex size-9 items-center justify-center rounded-full border border-accent/60 text-accent lg:size-10">
            <Activity className="size-5" aria-hidden="true" />
          </span>
          <span className="leading-tight">
            <span className="block text-base font-semibold tracking-[0.18em] text-ink" translate="no">OMNI·TWIN</span>
            <span className="hidden text-[11px] tracking-[0.12em] text-ink-2 lg:block">超個體動態生命操作系統</span>
          </span>
        </Link>
        <div className="mx-auto hidden items-center gap-4 rounded-full border border-line bg-surface px-4 py-1.5 text-sm lg:flex" aria-label="地點與天氣（示意資料）">
          <span className="inline-flex items-center gap-2"><CloudSun className="size-4 text-accent" aria-hidden="true" /><span>{WEATHER.place}<span className="ml-2 text-ink-2">{WEATHER.sky}</span></span></span>
          <span className="h-4 w-px bg-line" aria-hidden="true" />
          <span className="inline-flex items-center gap-1"><Thermometer className="size-4 text-ink-2" aria-hidden="true" /><span className="num">{WEATHER.temp}</span></span>
          <span className="inline-flex items-center gap-1"><Droplets className="size-4 text-accent-2" aria-hidden="true" /><span>濕度 <span className="num">{WEATHER.humidity}</span></span></span>
        </div>
        <span className="ml-auto hidden items-center gap-2 rounded-full border border-accent/40 px-3 py-1 text-sm text-accent sm:inline-flex" aria-live="off">
          <span className="glow size-2 rounded-full bg-accent" aria-hidden="true" />
          孿生同步中
        </span>
        {identity ? (
          <Link href={ROLE_HOME[identity.role]} className="flex min-h-11 items-center gap-2 rounded-lg px-1 hover:bg-surface" aria-label={`${ROLE_LABEL[identity.role]} ${identity.name}，回自己的艙`}>
            <span className="hidden text-right leading-tight sm:block">
              <span className="block text-sm font-medium">{identity.name}</span>
              <span className="block text-xs text-ink-2">{ROLE_LABEL[identity.role]}{patient ? ` · ${patient}` : ""}</span>
            </span>
            <span className="inline-flex size-9 items-center justify-center rounded-full border border-line bg-surface-2 text-sm font-medium" aria-hidden="true">{identity.name.slice(0, 1)}</span>
          </Link>
        ) : (
          <Link href="/" className="inline-flex min-h-11 items-center rounded-lg px-2 text-sm text-ink hover:bg-surface">選擇身份</Link>
        )}
      </div>
    </header>
  );
}
