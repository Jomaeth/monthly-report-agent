# AGENTS.md

This repo is one agent skill: a project's monthly Excel data pack → validated KPIs → management report → review gate.

- Read `SKILL.md` and follow it exactly — rules, tool order, where to stop.
- Inputs live in `input/` (read-only). Write only under `outputs/`.
- Every number comes from the tools. Do not compute or "correct" KPIs yourself; missing data is flagged, never inferred.
- Never send, publish or distribute. `tools/send_report_email.py` refuses while blockers remain; never use `--override-blockers`.
- Do not install packages, download anything, or ask for permission to do so. If `export_premium_pdf.py` reports no Chrome/Edge, `monthly_report.pdf` is the PDF deliverable — say so and continue.
- Reply in the user's language (廣東話 / 繁體中文 / English).
