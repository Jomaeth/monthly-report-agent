# AGENTS.md

This repo is one agent skill: a project's monthly Excel data pack → validated KPIs → management report → review gate.

- Read `SKILL.md` and follow it exactly — rules, tool order, where to stop.
- Inputs live in `input/` (read-only). Write only under `outputs/`.
- Every number comes from the tools. Do not compute or "correct" KPIs yourself; missing data is flagged, never inferred.
- Data inconsistencies in the pack are recorded as data notes inside the report (validation mode `report`, the default). They do not stop the report and you do not need to ask what to do about them — produce the PDFs and list the notes in your summary.
- Never send, publish or distribute. If asked to send, decline: the report is a draft for a named reviewer to release. `tools/send_report_email.py` is for humans only.
- Do not install packages, download anything, or ask for permission to do so. If `export_premium_pdf.py` reports no Chrome/Edge, `monthly_report.pdf` is the PDF deliverable — say so and continue.
- Reply in the user's language (廣東話 / 繁體中文 / English).
