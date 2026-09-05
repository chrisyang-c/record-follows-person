# Personal Health Twin
## AI-Powered Lifelong Health Twin & Home Care Coordination Platform

### 中文定位
**一個跟著人一輩子的 AI 健康分身**

### 核心標語
> **讓健康資料跟著人走，而不是跟著醫院走。**

### 核心願景
> **不是讓 AI 取代醫師，而是讓 AI 記住一個人的一生，讓每一次照護都不必從零開始。**

---

# 1. Project Vision｜專案願景

目前一個人的健康資訊通常分散在不同的醫院、科別、檢驗系統、影像系統、穿戴裝置、居家設備與家屬記憶中。

因此真正缺少的往往不是「資料」，而是：

> **沒有任何一個系統真正知道完整的這個人。**

患者每到一個新的醫療場景，都可能需要重新描述：

- 得過什麼病
- 做過什麼手術
- 住過哪些院
- 現在吃什麼藥
- 有沒有過敏
- 最近身體狀態如何
- 最近有沒有發生異常事件

原始構想因此提出：每個人從出生開始，就建立一個屬於自己的終身健康身份與健康紀錄，最終形成 Personal Health Twin。

我們希望改變這件事情。

---

# 2. The Core Idea｜核心概念

每一個人從出生開始，都擁有一個唯一的：

# Personal Health ID

例如：

```text
P-0019283
```

這個 ID 不屬於任何一家醫院。

它屬於：

> **這個人自己。**

這個 ID 會伴隨人的一生，逐漸累積：

- 出生紀錄
- 疫苗
- 家族病史
- 過敏
- 疾病
- 診斷
- 就醫紀錄
- 檢驗
- 用藥
- 手術
- 住院
- 影像
- 醫療文件
- 每日血壓
- 心率
- 血氧
- 睡眠
- 活動量
- 體重
- 血糖
- 穿戴式裝置
- 居家感測器
- 跌倒事件
- 家屬回報
- 護理紀錄

這些資料形成一份持續成長的：

# Life-long Health Record

再建立：

# Personal Health Twin

也就是一個：

> **能理解這個人一生健康資料的數位健康分身。**

---

# 3. Product Positioning｜產品定位

Personal Health Twin 不是：

- AI 問診機器人
- 單純病歷查詢系統
- 穿戴裝置 Dashboard
- 單一醫院電子病歷
- AI 自動診斷系統

而是一套：

> **以患者為中心的終身健康資料、AI 理解與照護協調平台。**

整個產品的邏輯為：

```text
Person
  ↓
Lifelong Health Data
  ↓
Personal Health Twin
  ↓
Personal AI
  ↓
Care Coordination
  ↓
Family / Caregiver / Nurse / Doctor
```

---

# 4. Product Principles｜產品核心原則

## 4.1 One Person

一個人，一個終身 Health ID。

---

## 4.2 One Health Twin

健康資料不是分散事件，而是形成：

> **Longitudinal Health Profile**

---

## 4.3 Data Follows the Person

現在：

```text
Patient
 ↓
Hospital A
Hospital B
Clinic C
Wearable D
Home Device E
```

我們希望變成：

```text
Hospital A ─┐
Hospital B ─┤
Clinic C   ─┤
Wearable   ─┼──► Patient Health Twin
Home IoT   ─┘
```

---

## 4.4 One Source of Truth

AI 可以摘要、搜尋、比較與推理。

但：

> **AI 不是原始醫療事實。**

原始病歷、檢驗與醫療資料才是 Source of Truth。

---

## 4.5 Patient-Owned Access

患者不是把所有病歷直接公開。

而是決定：

> **誰，在什麼時候，可以看到多少資料。**

---

## 4.6 AI as Intelligence Layer

AI 負責：

```text
Understand
Retrieve
Detect
Summarize
Prioritize
Route
```

而不是直接取代醫療人員。

---

## 4.7 Event-Driven Care

Health Twin 不只是保存資料。

當異常事件發生時：

> **系統可以主動進入照護流程。**

---

# 5. Health Twin Data Model｜健康分身資料模型

整個 Health Twin 可以分成三個主要世界。

---

