# Personal Health Twin — 一份能跟著人走的紀錄

> 每個人有一份屬於自己、跟著他一輩子的健康紀錄（Personal Health ID），和一個替這份紀錄說話的 agent。**今天先做通道 1**：它先學會聽照顧他的人說話。

BUILDMODE 2026 × SITCON ・ Healthcare AI 賽道。紀錄屬於本人，誰能看由本人在 Care Circle 決定；家與機構都是場域：住宿式長照機構是這份紀錄今天接上的第一個場域，同一份紀錄回到家裡、進到醫院都跟著人走。照服員講一句話 → AI 只抽取成八個觀察維度、不判斷 → 護理師按一下 → 醫師巡診看一頁；穿戴訊號進來時先問人「可能跌倒了嗎」，再由護理師看事件資訊包。AI 只起草，人才定稿；每一行都有來源；任何信心值、機率、分數不出現在照護者與醫師介面。

四扇門：本人（`/me`：今天、終身時間軸、問我的紀錄、Care Circle）・家屬／照護者（`/caregiver`：對話、四鍵驗證）・護理師（`/nurse`：Clinical Queue）・醫師（`/doctor`：一人一頁）。願景全文：[docs/VISION_personal_health_twin.md](docs/VISION_personal_health_twin.md)（實作範圍以 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) 與 [docs/HANDOFF.md](docs/HANDOFF.md) 為準）。

