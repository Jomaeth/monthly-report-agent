---
name: monthly-report-agent
description: >
  Turn a construction project's monthly Excel data pack into a governed,
  management-ready HTML health report. Use this skill whenever the user asks to
  generate, rebuild, or QA a monthly project report from a data pack (e.g.
  "run the monthly report for 2026-04", "出四月份月報", "generate the project
  health report"), or asks whether a monthly report is safe to distribute.
  The skill drafts; a named human always checks and signs before anything is sent.
---

# Monthly Report Agent 月度報告代理

## Intent 意圖

Produce the monthly project health report a Project Manager would otherwise
assemble by hand over ~2 days: read the project's Excel data pack, validate it,
compute KPIs and RAG status, render a branded HTML report — then **stop at the
human review gate**. 讀取項目 Excel 資料包 → 驗證 → 計算 KPI 與紅黃綠狀態 →
產出品牌化 HTML 報告 → 停在人手批核關卡。

The full plain-language SOP is `workflows/construction_monthly_report.md` —
read it when a step below needs more detail than this file gives.

## Principles 原則（不可妥協）

1. **AI drafts → Human checks → Human signs.** The report you produce is a
   DRAFT for review. AI 起草，人手覆核，人手簽發。
2. **Never send anything.** Do not email, publish, or distribute any output.
   The send tool exists to DEMONSTRATE refusal — it hard-stops while blockers
   remain, and even then only a human may run it. 絕不代發。
3. **Never infer missing data.** A blank cell is a Data Gap to be flagged,
   not a number to be guessed. 缺值只可標示，不可推斷。
4. **Do not modify sources.** The Excel data pack and these tools are
   read-only to you. 不修改資料來源與工具。
5. **Blockers are the product.** Surfacing what is wrong (and who must fix it
   by when) is worth more than a clean-looking report. 揭示問題比報表美觀更重要。

## Deterministic tools 確定性工具（動詞 → 工具）

| # | Verb | Tool (`tools/`) | What it does |
|---|------|------------------|--------------|
| 1 | LOAD | `load_data_pack.py` | Read all sheets of the Excel pack |
| 2 | VALIDATE | `validate_data_pack.py` | Recompute vs cached values → blockers & warnings |
| 3 | KPI | `calculate_monthly_kpis.py` | KPIs + overall RAG (GO / CONTROL / STOP) |
| 4 | CHARTS | `generate_report_charts.py` | Chart set for the classic report |
| 5 | DRAFT | `render_monthly_report.py` | Narrative sections (MD/HTML/PDF) |
| 6 | DASHBOARD | `generate_premium_html_report.py` | Branded premium HTML with embedded charts (`_v2.py` = SVG variant, not QA-readable) |
| 7 | QA | `visual_qa_report.py` | Visual QA of the rendered output (`--simulate` = offline) |
| 8 | GATE | `send_report_email.py` | Send gate — REFUSES while blockers remain |

Orchestrator: `run_monthly_report.py` runs 1–5 plus the email manifest in one
pass. Tools resolve their own paths — they work from any working directory.

## Standard run 標準執行（demo path）

Input: the Excel pack in `demo-data/` (`AI2C_Day2_Monthly_Report_Data_Pack_Demo.xlsx`).
Reporting period format: `YYYY-MM`. Run from the repo root.

1. `python tools/run_monthly_report.py --input "demo-data/AI2C_Day2_Monthly_Report_Data_Pack_Demo.xlsx" --period 2026-04`
   — LOAD → VALIDATE → KPI → CHARTS → DRAFT in one pass; prints blocker / warning counts and writes the email draft + manifest.
2. `python tools/generate_premium_html_report.py --input "demo-data/AI2C_Day2_Monthly_Report_Data_Pack_Demo.xlsx" --period 2026-04`
   — DASHBOARD: branded premium HTML with embedded charts (`monthly_report_premium.html`).
3. `python tools/visual_qa_report.py --report-dir outputs/monthly_report/2026-04 --simulate`
   — QA gate over every embedded chart (`--simulate` = offline, no API key).
4. Stop. Report back: which tools ran, blocker count and warning count, overall
   RAG status, and the full path of `monthly_report_premium.html`. Do not open,
   send, or edit anything else.

Optional: `generate_premium_html_report_v2.py` renders an SVG-based dashboard
(`monthly_report_premium_v2.html`). It is prettier but the visual QA tool cannot
read SVG charts — use it for the screen, not for the gate.

## Extended run 完整執行（orchestrator path）

When the user asks for the full pack (narrative + charts + email draft):
`python tools/run_monthly_report.py --input "demo-data/AI2C_Day2_Monthly_Report_Data_Pack_Demo.xlsx" --period 2026-04` — this also writes the
email manifest that the send gate checks. The gate demo
(`send_report_email.py --report-dir outputs/monthly_report/2026-04 --to
<reviewer> --send-approved`) must refuse while blockers exist; show the refusal
message verbatim — it is the governance moment, not an error.

## Review gates 批核關卡

- Gate type: **Human-IN（事前批核）** — output may not leave the project team
  until the named reviewer clears blockers and signs. 批核前不得外發。
- Criteria follow the four dimensions taught in AI2C: Source（可追溯）·
  Accuracy（準確）· Risk（不可逆後果全面覆核）· Accountability（簽名存檔）。

## Outputs 輸出

`outputs/monthly_report/<period>/` — premium HTML (`monthly_report_premium_v2.html`),
visual QA files, and (extended run) narrative MD/HTML/PDF, charts, email draft.
All outputs carry DRAFT status until a human signs.