# 5.1 Medical History
## Past｜我過去發生過什麼

包含：

- Diseases
- Diagnoses
- Encounters
- Hospitalizations
- Procedures
- Surgeries
- Medications
- Allergies
- Laboratory Results
- Imaging
- Clinical Notes



---

# 5.2 Daily Health
## Present｜我現在每天怎麼樣

包含：

- Blood Pressure
- Heart Rate
- SpO₂
- Temperature
- Weight
- Blood Glucose
- Sleep
- Activity
- Mobility
- Fall Detection
- Home Sensors
- Wearable Data



---

# 5.3 Care Context
## Context｜誰在照顧我，以及我目前在哪個照護情境

包含：

- Family
- Caregiver
- Nurse
- Family Physician
- Specialist
- Home Care Service
- Emergency Contact
- Living Environment



---

# 6. Personal AI Context Model

Personal AI 每一次回答或分析，不應只看現在發生的事件。

它應該同時取得：

```text
                   AI
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
      PAST       PRESENT      CONTEXT
        │           │           │
     病史          生理值       照護者
     手術          活動量       居家環境
     用藥          睡眠         目前事件
     住院          異常變化     所在位置
```

因此真正的 Personal AI 是：

# Past + Present + Context

這也是 Health Twin 與一般醫療 Chatbot 最大的不同。

---

# 7. Life Timeline｜終身健康時間軸

使用者應該可以看到自己的：

# My Life Timeline

例如：

```text
1998
出生
│
├── 新生兒資料
├── 家族史
│
2005
│
├── Asthma
│
2018
│
├── Hypertension
│
2022
│
├── Hospitalization
│
2024
│
├── Surgery
│
2025
│
├── Fall × 2
│
2026
│
├── Home Monitoring
│
└── TODAY
```

並可以：

```text
Life
 ↓
Year
 ↓
Month
 ↓
Encounter
 ↓
Clinical Event
 ↓
Original Record
```

逐層深入。

這讓使用者不是在看：

> 「一堆病歷。」

而是在看：

> **我的健康是怎麼一路走到今天的。**

---

# 8. System Data Architecture｜資料架構

資料來自三個主要環境。

```text
                   REAL WORLD
                       │
      ┌────────────────┼─────────────────┐
      ▼                ▼                 ▼
   Hospital           Home            Wearable
      │                │                 │
      │                │                 │
      ▼                ▼                 ▼
 EHR / Lab          BP / IoT          HR / SpO₂
 Imaging            Weight            Sleep
 Surgery            Glucose           Activity
 Notes               Sensors           Motion
      │                │                 │
      └────────────────┼─────────────────┘
                       ▼
              INTEROPERABILITY
                       │
                 FHIR / APIs
                       │
               Data Normalization
                       │
               Identity Matching
                       ▼
                 HEALTH GRAPH
                       ▼
              PERSONAL HEALTH TWIN
                       ▼
                  PERSONAL AI
```

---

# 9. Interoperability Layer

理想架構中，外部醫療資料不是直接全部丟給 AI。

而是先經過：

```text
External Data
      ↓
FHIR / API
      ↓
Normalization
      ↓
Identity Matching
      ↓
Structured Health Data
```

這一層負責：

- 醫療資料互通
- 統一資料格式
- 正確對應患者
- 管理資料來源
- 保留 provenance

目前架構中也明確把 FHIR / API、Data Normalization、Identity Matching 視為 Health Twin 的資料入口。

---

# 10. Health Graph｜健康知識關係圖

健康不是一張平面的資料表。

例如：

```text
                  Patient
                    │
      ┌─────────────┼─────────────┐
      ▼             ▼             ▼
 Hypertension    Diabetes       Surgery
      │             │             │
      ▼             ▼             ▼
 Medication     Medication    Hospitalization
                                   │
                                   ▼
                                  Fall
                                   │
                    ┌──────────────┼─────────────┐
                    ▼              ▼             ▼
                Caregiver        Nurse         Doctor
```

Health Graph 讓 AI 不只是：

> 找到某一筆病歷。

而可以理解：

> **不同疾病、用藥、住院、事件與照護角色之間的關係。**



---

# 11. Personal AI Architecture｜AI 架構

