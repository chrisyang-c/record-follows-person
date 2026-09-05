import type { Direction, Document, IncidentKind, LifeEventType, RouteDecision, Shift } from "@schema";

/** interrupt 節點名 → 護理師看得懂的待辦名稱（節點名以 docs/*.mermaid 為準） */
export const TYPE_LABEL: Record<string, string> = {
  nurse_onsite_assessment: "紅燈：現場評估",
  nurse_review: "ISBAR 草稿待審核",
  nurse_route_choice: "待決定路徑",
  nurse_approve_notification: "家屬通知待核准",
  nurse_10s_confirm: "每班 10 秒確認",
  head_nurse_edit_list: "巡診名單待護理長",
  doctor_round: "等待輸入醫囑",
  nurse_confirm_baseline: "基線更新待確認",
};

export const typeLabel = (t: string | null | undefined) => (t ? (TYPE_LABEL[t] ?? t) : "");

export const DIRECTION_LABEL: Record<Direction, string> = { up: "上升", down: "下降", same: "相同", unknown: "不明" };

export const INCIDENT_LABEL: Record<IncidentKind | "acute", string> = {
  fall: "跌倒",
  medication_issue: "拒藥／吐藥",
  choking: "嗆咳",
  behavior: "攻擊／遊走",
  acute: "急症",
};

export const LIFE_EVENT_LABEL: Record<LifeEventType, string> = {
  condition: "確診",
  hospitalization: "住院",
  surgery: "手術",
  fall: "跌倒",
  other: "其他",
};

export const DOC_TYPE_LABEL: Record<Document["doc_type"], string> = {
  round_page: "RoundPage 熟悉頁",
  handoff_page: "後送頁",
  visit_page: "陪診頁",
  incident_file: "事件資訊包",
  caregiver_notes: "照護者注意事項",
};

export const ROUTE_LABEL: Record<RouteDecision, string> = {
  contact_contract_hospital: "聯絡特約醫療機構",
  home_acute_mode_b: "在宅急症模式 B",
  accompany_visit: "安排陪同就醫",
  observe: "轉為觀察",
  escalate_119: "119 後送",
};

export const SHIFT_LABEL: Record<Shift, string> = { day: "白班", evening: "小夜", night: "大夜" };
