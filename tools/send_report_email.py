from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import smtplib

try:
    from ._common import load_env_file, project_path
    from .prepare_report_email import load_email_config, prepare_report_email
    from .report_utils import clean_text
except ImportError:  # pragma: no cover
    from _common import load_env_file, project_path
    from prepare_report_email import load_email_config, prepare_report_email
    from report_utils import clean_text


def _resolve(path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = project_path(str(candidate))
    return candidate.resolve()


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _load_manifest(report_dir: Path) -> dict[str, object]:
    path = report_dir / "email" / "email_manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"Email manifest not found. Run prepare_report_email first: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_visual_qa_status(report_dir: Path) -> dict[str, object] | None:
    """Load visual_qa_status.json if present; return None if QA was not run."""
    path = report_dir / "visual_qa_status.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _check_send_gate(
    manifest: dict[str, object],
    config: dict[str, object],
    send_approved: bool,
    override_blockers: bool,
    report_dir: Path | None = None,
    override_visual_qa: bool = False,
) -> None:
    email_config = config.get("email", {})
    if email_config.get("require_send_approved_flag", True) and not send_approved:
        raise RuntimeError("Refusing to send: --send-approved is required.")
    if not manifest.get("to"):
        raise RuntimeError("Refusing to send: no recipients configured.")
    has_blocker_status = "blocker" in clean_text(manifest.get("status")).lower()
    if email_config.get("require_no_blockers_for_send", True) and has_blocker_status and not override_blockers:
        raise RuntimeError("Refusing to send: report status has blockers. Use --override-blockers only after human approval.")

    # Visual QA gate (v1.1+): the rendered charts must have passed a
    # vision-model review before the report can leave the building.
    # Mirrors the blockers gate above — separate flag for separate concerns.
    require_qa = bool(email_config.get("require_visual_qa_pass", True))
    if require_qa and report_dir is not None:
        qa = _load_visual_qa_status(report_dir)
        if qa is None:
            if not override_visual_qa:
                raise RuntimeError(
                    "Refusing to send: visual_qa_status.json not found. "
                    "Run `python tools/visual_qa_report.py --report-dir "
                    f"{report_dir} --execute` (or --simulate for offline demo) "
                    "first, or use --override-visual-qa only after a human "
                    "has reviewed every chart by eye."
                )
            return
        qa_status = str(qa.get("status", "")).lower()
        if qa_status != "pass" and not override_visual_qa:
            fail_n = qa.get("fail_count", 0)
            pending_n = sum(1 for f in qa.get("findings", [])
                            if str(f.get("verdict", "")).lower() == "pending")
            raise RuntimeError(
                f"Refusing to send: visual QA status is '{qa_status.upper()}' "
                f"({fail_n} failing chart(s), {pending_n} pending). "
                "Open outputs/.../visual_qa_report.html to see flagged charts, "
                "fix them, re-run visual_qa_report.py, then retry. "
                "Use --override-visual-qa only after a documented human review."
            )


def send_report_email(
    report_dir: str | Path,
    config_path: str | Path = "config/report_sections.json",
    send_approved: bool = False,
    override_blockers: bool = False,
    override_visual_qa: bool = False,
    to_addresses: list[str] | None = None,
    cc_addresses: list[str] | None = None,
) -> dict[str, object]:
    load_env_file()
    report_dir = _resolve(report_dir)
    config = load_email_config(config_path)
    if to_addresses or cc_addresses or not (report_dir / "email" / "email_manifest.json").exists():
        prepare_report_email(report_dir, config_path, to_addresses=to_addresses, cc_addresses=cc_addresses)
    manifest = _load_manifest(report_dir)
    _check_send_gate(
        manifest, config, send_approved, override_blockers,
        report_dir=report_dir, override_visual_qa=override_visual_qa,
    )

    eml_path = Path(manifest["draft_paths"]["eml"])
    message_bytes = eml_path.read_bytes()
    host = _required_env("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    username = _required_env("SMTP_USERNAME")
    password = _required_env("SMTP_PASSWORD")
    smtp_from = os.environ.get("SMTP_FROM", username)
    recipients = list(manifest.get("to", [])) + list(manifest.get("cc", []))

    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(username, password)
        smtp.sendmail(smtp_from, recipients, message_bytes)

    send_log = {
        "sent": True,
        "recipients": recipients,
        "subject": manifest.get("subject"),
        "eml_path": str(eml_path),
    }
    log_path = report_dir / "email" / "send_log.json"
    log_path.write_text(json.dumps(send_log, indent=2, ensure_ascii=False), encoding="utf-8")
    return send_log | {"send_log_path": str(log_path)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send an approved monthly report email via SMTP.")
    parser.add_argument("--report-dir", required=True, help="Generated report output directory.")
    parser.add_argument("--config", default="config/report_sections.json", help="Report config JSON.")
    parser.add_argument("--to", nargs="*", default=None, help="To recipients. Comma-separated values are accepted by draft preparation.")
    parser.add_argument("--cc", nargs="*", default=None, help="Cc recipients. Comma-separated values are accepted by draft preparation.")
    parser.add_argument("--send-approved", action="store_true", help="Required human approval flag.")
    parser.add_argument("--override-blockers", action="store_true", help="Allow sending despite Draft with blockers status after human approval.")
    parser.add_argument("--override-visual-qa", action="store_true",
                        help="Allow sending despite missing/failing visual QA status. "
                             "Use only after a documented human eye-check of every chart.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = send_report_email(
        report_dir=args.report_dir,
        config_path=args.config,
        send_approved=args.send_approved,
        override_blockers=args.override_blockers,
        override_visual_qa=args.override_visual_qa,
        to_addresses=args.to,
        cc_addresses=args.cc,
    )
    print(f"Sent email to {', '.join(result['recipients'])}")
    print(f"Send log: {result['send_log_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