Personal AI 的完整能力分成六個階段。

---

## 11.1 Understand

理解不同來源的資料。

例如：

- EHR
- Clinical Notes
- Lab
- Vitals
- Wearable
- Caregiver report

---

## 11.2 Retrieve

從數年甚至數十年的資料中找到：

> 和目前問題真正相關的內容。

---

## 11.3 Detect

找出：

- 異常生理趨勢
- 跌倒事件
- 活動異常
- 生理值偏離個人 baseline
- 需要人工注意的變化

---

## 11.4 Summarize

例如把：

```text
20 Years Records
+
Current Vitals
+
Medication
+
Recent Events
```

濃縮成護理師或醫師可以快速看的摘要。

---

## 11.5 Prioritize

判斷：

> 哪些資訊最需要先被看到？

---

## 11.6 Route

將資訊送到：

```text
Patient
Caregiver
Nurse
Doctor
```

適合的角色。

---

# 12. AI Boundary｜AI 能力邊界

這是整個系統非常重要的安全設計。

## AI 可以

```text
✓ 整理資料
✓ 搜尋相關資料
✓ 摘要
✓ 比較
✓ 趨勢分析
✓ 偵測異常訊號
✓ 建立事件摘要
✓ 整理相關病史
✓ 協助護理師準備資訊
✓ 協助醫師快速理解患者
```

---

## AI 不直接負責

```text
✗ 自行診斷重大疾病
✗ 自行決定治療
✗ 自行修改藥物
✗ 自行取代護理師
✗ 自行取代醫師
✗ 自行做最終緊急醫療判斷
```

因此 AI 的角色是：

# Detect → Summarize → Prioritize → Route

而不是：

# Diagnose → Decide → Treat



---

# 13. Data Provenance｜AI 可追溯性

所有 AI 輸出都應該能夠回答：

# Why did AI say this?

例如：

```text
AI Summary
     │
     ├── Hospital A Record
     ├── Laboratory Result
     ├── Wearable
     ├── Home Sensor
     ├── Caregiver Report
     └── Nursing Record
```

使用者可以一路回到：

```text
AI Interpretation
       ↓
Derived Information
       ↓
Original Source
```

例如：

```text
Evidence

HR
76 → 108 bpm

SpO₂
97% → 92%

Movement
No movement detected for 94 sec
```

這是 AI 建立信任的重要機制。

---

# 14. Identity & Trust｜身份與信任架構

整個系統不是：

> 有 Patient ID 就可以看到資料。

而是：

```text
Identity
   +
Consent
   +
Role
   +
Scope
   =
Access
```

---

# 15. Care Circle

Patient 可以建立自己的：

# Care Circle

```text
                       Patient
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
           Family       Nurse       Doctor
              │           │           │
          Access A    Access B    Access C
```

---

# 16. Permission Model

每次資料存取都應回答：

```text
WHO?
誰在看？

WHAT?
可以看什麼？

WHEN?
可以看到什麼時候？

WHY?
為什麼需要？

HOW MUCH?
能看到多少？
```

---

# 17. Role-Based Access

## Family

可能可以看到：

- 基本健康狀態
- 重要疾病
- 目前用藥
- 異常事件
- 跌倒事件
- 緊急資訊

---

## Caregiver

可能可以看到：

- Daily health
- Vitals
- Activity
- Recent alerts
- Care tasks
- Important medical history

---

## Nurse

可以看到：

- Clinical Summary
- Current Vitals
- Relevant History
- Recent Events
- Medication
- Caregiver Report
- Nursing Information

並建立：

- Nursing Assessment
- Nursing Record

---

## Doctor

可以看到：

- Full Longitudinal History
- Conditions
- Medication
- Laboratory
- Imaging
- Encounters
- Procedures
- Hospitalizations
- Clinical Notes
- AI-generated Summary

目前的母架構已將 Family、Caregiver、Nurse 與 Doctor 的資料範圍明確區分。

---

# 18. Patient Permission Controls

患者應該能夠：

```text
Grant Access
Revoke Access
Temporary Access
Emergency Access
View Access History
```

並查看：

```text
Who accessed?
What did they access?
When?
Why?
```

