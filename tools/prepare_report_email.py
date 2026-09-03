from __future__ import annotations

import argparse
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
import json
import mimetypes
from pathlib import Path

try:
    from ._common import project_path
    from .report_utils import clean_text
except ImportError:  # pragma: no cover
    from _common import project_path
    from report_utils import clean_text


def _resolve_report_dir(path: str | Path) -> Path:
    report_dir = Path(path)
    if not report_dir.is_absolute():
        report_dir = project_path(str(report_dir))
    return report_dir.resolve()


def load_email_config(path: str | Path) -> dict[str, object]:
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = project_path(str(config_path))
    config = json.loads(config_path.read_text(encoding="utf-8"))
    brand = config.setdefault("brand", {})
    logo_path = Path(str(brand.get("logo_path", "")))
    if logo_path and not logo_path.is_absolute():
        brand["logo_path"] = str(project_path(str(logo_path)))
    return config


def _split_addresses(values: list[str] | None) -> list[str]:
    addresses: list[str] = []
    for value in values or []:
        for part in str(value).replace(";", ",").split(","):
            part = part.strip()
            if part:
                addresses.append(part)
    return addresses


def _load_metrics(report_dir: Path) -> dict[str, object]:
    metrics_path = report_dir / "metrics.json"
    if not metrics_path.exists():
        raise FileNotFoundError(f"metrics.json not found in report folder: {report_dir}")
    return json.loads(metrics_path.read_text(encoding="utf-8"))


def _attachment_paths(report_dir: Path, config: dict[str, object]) -> list[Path]:
    email_config = config.get("email", {})
    attachments: list[Path] = []
    if email_config.get("attach_pdf", True):
        attachments.append(report_dir / "monthly_report.pdf")
    if email_config.get("attach_markdown", False):
        attachments.append(report_dir / "monthly_report.md")
    if email_config.get("attach_metrics_json", False):
        attachments.append(report_dir / "metrics.json")
    return [path for path in attachments if path.exists()]


def _project_context(metrics: dict[str, object]) -> dict[str, str]:
    profile = metrics.get("profile", {})
    meta = metrics.get("meta", {})
    return {
        "project_id": clean_text(profile.get("Project_ID"), "Project"),
        "project_name": clean_text(profile.get("Project_Name"), "Construction Project"),
        "period": clean_text(meta.get("period"), clean_text(meta.get("report_as_of"), "latest")[:7]),
        "report_as_of": clean_text(meta.get("report_as_of"), "-"),
        "status": clean_text(meta.get("report_status"), "Draft with blockers"),
    }


def _email_subject(metrics: dict[str, object], config: dict[str, object], override: str | None = None) -> str:
    if override:
        return override
    template = clean_text(
        config.get("email", {}).get("subject_template"),
        "[Draft Review] {project_id} Monthly Project Health Report - {period}",
    )
    return template.format(**_project_context(metrics))


def _top_findings(metrics: dict[str, object]) -> list[str]:
    return [clean_text(item) for item in metrics.get("executive_summary", {}).get("findings", []) if clean_text(item)]


def _review_gate_summary(metrics: dict[str, object]) -> tuple[int, int, int]:
    gates = metrics.get("validation", {}).get("review_gates", [])
    blocked = sum(1 for gate in gates if clean_text(gate.get("status")).lower() == "blocked")
    pending = sum(1 for gate in gates if "pending" in clean_text(gate.get("status")).lower())
    ready = sum(1 for gate in gates if "ready" in clean_text(gate.get("status")).lower())
    return blocked, pending, ready