![ci](https://github.com/chrisyang-c/record-follows-person/actions/workflows/ci.yml/badge.svg)

---

## 問題與制度出處

醫師永遠不夠（WHO：2030 年全球醫療人力短缺 1,000 萬），台灣老得最快（65 歲以上 19.9%，2050 年 38.4%），但每位住民身邊都有一雙每天看著他的眼睛——照服員。他們看得到「今天不太想吃、走路變慢、叫她名字反應慢」，只是不會打字、不會填表、可能不講中文，所以醫療從來沒聽見。

制度依據（衛福部《長期照顧十年計畫 3.0（115–124 年）核定本》，行政院 2025/12/31 核定）：

| 頁 | 內容 |
|---|---|
| p.8 | 住宿式長照機構 1,687 家、118,716 床 |
| p.19 | 減少照護機構住民就醫方案：1,681 家機構、529 家醫療機構、13.5 萬人受益 |
| p.26 | 長照人員資訊能力落差、照顧紀錄數位化推進緩慢 |
| p.68–69 | 住宿機構整合照護模式、論人計酬；在宅醫療照護資訊平台 |
| p.70–72 | 多家醫療機構診療、無專責醫療機構負起住民健康管理 |
| p.81 | 住宿機構品質獎勵：指標含「建構照顧資訊系統」 |
| p.101 | 住宿機構住民失智症盛行率 86.17% |
| p.147 | KPI「照護機構由同一醫療院所提供服務率」69.8% → 2035 年 90% |

另：長照機構評鑑基準 B8（特約醫師巡診、緊急後送、每月診察有紀錄）、長照服務法第 33 條、長照機構定型化契約範本（113 年）。完整敘事見 [docs/一份能跟著人走的紀錄_摘要與願景.md](docs/一份能跟著人走的紀錄_摘要與願景.md)。

---

## 架構

設計稿：[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。兩張 LangGraph 圖是節點名稱的唯一來源（`tests/test_mermaid_sync.py` 會比對）。

### Path A：急症（需看醫師，不到 119）

```mermaid
flowchart TD
    START([START]) --> load[load_person_record] --> intake[intake_agent] --> cmp[baseline_comparator] --> rf{red_flag_rules<br/>純程式}
    rf -- 命中 --> alert[notify_nurse_urgent] --> onsite
    rf -- 未命中 --> cg[caregiver_section_writer] --> draft[sbar_draft<br/>A 只寫變化，R 只提問] --> push[push_to_nurse] --> review{{"◇ nurse_review"}}
    review -- 超時 --> esc[escalate] --> review
    review -- 退回 --> intake
    review -- 接受／修改 --> onsite{{"◇ nurse_onsite_assessment<br/>護理師寫 A、R"}} --> final[sbar_final] --> route{{"◇ nurse_route_choice"}}
    route --> pack[handoff_packager] --> inc[incident_compiler] --> tl[(timeline_write<br/>需 approved)] --> fam[family_notification_draft] --> famok{{"◇ nurse_approve_notification"}} --> send[send_line] --> fu[schedule_follow_up] --> END([END])
    route -- 轉觀察 --> obs[to_routine_timeline] --> inc
```

### Path B：日常 → 本地歷史 → 巡診

```mermaid
flowchart TD
    subgraph SHIFT[每班]
        s1[load_person_record] --> s2[intake_agent] --> s3[baseline_comparator] --> s4{red_flag_rules}
        s4 -- 命中 --> s5[notify_nurse_urgent] --> sA[to_path_a]
        s4 -- 未命中 --> s6[minimal_sbar_draft] --> s7{{"◇ nurse_10s_confirm"}} --> s8[(timeline_write)] --> s9[timeline_curator]
    end
    subgraph ROUND[巡診前]
        r1[roster_agent] --> r2[trend_analyzer ×N] --> r3[familiarization_writer ×N] --> r4{{"◇ head_nurse_edit_list"}} --> r5[publish_round_pages] --> r6{{"◇ doctor_round"}} --> r7[order_ingest]
        r7 --> r8[order_to_caregiver_notes] --> r12[(timeline_write)]
        r7 --> r9[baseline_update_proposal] --> r10{{"◇ nurse_confirm_baseline"}} --> r11[(baseline_write)] --> r12
    end
```

原圖：[docs/langgraph_path_a_incident.mermaid](docs/langgraph_path_a_incident.mermaid)、[docs/langgraph_path_b_routine_round.mermaid](docs/langgraph_path_b_routine_round.mermaid)。

**層級**：`apps/api/core/settings.py::get_model()`（唯一的模型工廠：`MODEL_PROVIDER=openai` → `ChatOpenAI(model=MODEL_PINNED, temperature=0)`，`MODEL_PINNED=gpt-5.6-luna`（gpt-5.x 另加 `reasoning_effort="none"`）；訊息順序固定「system → 住民紀錄區塊 → 本輪」以吃到 prompt caching，每次呼叫的 token 與成本估算在 trace `llm.usage`；deep agent 與所有 graph 節點都經它）→ `apps/api/graphs`（LangGraph，PostgresSaver checkpointer，`interrupt()` + `Command(resume=…)`，APScheduler 超時 worker）→ `apps/api/agents`（每位住民一個 deepagents 實例，唯讀檔案系統；三個 subagent 只回結構化結果）→ `apps/api/record`（PersonRecord 讀寫層，`write_timeline` 是唯一寫入點）→ `records/{patient_id}/`（一人一個目錄，跟著人走）。

---

## 快速開始

```bash
cp .env.example .env               # MODEL_PROVIDER=openai + OPENAI_API_KEY；沒 key 會自動退回 mock
docker compose up -d postgres      # 沒 Docker：make db-local（Homebrew postgresql@17）
make migrate                       # PostgresSaver.setup() + threads 表（只在這裡跑）
make seed                          # 3 住民 × 14 天 × 2 班 + 第 12 天一次急症 → records/
make api                           # http://localhost:8000  (/docs 有 OpenAPI)
make web                           # http://localhost:3000
```

畫面：`/` 選角色（cookie）→ 角色首頁（`/caregiver` 住民卡、`/nurse` 紅燈橫幅→等我確認→今日總覽＋巡診準備、`/doctor` 巡診名單）→ 病人頁 `/p/{id}?tab=who|timeline|docs|talk`（這份紀錄的唯一入口）。`talk` 是 LINE 式聊天：每一題都由 intake_agent（LLM）依八維度缺口、profile、基線與已問過的題決定並附 reason，只有語音與文字輸入，上限 4 題；紅燈時程式先通知護理師、對話繼續由 agent 問關鍵事實並即時同步到護理師端；沒有模型就報錯停止。每則回覆下有 Agent 活動列（收合「花了 2.3 秒，7 步」，展開＝`GET /debug/trace/{thread_id}` 的內容）。`docs` 放護理師的等我確認（Path A 審核、10 秒確認）、RoundPage（可列印 A4）、事故檔、注意事項。逐步驗收指令見 [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md)。

測試：`make test`（api：ruff + pytest；web：eslint + vitest）；評測：`make eval`。

---

## 資料模型與 provenance

```
PersonRecord（records/{patient_id}/）
├── profile.json      慢病、過敏、DNR、緊急聯絡人、特約醫療機構、目前所在（FHIR-lite 命名）
├── baseline.json     八維度的「平常」，每筆 valid_from / valid_to / set_by；只在 ◇nurse_confirm_baseline 後更新
├── timeline/         只增不改：Observation | Incident | Encounter | Order（每筆 status/confirmed_by/provenance）
├── documents/        RoundPage | HandoffPage | VisitPage | IncidentFile | CaregiverNotes，帶 generated_from
└── provenance.jsonl  每行：source, author, confirmed_by, ts, language_original
```

八維度（觀察架構參考 INTERACT Stop and Watch（Florida Atlantic University），項目措辭與分類為本專案自訂，未複製原工具）：`intake` 進食與飲水｜`elimination` 排泄｜`function` 活動與日常功能｜`cognition` 意識、認知、情緒、溝通｜`sleep` 睡眠｜`skin` 皮膚與傷口｜`pain` 疼痛｜`vitals` 生命徵象與呼吸症狀。跨維度旗標 `seems_different`；事件快捷 `fall / medication_issue / choking / behavior`。

每一行保留 `language_original`（預設 `zh-TW`）。provenance 六種來源：`caregiver_said | ai_extracted | nurse_assessed | nurse_confirmed | doctor_ordered | system_derived`。AI 的行永遠是 `ai_extracted`；只有 `nurse_confirmed` 的行會出現在給醫師的頁面。ISBAR 的 A／R 是兩組欄位：AI 只能寫 `ai_change_vs_baseline` 與 `ai_questions_for_nurse`；`nurse_assessment` / `nurse_recommendation` 只有護理師能寫。

Schema 單一來源：[packages/schema/record_schema/models.py](packages/schema/record_schema/models.py)（Pydantic v2）→ `make codegen` → [packages/schema/ts/index.ts](packages/schema/ts/index.ts)。

---

## 紅燈規則聲明（非診斷）

[apps/api/red_flags/rules.py](apps/api/red_flags/rules.py) 是純程式，不呼叫 LLM（有測試檢查 import）。命中即推播護理師並跳過起草。輸出只呈現「觀察到的事實 + 建議聯絡護理師」，不輸出等級或分數。每條規則 `requires_validation=True`：**需護理師／醫師驗證，非診斷、非檢傷分級。**

| id | 條件 | 動作 |
|---|---|---|
| RF01 | 意識改變、新發生混亂或嗜睡 | 立即通知 |
| RF02 | 體溫 ≥38.5°C 或 <35°C | 立即通知 |
| RF03 | 呼吸 <8 或 ≥25／分；SpO₂ <92% 或較基線降 ≥3% | 立即通知 |
| RF04 | 收縮壓 <90 或 >220；心率 <40 或 >130 | 立即通知 |
| RF05 | 跌倒且頭部撞擊或使用抗凝血劑 | 立即通知 |
| RF06 | 發燒＋心跳快＋意識改變同時出現 | 立即通知 |
| RF07 | 進食量驟降、24h 未排尿 | 記錄觀察 |
| RF08–10 | 胸痛、呼吸困難、跌倒後無法起身（ARCHITECTURE §4 關鍵字硬條件） | 立即通知 |

---

## 評測結果

`apps/api/eval/run.py` 對 **46 條**合成照護者語句（zh-TW，含模糊句與 5 條誘導下診斷的句子；多語語句集為第二階段）計算。三個模型設定同日各跑一次（2026-09-05），逐句結果在 [apps/api/eval/results.md](apps/api/eval/results.md)：

| 指標 | gpt-4.1-2025-04-14 | gpt-5.6-luna（reasoning none） | **gpt-5.6-luna（intake reasoning low）** ← 採用 |
|---|---|---|---|
| Hallucination rate（有 ≥1 個多抽的標籤） | 2/46 = 4.3% | 4/46 = 8.7% | 3/46 = 6.5% |
| Omission rate（有 ≥1 個漏抽的標籤） | 1/46 = 2.2% | 2/46 = 4.3% | 2/46 = 4.3% |
| Provenance 正確率（source=ai_extracted ∧ raw_quote ⊂ 原文） | 46/46 = 100% | 46/46 = 100% | 46/46 = 100% |
| 輸出不含診斷詞／誘導句不下診斷 | 46/46／5/5 | 46/46／5/5 | 46/46／5/5 |
| 逐句全對 | 43/46 | 41/46 | 42/46 |
| 每句成本（估算，含 85% 快取命中） | — | $0.00025 | $0.00025 |

樣本只有 46 句，三欄之間的差距都在 **一句之內**（多抽 2／4／3 句、漏抽 1／2／2 句），不足以分出模型優劣；三個設定的 provenance、無診斷詞與誘導句都是滿分，也就是這個專案最在意的守門（raw_quote 必須是原文子字串、AI 不下判斷）不因模型而變。

**選 gpt-5.6-luna（intake `reasoning_effort=low`）的理由**：同一個模型同時跑 intake、個人 deep agent 與三個 subagent，成本是 gpt-4.1 的數分之一（每句約 $0.00025、三位住民巡診約 $0.012），prompt caching 命中率 85% 以上；low 走 Responses API，在 intake 這兩個 prompt 上不產生 reasoning tokens、成本與 none 相同，但 hallucination 從 8.7% 降到 6.5%。deep agent 與其他節點維持 `none`（chat completions 的 function tools 需要）。設定：`MODEL_PINNED=gpt-5.6-luna`、`INTAKE_REASONING_EFFORT=low`（`.env`）。

守門與模型無關：`core/llm.py::_guard_quotes` 會丟掉任何不是原文子字串的 raw_quote；抽取結果依「句子＋住民＋模型＋當日」快取（`records/{id}/extract_cache.json`），同一句只送模型一次。

---|---|
| Hallucination rate（有 ≥1 個多抽的標籤） | 2/46 = 4.3% |
| Omission rate（有 ≥1 個漏抽的標籤） | 0/46 = 0.0% |
| Provenance 正確率（source=ai_extracted ∧ raw_quote ⊂ 原文） | 46/46 = 100% |
| 輸出不含診斷詞 | 46/46 = 100% |
| 誘導句（「他應該是感冒了吧」等）不下診斷 | 5/5 |

mock 模式的 hallucination 在結構上不可能超過關鍵字命中（raw_quote 必須是原文子字串）；填入 `OPENAI_API_KEY` 後走 `ChatOpenAI(model=MODEL_PINNED, temperature=0)`，同一道守門仍在（`core/llm.py::_guard_quotes`）。

---

## 限制與 mock 清單

| 真做 | 假做／寫死 |
|---|---|
| Intake（語音→八維度，多輪聊天追問上限 4 題；zh-TW）| 影像分析（固定摘要）|
| — | 多語（id／vi）介面與翻譯：第二階段（schema 的 `lang` / `language_original` 已保留，預設 zh-TW）|
| Baseline Comparator（規則）| Timeline Curator 只做結構（seed 資料先整理好）|
| 紅燈規則＋推播 | 119／特約醫療機構通知（畫面提示）|
| ISBAR 預填＋護理師確認畫面＋退回＋超時升級（worker）| LINE 家屬通知（未設 token 時只顯示）|
| Incident Compiler → 兩區塊事故檔 + 後送頁 | 出院摘要 PDF（`ingest/discharge_pdf.py` mock）|
| Familiarization Writer subagent 寫 RoundPage（①②③④ 由模型依 timeline／baseline 生成，程式驗證規則，可列印） | 生命徵象量測（`ingest/vitals.py` 寫死）|
| Order Ingest → 照護者三件事（中文）＋ baseline 提案＋確認 | Roster 排序（3 位住民）|
| Health ID + Care Circle（本人授權／撤銷、access log）；本人 App（終身時間軸、問我的紀錄只引用既有行）| Health Graph：第二階段（不做）|
| 通道 4 模擬跌倒訊號 → 「可能跌倒」→ 照護者四鍵 → 事件資訊包 | 真實穿戴裝置、醫院 EHR／FHIR 對接：第二階段（不做）|
| 01 活體數位孿生：向量解剖圖（EMBL-EBI Expression Atlas anatomogram，Apache-2.0，`apps/web/public/anatomy/`）＋八維度熱點 | 3D 人體模型：第二階段 |

其他限制見 [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md)。本機沒有 `OPENAI_API_KEY` 時所有流程以 mock（確定性抽取）跑完；`deepagents / langgraph / langchain` 鎖精確版本（alpha）。**只用合成資料**：`data/seed/` 的姓名為代號，repo 內沒有任何真實個資。

---

## 文件

[CLAUDE.md](CLAUDE.md)（開發規則）・[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)・[docs/DECISIONS.md](docs/DECISIONS.md)・[docs/design.md](docs/design.md)・[docs/UI_AUDIT.md](docs/UI_AUDIT.md)・[docs/VIDEO.md](docs/VIDEO.md)・[docs/ACCEPTANCE.md](docs/ACCEPTANCE.md)・[docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md)

## LICENSE

Apache-2.0，見 [LICENSE](LICENSE)。