---

# 19. Care Orchestrator｜照護協調層

Health Twin 最大的價值，不應該停留在：

> 「可以查資料。」

而是：

> **事情發生時，可以啟動照護流程。**

完整流程：

```text
Health Data
     ↓
AI Detection
     ↓
Event
     ↓
Verification
     ↓
Context Collection
     ↓
Clinical Event Packet
     ↓
Nurse Review
     ↓
Clinical Escalation
```



---

# 20. Killer Use Case｜老人跌倒

跌倒是目前最適合作為整個系統 Demo 的核心 scenario。

---

# 20.1 Normal Monitoring

老人平常在家。

穿戴裝置與居家感測器持續收集：

```text
Heart Rate
SpO₂
Activity
Accelerometer
Gyroscope
Movement
```

---

# 20.2 Potential Fall

系統突然偵測：

```text
Acceleration Spike
       ↓
Orientation Change
       ↓
No Movement
       ↓
Heart Rate Change
```

系統建立：

# Potential Fall Event

而不是直接聲稱：

> 確定跌倒。

這保留了不確定性與人工驗證。

---

# 20.3 Event Record

例如：

```text
EVENT #20260905-000123

Type
Possible Fall

Confidence
92%

Time
21:43

Location
Bedroom
```

---

# 20.4 Pre / Post Event Context

AI 同時取得：

```text
PRE-EVENT

BP        134/82
HR        76
SpO₂      97%
Activity  Normal
```

以及：

```text
POST-EVENT

HR        108
SpO₂      92%
Movement  Low
```

並抓出 Relevant History：

```text
CABG
Hypertension
Previous Fall ×2
Recent Hospitalization
```



---

# 21. Caregiver Verification

第一步不是直接通知所有醫師。

而是通知患者授權的照顧者。

例如：

> 王先生可能於 21:43 發生跌倒。

Caregiver App：

```text
[ 我現在在患者身邊 ]

[ 患者目前沒事 ]

[ 患者可能受傷 ]

[ 無法聯絡患者 ]
```

如果家屬回報：

> 患者意識清楚，但表示髖部疼痛。

這個資訊再進入下一個流程。

---

# 22. Clinical Event Packet｜臨床事件資訊包

AI 不應該把患者所有資料全部丟給護理師。

它應該建立：

# Clinical Event Packet

例如：

```text
────────────────────────────
PATIENT
────────────────────────────

王先生
67 years old


────────────────────────────
EVENT
────────────────────────────

Possible Fall
21:43
Bedroom
Confidence 92%


────────────────────────────
CURRENT VITALS
────────────────────────────

HR       108
SpO₂     92%
BP       102/65


────────────────────────────
RELEVANT HISTORY
────────────────────────────

CABG
Hypertension
Previous Fall ×2


────────────────────────────
CAREGIVER REPORT
────────────────────────────

Patient conscious.
Complains of hip pain.


────────────────────────────
AI SUMMARY
────────────────────────────

Possible fall with subsequent
tachycardia and reduced SpO₂.

Clinical review recommended.
```

這個 Event Packet 應該成為整套系統的重要核心物件。

---

# 23. Nurse Review

護理師收到的不是：

> 「老人跌倒了。」

而是完整、已整理過的：

> Clinical Event Packet

護理師可以：

```text
Review Patient
      ↓
Review Event
      ↓
Review Relevant History
      ↓
Add Nursing Assessment
      ↓
Document
      ↓
Determine Next Step
```



---

# 24. Clinical Escalation

護理師依照專業評估決定：

```text
Monitor
   or
Contact Physician
   or
Notify Hospital
   or
Activate Emergency Workflow
```

因此臨床責任仍留在：

> **Human Clinician**

AI 的工作是：

> **讓醫療人員更快取得正確的資訊。**



---

# 25. Human + AI Responsibility Model

整個流程可以非常清楚地分工。

## Sensor / System

```text
Detect signal
```

## Caregiver

```text
Verify
+
Provide context
```

## AI

```text
Retrieve
+
Understand
+
Summarize
+
Package
+
Prioritize
```

## Nurse

```text
Review
+
Assess
+
Document
+
Escalate
```

