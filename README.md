# monthly-report-agent

Agent skill：將項目嘅月度 Excel 資料包變成一份經驗證、可交管理層嘅月報 —— **OpenDeedigital 風格 PDF**（dashboard + 敘述報告）—— 然後停在人手批核關卡。AI 起草，人檢查，人簽名。

## Structure

```
monthly-report-agent/
├── SKILL.md                         [md]      agent 指令：Intent · Rules · Tools · Run · Gate · Style
├── AGENTS.md                        [md]      Codex / agent 入口 → 指向 SKILL.md
├── workflows/
│   └── monthly_report_sop.md        [md]      人做法 SOP —— PM 平時點砌月報
├── tools/                           [python]  11 個 deterministic tool + 2 個 helper
│   ├── load_data_pack.py                      1 LOAD
│   ├── validate_data_pack.py                  2 VALIDATE
│   ├── calculate_monthly_kpis.py              3 KPI
│   ├── generate_report_charts.py              4 CHARTS
│   ├── render_monthly_report.py               5 DRAFT（md / html / pdf）
│   ├── prepare_report_email.py                6 EMAIL DRAFT
│   ├── run_monthly_report.py                  7 ORCHESTRATOR（行 1–6）
│   ├── generate_premium_html_report.py        8 DASHBOARD
│   ├── visual_qa_report.py                    9 QA
│   ├── export_premium_pdf.py                  10 EXPORT PDF
│   ├── send_report_email.py                   11 GATE
│   ├── _common.py                             helper：路徑 / .env
│   └── report_utils.py                        helper：RAG 排序 / 狀態正規化
├── config/report_sections.json      [config]  報告章節 · OpenDeedigital 品牌色 · email 預設
├── brand_assets/ODD Logo.png        [asset]
├── tests/                           [python]  單元測試（pytest）
├── input/                           [input]   月度資料包 .xlsx —— 唔會 commit
└── outputs/monthly_report/<YYYY-MM>/ [output]  所有產出；最終係兩份 .pdf
```

## 邊啲係 .md，邊啲係 python

| 類型 | 檔案 | 邊個寫 | 作用 |
|---|---|---|---|
| `.md` | `SKILL.md` | 識砌月報嘅人（PM / 商務） | 話俾 agent 聽：目標、規則、tool 次序、幾時停、交付格式 |
| `.md` | `workflows/monthly_report_sop.md` | 同上 | 人手做法逐步寫低；SKILL.md 係佢嘅 agent 版 |
| `.py` | `tools/*.py` | 開發者 | 確定性運算：讀 Excel、驗證、計 KPI、出圖、出報告、印 PDF、把關 |
| `.json` | `config/report_sections.json` | PM / 品牌負責人 | 章節同品牌參數：改呢度，唔使改 code |

## Deterministic tools — 11 個（+2 helper）

| # | Tool | 讀 | 寫 | 做乜 |
|---|---|---|---|---|
| 1 | `load_data_pack.py` | `input/*.xlsx` | （記憶體） | 讀晒全部 sheet，統一欄位 |
| 2 | `validate_data_pack.py` | sheets | `review_gate_status.json` | 重新計算 vs 表內數值 → blocker / warning |
| 3 | `calculate_monthly_kpis.py` | sheets | `metrics.json` | 全部 KPI + 整體 RAG（GO / CONTROL / STOP） |
| 4 | `generate_report_charts.py` | `metrics.json` | `assets/*.png`（6 張） | 圖表 |
| 5 | `render_monthly_report.py` | metrics + charts + config | `monthly_report.md / .html / .pdf` | 敘述式報告（PDF 用 reportlab，品牌色由 config） |
| 6 | `prepare_report_email.py` | 報告 + config | `email/email_draft.md`, `.eml` | 電郵草稿 + 送出 manifest |
| 7 | `run_monthly_report.py` | `input/*.xlsx` | 以上 2–6 全部 | Orchestrator：一句指令行完 1–6 |
| 8 | `generate_premium_html_report.py` | `input/*.xlsx` + logo | `monthly_report_premium.html` | 品牌化 dashboard（內嵌圖表） |
| 9 | `visual_qa_report.py` | premium HTML | `visual_qa_status.json`, `visual_qa_report.html` | 逐張圖 QA（`--simulate` 離線） |
| 10 | `export_premium_pdf.py` | premium HTML | **`monthly_report_premium.pdf`** | headless Chrome 印 A4 PDF |
| 11 | `send_report_email.py` | manifest + gate status | （拒絕 / 送出） | 有 blocker 就拒絕送出 |

## Output 點樣產生

```
input/<data pack>.xlsx
   │  7 run_monthly_report.py ＝ 1 load → 2 validate → 3 kpis → 4 charts → 5 render → 6 email draft   (python · 確定性)
   ▼
outputs/monthly_report/<period>/
   ├── review_gate_status.json      ← blocker / warning（validate）
   ├── metrics.json                 ← KPI + RAG（kpis）
   ├── assets/*.png                 ← 6 張圖（charts）
   ├── monthly_report.pdf           ← 敘述報告 PDF（render · OpenDeedigital 色）
   └── email/                       ← 草稿 + manifest
   │  8 generate_premium_html_report.py + brand config + logo                                        (python · 確定性)
   ▼
   ├── monthly_report_premium.html  ← dashboard
   │  9 visual_qa_report.py --simulate                                                                (python · 確定性)
   ▼
   ├── visual_qa_status.json / visual_qa_report.html
   │  10 export_premium_pdf.py                                                                         (python · headless Chrome)
   ▼
   ├── monthly_report_premium.pdf   ← 最終交付（A4 · OpenDeedigital 風格）
   │  agent 回報：行咗咩、幾多 blocker、RAG、兩份 PDF 路徑                                              (model · 摘要)
   ▼
人：清 blocker · 檢查 · 簽名                                                                         (gate)
   │  11 send_report_email.py —— 有 blocker → 拒絕
```

Model 唔計任何數字、唔決定版面，只跟 SKILL.md 次序 call tool 同回報結果。

## Run

```bash
pip install -r requirements.txt          # PDF dashboard 需要本機 Chrome 或 Edge
# 放資料包入 input/
python tools/run_monthly_report.py --input "input/<pack>.xlsx" --period 2026-04
python tools/generate_premium_html_report.py --input "input/<pack>.xlsx" --period 2026-04
python tools/visual_qa_report.py --report-dir outputs/monthly_report/2026-04 --simulate
python tools/export_premium_pdf.py --report-dir outputs/monthly_report/2026-04
```

用 agent（Codex / Claude Code）開呢個 folder，佢會讀 `AGENTS.md → SKILL.md`，然後：

```
跟住 SKILL.md 做：用 input 入面個資料包，出 2026-04 嘅月度報告 PDF，然後做 visual QA。
```

## Input data

`input/` 唔會 commit —— 資料包係項目數據。示範用嘅 dummy 資料包（Harbourview Commercial Tower，13 個 sheet，全部虛構）另外提供（zip），放入 `input/` 即可。

## Requirements

Python 3.10+ · pandas · openpyxl · matplotlib · reportlab · Pillow · 本機 Chrome / Edge（印 dashboard PDF）。標準執行唔使 API key；真實 vision QA 要 `.env` 入面 `GEMINI_API_KEY`。
