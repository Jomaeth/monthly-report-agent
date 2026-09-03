from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from ._common import project_path
    from .calculate_monthly_kpis import calculate_monthly_kpis
    from .generate_report_charts import generate_report_charts
    from .load_data_pack import load_data_pack, resolve_input_path
    from .prepare_report_email import prepare_report_email
    from .render_monthly_report import render_report_package
    from .validate_data_pack import validate_data_pack
except ImportError:  # pragma: no cover
    from _common import project_path
    from calculate_monthly_kpis import calculate_monthly_kpis
    from generate_report_charts import generate_report_charts
    from load_data_pack import load_data_pack, resolve_input_path
    from prepare_report_email import prepare_report_email
    from render_monthly_report import render_report_package
    from validate_data_pack import validate_data_pack


def load_config(path: str | Path) -> dict[str, object]:
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = project_path(str(config_path))
    config = json.loads(config_path.read_text(encoding="utf-8"))
    brand = config.setdefault("brand", {})
    logo_path = Path(str(brand.get("logo_path", "")))
    if logo_path and not logo_path.is_absolute():
        brand["logo_path"] = str(project_path(str(logo_path)))
    return config


def build_output_dir(config: dict[str, object], period: str | None, report_as_of: str | None, output_root: str | None = None) -> Path:
    root = output_root or str(config.get("report", {}).get("output_root", "outputs/monthly_report"))
    root_path = Path(root)
    if not root_path.is_absolute():
        root_path = project_path(root)
    folder_name = period or (report_as_of[:7] if report_as_of else "latest")
    return root_path / folder_name


def run_monthly_report(
    input_path: str | Path,
    period: str | None = None,
    report_as_of: str | None = None,
    config_path: str | Path = "config/report_sections.json",
    output_root: str | None = None,
    prepare_email: bool = True,
    email_to: list[str] | None = None,
    email_cc: list[str] | None = None,
) -> dict[str, object]:
    config = load_config(config_path)
    resolved_input = resolve_input_path(input_path)
    data_pack = load_data_pack(resolved_input)
    logo_path = config.get("brand", {}).get("logo_path")
    validation = validate_data_pack(data_pack, period=period, report_as_of=report_as_of, brand_logo_path=logo_path, mode=(config.get("validation", {}) or {}).get("mode"))
    report_model = calculate_monthly_kpis(data_pack, validation)
    output_dir = build_output_dir(config, period, validation.get("report_as_of"), output_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    charts = generate_report_charts(report_model, config, output_dir)
    outputs = render_report_package(report_model, config, output_dir)
    email_manifest = None
    if prepare_email and config.get("email", {}).get("enabled", True):
        email_manifest = prepare_report_email(output_dir, config_path, to_addresses=email_to, cc_addresses=email_cc)
    return {
        "status": validation.get("report_status"),
        "output_dir": str(output_dir),
        "outputs": outputs,
        "charts": charts,
        "email": email_manifest,
        "validation": validation,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the branded ODD construction monthly report package.")
    parser.add_argument("--input", required=True, help="Excel workbook, CSV file, or folder of CSV files.")
    parser.add_argument("--period", default=None, help="Reporting period in YYYY-MM format.")
    parser.add_argument("--report-as-of", default=None, help="Override report-as-of date in YYYY-MM-DD format.")
    parser.add_argument("--config", default="config/report_sections.json", help="Report configuration JSON.")
    parser.add_argument("--output-root", default=None, help="Optional output root folder.")
    parser.add_argument("--no-email-draft", action="store_true", help="Skip email draft generation.")
    parser.add_argument("--email-to", nargs="*", default=None, help="Email draft To recipients.")
    parser.add_argument("--email-cc", nargs="*", default=None, help="Email draft Cc recipients.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_monthly_report(
        input_path=args.input,
        period=args.period,
        report_as_of=args.report_as_of,
        config_path=args.config,
        output_root=args.output_root,
        prepare_email=not args.no_email_draft,
        email_to=args.email_to,
        email_cc=args.email_cc,
    )
    print(f"Report status: {result['status']}")
    print(f"Output directory: {result['output_dir']}")
    for label, path in result["outputs"].items():
        print(f"{label}: {path}")
    print(f"charts: {len(result['charts'])} generated")
    if result.get("email"):
        print(f"email draft: {result['email']['draft_paths']['markdown']}")
        print(f"email eml: {result['email']['draft_paths']['eml']}")
    blockers = result["validation"].get("issue_counts", {}).get("blocker", 0)
    warnings = result["validation"].get("issue_counts", {}).get("warning", 0)
    notes = result["validation"].get("issue_counts", {}).get("data_note", 0)
    status = result["validation"].get("report_status")
    print(f"validation: {blockers} blocker(s), {warnings} warning(s) incl. {notes} data note(s) -- status: {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