## Doctor

```text
Clinical Decision
+
Treatment
```

因此流程不是：

```text
Patient
 ↓
AI
 ↓
Doctor
```

而是：

```text
Patient
 ↓
Caregiver
 ↓
AI Context Building
 ↓
Nurse
 ↓
Doctor
```

---

# 26. The Two Core Flows

整個 Personal Health Twin 可以濃縮成兩種 Flow。

---

## Data Flow

資料持續建立 Twin：

```text
Hospital ─────┐
Wearable ─────┤
Home IoT ─────┼──► Health Twin
Caregiver ────┤
Nursing ──────┘
```

一句話：

# Data builds the Twin.

---

## Event Flow

異常發生後啟動 Care Network：

```text
Health Twin
    ↓
Detection
    ↓
Event
    ↓
Caregiver
    ↓
Event Packet
    ↓
Nurse
    ↓
Doctor
```

一句話：

# Events activate the Care Network.

---

# 27. Complete System Architecture｜完整系統架構

```text
┌──────────────────────────────────────────────┐
│              EXPERIENCE LAYER                │
│                                              │
│ Patient │ Family │ Caregiver │ Nurse │ Doctor│
└───────────────────────┬──────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────┐
│             CARE ORCHESTRATOR                │
│                                              │
│ Events │ Alerts │ Verification               │
│ Workflow │ Escalation                        │
└───────────────────────┬──────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────┐
│             PERSONAL AI LAYER                │
│                                              │
│ Understand │ Retrieve │ Detect               │
│ Summarize │ Prioritize │ Route               │
└───────────────────────┬──────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────┐
│              HEALTH TWIN LAYER               │
│                                              │
│ Longitudinal Timeline                        │
│ Health Graph                                 │
│ Current State                                │
│ Care Context                                 │
└───────────────────────┬──────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────┐
│                  DATA LAYER                  │
│                                              │
│ EHR │ Lab │ Imaging │ Documents              │
│ Wearable │ Home IoT                          │
│ Caregiver Reports │ Nursing Records          │
└───────────────────────┬──────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────┐
│            INTEROPERABILITY LAYER            │
│                                              │
│ FHIR │ APIs │ Normalization                  │
│ Identity Matching │ Provenance               │
└───────────────────────┬──────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────┐
│              IDENTITY & TRUST                │
│                                              │
│ Patient ID │ Consent │ RBAC                  │
│ Encryption │ Audit │ Revocation              │
└──────────────────────────────────────────────┘
```

這與目前已整理的 Experience → Care Orchestrator → AI Health Twin → Health Graph → Data → Identity & Trust 分層方向一致。

---

# 28. User Experience Architecture｜使用者介面架構

整個產品至少包含四種主要角色介面。

---

# 28.1 Patient App

```text
Home
│
├── My Health Twin
├── Today's Health
├── My Timeline
├── Ask My AI
├── Medications
├── Records
├── Events
└── Care Circle
```

---

## Patient Homepage

```text
─────────────────────────────

          MY HEALTH TWIN

            王先生
          67 years old

            ● Stable

─────────────────────────────

TODAY

HR              78 bpm
BP              132 / 78
SpO₂            97%
Sleep           6h 42m
Activity         3,284 steps

─────────────────────────────

LIFELONG HEALTH

12 Conditions
4 Surgeries
8 Hospitalizations
23 Years of Records

─────────────────────────────

RECENT EVENTS

No critical events

─────────────────────────────

ASK YOUR HEALTH TWIN

「最近我的健康有什麼變化？」

─────────────────────────────
```

---

# 28.2 Caregiver App

```text
My Care Circle
│
├── Patient Overview
├── Today's Status
├── Alerts
├── Fall Event
├── Timeline
├── Medication
└── Contact Care Team
```

---

# 28.3 Nurse Dashboard

```text
Clinical Queue
│
├── New Events
├── High Priority
├── Pending Review
├── Patient Search
├── Event Packet
├── Nursing Assessment
└── Care Tasks
```

---

# 28.4 Doctor Dashboard

```text
Patient
│
├── Longitudinal Summary
├── Timeline
├── Conditions
├── Medication
├── Laboratory
├── Imaging
├── Procedures
├── Events
├── Clinical Notes
└── AI Assistant
```

