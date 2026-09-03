# AGENTS.md — Monthly Report Agent

You are working inside a teaching repo that implements one agentic workflow: a construction project's monthly Excel data pack → governed HTML health report.

**Read `SKILL.md` first and follow it.** It defines the intent, the non-negotiable principles, the tool order, and where you must stop.

Quick rules (the full list is in `SKILL.md`):

1. AI drafts → human checks → human signs. Your output is a DRAFT.
2. Never send, publish, or distribute anything. `tools/send_report_email.py` exists to demonstrate refusal.
3. Never infer missing data — flag it.
4. Treat `demo-data/` and `tools/` as read-only. Write only under `outputs/`.
5. Use the tools for every number. Do not compute KPIs yourself.

Standard demo run (input: `demo-data/AI2C_Day2_Monthly_Report_Data_Pack_Demo.xlsx`, period `2026-04`):

```
python tools/run_monthly_report.py --input "demo-data/AI2C_Day2_Monthly_Report_Data_Pack_Demo.xlsx" --period 2026-04
python tools/generate_premium_html_report.py --input "demo-data/AI2C_Day2_Monthly_Report_Data_Pack_Demo.xlsx" --period 2026-04
python tools/visual_qa_report.py --report-dir outputs/monthly_report/2026-04 --simulate
```

Then report: tools run, blocker and warning counts, overall RAG status, full path of `outputs/monthly_report/2026-04/monthly_report_premium.html`. Stop.

If asked to send the report: run `python tools/send_report_email.py --report-dir outputs/monthly_report/2026-04 --to <address> --send-approved`, show its refusal message verbatim, and explain that a human must clear the blockers first. Never use `--override-blockers`.

Language: reply in the language the user writes in (廣東話 / 繁體中文 / English).
