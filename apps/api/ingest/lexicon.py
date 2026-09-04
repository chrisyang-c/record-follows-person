"""Deterministic caregiver-speech lexicon (mock extractor) for zh-TW / id / vi / en.

Used by MockLLM (default) and as the safety net for ChatModelLLM. It is intentionally
conservative: a dimension is only produced when a keyword literally appears in the text,
and raw_quote is always the clause that contained it — so hallucination is structurally
impossible; omissions are the failure mode we measure in eval/.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from record_schema import (
    DIMENSION_LABELS,
    DIMENSIONS,
    DimensionValue,
    FollowupQA,
    Lang,
    ObservationFlags,
    Provenance,
    StructuredObservation,
    Vitals,
)

# --- clause splitting --------------------------------------------------------------------

_CLAUSE_SPLIT = re.compile(
    r"[。！？!?；;，,、\n]|(?<=\S)\s+(?:dan|tapi|terus|lalu|và|nhưng|rồi|còn)\s+|然後|而且|但是|還有|不過"
)


def clauses(text: str) -> list[str]:
    parts = [p.strip(" \t.…") for p in _CLAUSE_SPLIT.split(text)]
    return [p for p in parts if p]


# --- dimension keywords (longest first inside each alternation) ---------------------------

_DIM_PATTERNS: dict[str, list[str]] = {
    "intake": [
        r"食慾|胃口|吃(?!藥)|喝水|喝|飯|碗|粥|牛奶|營養品|進食|飲水|吞|幾口|一口|兩口|三口",
        r"nafsu makan|makan|minum|susu|bubur|nasi|suap|menelan",
        r"ăn|uống|cháo|sữa|nuốt|muỗng|chén",
        r"\beat|\bate|drink|appetite|meal",
    ],
    "elimination": [
        r"大便|排便|便秘|拉肚子|腹瀉|尿|失禁|包尿布|尿布|排泄",
        r"\bBAB\b|\bBAK\b|kencing|pipis|buang air|mencret|diare|sembelit|popok|ngompol",
        r"đi ngoài|đi cầu|đại tiện|tiêu chảy|táo bón|đi tiểu|tiểu|tã|són",
        r"stool|urine|pee|diarrh|constipat|incontinen",
    ],
    "function": [
        r"走路|走|站|轉位|起床|扶|需要人|需要幫|幫忙|活動|無力|沒力|軟腳|坐不住|下床|輪椅",
        r"jalan|berdiri|dibantu|bantu|lemas|lemah|duduk|kursi roda|bangun dari",
        r"đi lại|đi bộ|đứng|đỡ|dìu|giúp|yếu|ngồi|xe lăn|xuống giường",
        r"walk|stand|transfer|assist|help|weak",
    ],
    "cognition": [
        r"混亂|胡言亂語|嗜睡|一直睡|叫不醒|叫不太醒|認不得|認不出|講話變少|不講話|不太講話|躁動|情緒|不理人|"
        r"反應(?:比較|變|很|有點)?慢|意識|不清楚|怪怪的|亂講|發呆|不太對|心情|哭|生氣|罵人|理人",
        r"bingung|ngantuk terus|mengantuk|susah dibangunkan|tidak sadar|tidak kenal|lupa|gelisah|"
        r"diam saja|tidak mau bicara|bicara(?:nya)?(?: agak| sedikit)? aneh|"
        r"ngomong(?:nya)?(?: agak| sedikit)? aneh|bengong|marah|"
        r"nangis|linglung|ngaco",
        r"lú lẫn|lẫn|buồn ngủ|ngủ gà|gọi không dậy|không tỉnh|lơ mơ|không nhận ra|ít nói|"
        r"không nói|kích động|bồn chồn|khóc|cáu|la hét|ngơ ngác|nói lung tung",
        r"confus|drows|sleepy|agitat|unrespons|recogni|quiet|mood",
    ],
    "sleep": [
        r"(?<!嗜)(?<!一直)睡(?!藥)|夜裡|晚上起來|半夜|日夜顛倒|失眠|(?<!不太)(?<!不)醒|白天一直睡",
        r"tidur|bangun malam|malam bangun|bangun tengah malam|terbangun|begadang|siang tidur",
        r"ngủ|thức giấc|thức đêm|dậy đêm|đêm dậy|ban đêm|mất ngủ|ngày ngủ",
        r"sleep|awake|night|insomnia",
    ],
    "skin": [
        r"皮膚|傷口|破皮|壓瘡|褥瘡|水腫|腫|紅紅的|發紅|瘀青|烏青|尾椎|屁股紅|腳腫|流湯|滲液",
        r"kulit|luka|lecet|merah|bengkak|memar|dekubitus|tumit|pantat merah|bernanah",
        r"\bda\b|vết thương|loét|trầy|đỏ|sưng|phù|bầm|mông đỏ|gót|chảy dịch",
        r"skin|wound|sore|swell|edema|redness|bruise",
    ],
    "pain": [
        r"痛|疼|喊痛|酸痛|不舒服",
        r"sakit|nyeri|ngilu|kesakitan",
        r"đau|nhức|kêu đau",
        r"pain|ache|hurt|sore",
    ],
    "vitals": [
        r"咳|痰|喘|呼吸|發燒|燙|體溫|血壓|心跳|脈搏|血氧|度|冒冷汗|冷汗|發抖|手腳冰",
        r"batuk|dahak|sesak|napas|nafas|demam|panas|suhu|tensi|tekanan darah|nadi|denyut|"
        r"oksigen|saturasi|derajat|menggigil|keringat dingin",
        r"\bho\b|đờm|khó thở|thở gấp|thở|sốt|nóng|nhiệt độ|huyết áp|mạch|nhịp tim|oxy|độ|"
        r"run|lạnh toát|mồ hôi lạnh",
        r"cough|phlegm|breath|fever|temperature|blood pressure|pulse|oxygen|spo2|chill",
    ],
}
_DIM_RE = {k: re.compile("|".join(v), re.IGNORECASE) for k, v in _DIM_PATTERNS.items()}

_DOWN = re.compile(
    r"少|減|沒|不|一半|半|降|變差|剩|只|kurang|sedikit|setengah|tidak|turun|cuma|hanya|"
    r"ít|giảm|nửa|không|kém|chỉ|less|half|not|barely",
    re.IGNORECASE,
)
_UP = re.compile(
    r"多|增|次|變多|更|一直|lebih|banyak|kali|terus|sering|nhiều|tăng|hơn|lần|liên tục|hay|"
    r"more|times|often",
    re.IGNORECASE,
)

# --- flags (observed facts for red_flags/rules.py) --------------------------------------

_FLAGS: dict[str, str] = {
    "consciousness_change": (
        r"意識不清|叫不醒|叫不太醒|沒反應|叫他都不理|眼神呆|"
        r"tidak sadar|susah dibangunkan|tidak ada respon|tidak merespon|"
        r"không tỉnh|gọi không dậy|lơ mơ|không phản ứng|unrespons|not respond"
    ),
    "new_confusion_or_drowsiness": (
        r"混亂|胡言亂語|亂講|嗜睡|一直睡|認不得|認不出|今天不認得|"
        r"bingung|ngantuk terus|mengantuk|tidak kenal|linglung|ngaco|"
        r"lú lẫn|buồn ngủ|ngủ gà|không nhận ra|nói lung tung|confus|drows"
    ),
    "breathing_difficulty": (
        r"喘|呼吸困難|呼吸很快|呼吸急|吸不到氣|"
        r"sesak|napas cepat|nafas cepat|susah napas|"
        r"khó thở|thở gấp|thở nhanh|short of breath|breathing hard"
    ),
    "chest_pain": (
        r"胸痛|胸口痛|胸口悶|心口痛|dada sakit|nyeri dada|dada sesak sakit|đau ngực|tức ngực|"
        r"chest pain"
    ),
    "fall_head_strike": (
        r"撞到頭|頭撞|頭去撞|頭部撞|頭有撞|撞頭|"
        r"kepala(?:nya)? (?:terbentur|kebentur|kena|terantuk)|kena kepala|"
        r"đập đầu|va đầu|đầu đập|hit (?:his|her|the) head|head hit"
    ),
    "cannot_get_up_after_fall": (
        r"起不來|站不起來|爬不起來|自己起不來|tidak bisa bangun|tidak bisa berdiri|"
        r"không đứng dậy được|không dậy được|không đứng được|can.?t get up|cannot get up"
    ),
    "no_urine_24h": (
        r"一整天沒尿|整天沒尿|整天沒有尿|24 ?小時沒尿|一天沒有尿|都沒尿|尿布都是乾的|尿布是乾的|"
        r"tidak kencing seharian|seharian tidak pipis|seharian tidak kencing|popok kering seharian|"
        r"cả ngày không đi tiểu|cả ngày không tiểu|tã khô cả ngày|no urine all day"
    ),
    "intake_sudden_drop": (
        r"都不吃|完全不吃|一口都沒|一口也沒|整天沒吃|都沒吃|不吃也不喝|"
        r"tidak makan sama sekali|sama sekali tidak makan|tidak mau makan sama sekali|"
        r"không ăn gì cả|bỏ ăn hoàn toàn|không ăn không uống|not eating at all"
    ),
    "fever_feel": (
        r"發燒|燒|摸起來燙|身體很燙|很燙|燙燙的|發熱|"
        r"demam|panas badan|badannya panas|panas|"
        r"sốt|nóng người|người nóng|fever|feels hot"
    ),
}
_FLAG_RE = {k: re.compile(v, re.IGNORECASE) for k, v in _FLAGS.items()}

_INCIDENTS: dict[str, str] = {
    "fall": r"跌倒|摔倒|跌|摔|滑倒|跌坐|jatuh|terjatuh|terpeleset|ngã|té|bị ngã|\bfell\b|\bfall\b",
    "medication_issue": (
        r"拒藥|不吃藥|不肯吃藥|吐藥|把藥吐|漏藥|忘記吃藥|藥沒吃|藥吐出來|"
        r"tidak mau minum obat|muntah obat|obatnya dimuntahkan|lupa minum obat|obat tidak diminum|"
        r"không chịu uống thuốc|nôn thuốc|quên uống thuốc|bỏ thuốc|refus\w* (?:the )?med|spat out"
    ),
    "choking": r"嗆到|嗆咳|嗆|噎到|tersedak|keselek|sặc|nghẹn|chok",
    "behavior": (
        r"打人|攻擊|遊走|亂走|亂跑|罵人|大叫|想跑出去|"
        r"memukul|mukul|marah-marah|keluyuran|mau kabur|teriak|"
        r"đánh người|đánh|đi lang thang|la hét|đòi ra ngoài|aggress|wander|hit (?:the )?staff"
    ),
}
_INC_RE = {k: re.compile(v, re.IGNORECASE) for k, v in _INCIDENTS.items()}

_SEEMS_DIFFERENT = re.compile(
    r"跟平常不一樣|跟平常不太一樣|和平常不一樣|和平常不太一樣|跟平常不同|怪怪的|不太對勁|不太對|不像平常|今天很不一樣|"
    r"tidak seperti biasa|beda dari biasanya|tidak seperti biasanya|aneh|lain dari biasa|"
    r"khác thường|không như mọi khi|lạ lạ|khác mọi ngày|không bình thường|"
    r"not (?:like )?(?:him|her)self|"
    r"seems different|something.s off",
    re.IGNORECASE,
)

_NO_PAIN = re.compile(
    r"不痛|不喊痛|沒痛|沒有痛|不會痛|不再痛|沒喊痛|tidak sakit|không đau", re.IGNORECASE
)
_SKIN_BETTER = re.compile(
    r"變小|比較不紅|不紅了|快好了|快癒合|癒合|結痂|比較乾|乾了|小很多|好多了|"
    r"mengecil|membaik|nhỏ hơn|đỡ hơn",
    re.IGNORECASE,
)
_SLEPT_WELL = re.compile(
    r"睡得好|睡得很好|一覺到天亮|沒有醒|nyenyak|tidak bangun|ngủ ngon|ngủ yên|slept well",
    re.IGNORECASE,
)
_MED_WORD = re.compile(r"藥|obat|thuốc|medic|pill", re.IGNORECASE)
_PAINKILLER = re.compile(r"止痛|obat nyeri|thuốc giảm đau|painkiller", re.IGNORECASE)

# --- numbers -----------------------------------------------------------------------------

_ZH_NUM = {
    "一": 1,
    "二": 2,
    "兩": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}
_ID_NUM = {"satu": 1, "dua": 2, "tiga": 3, "empat": 4, "lima": 5, "enam": 6}
_VI_NUM = {"một": 1, "hai": 2, "ba": 3, "bốn": 4, "năm": 5, "sáu": 6}

_INTAKE_FRACTION: list[tuple[re.Pattern[str], float]] = [
    (
        re.compile(
            r"一口都沒|一口也沒|都沒吃|完全不吃|都不吃|整天沒吃|tidak makan sama sekali|"
            r"sama sekali tidak|không ăn gì|bỏ ăn hoàn toàn|not eating at all",
            re.I,
        ),
        0.0,
    ),
    (re.compile(r"三分之一|1/3|sepertiga|một phần ba", re.I), 0.33),
    (re.compile(r"三分之二|2/3|dua pertiga|hai phần ba", re.I), 0.67),
    (re.compile(r"八分|八成", re.I), 0.8),
    (re.compile(r"一半|半碗|半|setengah|separuh|một nửa|nửa|half", re.I), 0.5),
    (
        re.compile(
            r"幾口|兩口|三口|一點點|一點|beberapa suap|sedikit|dikit|vài muỗng|vài thìa|"
            r"một chút|ít|a few bites|a little",
            re.I,
        ),
        0.2,
    ),
    (re.compile(r"吃完|吃光|全部|都吃|habis|semua|hết|ăn hết|finished|all of it", re.I), 1.0),
]


def _count(clause: str) -> float | None:
    m = re.search(r"(\d+)\s*(?:次|回|kali|lần|times)", clause, re.I)
    if m:
        return float(m.group(1))
    m = re.search(r"([一二兩三四五六七八九十])\s*(?:次|回)", clause)
    if m:
        return float(_ZH_NUM[m.group(1)])
    m = re.search(r"(satu|dua|tiga|empat|lima|enam)\s+kali", clause, re.I)
    if m:
        return float(_ID_NUM[m.group(1).lower()])
    m = re.search(r"(một|hai|ba|bốn|năm|sáu)\s+lần", clause, re.I)
    if m:
        return float(_VI_NUM[m.group(1).lower()])
    return None


def _intake_value(clause: str) -> float | None:
    for pat, v in _INTAKE_FRACTION:
        if pat.search(clause):
            return v
    return None


def _vitals_reported(text: str) -> Vitals:
    v = Vitals()
    m = re.search(r"(3[4-9]|4[0-2])(?:[.,](\d))?\s*(?:度|°C|°|℃|derajat|độ)", text)
    if not m:
        m = re.search(r"(?:體溫|suhu|nhiệt độ|temp)\D{0,6}(3[4-9]|4[0-2])(?:[.,](\d))?", text, re.I)
    if m:
        v.temp_c = float(f"{m.group(1)}.{m.group(2) or 0}")
    m = re.search(r"(\d{2,3})\s*/\s*(\d{2,3})", text)
    if m and 60 <= int(m.group(1)) <= 260:
        v.sbp, v.dbp = int(m.group(1)), int(m.group(2))
    m = re.search(r"(?:心跳|脈搏|nadi|denyut|mạch|nhịp tim|pulse|hr)\D{0,6}(\d{2,3})", text, re.I)
    if m:
        v.hr = int(m.group(1))
    m = re.search(r"(?:血氧|oksigen|saturasi|spo2|oxy)\D{0,6}(\d{2,3})", text, re.I)
    if m:
        v.spo2 = int(m.group(1))
    m = re.search(
        r"(?:呼吸|napas|nafas|thở|resp|rr)\D{0,6}(\d{1,2})\s*(?:次|/|kali|lần|per)", text, re.I
    )
    if m:
        v.rr = int(m.group(1))
    return v


# --- follow-up questions (max 2, caregiver's language, always answerable with 不知道) -----

_FOLLOWUPS: dict[str, dict[str, str]] = {
    "intake_amount": {
        "zh-TW": "大概吃了多少？（一半／幾口／都沒吃）",
        "id": "Kira-kira makan berapa banyak? (setengah / beberapa suap / tidak makan)",
        "vi": "Ăn được khoảng bao nhiêu? (một nửa / vài muỗng / không ăn)",
        "en": "Roughly how much did they eat? (half / a few bites / nothing)",
    },
    "fall_head": {
        "zh-TW": "有撞到頭嗎？能自己站起來嗎？",
        "id": "Kepalanya terbentur? Bisa berdiri sendiri?",
        "vi": "Có đập đầu không? Có tự đứng dậy được không?",
        "en": "Did they hit their head? Can they stand up by themselves?",
    },
    "fever_temp": {
        "zh-TW": "有量體溫嗎？幾度？",
        "id": "Sudah ukur suhu? Berapa derajat?",
        "vi": "Đã đo nhiệt độ chưa? Bao nhiêu độ?",
        "en": "Did you take the temperature? How many degrees?",
    },
    "since_when": {
        "zh-TW": "從什麼時候開始的？（今天／昨天／好幾天了）",
        "id": "Sejak kapan? (hari ini / kemarin / sudah beberapa hari)",
        "vi": "Bắt đầu từ khi nào? (hôm nay / hôm qua / mấy ngày rồi)",
        "en": "Since when? (today / yesterday / several days)",
    },
    "pain_where": {
        "zh-TW": "痛在哪裡？會影響走路或睡覺嗎？",
        "id": "Sakit di mana? Mengganggu jalan atau tidur?",
        "vi": "Đau ở đâu? Có ảnh hưởng đi lại hay ngủ không?",
        "en": "Where is the pain? Does it affect walking or sleeping?",
    },
}


def _followups(obs: StructuredObservation, lang: Lang) -> list[FollowupQA]:
    keys: list[str] = []
    f = obs.flags
    if "fall" in obs.incident_flags and not (f.fall_head_strike or f.cannot_get_up_after_fall):
        keys.append("fall_head")
    if f.fever_feel and (obs.vitals_reported is None or obs.vitals_reported.temp_c is None):
        keys.append("fever_temp")
    if "intake" in obs.domains and obs.domains["intake"].value is None:
        keys.append("intake_amount")
    if "pain" in obs.domains:
        keys.append("pain_where")
    if obs.domains and "since_when" not in keys and len(keys) < 2:
        keys.append("since_when")
    if not obs.domains and obs.seems_different and len(keys) < 2:
        keys.append("since_when")
    lang_key = lang if lang in ("zh-TW", "id", "vi", "en") else "zh-TW"
    return [FollowupQA(question=_FOLLOWUPS[k][lang_key], lang=lang) for k in keys[:2]]


# --- main entry ---------------------------------------------------------------------------


def extract_with_lexicon(
    text: str, lang: Lang, ts: datetime | None = None
) -> StructuredObservation:
    ts = ts or datetime.now(UTC)
    prov = Provenance(source="ai_extracted", author="intake_agent", ts=ts, language_original=lang)
    domains: dict[str, DimensionValue] = {}
    drowsy = _FLAG_RE["new_confusion_or_drowsiness"]
    consc = _FLAG_RE["consciousness_change"]
    for clause in clauses(text):
        for dim in DIMENSIONS:
            if not _DIM_RE[dim].search(clause):
                continue
            if dim == "sleep" and (drowsy.search(clause) or consc.search(clause)):
                continue  # 嗜睡／叫不醒 is cognition, not the sleep dimension
            if dim == "intake" and _MED_WORD.search(clause):
                continue  # 吃藥／minum obat／uống thuốc is medication, not intake
            if dim == "function" and _FLAG_RE["cannot_get_up_after_fall"].search(clause):
                continue  # 跌倒後站不起來 is a red-flag fact, not the function dimension
            if dim == "pain" and _PAINKILLER.search(clause):
                continue  # 止痛藥 names a drug, not a pain observation
            if dim in domains:
                if dim == "intake" and domains[dim].value in (None, 0.2):
                    v = _intake_value(clause)
                    if v is not None and v != 0.2:
                        domains[dim].value = v
                        domains[dim].direction = "down" if v < 0.8 else "same"
                        domains[dim].raw_quote = clause
                continue
            direction = "unknown"
            value: float | None = None
            if dim == "intake":
                value = _intake_value(clause)
                if value is not None:
                    direction = "down" if value < 0.8 else "same"
            if dim == "sleep":
                value = _count(clause)
                if value is not None:
                    direction = "up"
                elif _SLEPT_WELL.search(clause):
                    value, direction = 0.0, "same"
            if dim == "elimination":
                c = _count(clause)
                if c is not None:
                    value = c
            if direction == "unknown":
                if dim == "pain" and _NO_PAIN.search(clause):
                    value, direction = 0.0, "down"  # 不痛／不喊痛了 = improvement
                elif dim == "skin" and _SKIN_BETTER.search(clause):
                    direction = "down"  # 變小／比較不紅／快好了 = improvement
                elif dim in ("pain", "skin"):
                    direction = "up"
                elif _DOWN.search(clause) and not _UP.search(clause):
                    direction = "down"
                elif _UP.search(clause) and not _DOWN.search(clause):
                    direction = "up"
                elif dim in ("cognition", "vitals"):
                    direction = "up"
                elif _DOWN.search(clause):
                    direction = "down"
            domains[dim] = DimensionValue(
                value=value,
                raw_quote=clause,
                provenance=prov,
                confidence=0.85 if value is not None else 0.7,
                lang=lang,
                direction=direction,
            )
    flags = ObservationFlags(**{k: bool(r.search(text)) for k, r in _FLAG_RE.items()})
    incidents = [k for k, r in _INC_RE.items() if r.search(text)]
    vitals = _vitals_reported(text)
    has_vitals = any(v is not None for v in vitals.model_dump().values())
    if has_vitals and "vitals" not in domains:
        domains["vitals"] = DimensionValue(
            value=None,
            raw_quote=text.strip(),
            provenance=prov,
            confidence=0.8,
            lang=lang,
            direction="up",
        )
    if flags.intake_sudden_drop and "intake" in domains:
        domains["intake"].value = 0.0
        domains["intake"].direction = "down"
    obs = StructuredObservation(
        raw_text=text,
        language=lang,
        translation_zh=_summary_zh(domains, lang) if lang != "zh-TW" else None,
        domains=domains,
        seems_different=bool(_SEEMS_DIFFERENT.search(text)),
        incident_flags=incidents,  # type: ignore[arg-type]
        flags=flags,
        vitals_reported=vitals if has_vitals else None,
        unknown=[d for d in DIMENSIONS if d not in domains],
    )
    obs.followups = _followups(obs, lang)
    return obs


def _summary_zh(domains: dict[str, DimensionValue], lang: Lang) -> str:
    if not domains:
        return "（機器摘要：未辨識到八維度關鍵字，原文保留）"
    arrow = {"down": "減少／變差", "up": "增加／出現", "same": "與平常相同", "unknown": "有提到"}
    parts = [f"{DIMENSION_LABELS[k]['zh-TW']}：{arrow[v.direction]}" for k, v in domains.items()]
    src = {"id": "印尼語", "vi": "越南語", "en": "英語"}.get(lang, lang)
    return f"（機器摘要，原文為{src}）" + "；".join(parts)


# --- caregiver-note translation (order_to_caregiver_notes) -------------------------------

_NOTE_TEMPLATES: list[tuple[re.Pattern[str], dict[str, str]]] = [
    (
        re.compile(r"每餐記錄吃了幾分（例：(?P<ex>.+?)）"),
        {
            "id": "Catat berapa banyak makan setiap kali makan (contoh: {ex})",
            "vi": "Ghi lại mỗi bữa ăn được bao nhiêu (ví dụ: {ex})",
            "en": "Record how much was eaten at each meal (e.g. {ex})",
        },
    ),
    (
        re.compile(r"每天量體重一次，早餐前"),
        {
            "id": "Timbang berat badan sekali sehari, sebelum sarapan",
            "vi": "Cân mỗi ngày một lần, trước bữa sáng",
            "en": "Weigh once a day, before breakfast",
        },
    ),
    (
        re.compile(r"夜間醒來時記錄時間與原因"),
        {
            "id": "Kalau bangun malam, catat jam dan alasannya",
            "vi": "Khi thức dậy ban đêm, ghi lại giờ và lý do",
            "en": "When they wake at night, note the time and the reason",
        },
    ),
    (
        re.compile(r"新藥 (?P<name>.+?)，(?P<schedule>.+?)，吃完後看有沒有(?P<sx>.+)"),
        {
            "id": "Obat baru {name}, {schedule}; setelah minum perhatikan apakah ada {sx}",
            "vi": "Thuốc mới {name}, {schedule}; sau khi uống để ý xem có {sx} không",
            "en": "New medicine {name}, {schedule}; after taking it watch for {sx}",
        },
    ),
    (
        re.compile(r"每班翻身檢查(?P<site>.+?)皮膚，發紅或破皮馬上告訴護理師"),
        {
            "id": (
                "Setiap shift balikkan badan dan periksa kulit {site}; "
                "kalau merah atau lecet segera beri tahu perawat"
            ),
            "vi": "Mỗi ca xoay trở và kiểm tra da {site}; nếu đỏ hoặc trầy báo ngay điều dưỡng",
            "en": (
                "Every shift turn and check the skin at {site}; "
                "tell the nurse right away if red or broken"
            ),
        },
    ),
    (
        re.compile(r"每天陪走廊走一趟，需要扶就扶"),
        {
            "id": "Setiap hari temani jalan di koridor satu kali, bantu pegang kalau perlu",
            "vi": "Mỗi ngày cùng đi bộ hành lang một lần, cần thì đỡ",
            "en": "Walk the corridor together once a day; support them if needed",
        },
    ),
    (
        re.compile(r"喝水目標每天 (?P<n>\d+) 杯，記錄杯數"),
        {
            "id": "Target minum {n} gelas per hari, catat jumlah gelasnya",
            "vi": "Mục tiêu uống {n} ly nước mỗi ngày, ghi số ly",
            "en": "Aim for {n} cups of water a day and record the count",
        },
    ),
    (
        re.compile(r"如果(?P<x>.+?)，馬上告訴護理師"),
        {
            "id": "Kalau {x}, segera beri tahu perawat",
            "vi": "Nếu {x}, báo ngay cho điều dưỡng",
            "en": "If {x}, tell the nurse immediately",
        },
    ),
    (
        re.compile(r"疼痛時記錄部位與時間"),
        {
            "id": "Kalau kesakitan, catat bagian mana dan jam berapa",
            "vi": "Khi đau, ghi lại vị trí và giờ",
            "en": "When in pain, note where and when",
        },
    ),
]

_PHRASES: dict[str, dict[str, str]] = {
    "頭暈或想吐": {
        "id": "pusing atau mual",
        "vi": "chóng mặt hoặc buồn nôn",
        "en": "dizziness or nausea",
    },
    "半碗": {"id": "setengah mangkuk", "vi": "nửa chén", "en": "half a bowl"},
    "尾椎": {"id": "tulang ekor", "vi": "xương cụt", "en": "tailbone"},
    "腳跟": {"id": "tumit", "vi": "gót chân", "en": "heels"},
    "整天沒尿": {
        "id": "seharian tidak kencing",
        "vi": "cả ngày không đi tiểu",
        "en": "no urine all day",
    },
    "又跌倒": {"id": "jatuh lagi", "vi": "ngã lần nữa", "en": "another fall"},
    "叫不醒或講話怪怪的": {
        "id": "susah dibangunkan atau bicaranya aneh",
        "vi": "gọi không tỉnh hoặc nói năng lạ",
        "en": "hard to wake or speech seems odd",
    },
    "每天早晚各一次": {
        "id": "pagi dan malam sekali",
        "vi": "sáng và tối mỗi lần một viên",
        "en": "morning and evening",
    },
    "早餐後一次": {
        "id": "sekali setelah sarapan",
        "vi": "một lần sau bữa sáng",
        "en": "once after breakfast",
    },
    "睡前一次": {
        "id": "sekali sebelum tidur",
        "vi": "một lần trước khi ngủ",
        "en": "once before bed",
    },
    "吃完飯吐": {
        "id": "muntah setelah makan",
        "vi": "nôn sau khi ăn",
        "en": "vomiting after meals",
    },
}


def translate_instruction(line_zh: str, lang: Lang) -> str:
    if lang == "zh-TW":
        return line_zh
    for pat, forms in _NOTE_TEMPLATES:
        m = pat.search(line_zh)
        if m and lang in forms:
            fields = {k: _PHRASES.get(v, {}).get(lang, v) for k, v in m.groupdict().items()}
            return forms[lang].format(**fields)
    suffix = {
        "id": "（minta perawat menjelaskan）",
        "vi": "（nhờ điều dưỡng giải thích）",
        "en": "(ask the nurse to explain)",
    }.get(lang, "")
    return f"{line_zh} {suffix}".strip()