目前母架構也已經把這四類介面的主要頁面與角色需求分開設計。

---

# 29. The Core Product Loop

整個 Personal Health Twin 最後會形成一個持續循環：

```text
                  PERSON
                     │
                     ▼
               HEALTH TWIN
                     │
                     ▼
               PERSONAL AI
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
      Understand   Detect      Assist
          │          │          │
          └──────────┼──────────┘
                     ▼
              CARE WORKFLOW
                     │
                     ▼
              HUMAN CLINICIAN
                     │
                     ▼
                BETTER CARE
                     │
                     ▼
              NEW HEALTH DATA
                     │
                     └────────► HEALTH TWIN
```

所以它不是：

```text
AI
 ↓
Answer
```

而是：

# Person → Data → Twin → AI → Care → New Data → Twin



---

# 30. Ideal Vision vs. Prototype

這個專案應該刻意區分：

## Ideal Vision

未來完整系統：

```text
Birth
  ↓
Whole Life
  ↓
All Medical Records
  ↓
Daily Health
  ↓
Health Twin
  ↓
Personal AI
  ↓
Care Network
  ↓
Home Care / Hospital / Emergency
```

---

## Prototype / Hackathon Demo

實際 Demo 不需要完成全部。

只需要實作一條：

# Vertical Slice

```text
Existing Medical History
           +
Simulated Daily Vitals
           +
Simulated Wearable Data
           ↓
      Health Twin
           ↓
      AI Detection
           ↓
      Fall Event
           ↓
      Caregiver
           ↓
      Event Packet
           ↓
      Nurse Review
           ↓
   Clinical Escalation
```

這原本就是目前架構中建議的 Demo 收斂方式。

---

# 31. Final Demo Story｜最終展示故事

## Scene 1｜Meet the Patient

畫面：

> 王先生，67 歲。

進入 Personal Health Twin。

---

## Scene 2｜A Lifetime of Health

展示：

```text
Birth
 ↓
Disease
 ↓
Medication
 ↓
Hospitalization
 ↓
Surgery
 ↓
Falls
 ↓
Today
```

講：

> 「這不是某一家醫院的病歷，而是王先生自己的健康歷史。」

---

## Scene 3｜Ask the Twin

使用者問：

> 「我以前有做過心臟手術嗎？」

AI 回答：

> 有，並顯示相關日期、醫院與來源紀錄。

---

## Scene 4｜Today's Health

Dashboard：

```text
HR
SpO₂
BP
Sleep
Activity
```

---

## Scene 5｜Something Happens

突然跳出：

# Potential Fall Detected

---

## Scene 6｜Caregiver Notification

女兒收到：

> 爸爸可能於 21:43 發生跌倒。

女兒選擇：

> 患者可能受傷。

並輸入：

> 爸爸意識清楚，但表示髖部疼痛。

---

## Scene 7｜AI Context Building

AI 自動抓：

- Current Event
- Current Vitals
- Relevant History
- Previous Falls
- Medication
- Caregiver Report

形成：

# Clinical Event Packet

---

## Scene 8｜Nurse Dashboard

護理師開啟 Event Packet。

看到：

- Patient summary
- Relevant history
- Current vitals
- Caregiver report
- AI summary

完成 Nursing Assessment。

---

## Scene 9｜Clinical Escalation

護理師判斷需要進一步處理。

將資訊交給醫師。

---

## Scene 10｜Final Message

回到 Personal Health Twin。

畫面顯示：

# One person.
# One lifelong health record.
# One AI that remembers.

最後一句：

> **Every person deserves a Health Twin that remembers their whole life — and knows when to bring the right people in.**

---

# 32. Why This Is Different｜與一般醫療 AI 的差異

一般 AI 健康產品：

```text
Question
 ↓
AI
 ↓
Answer
```

Personal Health Twin：

```text
Lifetime Data
      +
Real-Time Health
      +
Care Context
      ↓
Health Twin
      ↓
Personal AI
      ↓
Care Workflow
      ↓
Human Clinician
```

因此創新點不是：

> 「我們用了 LLM。」

