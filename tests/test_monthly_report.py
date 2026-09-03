from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from tools.load_data_pack import load_data_pack
from tools.prepare_report_email import prepare_report_email
from tools.run_monthly_report import run_monthly_report
from tools.send_report_email import send_report_email
from tools.validate_data_pack import validate_data_pack


ROOT = Path(__file__).resolve().parents[1]
DEMO_WORKBOOK = ROOT / "input" / "AI2C_Day2_Monthly_Report_Data_Pack_Demo.xlsx"
CONFIG = ROOT / "config" / "report_sections.json"
LOGO = ROOT / "brand_assets" / "ODD Logo.png"


class MonthlyReportAutomationTests(unittest.TestCase):
    def test_demo_workbook_loads_expected_sheets(self) -> None:
        data_pack = load_data_pack(DEMO_WORKBOOK)
        self.assertIn("01_Area_Progress", data_pack.sheet_names)
        self.assertIn("09_Review_Gates", data_pack.sheet_names)
        self.assertGreaterEqual(len(data_pack.sheet_names), 13)
        progress = data_pack.get("01_Area_Progress")
        self.assertIn("Progress_ID", progress.columns)
        self.assertIn("RAG_Status", progress.columns)

    def test_validation_uses_demo_cutoff_and_marks_draft_blockers(self) -> None:
        data_pack = load_data_pack(DEMO_WORKBOOK)
        validation = validate_data_pack(data_pack, period="2026-04", brand_logo_path=LOGO)
        self.assertEqual(validation["report_as_of"], "2026-04-30")
        self.assertEqual(validation["report_status"], "Draft with blockers")
        blocker_ids = {issue["id"] for issue in validation["issues"] if issue["severity"] == "blocker"}
        self.assertIn("FORMULA_MISMATCH", blocker_ids)
        self.assertIn("MISSING_LINK", blocker_ids)

    def test_full_report_package_is_branded_and_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_monthly_report(
                input_path=DEMO_WORKBOOK,
                period="2026-04",
                config_path=CONFIG,
                output_root=temp_dir,
            )
            output_dir = Path(result["output_dir"])
            self.assertEqual(result["status"], "Draft with blockers")
            for label in ("markdown", "html", "pdf", "metrics", "review_gates"):
                path = Path(result["outputs"][label])
                self.assertTrue(path.exists(), label)
                self.assertGreater(path.stat().st_size, 100, label)
            self.assertIn("email", result)
            self.assertTrue(Path(result["email"]["draft_paths"]["eml"]).exists())

            self.assertEqual(len(result["charts"]), 6)
            copied_logo = output_dir / "assets" / "ODD Logo.png"
            self.assertTrue(copied_logo.exists())

            markdown = (output_dir / "monthly_report.md").read_text(encoding="utf-8")
            html = (output_dir / "monthly_report.html").read_text(encoding="utf-8")
            self.assertIn("![OpenDeedigital](assets/ODD Logo.png)", markdown)
            self.assertIn("RFI-034", markdown)
            self.assertIn('class="logo"', html)
            self.assertIn('class="chart"', html)

            metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))
            self.assertEqual(metrics["meta"]["report_as_of"], "2026-04-30")
            self.assertGreaterEqual(metrics["validation"]["issue_counts"]["blocker"], 1)

            for chart in result["charts"].values():
                chart_path = Path(chart["path"])
                self.assertTrue(chart_path.exists())
                self.assertGreater(chart_path.stat().st_size, 1000)
                with Image.open(chart_path) as image:
                    self.assertEqual(image.size, (1200, 720))

    def test_email_draft_and_send_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_monthly_report(
                input_path=DEMO_WORKBOOK,
                period="2026-04",
                config_path=CONFIG,
                output_root=temp_dir,
                prepare_email=False,
            )
            manifest = prepare_report_email(
                result["output_dir"],
                CONFIG,
                to_addresses=["director@example.com"],
                cc_addresses=["pm@example.com"],
            )
            self.assertEqual(manifest["to"], ["director@example.com"])
            self.assertEqual(manifest["cc"], ["pm@example.com"])
            self.assertFalse(manifest["send_allowed_without_override"])
            self.assertTrue(Path(manifest["draft_paths"]["markdown"]).exists())
            self.assertTrue(Path(manifest["draft_paths"]["html"]).exists())
            self.assertTrue(Path(manifest["draft_paths"]["eml"]).exists())
            draft = Path(manifest["draft_paths"]["markdown"]).read_text(encoding="utf-8")
            self.assertIn("Draft with blockers", draft)
            self.assertIn("Do not issue externally", draft)
            with self.assertRaisesRegex(RuntimeError, "--send-approved"):
                send_report_email(result["output_dir"], CONFIG, to_addresses=["director@example.com"])


if __name__ == "__main__":
    unittest.main()
