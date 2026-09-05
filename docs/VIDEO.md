# VIDEO.md — ≤2 分鐘影片腳本（Personal Health Twin，十幕）

依 docs/VISION_personal_health_twin.md §31 的十幕改編；畫面全部來自本 repo（`make reset` 後）。旁白中文，字幕可雙語。總長 120 秒。

| 幕 | 時間 | 畫面 | 旁白 | 操作 |
|---|---|---|---|---|
| 1 Meet the Patient | 0:00–0:08 | `/` 四扇門 → 「本人」→ 王伯 → `/me`：MY HEALTH TWIN，86 歲，Health ID P-0000001，狀態一行「跟平常差不多」 | 這是王伯。這是他的紀錄，不是某一家醫院的病歷，是他自己的。 | 點「本人 → 王伯」 |
| 2 A Lifetime of Health | 0:08–0:20 | `/me/timeline`：年層只列大事件——2008 確診高血壓、2015 心房顫動住院、2019 白內障手術、2023 在家跌倒、2024 確診輕度失智、2026 機構內跌倒；展開 2026 看每月筆數 | 從第一次確診到今天，十八年，一條線。住院、手術、跌倒，都在同一份紀錄裡。 | 捲動年層，展開 2026 |
| 3 Ask the Twin | 0:20–0:32 | `/me` 問我的紀錄：「我以前有做過心臟手術嗎？」→「紀錄裡沒有這件事。」；「我住過幾次院？」→ 一句話＋來源行（2015-06-20 心房顫動住院）可點回時間軸 | 問他的 agent，它只回答紀錄裡有的事，每一句附來源；沒有的就說沒有，不猜、不解讀。 | 打字或按建議問題 |
| 4 Today's Health | 0:32–0:40 | `/me` 今天：八維度最近一筆，「晚上起來兩次」睡眠上升；終身摘要 3 慢性病／1 住院／1 手術／18 年 | 今天的他，八個面向，來自照顧他的人每天說的一句話。 | 捲回首頁 |
| 5 Something Happens | 0:40–0:48 | 終端：`curl -X POST localhost:8000/sim/fall/P-0000001` → 切「護理師」`/nurse` 新事件卡：王伯 · 可能跌倒（感測器，房間），原始值只在這裡 | 晚上九點四十三分，穿戴裝置收到一個訊號。系統寫下的是「可能跌倒」，不是「跌倒」。 | 由 `/sim/fall` 觸發，不用手動輸入 |
| 6 Caregiver Notification | 0:48–1:00 | 切「家屬」（王小姐）→ `/p/P001?tab=talk`：系統訊息「感測器偵測到王伯可能於 21:43 跌倒」＋四鍵；女兒按「他可能受傷」，打「爸爸意識清楚，但說髖部痛」→ agent 接著問 | 第一個被通知的不是醫院，是女兒。她按「可能受傷」，補一句話，對話就接下去。 | 四鍵是全系統唯一的按鈕 |
| 7 AI Context Building | 1:00–1:10 | 活動列展開：red_flag_rules（RF05 跌倒＋抗凝血劑）→ notify_nurse_urgent → 追問；`/nurse` 紅燈橫幅「照護者目前回報」同步長出來 | 跌倒、抗凝血劑——程式直接叫護理師，不等 AI；女兒每一句回答即時進事件資訊包的照護者區塊。 | 純程式紅燈，AI 只抽取 |
| 8 Nurse Dashboard | 1:10–1:30 | `/nurse` Clinical Queue → 王伯 → `/p/P001?tab=docs`：事件資訊包（這是誰、事件、感測原始值、相關病史、照護者回報、AI 只寫「與基線比的變化」與「請確認」）＋護理評估欄；護理師填 A／R、確認、選路徑 | 護理師拿到的不是「他跌倒了」，是整理好的事件資訊包。A 和 R 由她寫，AI 不寫。 | 現場評估 → 定稿 → 路徑 |
| 9 Clinical Escalation | 1:30–1:45 | 選「聯絡特約醫療機構」→ 後送頁（通話版 ISBAR）→ 家屬通知白話版核准（只顯示不發）；切「醫師」`/doctor` → 王伯 docs：縱向摘要（慢病、用藥、住院手術年表、近期事件）＋ RoundPage | 需要醫師時，資訊已經在路上：縱向摘要、事件、這個月變了什麼。 | |
| 10 Final Message | 1:45–2:00 | 回到 `/me`；黑底白字：One person. One lifelong health record. One AI that remembers. ＋ repo 網址 | 一個人，一份一輩子的紀錄，一個記得他的 AI——而且知道什麼時候該找誰。 | |

## 錄製前
```bash
make db-local && make migrate && make reset && make api   # 另一個終端 make web
```
- 第五幕：`curl -X POST http://localhost:8000/sim/fall/P-0000001 -H 'content-type: application/json' -d '{"location":"房間"}'`（不帶 still_seconds／spo2_after → 不命中硬條件，走四鍵）；要示範硬條件直接紅燈就加 `{"still_seconds":90}`。
- 第六幕以家屬身份：`/role?set=fam_P001`。四鍵只在這裡出現；選「聯絡不上」會直接紅燈。
- 照護者、醫師、本人畫面不出現任何原始值、信心值或百分比；原始值只在 `/nurse` 新事件卡。
- Chrome（Web Speech API，zh-TW）；沒麥克風就打字。錄影前 `make reset`（清對話、事件與舊 thread）。