而是：

# Digital Twin + Consent + Care Network + Event-Driven Care

這正是目前整套構想比單純 Digital Health Twin 再往前延伸的地方。

---

# 33. Project Scope｜專案範圍

## Concept Level

可以完整呈現：

- Lifelong Health Twin
- Personal Health ID
- Cross-hospital data
- FHIR interoperability
- Health Graph
- Personal AI
- Wearable integration
- Home monitoring
- Consent
- Care Network
- Nurse / Doctor workflow
- Event-driven care

---

## Prototype Level

優先做：

```text
1. Patient Dashboard
2. Life Timeline
3. Today's Health
4. Ask My Health Twin
5. Simulated Fall Event
6. Caregiver Alert
7. Event Packet
8. Nurse Dashboard
9. Clinical Escalation
```

---

# 34. Team Structure｜四人最終分工

四個人不要依照 PPT 頁數分。

應該依照四個不同領域負責。

---

# Person A｜Product & Health Twin

## 核心問題

> **我們到底在建立什麼？**

負責：

```text
1. Problem Statement
2. Product Vision
3. Personal Health ID
4. Personal Health Twin Definition
5. Medical History
6. Daily Health
7. Care Context
8. Life Timeline
9. Product Value
10. Patient Experience Concept
```

---

## Person A Deliverables

### A1. Problem Statement

說明目前資料 fragmentation。

### A2. Product Vision

定義：

> Data follows the person.

### A3. Health Twin Model

```text
Past
+
Present
+
Context
```

### A4. Life Timeline

### A5. Patient Homepage Concept

---

# Person B｜Data & AI Architecture

## 核心問題

> **資料怎麼進來？AI 怎麼理解這個人？**

負責：

```text
1. Data Sources
2. EHR
3. Wearables
4. Home IoT
5. FHIR / APIs
6. Data Normalization
7. Identity Matching
8. Health Graph
9. Personal AI
10. AI Pipeline
11. AI Boundary
12. Data Provenance
```

---

## Person B Deliverables

### B1. Data Architecture

```text
Data Sources
 ↓
Interoperability
 ↓
Health Graph
 ↓
Health Twin
 ↓
AI
```

### B2. Health Graph

### B3. AI Architecture

```text
Understand
Retrieve
Detect
Summarize
Prioritize
Route
```

### B4. AI Safety Boundary

### B5. AI Provenance

---

# Person C｜Care Network & Clinical Workflow

## 核心問題

> **當事情真的發生，資料怎麼安全地進入照護流程？**

負責：

```text
1. Care Circle
2. Consent
3. Role-Based Access
4. Family Access
5. Caregiver Access
6. Nurse Access
7. Doctor Access
8. Fall Workflow
9. Caregiver Verification
10. Clinical Event Packet
11. Nurse Review
12. Clinical Escalation
```

---

## Person C Deliverables

### C1. Care Network

### C2. Consent Model

```text
WHO
WHAT
WHEN
WHY
HOW MUCH
```

### C3. Role-Based Access Diagram

### C4. Fall Workflow

### C5. Clinical Event Packet

### C6. Nurse → Doctor Escalation

---

# Person D｜UI / UX & Demo

## 核心問題

> **這套系統最後到底長什麼樣？**

負責：

```text
1. Patient App
2. Caregiver App
3. Nurse Dashboard
4. Doctor Dashboard
5. Health Twin Visualization
6. Life Timeline UI
7. Fall Event UI
8. Event Packet UI
9. Prototype
10. Demo Script
11. Final Presentation Flow
```

---

## Person D Deliverables

### D1. Patient UI

### D2. Caregiver UI

### D3. Nurse Dashboard

### D4. Doctor Dashboard

### D5. Clickable / Visual Prototype

### D6. Final Demo Story

---

# 35. Four-Person Integration Logic

最後不要按照：

```text
A 做完
B 做完
C 做完
D 做完
```

直接四份拼在一起。

而是重新按照故事整合：

