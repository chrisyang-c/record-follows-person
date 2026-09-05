"use client";

import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { Suspense } from "react";
import { AvatarModel } from "@/components/twin/avatar-model";
import type { Mood } from "@/lib/api";

export interface AvatarState { sleepHours: number | null; weightKg: number | null; mood: Mood }

/**
 * 我的分身（01）：現況分身；開沙盤時左右並排「現況｜沙盤」。
 * 沙盤只是「如果睡多一點、體重不同會怎樣」的示意，不是預測或診斷（面板上標明）。
 */
export function AvatarView({ now, sandbox, baseWeightKg, speaking }: { now: AvatarState; sandbox?: AvatarState | null; baseWeightKg: number | null; speaking: boolean }) {
  return (
    <div className="relative h-[420px] w-full overflow-hidden rounded-[12px] border border-line bg-surface-2 lg:h-[520px]">
      <Canvas camera={{ position: [0, 1.25, 2.6], fov: 44 }} dpr={[1, 1.5]}>
        <ambientLight intensity={0.8} />
        <directionalLight position={[-2, 3, 2]} intensity={1.3} />
        <directionalLight position={[2, 3, 2]} intensity={1.1} color="#dff7f3" />
        <OrbitControls target={[0, 1.05, 0]} maxPolarAngle={Math.PI / 2} enablePan={false} minDistance={1.6} maxDistance={4} />
        <Suspense fallback={null}>
          {sandbox ? (
            <>
              <AvatarModel position={[-0.55, 0, 0]} sleepHours={now.sleepHours} weightKg={now.weightKg} baseWeightKg={baseWeightKg} mood={now.mood} speaking={speaking} />
              <AvatarModel position={[0.55, 0, 0]} sleepHours={sandbox.sleepHours} weightKg={sandbox.weightKg} baseWeightKg={baseWeightKg} mood={sandbox.mood} tint="#a78bfa" />
            </>
          ) : (
            <AvatarModel sleepHours={now.sleepHours} weightKg={now.weightKg} baseWeightKg={baseWeightKg} mood={now.mood} speaking={speaking} />
          )}
        </Suspense>
      </Canvas>
      {sandbox && (
        <>
          <span className="absolute bottom-2 left-[25%] -translate-x-1/2 rounded-full border border-accent/60 bg-bg/85 px-2 py-0.5 text-[11px] text-accent">現況</span>
          <span className="absolute right-[25%] bottom-2 translate-x-1/2 rounded-full border border-accent-2/60 bg-bg/85 px-2 py-0.5 text-[11px] text-accent-2">沙盤</span>
        </>
      )}
      <p className="absolute top-2 right-2 rounded-full bg-bg/80 px-2 py-0.5 text-[11px] text-ink-2">拖曳可旋轉</p>
    </div>
  );
}