def build_email_body(metrics: dict[str, object], config: dict[str, object]) -> tuple[str, str]:
    brand = config.get("brand", {})
    ctx = _project_context(metrics)
    validation = metrics.get("validation", {})
    issue_counts = validation.get("issue_counts", {})
    blocked_gates, pending_gates, ready_gates = _review_gate_summary(metrics)
    findings = _top_findings(metrics)
    primary = clean_text(brand.get("primary_color"), "#F36B15")
    secondary = clean_text(brand.get("secondary_color"), "#9B0A68")
    dark = clean_text(brand.get("dark_color"), "#231F20")

    status_warning = "This package is a draft for named-reviewer sign-off. Do not issue externally until the review gates are signed off."

    text_lines = [
        f"{ctx['project_id']} Monthly Project Health Report - {ctx['period']}",
        "",
        f"Project: {ctx['project_name']}",
        f"Report as of: {ctx['report_as_of']}",
        f"Status: {ctx['status']}",
        "",
        status_warning,
        "",
        "Executive findings:",
    ]
    text_lines.extend(f"- {finding}" for finding in findings)
    text_lines.extend(
        [
            "",
            "Review status:",
            f"- Validation blockers: {issue_counts.get('blocker', 0)}",
            f"- Validation warnings: {issue_counts.get('warning', 0)}",
            f"- Review gates blocked: {blocked_gates}",
            f"- Review gates pending: {pending_gates}",
            f"- Review gates ready: {ready_gates}",
            "",
            "Attached: monthly report PDF.",
        ]
    )

    finding_items = "\n".join(f"<li>{finding}</li>" for finding in findings)
    html_body = f"""<!doctype html>
<html>
<body style="font-family:Arial,sans-serif;color:{dark};margin:0;padding:0;background:#ffffff;">
  <div style="height:10px;background:linear-gradient(90deg,{primary},{secondary});"></div>
  <div style="padding:24px 28px;max-width:760px;">
    <h1 style="margin:0 0 8px;color:{secondary};font-size:24px;">{ctx['project_id']} Monthly Project Health Report</h1>
    <p style="margin:0 0 16px;color:#555;">{ctx['project_name']} | Period {ctx['period']} | As of {ctx['report_as_of']}</p>
    <div style="border-left:6px solid {primary};background:#FFF7F0;padding:12px 14px;margin:16px 0;">
      <strong>Status: {ctx['status']}</strong><br>
      {status_warning}
    </div>
    <h2 style="font-size:18px;color:{secondary};">Executive Findings</h2>
    <ul>{finding_items}</ul>
    <h2 style="font-size:18px;color:{secondary};">Review Status</h2>
    <table style="border-collapse:collapse;width:100%;font-size:14px;">
      <tr><td style="padding:8px;border-bottom:1px solid #ddd;">Validation blockers</td><td style="padding:8px;border-bottom:1px solid #ddd;"><strong>{issue_counts.get('blocker', 0)}</strong></td></tr>
      <tr><td style="padding:8px;border-bottom:1px solid #ddd;">Validation warnings</td><td style="padding:8px;border-bottom:1px solid #ddd;"><strong>{issue_counts.get('warning', 0)}</strong></td></tr>
      <tr><td style="padding:8px;border-bottom:1px solid #ddd;">Review gates blocked</td><td style="padding:8px;border-bottom:1px solid #ddd;"><strong>{blocked_gates}</strong></td></tr>
      <tr><td style="padding:8px;border-bottom:1px solid #ddd;">Review gates pending</td><td style="padding:8px;border-bottom:1px solid #ddd;"><strong>{pending_gates}</strong></td></tr>
      <tr><td style="padding:8px;border-bottom:1px solid #ddd;">Review gates ready</td><td style="padding:8px;border-bottom:1px solid #ddd;"><strong>{ready_gates}</strong></td></tr>
    </table>
    <p style="margin-top:18px;">Attached: monthly report PDF.</p>
  </div>
</body>
</html>
"""
    return "\n".join(text_lines), html_body


