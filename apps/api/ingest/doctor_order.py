"""Channel 2 — doctor's order (typed by the nurse) → OrderItems + caregiver instructions."""

from __future__ import annotations

import re

from record_schema import Dimension, OrderItem

_CATEGORY = [
    ("medication", re.compile(r"mg|藥|錠|膠囊|停用|改為|加開|新藥|每日.*次|睡前|飯後|飯前")),
    ("referral", re.compile(r"轉診|回診|門診|抽血|檢查|X光|照會")),
    ("diet", re.compile(r"飲食|餐|喝水|飲水|營養|軟質|流質|水分")),
    ("activity", re.compile(r"活動|復健|走|下床|翻身|拍痰|運動")),
    ("observation", re.compile(r"觀察|記錄|量|監測|注意|追蹤|體重|體溫|血壓")),
]

_TARGET: list[tuple[Dimension, re.Pattern[str]]] = [
    ("intake", re.compile(r"飲食|餐|喝水|飲水|營養|體重|吃")),
    ("elimination", re.compile(r"排便|尿|便秘|軟便")),
    ("function", re.compile(r"活動|復健|走|下床|轉位")),
    ("cognition", re.compile(r"意識|認知|情緒|躁動|睡前.*鎮靜|混亂")),
    ("sleep", re.compile(r"睡眠|夜間|失眠")),
    ("skin", re.compile(r"皮膚|傷口|壓瘡|翻身|敷料")),
    ("pain", re.compile(r"疼痛|止痛|痛")),
    ("vitals", re.compile(r"血壓|體溫|心跳|血氧|咳|痰|喘|發燒")),
]


def _category(text: str) -> str:
    for cat, pat in _CATEGORY:
        if pat.search(text):
            return cat
    return "other"


def _target(text: str) -> Dimension | None:
    for dim, pat in _TARGET:
        if pat.search(text):
            return dim
    return None


def _instruction(text: str, cat: str, dim: Dimension | None) -> str | None:
    """Turn an order line into one caregiver-facing sentence (zh; translated downstream)."""
    m = re.search(
        r"(?:新藥|加開|開立)\s*(?P<name>[A-Za-z][A-Za-z0-9\-]*)\s*(?P<dose>[\d.]+\s*mg)?[，,]?\s*(?P<sched>每日\S+|睡前|早餐後|早晚各?一次|一天\S+次)?",
        text,
    )
    if cat == "medication" and m:
        sched = m.group("sched") or "依護理師指示"
        sched_zh = {"睡前": "睡前一次", "早餐後": "早餐後一次", "早晚各一次": "每天早晚各一次"}.get(
            sched, sched
        )
        return f"新藥 {m.group('name')}，{sched_zh}，吃完後看有沒有頭暈或想吐"
    if dim == "intake" and re.search(r"體重", text):
        return "每天量體重一次，早餐前"
    if dim == "intake" and re.search(r"喝水|飲水|水分", text):
        cups = re.search(r"(\d+)\s*杯", text)
        return f"喝水目標每天 {cups.group(1) if cups else 6} 杯，記錄杯數"
    if dim == "intake":
        return "每餐記錄吃了幾分（例：半碗）"
    if dim == "sleep":
        return "夜間醒來時記錄時間與原因"
    if dim == "skin":
        site = re.search(r"(尾椎|腳跟|臀部|薦骨|腳踝)", text)
        return f"每班翻身檢查{site.group(1) if site else '尾椎'}皮膚，發紅或破皮馬上告訴護理師"
    if dim == "function":
        return "每天陪走廊走一趟，需要扶就扶"
    if dim == "pain":
        return "疼痛時記錄部位與時間"
    if dim == "elimination":
        return "如果整天沒尿，馬上告訴護理師"
    if dim == "cognition":
        return "如果叫不醒或講話怪怪的，馬上告訴護理師"
    return None


def parse_order(raw_text: str) -> list[OrderItem]:
    items: list[OrderItem] = []
    for line in re.split(r"[\n;；]|(?<=。)", raw_text):
        line = line.strip(" 。\t")
        if not line:
            continue
        cat = _category(line)
        dim = _target(line)
        items.append(
            OrderItem(
                text=line,
                category=cat,  # type: ignore[arg-type]
                target_dimension=dim,
                caregiver_instruction=_instruction(line, cat, dim),
            )
        )
    return items


def caregiver_notes_zh(items: list[OrderItem], max_items: int = 3) -> list[str]:
    """本月注意三件事 — the first three concrete instructions, deduplicated."""
    seen: list[str] = []
    for it in items:
        if it.caregiver_instruction and it.caregiver_instruction not in seen:
            seen.append(it.caregiver_instruction)
    return seen[:max_items]
