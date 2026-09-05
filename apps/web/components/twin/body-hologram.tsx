"use client";

import { useEffect, useRef, useState } from "react";
import type { Dimension } from "@schema";
import { cn } from "@/lib/utils";

/**
 * 全像人體（01）：EMBL-EBI anatomogram 的向量解剖圖（public/anatomy/homo_sapiens.male.svg，Apache-2.0），
 * 76 個器官以 UBERON id 分群。這裡把輪廓與器官點成青色 X 光樣，選中維度的器官改紫色；
 * 熱點位置由器官的實際外框算出，不寫死座標。發光只在熱點（規格 §1.6）。
 */
export const ORGANS: Record<Dimension, { ids: string[]; short: string; anchor?: "temple" | "hip" | "thigh" | "arm" }> = {
  cognition: { ids: ["UBERON_0000955", "UBERON_0002037"], short: "認知" },
  sleep: { ids: ["UBERON_0000955"], short: "睡眠", anchor: "temple" },
  vitals: { ids: ["UBERON_0000948", "UBERON_0002048"], short: "心肺" },
  intake: { ids: ["UBERON_0000945", "UBERON_0001043", "UBERON_0002107"], short: "進食" },
  elimination: { ids: ["UBERON_0001255", "UBERON_0001155", "UBERON_0002113", "UBERON_0002108"], short: "排泄" },
  function: { ids: ["UBERON_0001134"], short: "活動", anchor: "thigh" },
  skin: { ids: ["UBERON_0000014"], short: "皮膚", anchor: "arm" },
  pain: { ids: [], short: "疼痛", anchor: "hip" },
};
const COLOR = { same: "var(--accent)", changed: "var(--accent-2)", red: "var(--danger)", idle: "var(--ink-2)" } as const;

type Pt = { x: number; y: number };

export function BodyHologram({ states, selected, onSelect, idle = false }: { states: Record<string, "same" | "changed" | "red">; selected: Dimension; onSelect: (d: Dimension) => void; idle?: boolean }) {
  const host = useRef<HTMLDivElement | null>(null);
  const [svg, setSvg] = useState<string | null>(null);
  const [pts, setPts] = useState<Partial<Record<Dimension, Pt>>>({});

  useEffect(() => {
    let alive = true;
    fetch("/anatomy/homo_sapiens.male.svg")
      .then((r) => r.text())
      .then((t) => alive && setSvg(t.replace(/<\?xml[^>]*>/, "")))
      .catch(() => alive && setSvg(""));
    return () => {
      alive = false;
    };
  }, []);

  // organ groups → percent positions for the hotspots; selected organs get the "on" class
  useEffect(() => {
    const root = host.current?.querySelector("svg");
    if (!root) return;
    root.removeAttribute("width");
    root.removeAttribute("height");
    root.setAttribute("preserveAspectRatio", "xMidYMid meet");
    const box = root.getBoundingClientRect();
    const next: Partial<Record<Dimension, Pt>> = {};
    root.querySelectorAll(".organ-on, .organ-state-changed, .organ-state-red").forEach((el) => el.classList.remove("organ-on", "organ-state-changed", "organ-state-red"));
    (Object.keys(ORGANS) as Dimension[]).forEach((d) => {
      const spec = ORGANS[d];
      const els = spec.ids.map((id) => root.querySelector<SVGGraphicsElement>(`#${id}`)).filter(Boolean) as SVGGraphicsElement[];
      els.forEach((el) => {
        if (d === selected) el.classList.add("organ-on");
        const st = states[d];
        if (!idle && (st === "changed" || st === "red")) el.classList.add(`organ-state-${st}`);
      });
      const first = els[0];
      if (first && box.width) {
        const r = first.getBoundingClientRect();
        let x = ((r.left + r.width / 2 - box.left) / box.width) * 100;
        let y = ((r.top + r.height / 2 - box.top) / box.height) * 100;
        if (spec.anchor === "temple") { x += 9; y -= 2; }
        if (spec.anchor === "thigh") { x -= 6; y = 62; }
        if (spec.anchor === "arm") { x = 76; y = 30; }
        next[d] = { x, y };
      }
    });
    next.pain = { x: 25, y: 47 };
    if (!next.skin) next.skin = { x: 72, y: 32 };
    setPts(next);
  }, [svg, selected, states, idle]);

  return (
    <div className="holo relative mx-auto w-full max-w-[340px] lg:max-w-[360px]">
      <div className="holo-grid absolute inset-0 rounded-[12px]" aria-hidden="true" />
      <div ref={host} className="relative" dangerouslySetInnerHTML={{ __html: svg ?? "" }} aria-label="八維度全像人體（EMBL-EBI anatomogram）" role="group" />
      {svg === null && <p className="absolute inset-0 grid place-items-center text-sm text-ink-2">載入人體…</p>}
      {svg === "" && <p className="absolute inset-0 grid place-items-center text-sm text-danger-ink">人體圖載入失敗</p>}
      {(Object.keys(ORGANS) as Dimension[]).map((d) => {
        const p = pts[d];
        if (!p) return null;
        const st = idle ? "idle" : (states[d] ?? "same");
        const color = COLOR[st];
        const on = d === selected;
        return (
          <button
            key={d}
            type="button"
            aria-label={`${ORGANS[d].short}${on ? "（已選）" : ""}`}
            aria-pressed={on}
            onClick={() => onSelect(d)}
            style={{ left: `${p.x}%`, top: `${p.y}%`, color }}
            className={cn("absolute size-11 -translate-x-1/2 -translate-y-1/2 rounded-full focus-visible:ring-2 focus-visible:ring-accent", st === "changed" && "breathe")}
          >
            <span className={cn("absolute inset-2 rounded-full border-2 bg-surface/80", st !== "idle" && "glow")} style={{ borderColor: color, borderWidth: on ? 3 : 2 }} aria-hidden="true" />
            <span className="absolute inset-[15px] rounded-full" style={{ background: color }} aria-hidden="true" />
          </button>
        );
      })}
    </div>
  );
}