def build_eml(
    report_dir: Path,
    metrics: dict[str, object],
    config: dict[str, object],
    to_addresses: list[str],
    cc_addresses: list[str],
    subject: str,
    text_body: str,
    html_body: str,
) -> EmailMessage:
    email_config = config.get("email", {})
    sender_name = clean_text(email_config.get("from_name"), "OpenDeedigital Project Controls")
    sender_email = clean_text(email_config.get("from_email"), "project.controls@example.com")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{sender_name} <{sender_email}>"
    message["To"] = ", ".join(to_addresses)
    if cc_addresses:
        message["Cc"] = ", ".join(cc_addresses)
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain="opendeedigital.local")
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    for attachment in _attachment_paths(report_dir, config):
        content_type, _ = mimetypes.guess_type(attachment)
        maintype, subtype = (content_type or "application/octet-stream").split("/", 1)
        message.add_attachment(attachment.read_bytes(), maintype=maintype, subtype=subtype, filename=attachment.name)
    return message


def prepare_report_email(
    report_dir: str | Path,
    config_path: str | Path = "config/report_sections.json",
    to_addresses: list[str] | None = None,
    cc_addresses: list[str] | None = None,
    subject: str | None = None,
) -> dict[str, object]:
    report_dir = _resolve_report_dir(report_dir)
    config = load_email_config(config_path)
    metrics = _load_metrics(report_dir)
    email_config = config.get("email", {})
    to_list = _split_addresses(to_addresses) or _split_addresses(email_config.get("default_to", []))
    cc_list = _split_addresses(cc_addresses) or _split_addresses(email_config.get("default_cc", []))
    final_subject = _email_subject(metrics, config, subject)
    text_body, html_body = build_email_body(metrics, config)

    email_dir = report_dir / "email"
    email_dir.mkdir(parents=True, exist_ok=True)
    md_path = email_dir / "email_draft.md"
    html_path = email_dir / "email_draft.html"
    eml_path = email_dir / "monthly_report_email.eml"
    manifest_path = email_dir / "email_manifest.json"

    md_path.write_text(
        "\n".join(
            [
                f"# {final_subject}",
                "",
                f"To: {', '.join(to_list) if to_list else '[add recipients before sending]'}",
                f"Cc: {', '.join(cc_list) if cc_list else '-'}",
                "",
                text_body,
            ]
        ),
        encoding="utf-8",
    )
    html_path.write_text(html_body, encoding="utf-8")
    message = build_eml(report_dir, metrics, config, to_list, cc_list, final_subject, text_body, html_body)
    eml_path.write_bytes(message.as_bytes())

    attachments = [str(path) for path in _attachment_paths(report_dir, config)]
    manifest = {
        "mode": email_config.get("mode", "draft_only"),
        "status": metrics.get("meta", {}).get("report_status"),
        "subject": final_subject,
        "to": to_list,
        "cc": cc_list,
        "attachments": attachments,
        "draft_paths": {
            "markdown": str(md_path),
            "html": str(html_path),
            "eml": str(eml_path),
        },
        "send_allowed_without_override": (
            metrics.get("validation", {}).get("issue_counts", {}).get("blocker", 0) == 0
            and "blocker" not in clean_text(metrics.get("meta", {}).get("report_status")).lower()
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest | {"manifest_path": str(manifest_path)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a safe email draft package for a generated monthly report.")
    parser.add_argument("--report-dir", required=True, help="Generated report output directory.")
    parser.add_argument("--config", default="config/report_sections.json", help="Report config JSON.")
    parser.add_argument("--to", nargs="*", default=None, help="To recipients. Comma-separated values are accepted.")
    parser.add_argument("--cc", nargs="*", default=None, help="Cc recipients. Comma-separated values are accepted.")
    parser.add_argument("--subject", default=None, help="Optional subject override.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = prepare_report_email(args.report_dir, args.config, args.to, args.cc, args.subject)
    print(f"Email draft: {manifest['draft_paths']['markdown']}")
    print(f"HTML draft: {manifest['draft_paths']['html']}")
    print(f"EML draft: {manifest['draft_paths']['eml']}")
    print(f"Manifest: {manifest['manifest_path']}")
    if not manifest["to"]:
        print("Recipients: none configured; add --to before sending.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