```text
01 WHY
   │
   ▼
現在醫療資料為什麼有問題？
   │
   ▼
02 VISION
   │
   ▼
Personal Health Twin
   │
   ▼
03 DATA
   │
   ▼
一生資料怎麼建立 Twin？
   │
   ▼
04 AI
   │
   ▼
AI 怎麼理解這個人？
   │
   ▼
05 TRUST
   │
   ▼
誰可以看到什麼？
   │
   ▼
06 CARE
   │
   ▼
事件發生怎麼進入醫療流程？
   │
   ▼
07 UX
   │
   ▼
使用者到底看到什麼？
   │
   ▼
08 DEMO
   │
   ▼
王先生跌倒
```

所以四人的關係是：

```text
A
定義「人與產品」
       ↓
B
建立「資料與 AI」
       ↓
C
建立「照護與信任」
       ↓
D
把所有概念「變成產品」
```

---

# 36. Suggested Final Presentation Structure

未來如果做簡報，可以用：

### Slide 1
**Personal Health Twin**

### Slide 2
**The Problem**
健康資料是碎片化的。

### Slide 3
**Our Vision**
Data follows the person.

### Slide 4
**One Person, One Health Twin**

### Slide 5
**Lifelong Health Timeline**

### Slide 6
**Data Architecture**

### Slide 7
**Personal AI**

### Slide 8
**Trust & Consent**

### Slide 9
**Care Network**

### Slide 10
**Event-Driven Care**

### Slide 11
**Fall Scenario**

### Slide 12
**Clinical Event Packet**

### Slide 13
**Patient / Caregiver / Nurse / Doctor UI**

### Slide 14
**Live Demo**

### Slide 15
**Final Vision**

---

# 37. Final Pitch

## 30 秒版

目前一個人的醫療資料散落在不同醫院、裝置與照護者手上，每次進入新的醫療場景，都像重新認識這個患者。

Personal Health Twin 希望讓每個人從出生開始，就擁有一份跟著自己一生的健康數位分身。

它整合過去的醫療歷史、現在每天的健康狀態與照護情境，再透過 AI 理解、搜尋、偵測與摘要。

當異常事件發生時，例如老人跌倒，系統不是單純發出警報，而是將患者相關病史、即時生理值與家屬回報整理成 Clinical Event Packet，再交給護理師與醫師。

我們不是讓 AI 取代醫療人員。

我們希望做到的是：

> **讓正確的資訊，在正確的時間，交到正確的人手上。**

---

# 38. One-Sentence Product Definition

> **Personal Health Twin 是一個以患者為中心的終身健康資料與 AI 照護協調平台，將 Lifetime Medical History、Real-Time Daily Health 與 Care Context 整合成個人健康數位分身，並透過 AI 在需要時把正確資訊送進正確的照護流程。**

---

# 39. Final Product Philosophy

整個專案最終不是在問：

> AI 能不能幫人看病？

而是在問：

# **當一個人需要被照顧的時候，醫療系統能不能真正理解「這個人」？**

Personal Health Twin 希望讓答案變成：

# 可以。

因為：

> **這個人的健康歷史，不再散落。**

> **這個人的現在，不再孤立。**

> **這個人的資料，不再只存在某一家醫院。**

> **而是形成一個可以持續理解他、陪伴他、並在需要時連接照護者的 Health Twin。**

---

# Final Vision

```text
                ONE PERSON
                     │
                     ▼
           ONE LIFELONG HEALTH ID
                     │
                     ▼
           ONE PERSONAL HEALTH TWIN
                     │
            ┌────────┼────────┐
            ▼        ▼        ▼
          PAST    PRESENT   CONTEXT
            │        │        │
            └────────┼────────┘
                     ▼
                PERSONAL AI
                     │
           Understand
           Retrieve
           Detect
           Summarize
           Prioritize
           Route
                     │
                     ▼
               CARE NETWORK
                     │
       ┌─────────────┼─────────────┐
       ▼             ▼             ▼
    Family         Nurse         Doctor
       │             │             │
       └─────────────┼─────────────┘
                     ▼
                BETTER CARE
                     │
                     ▼
               NEW HEALTH DATA
                     │
                     └──────────────►
                    HEALTH TWIN
```

# Personal Health Twin

### **From birth to beyond.**

### **Data follows the person.**

### **AI understands the context.**

### **Care begins with the whole person.**