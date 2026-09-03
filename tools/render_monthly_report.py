from __future__ import annotations

from pathlib import Path
import html
import json

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image as PdfImage
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

try:
    from .report_utils import clean_text, json_ready
except ImportError:  # pragma: no cover
    from report_utils import clean_text, json_ready


def _fmt_pct(value: object) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return clean_text(value, "-")


def _fmt_money(value: object) -> str:
    if value is None:
        return "-"
    try:
        return f"HK${float(value):.2f}M"
    except (TypeError, ValueError):
        return clean_text(value, "-")


def _md_table(headers: list[str], rows: list[list[object]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(clean_text(cell, "-").replace("\n", " ") for cell in row) + " |")
    return "\n".join(lines)


def _chart_md(report_model: dict[str, object], chart_id: str) -> str:
    chart = report_model.get("charts", {}).get(chart_id)
    if not chart:
        return ""
    return f"\n![{chart['title']}]({chart['relative_path']})\n"


def _top_rows(records: list[dict[str, object]], fields: list[str], limit: int = 6) -> list[list[object]]:
    return [[record.get(field) for field in fields] for record in records[:limit]]


def render_markdown(report_model: dict[str, object], config: dict[str, object], output_dir: Path) -> Path:
    brand = config.get("brand", {})
    report = config.get("report", {})
    profile = report_model.get("profile", {})
    metrics = report_model.get("metrics", {})
    validation = report_model.get("validation", {})
    logo = report_model.get("brand", {}).get("logo_asset", brand.get("logo_path", ""))

    lines: list[str] = [
        f"![{brand.get('name', 'OpenDeedigital')}]({logo})",
        "",
        f"# {report.get('title', 'Construction Project Monthly Health Report')}",
        "",
        f"**Brand:** {brand.get('name', 'OpenDeedigital')}  ",
        f"**Status:** {report_model.get('meta', {}).get('report_status', 'Draft with blockers')}  ",
        f"**Reporting Period:** {report_model.get('meta', {}).get('period') or '-'}  ",
        f"**Report As Of:** {report_model.get('meta', {}).get('report_as_of') or '-'}  ",
        f"**Source:** `{report_model.get('meta', {}).get('source_path')}`",
        "",
        "## Project Profile",
        "",
        _md_table(
            ["Field", "Value"],
            [
                ["Project ID", profile.get("Project_ID")],
                ["Project Name", profile.get("Project_Name")],
                ["Contract No.", profile.get("Contract_No")],
                ["Subcontractor", profile.get("Subcontractor")],
                ["Client / Main Contractor", profile.get("Client_Main_Contractor")],
            ],
        ),
        "",
        "## Executive Summary",
        "",
    ]
    lines.extend(f"- {finding}" for finding in report_model.get("executive_summary", {}).get("findings", []))

    progress = metrics.get("progress", {})
    programme = metrics.get("programme_milestones", {})
    rfi = metrics.get("submission_rfi", {})
    procurement = metrics.get("procurement", {})
    safety = metrics.get("safety_quality", {})
    commercial = metrics.get("commercial_cost", {})
    risks = metrics.get("risk_action_decision", {})

    lines.extend(
        [
            "",
            "## Data Quality And Review Gates",
            "",
            f"Validation found **{validation.get('issue_counts', {}).get('blocker', 0)} blocker(s)** and **{validation.get('issue_counts', {}).get('warning', 0)} warning(s)**.",
            "",
            _md_table(
                ["Gate", "Section", "Reviewer", "Status", "Blockers"],
                _top_rows(validation.get("review_gates", []), ["gate_id", "section", "reviewer", "status", "blocker_count"], 20),
            ),
            "",
            "### Blockers And Warnings",
            "",
            _md_table(
                ["Severity", "Section", "Record", "Message"],
                _top_rows(validation.get("issues", []), ["severity", "section", "record_id", "message"], 20),
            ),
            "",
            "## Progress By Zone / Trade",
            "",
            _chart_md(report_model, "progress_by_zone"),
            _md_table(
                ["ID", "Zone", "Trade", "Activity", "Variance", "RAG", "Action", "Owner"],
                [
                    [
                        item.get("id"),
                        item.get("zone"),
                        item.get("trade"),
                        item.get("activity"),
                        _fmt_pct(item.get("variance_pct")),
                        item.get("rag"),
                        item.get("action"),
                        item.get("owner"),
                    ]
                    for item in progress.get("exceptions", [])
                ],
            ),
            "",
            "## Programme And Milestones",
            "",
            _chart_md(report_model, "milestone_delay"),
            _md_table(
                ["ID", "Milestone", "Delay Days", "Critical", "RAG", "Recovery Action", "Owner"],
                _top_rows(programme.get("delayed", []), ["id", "name", "variance_days", "critical_path", "rag", "recovery_action", "owner"]),
            ),
            "",
            "## Submission / RFI Bottlenecks",
            "",
            _chart_md(report_model, "rfi_aging"),
            _md_table(
                ["ID", "Type", "Trade", "Days", "Impact Days", "RAG", "Escalate", "Responsible"],
                _top_rows(rfi.get("bottlenecks", []), ["id", "type", "trade", "days_open_overdue", "programme_impact_days", "rag", "escalation_required", "responsible_person"]),
            ),
            "",
            "## Procurement Delivery Risk",
            "",
            _chart_md(report_model, "procurement_variance"),
            _md_table(
                ["ID", "Description", "Package", "Variance Days", "RAG", "Action", "Owner"],
                _top_rows(procurement.get("risks", []), ["id", "description", "package", "variance_days", "rag", "action", "owner"]),
            ),
            "",
            "## Safety / Quality",
            "",
            _md_table(
                ["ID", "Category", "Issue", "Area", "Days Overdue", "RAG", "Action", "Evidence"],
                _top_rows(safety.get("exceptions", []), ["id", "category", "metric_or_issue", "area", "days_overdue", "rag", "action_required", "evidence_ref"]),
            ),
            "",
            "## Commercial Cost",
            "",
            _chart_md(report_model, "commercial_movement"),
        ]
    )

    current = commercial.get("current") or {}
    movement = commercial.get("movement") or {}
    lines.extend(
        [
            _md_table(
                ["Metric", "Current", "Movement"],
                [
                    ["Contract Sum with VO", _fmt_money(current.get("contract_sum_with_vo_hkd_m")), "-"],
                    ["Current GP", _fmt_money(current.get("current_gp_hkd_m")), _fmt_money(movement.get("current_gp_hkd_m"))],
                    ["GP vs Objective", _fmt_money(current.get("gp_vs_objective_hkd_m")), _fmt_money(movement.get("gp_vs_objective_hkd_m"))],
                    ["Net Cashflow", _fmt_money(current.get("nett_cashflow_hkd_m")), _fmt_money(movement.get("nett_cashflow_hkd_m"))],
                    ["Risk Exposure", _fmt_money(current.get("risk_exposure_hkd_m")), _fmt_money(movement.get("risk_exposure_hkd_m"))],
                    ["RAG", current.get("rag"), "-"],
                ],
            ),
            "",
            "## Risk Action Decision Log",
            "",
            _chart_md(report_model, "rag_mix"),
            _md_table(
                ["ID", "Category", "Description", "Decision Required", "RAG", "Reviewer"],
                _top_rows(risks.get("open_items", []), ["id", "category", "description", "decision_required", "rag", "human_review_gate"], 10),
            ),
            "",
            "## Appendix Metrics",
            "",
            _md_table(
                ["Workstream", "RAG Counts"],
                [
                    ["Progress", progress.get("rag_counts")],
                    ["Programme", programme.get("rag_counts")],
                    ["Submission / RFI", rfi.get("rag_counts")],
                    ["Procurement", procurement.get("rag_counts")],
                    ["Safety / Quality", safety.get("rag_counts")],
                    ["Commercial", commercial.get("rag_counts")],
                    ["Risk / Action", risks.get("rag_counts")],
                ],
            ),
        ]
    )
    output = output_dir / "monthly_report.md"
    output.write_text("\n".join(lines), encoding="utf-8")
    return output


def render_html(report_model: dict[str, object], config: dict[str, object], markdown_path: Path, output_dir: Path) -> Path:
    brand = config.get("brand", {})
    primary = brand.get("primary_color", "#F36B15")
    secondary = brand.get("secondary_color", "#9B0A68")
    dark = brand.get("dark_color", "#231F20")
    light = brand.get("light_color", "#FFF7F0")
    logo = report_model.get("brand", {}).get("logo_asset", brand.get("logo_path", ""))
    md_text = markdown_path.read_text(encoding="utf-8")

    # A compact purpose-built renderer for the report structure. The Markdown is
    # still the audit source; HTML gets a branded readable equivalent.
    body_parts = []
    in_table = False
    for line in md_text.splitlines():
        if line.startswith("| ---"):
            continue
        if line.startswith("| "):
            cells = [html.escape(part.strip()) for part in line.strip("|").split("|")]
            if not in_table:
                body_parts.append("<table><tr>" + "".join(f"<th>{cell}</th>" for cell in cells) + "</tr>")
                in_table = True
            else:
                body_parts.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>")
            continue
        if in_table:
            body_parts.append("</table>")
            in_table = False

        if line.startswith("!["):
            alt = html.escape(line.split("]", 1)[0].lstrip("!["))
            src = html.escape(line.split("(", 1)[1].rstrip(")")) if "(" in line else html.escape(logo)
            css_class = "logo" if "logo" in src.lower() else "chart"
            body_parts.append(f'<img class="{css_class}" src="{src}" alt="{alt}">')
        elif line.startswith("# "):
            body_parts.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            body_parts.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("### "):
            body_parts.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("- "):
            body_parts.append(f"<p class=\"finding\">{html.escape(line[2:])}</p>")
        elif line.strip() == "":
            continue
        elif line.startswith("**"):
            body_parts.append(f"<p class=\"meta\">{html.escape(line)}</p>")
        else:
            body_parts.append(f"<p>{html.escape(line)}</p>")
    if in_table:
        body_parts.append("</table>")

    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(config.get("report", {}).get("title", "Monthly Report"))}</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; color: {dark}; background: #fff; }}
    body::before {{ content: ""; display: block; height: 14px; background: linear-gradient(90deg, {primary}, {secondary}); }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 28px 36px 64px; }}
    .logo {{ max-width: 360px; height: auto; margin: 16px 0 10px; }}
    h1 {{ color: {dark}; margin: 8px 0 10px; font-size: 34px; }}
    h2 {{ border-left: 8px solid {primary}; padding-left: 12px; margin-top: 34px; color: {secondary}; }}
    h3 {{ color: {dark}; margin-top: 24px; }}
    .meta {{ color: #555; line-height: 1.45; }}
    .finding {{ background: {light}; border-left: 5px solid {primary}; padding: 10px 14px; }}
    img:not(.logo) {{ max-width: 100%; border: 1px solid #eee; margin: 10px 0 18px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0 22px; font-size: 13px; }}
    th {{ background: {secondary}; color: white; text-align: left; padding: 8px; }}
    td {{ border-bottom: 1px solid #e5e5e5; padding: 8px; vertical-align: top; }}
    tr:nth-child(even) td {{ background: #fafafa; }}
  </style>
</head>
<body>
<main>
{chr(10).join(body_parts)}
</main>
</body>
</html>
"""
    output = output_dir / "monthly_report.html"
    output.write_text(html_text, encoding="utf-8")
    return output


def _pdf_table(rows: list[list[object]], widths: list[float] | None = None) -> Table:
    table = Table([[clean_text(cell, "-") for cell in row] for row in rows], colWidths=widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#9B0A68")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#DDDDDD")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
            ]
        )
    )
    return table


def render_pdf(report_model: dict[str, object], config: dict[str, object], output_dir: Path) -> Path:
    output = output_dir / "monthly_report.pdf"
    doc = SimpleDocTemplate(str(output), pagesize=A4, rightMargin=34, leftMargin=34, topMargin=34, bottomMargin=34)
    styles = getSampleStyleSheet()
    brand = config.get("brand", {})
    title_style = ParagraphStyle(
        "ODDTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        textColor=colors.HexColor(brand.get("secondary_color", "#9B0A68")),
        fontSize=22,
        leading=26,
    )
    heading = ParagraphStyle("ODDHeading", parent=styles["Heading2"], textColor=colors.HexColor(brand.get("primary_color", "#F36B15")))
    normal = ParagraphStyle("ODDNormal", parent=styles["BodyText"], fontSize=8.5, leading=11)
    story = []

    logo = report_model.get("brand", {}).get("logo_asset")
    if logo:
        logo_path = output_dir / logo
        if logo_path.exists():
            story.append(PdfImage(str(logo_path), width=3.2 * inch, height=0.55 * inch))
            story.append(Spacer(1, 8))
    story.append(Paragraph(config.get("report", {}).get("title", "Construction Project Monthly Health Report"), title_style))
    story.append(Paragraph(f"Status: {report_model.get('meta', {}).get('report_status')} | Period: {report_model.get('meta', {}).get('period')} | As of: {report_model.get('meta', {}).get('report_as_of')}", normal))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Executive Summary", heading))
    for finding in report_model.get("executive_summary", {}).get("findings", []):
        story.append(Paragraph(f"- {html.escape(clean_text(finding))}", normal))
    story.append(Spacer(1, 8))

    validation = report_model.get("validation", {})
    story.append(Paragraph("Review Gates", heading))
    gate_rows = [["Gate", "Section", "Reviewer", "Status", "Blockers"]]
    for gate in validation.get("review_gates", [])[:14]:
        gate_rows.append([gate.get("gate_id"), gate.get("section"), gate.get("reviewer"), gate.get("status"), gate.get("blocker_count")])
    story.append(_pdf_table(gate_rows, [0.7 * inch, 1.3 * inch, 1.3 * inch, 1.0 * inch, 0.6 * inch]))
    story.append(PageBreak())

    metrics = report_model.get("metrics", {})
    chart_order = [
        ("progress_by_zone", "Progress Exceptions", metrics.get("progress", {}).get("exceptions", []), ["id", "zone", "trade", "variance_pct", "rag", "owner"]),
        ("milestone_delay", "Programme Delays", metrics.get("programme_milestones", {}).get("delayed", []), ["id", "name", "variance_days", "rag", "owner"]),
        ("rfi_aging", "Submission / RFI Bottlenecks", metrics.get("submission_rfi", {}).get("bottlenecks", []), ["id", "type", "days_open_overdue", "programme_impact_days", "rag", "responsible_person"]),
        ("procurement_variance", "Procurement Risks", metrics.get("procurement", {}).get("risks", []), ["id", "description", "variance_days", "rag", "owner"]),
    ]
    for chart_id, title, records, fields in chart_order:
        story.append(Paragraph(title, heading))
        chart = report_model.get("charts", {}).get(chart_id)
        if chart:
            chart_path = output_dir / chart["relative_path"]
            if chart_path.exists():
                story.append(PdfImage(str(chart_path), width=6.7 * inch, height=4.0 * inch))
        rows = [[field.replace("_", " ").title() for field in fields]]
        rows.extend(_top_rows(records, fields, 6))
        story.append(_pdf_table(rows))
        story.append(Spacer(1, 10))

    story.append(PageBreak())
    story.append(Paragraph("Commercial Cost", heading))
    commercial = metrics.get("commercial_cost", {})
    chart = report_model.get("charts", {}).get("commercial_movement")
    if chart:
        chart_path = output_dir / chart["relative_path"]
        if chart_path.exists():
            story.append(PdfImage(str(chart_path), width=6.7 * inch, height=4.0 * inch))
    current = commercial.get("current") or {}
    movement = commercial.get("movement") or {}
    story.append(
        _pdf_table(
            [
                ["Metric", "Current", "Movement"],
                ["Current GP", _fmt_money(current.get("current_gp_hkd_m")), _fmt_money(movement.get("current_gp_hkd_m"))],
                ["GP vs Objective", _fmt_money(current.get("gp_vs_objective_hkd_m")), _fmt_money(movement.get("gp_vs_objective_hkd_m"))],
                ["Net Cashflow", _fmt_money(current.get("nett_cashflow_hkd_m")), _fmt_money(movement.get("nett_cashflow_hkd_m"))],
                ["Risk Exposure", _fmt_money(current.get("risk_exposure_hkd_m")), _fmt_money(movement.get("risk_exposure_hkd_m"))],
                ["RAG", current.get("rag"), "-"],
            ]
        )
    )

    story.append(Paragraph("Risk Action Decision Log", heading))
    rows = [["ID", "Category", "Description", "Decision", "RAG", "Reviewer"]]
    rows.extend(_top_rows(metrics.get("risk_action_decision", {}).get("open_items", []), ["id", "category", "description", "decision_required", "rag", "human_review_gate"], 8))
    story.append(_pdf_table(rows))
    doc.build(story)
    return output


def render_report_package(report_model: dict[str, object], config: dict[str, object], output_dir: str | Path) -> dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    metrics_path = output_dir / "metrics.json"
    gates_path = output_dir / "review_gate_status.json"
    metrics_path.write_text(json.dumps(json_ready(report_model), indent=2, ensure_ascii=False), encoding="utf-8")
    gates_path.write_text(json.dumps(json_ready(report_model.get("validation", {}).get("review_gates", [])), indent=2, ensure_ascii=False), encoding="utf-8")

    markdown_path = render_markdown(report_model, config, output_dir)
    html_path = render_html(report_model, config, markdown_path, output_dir)
    pdf_path = render_pdf(report_model, config, output_dir)

    return {
        "markdown": str(markdown_path),
        "html": str(html_path),
        "pdf": str(pdf_path),
        "metrics": str(metrics_path),
        "review_gates": str(gates_path),
    }
