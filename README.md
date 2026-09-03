# Monthly Report Agent 月度報告代理

> **AI drafts · Human checks · Human signs**
> 一條完整的 agentic workflow：讀一份 Excel 月度資料包 → 驗證 → 計 KPI → 出一份管理層可讀的 HTML 報告 → **停在人手批核關卡**

This repo is a self-contained teaching demo. Clone it, open the folder in **Codex** (or Claude Code / any agent that reads `SKILL.md`), and give it the prompt below. Everything it needs — the skill, the deterministic Python tools, and a dummy data pack — is inside.

呢個 repo 係一個自足嘅教學示範。Clone 落嚟，用 **Codex** 開呢個 folder，貼下面個 prompt 就得。Skill、確定性 Python tools、dummy 資料包全部喺入面。

---

## 30-second demo 三十秒示範

```bash
git clone --depth 1 https://github.com/Jomaeth/monthly-report-agent.git
cd monthly-report-agent
pip install -r requirements.txt
```

Open the folder in Codex and paste:

```
跟住 SKILL.md 做：用 demo-data 入面個 Excel 資料包，出 2026-04 嘅月度報告，然後做 visual QA。
最後話我知：行咗邊幾個 tool、有幾多個 blocker、整體 RAG 狀態、同 HTML 報告嘅路徑。
```

The agent runs the tools in order — validate, KPIs, charts, narrative, then the branded dashboard `outputs/monthly_report/2026-04/monthly_report_premium.html` — runs the visual QA gate, and **stops**. It will not send, publish, or "fix" anything. The data pack ships with 4 deliberate blockers; surfacing them is the point.

---

## What is inside 入面有咩

```
monthly-report-agent/
├── SKILL.md                 ← the agent reads this first (Intent · Principles · Tools · Gates)
├── AGENTS.md                ← Codex entry point → points to SKILL.md
├── workflows/
│   └── construction_monthly_report.md   ← plain-language SOP (how a PM does it by hand)
├── tools/                   ← deterministic Python (the agent calls these; it never guesses numbers)
│   ├── load_data_pack.py                  LOAD       read all 13 sheets
│   ├── validate_data_pack.py              VALIDATE   recompute vs cached → blockers & warnings
│   ├── calculate_monthly_kpis.py          KPI        KPIs + overall RAG (GO / CONTROL / STOP)
│   ├── generate_report_charts.py          CHARTS
│   ├── render_monthly_report.py           DRAFT      narrative MD / HTML / PDF
│   ├── generate_premium_html_report.py    DASHBOARD  branded premium HTML (v2 = SVG variant)
│   ├── visual_qa_report.py                QA         vision-model gate (--simulate = offline)
│   ├── send_report_email.py               GATE       refuses while blockers remain
│   └── run_monthly_report.py              orchestrator
├── demo-data/
│   └── AI2C_Day2_Monthly_Report_Data_Pack_Demo.xlsx   ← dummy project: Harbourview Commercial Tower
├── config/  brand_assets/  specs/  tests/
└── outputs/                 ← generated here (gitignored)
```

**The data pack is fictional.** Harbourview Commercial Tower, Wan Tsun E&M Engineering, Harbour Gate Construction and every number in the workbook were created for teaching. 資料包內所有公司、項目、數字均為教學虛構。

---

## Why this shape 點解咁設計

| Layer | What | Why it matters |
|---|---|---|
| **Workflow** (`workflows/*.md`) | The SOP a human PM follows | The practitioner writes this — not a programmer |
| **Agent** (Codex / Claude / Gemini) | Reads the SOP, decides which tool to call next | Handles understanding and judgement calls |
| **Tools** (`tools/*.py`) | Deterministic code | Numbers are computed, never hallucinated |
| **Gates** (validator · visual QA · send gate) | Hard stops | Nothing leaves the team until a named human signs |

The same pattern works for any repetitive document: monthly report, quotation, tender comparison, HR form. Change the SOP and the tools; keep the gates. See the sister repo [tender-comparison-agent](https://github.com/Jomaeth/tender-comparison-agent).

---

## Governance demo 治理示範

Ask the agent to send the report:

```
把報告 email 俾 reviewer@example.com
```

`send_report_email.py` **refuses** — the data pack ships with deliberate blockers. The refusal message is the lesson, not an error.

---

## Requirements

Python 3.10+ · `pip install -r requirements.txt` (pandas, openpyxl, matplotlib, reportlab, Pillow).
No API keys needed for the standard run (`--simulate` QA). Real vision QA needs `GEMINI_API_KEY` in `.env`.

---

Built by [OpenDeedigital](https://opendeedigital.io) · Johnny K.C. Ma · [johnnyma.ai](https://johnnyma.ai)
Teaching reference for the HKIC AI2C course and CEF AI courses. Code: MIT. SOP text: CC BY 4.0.
