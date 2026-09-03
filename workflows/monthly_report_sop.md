# Construction Project Monthly Report Automation

## Objective

Generate a branded OpenDeedigital monthly construction project health report from the project Excel/CSV data pack. The workflow produces a Markdown report, HTML report, PDF report, chart PNGs, machine-readable metrics, review gate status, and a safe email draft package for distribution.

## Required Inputs

- Project data pack: Excel workbook or CSV folder containing project profile, progress, milestones, submissions/RFIs, procurement, safety/quality, commercial cost, risks/actions, metric dictionary, and review gates.
- Reporting period: `YYYY-MM`, usually supplied by CLI.
- Brand asset: `brand_assets/ODD Logo.png`.
- Report config: `config/report_sections.json`.
- Optional email recipients: CLI args or config defaults.
- Optional SMTP credentials: `.env` only, required only for explicit approved sending.

## Tools

- `tools/load_data_pack.py`: reads Excel/CSV inputs into normalized dataframes.
- `tools/validate_data_pack.py`: validates schema, key cross-links, formula integrity, data quality, and review gates.
- `tools/calculate_monthly_kpis.py`: recomputes KPI/RAG metrics and prepares report sections.
- `tools/generate_report_charts.py`: creates branded chart PNGs.
- `tools/render_monthly_report.py`: renders Markdown, HTML, and PDF outputs.
- `tools/prepare_report_email.py`: creates branded email body, `.eml` draft, and email manifest.
- `tools/generate_premium_html_report.py`: produces a self-contained management-ready HTML report (AI exec summary, 6 KPI cards, 8 charts, RAG-coloured tables, gate panel) with logo and charts inlined as base64.
- `tools/visual_qa_report.py`: Visual QA gate — extracts every chart from the rendered HTML and asks Gemini 2.5 Flash Vision whether all labels, numbers, axes, and legends are clearly readable and unclipped. Writes `visual_qa_status.json` and `visual_qa_report.html`.
- `tools/send_report_email.py`: sends only with explicit approval flag, credentials, recipients, and gate checks. Refuses if blockers exist OR if `visual_qa_status.json` is missing / not `pass`.
- `tools/run_monthly_report.py`: orchestrates the full workflow.

## Procedure

1. Confirm the input file/folder exists and the ODD logo is available.
2. Load source sheets and normalize sheet names without changing the source workbook.
3. Validate required sheets, required columns, record links, report-as-of date, cached formula values, safety evidence, and review gates.
4. Recompute monthly KPIs from source values instead of trusting hidden workbook formulas.
5. Generate branded PNG charts under the report assets folder.
6. Render Markdown, HTML, PDF, `metrics.json`, and `review_gate_status.json`.
7. Generate the premium HTML report (`tools/generate_premium_html_report.py`) — single self-contained file with AI executive summary, KPI dashboard, 8 charts, RAG-coloured tables, gate panel.
8. Run the Visual QA gate (`tools/visual_qa_report.py`) — Gemini Vision reviews every chart for readability; produces `visual_qa_status.json` (pass / fail / pending) and `visual_qa_report.html`. **A numbers-only validator cannot catch chart-label clipping; the Visual QA gate exists specifically for that class of bug.**
9. Generate a branded email draft and `.eml` package for human review.
10. Mark the package as `Draft with blockers` until the human review gates are cleared AND Visual QA status is `pass`.
11. Send email only after human approval, only when the send command includes `--send-approved`, only when no blockers remain (or `--override-blockers` is supplied with documented sign-off), AND only when Visual QA status is `pass` (or `--override-visual-qa` with documented eye-check).

## Expected Outputs

- `outputs/monthly_report/<period>/monthly_report.md`
- `outputs/monthly_report/<period>/monthly_report.html`
- `outputs/monthly_report/<period>/monthly_report.pdf`
- `outputs/monthly_report/<period>/assets/*.png`
- `outputs/monthly_report/<period>/metrics.json`
- `outputs/monthly_report/<period>/review_gate_status.json`
- `outputs/monthly_report/<period>/email/email_draft.md`
- `outputs/monthly_report/<period>/email/email_draft.html`
- `outputs/monthly_report/<period>/email/monthly_report_email.eml`
- `outputs/monthly_report/<period>/email/email_manifest.json`
- `outputs/monthly_report/<period>/monthly_report_premium.html` (premium management-ready HTML, charts + logo inlined as base64)
- `outputs/monthly_report/<period>/visual_qa_status.json` (Visual QA verdict per chart + overall pass/fail)
- `outputs/monthly_report/<period>/visual_qa_report.html` (human-readable Visual QA review with thumbnails)

## Verification

- Check all expected outputs exist and are non-empty.
- Confirm the ODD logo appears in Markdown, HTML, PDF, and the report asset folder.
- Confirm critical examples such as overdue RFI and red/amber risk rows appear in exception sections.
- Confirm blocker/review status is visible in every output format.
- Confirm chart images are generated and referenced correctly.
- Confirm email draft subject, recipients, status warning, and attachments are correct.
- Confirm no email is sent unless explicit approval and credentials are provided.

## Edge Cases

- Missing source sheet or required column: generate validation blockers and still render a draft where possible.
- Missing ODD logo: continue with text branding and create a blocker.
- Stale Excel formulas: compare cached formulas against Python recomputation and flag mismatches.
- Missing linked IDs: show cross-link blockers in the review gate section.
- Commercial, EOT, VO, RFI, and claim-sensitive wording: require PM/QS or technical review before publishing.
- Email distribution: never send when `Draft with blockers` unless a human deliberately overrides the gate.
- Visual QA failure: when chart labels clip / overlap / become unreadable, the Visual QA gate must fail and block send. Re-render after fixing chart code, then re-run Visual QA. Override only with documented human eye-check via `--override-visual-qa`.
- Visual QA offline: when there is no internet access, run `tools/visual_qa_report.py --simulate` for reproducible findings, or `--dry-run` to print the prompt without an API call.

## Lessons Learned

- Keep business rules visible in the workbook metric dictionary and review gate sheets whenever possible.
- Use deterministic Python calculations for report-critical values, while treating Excel formulas as source audit evidence.
