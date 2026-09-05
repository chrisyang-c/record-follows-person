"use client";
/* eslint-disable react-hooks/immutability -- three.js 場景是命令式物件：複製一份場景、直接改 morph 與材質 */

/**
 * 3D 分身（01 我的分身）。模型：public/models/my_avatar.glb（見同目錄 LICENSE.txt）。
 * 行為規則參考 health-ref（frontend/components/Avatar.js，作者 Jennifer，2026-09-05）的想法，
 * 以 TypeScript 重寫並改接本專案的資料：
 *   - 睡眠 < 6 小時 → 膚色暗沉；體重相對基準 → 身材縮放（有 body_fat blendshape 就用它）
 *   - 心情：same（微笑）／changed（疲倦）／attention（擔心），對應 ARKit blendshape
 *   - 說話中 → 嘴巴隨機開合（嘴型同步）
 * 這是 wellness 區的視覺，不是任何臨床判斷（CLAUDE.md §1.9）。
 */
import { useAnimations, useGLTF } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { clone as skeletonClone } from "three/examples/jsm/utils/SkeletonUtils.js";
import type { Mood } from "@/lib/api";

export const AVATAR_URL = "/models/my_avatar.glb";

type Morphable = THREE.Mesh & { morphTargetDictionary?: Record<string, number>; morphTargetInfluences?: number[] };

function setMorph(mesh: Morphable | undefined, name: string, value: number) {
  if (!mesh?.morphTargetDictionary || !mesh.morphTargetInfluences) return;
  const idx = mesh.morphTargetDictionary[name];
  if (idx !== undefined) mesh.morphTargetInfluences[idx] = value;
}

const RESET = ["mouthSmileLeft", "mouthSmileRight", "smile", "mouthFrownLeft", "mouthFrownRight", "sad", "browDownLeft", "browDownRight", "browInnerUp", "eyeSquintLeft", "eyeSquintRight"];

export function AvatarModel({
  position = [0, 0, 0],
  sleepHours = 7,
  weightKg = 60,
  baseWeightKg = 60,
  mood = "same",
  speaking = false,
  tint,
}: {
  position?: [number, number, number];
  sleepHours?: number | null;
  weightKg?: number | null;
  baseWeightKg?: number | null;
  mood?: Mood;
  speaking?: boolean;
  /** 沙盤模式的第二個分身：加一盞紫色點光 */
  tint?: string;
}) {
  const group = useRef<THREE.Group>(null);
  const { scene, nodes, materials, animations } = useGLTF(AVATAR_URL) as unknown as {
    scene: THREE.Group;
    nodes: Record<string, Morphable>;
    materials: Record<string, THREE.MeshStandardMaterial>;
    animations: THREE.AnimationClip[];
  };
  // each instance gets its own clone (and its own head/body materials) so 現況／沙盤 do not share morphs
  const cloned = useMemo(() => {
    const c = skeletonClone(scene) as THREE.Group; // SkinnedMesh 需要連骨架一起複製，兩個分身才能各站各的位置
    c.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.isMesh && (m.name === "Wolf3D_Head" || m.name === "Wolf3D_Body") && m.material) {
        m.material = (m.material as THREE.Material).clone();
      }
    });
    return c;
  }, [scene]);
  const { actions } = useAnimations(animations, group);
  const head = useMemo(() => () => cloned.getObjectByName("Wolf3D_Head") as Morphable | undefined, [cloned]);
  const body = useMemo(() => () => cloned.getObjectByName("Wolf3D_Body") as Morphable | undefined, [cloned]);

  useEffect(() => {
    const sleep = sleepHours ?? 7;
    // 1. Idle 姿態（若模型帶動畫）
    const names = Object.keys(actions);
    if (names.length) {
      const tired = actions["Idle_Tired"] ?? actions[names[0]];
      const healthy = actions["Idle_Healthy"] ?? actions[names[0]];
      if (sleep < 6 || mood !== "same") {
        healthy?.fadeOut(0.4);
        tired?.reset().fadeIn(0.4).play();
      } else {
        tired?.fadeOut(0.4);
        healthy?.reset().fadeIn(0.4).play();
      }
    }
    // 2. 膚色：睡眠不足偏暗
    const skin = cloned.getObjectByName("Wolf3D_Head") as THREE.Mesh | undefined;
    const mat = (skin?.material as THREE.MeshStandardMaterial | undefined) ?? materials?.Wolf3D_Skin;
    if (mat && "color" in mat) {
      mat.color = new THREE.Color(sleep < 6 ? "#cfc2a7" : "#ffffff");
      mat.needsUpdate = true;
    }
    // 3. 表情
    const h = head();
    RESET.forEach((n) => setMorph(h, n, 0));
    if (mood === "same") {
      setMorph(h, "mouthSmileLeft", 0.7); setMorph(h, "mouthSmileRight", 0.7); setMorph(h, "eyeSquintLeft", 0.25); setMorph(h, "eyeSquintRight", 0.25); setMorph(h, "smile", 0.7);
    } else if (mood === "changed") {
      setMorph(h, "browDownLeft", 0.55); setMorph(h, "browDownRight", 0.55); setMorph(h, "mouthFrownLeft", 0.35); setMorph(h, "mouthFrownRight", 0.35);
    } else {
      setMorph(h, "mouthFrownLeft", 0.8); setMorph(h, "mouthFrownRight", 0.8); setMorph(h, "browInnerUp", 0.7); setMorph(h, "sad", 0.7);
    }
    // 4. 身材：相對基準體重
    const w = weightKg ?? baseWeightKg ?? 60;
    const base = baseWeightKg ?? 60;
    const b = body();
    if (b?.morphTargetDictionary?.body_fat !== undefined && b.morphTargetInfluences) {
      b.morphTargetInfluences[b.morphTargetDictionary.body_fat] = Math.max(0, Math.min((w - base) / 25, 1));
    } else if (group.current) {
      const s = 1 + Math.max(-0.12, Math.min((w - base) / 60, 0.35));
      group.current.scale.set(s, 1, s);
    }
  }, [sleepHours, weightKg, baseWeightKg, mood, actions, materials, nodes, cloned, head, body]);

  // 5. 嘴型同步
  useFrame(() => {
    const h = head();
    if (!h?.morphTargetDictionary || !h.morphTargetInfluences) return;
    const idx = h.morphTargetDictionary.mouthOpen;
    if (idx !== undefined) h.morphTargetInfluences[idx] = speaking ? Math.random() * 0.6 + 0.15 : 0;
  });

  return (
    <group ref={group} position={position} dispose={null}>
      {tint && <pointLight position={[0, 1.6, 0.9]} color={tint} intensity={2.2} />}
      <primitive object={cloned} />
    </group>
  );
}

useGLTF.preload(AVATAR_URL);
