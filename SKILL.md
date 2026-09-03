---
name: monthly-report-agent
description: >
  Turn a project's monthly Excel data pack into a validated, management-ready
  monthly report delivered as OpenDeedigital-styled PDFs, and stop at the human
  review gate. Use when asked to generate, rebuild or QA a monthly report from
  a data pack ("run the monthly report for 2026-04", "出四月份月報", "generate
  the project health report"), or asked whether a monthly report is safe to
  distribute. Drafts only — a named person checks and signs before anything is sent.
---

# Monthly Report Agent 月度報告代理

## Intent 意圖

做 PM 平時要花約兩日砌嘅月報：讀 `input/` 嘅 Excel 資料包 → 驗證 → 計 KPI 同
紅黃綠狀態 → 出圖、出敘述報告、出品牌化 dashboard → 視覺 QA → **出 PDF** →
**停在人手批核關卡**。

SOP（人做法）：`workflows/monthly_report_sop.md`

## Rules 規則（不可妥協）

1. **AI 起草 → 人檢查 → 人簽名。** 你出嘅報告係 DRAFT。
2. **絕不代發。** 唔會 email、發布、派發任何 output。`send_report_email.py` 有 blocker 就拒絕；就算冇 blocker，都只可以由人行。
3. **缺值只可標示，唔可推斷。** 空格係 Data Gap，唔係一個你估返嚟嘅數。
4. **`input/` 同 `tools/` 只讀。** 只寫入 `outputs/`。
5. **Blocker 先係產品。** 揭示邊度錯、邊個要幾時修，比一份靚報告更有價值。
6. **最終交付係 PDF。** 決定人拎住嘅係 `monthly_report_premium.pdf`（dashboard）同 `monthly_report.pdf`（敘述報告）。

## Tools 確定性工具

| # | Verb | Tool | Input → Output |
|---|------|------|----------------|
| 1 | LOAD | `tools/load_data_pack.py` | `input/*.xlsx` → sheets（記憶體） |
| 2 | VALIDATE | `tools/validate_data_pack.py` | sheets → `review_gate_status.json`（blocker / warning） |
| 3 | KPI | `tools/calculate_monthly_kpis.py` | sheets → `metrics.json`（KPI + 整體 RAG） |
| 4 | CHARTS | `tools/generate_report_charts.py` | metrics → `assets/*.png` |
| 5 | DRAFT | `tools/render_monthly_report.py` | metrics + charts → `monthly_report.md / .html / .pdf` |
| 6 | EMAIL DRAFT | `tools/prepare_report_email.py` | 報告 → `email/`（草稿 + 送出 manifest） |
| 7 | ORCHESTRATOR | `tools/run_monthly_report.py` | 一句行完 1–6 |
| 8 | DASHBOARD | `tools/generate_premium_html_report.py` | `input/*.xlsx` + logo → `monthly_report_premium.html` |
| 9 | QA | `tools/visual_qa_report.py` | premium HTML → `visual_qa_status.json`（`--simulate` = 離線） |
| 10 | EXPORT PDF | `tools/export_premium_pdf.py` | premium HTML → **`monthly_report_premium.pdf`**（A4） |
| 11 | GATE | `tools/send_report_email.py` | manifest + gate status → 有 blocker 即拒絕 |

全部係純 python：同一輸入永遠同一輸出（PDF 由 reportlab 同本機 headless Chrome / Edge 產生）。由 repo 任何位置行都得。所有數字由 tool 計，你唔計。

## Run 執行

Input：`input/` 入面嘅資料包（一個 `.xlsx`）。期間格式 `YYYY-MM`。由 repo root 行。

1. `python tools/run_monthly_report.py --input "input/<pack>.xlsx" --period <YYYY-MM>`
   — LOAD → VALIDATE → KPI → CHARTS → DRAFT → EMAIL DRAFT；出 `monthly_report.pdf`；terminal 印 blocker / warning 數。
2. `python tools/generate_premium_html_report.py --input "input/<pack>.xlsx" --period <YYYY-MM>`
   — 出 `monthly_report_premium.html`（OpenDeedigital 品牌 dashboard）。
3. `python tools/visual_qa_report.py --report-dir outputs/monthly_report/<period> --simulate`
   — 逐張內嵌圖表 QA。
4. `python tools/export_premium_pdf.py --report-dir outputs/monthly_report/<period>`
   — 出 **`monthly_report_premium.pdf`**。
5. 停。回報：行咗邊啲 tool、blocker 同 warning 數、整體 RAG 狀態、**兩份 PDF 嘅完整路徑**。唔好開、唔好送、唔好改其他嘢。

如果被要求送出報告：行 `python tools/send_report_email.py --report-dir outputs/monthly_report/<period> --to <address> --send-approved`，
原文顯示佢嘅拒絕訊息，解釋要由人先清 blocker。永遠唔用 `--override-blockers`。

## Gate 關卡

- **Human-IN（事前批核）**：output 唔可以離開項目團隊，直至具名審核人清晒 blocker 並簽名。
- Criteria：Source（可追溯）· Accuracy（準確）· Risk（不可逆後果全面覆核）· Accountability（簽名存檔）。

## Style 風格

OpenDeedigital 品牌：`config/report_sections.json` 嘅 `brand` 區（主色 #F36B15 橙、副色 #9B0A68 紫紅、深色 #231F20、淺底 #FFF7F0）+ `brand_assets/ODD Logo.png`；狀態色 GO 綠 / CONTROL 黃 / STOP 紅。
Dashboard 同敘述報告都由呢個 config 取色；換公司改 config，唔使改 code。

## Outputs

`outputs/monthly_report/<period>/` — `review_gate_status.json` · `metrics.json` · `assets/` ·
`monthly_report.md/.html` · **`monthly_report.pdf`** · `email/` · `monthly_report_premium.html` ·
`visual_qa_status.json` · `visual_qa_report.html` · **`monthly_report_premium.pdf`**。
全部 DRAFT 直至有人簽名。

## Configuration

`config/report_sections.json`：報告章節、品牌色、email 預設收件人。改呢度，唔使改 code。
