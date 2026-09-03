from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable

import pandas as pd

try:
    from .load_data_pack import DataPack, get_profile_map
    from .report_utils import (
        clean_text,
        days_between,
        is_blank,
        normalize_rag,
        normalize_status,
        percent,
        split_refs,
        to_date,
        to_float,
    )
except ImportError:  # pragma: no cover
    from load_data_pack import DataPack, get_profile_map
    from report_utils import (
        clean_text,
        days_between,
        is_blank,
        normalize_rag,
        normalize_status,
        percent,
        split_refs,
        to_date,
        to_float,
    )


REQUIRED_COLUMNS: dict[str, list[str]] = {
    "00_Project_Profile": ["Field", "Value"],
    "01_Area_Progress": [
        "Progress_ID",
        "Zone_Area",
        "Trade",
        "Activity",
        "Planned_%_This_Month",
        "Actual_%_This_Month",
        "Variance_%",
        "RAG_Status",
        "Owner",
        "Due_Date",
    ],
    "02_Programme_Milestones": [
        "Milestone_ID",
        "Milestone_Name",
        "Baseline_Date",
        "Current_Forecast_Date",
        "Variance_Days",
        "Critical_Path",
        "Owner",
        "RAG_Status",
    ],
    "03_Submission_RFI": [
        "Record_ID",
        "Type",
        "Description",
        "Response_Due_Date",
        "Response_Received_Date",
        "Days_Open_Overdue",
        "Status_Raw",
        "Status_Normalized",
        "Programme_Impact_Days",
        "Responsible_Person",
        "Escalation_Required",
        "RAG_Status",
    ],
    "04_Procurement": [
        "Item_ID",
        "Item_Description",
        "Required_Onsite_Date",
        "Approval_Status",
        "PO_Status",
        "Forecast_Delivery_Date",
        "Variance_Days",
        "Risk_Status",
        "Owner",
    ],
    "05_Safety_Quality": [
        "Record_ID",
        "Category",
        "Metric_or_Issue",
        "Status",
        "Owner",
        "Due_Date",
        "Days_Overdue",
        "RAG_Status",
        "Evidence_Ref",
    ],
    "06_Commercial_Cost": [
        "Reporting_Month",
        "Project_ID",
        "Contract_Sum_with_VO_HKD_M",
        "Accounted_VO_Income_HKD_M",
        "Accounted_VO_Cost_HKD_M",
        "VO_Net_HKD_M",
        "Obj_GP_HKD_M",
        "Obj_GP_%",
        "Current_GP_HKD_M",
        "Current_GP_%",
        "GP_vs_Objective_HKD_M",
        "GP_vs_Objective_%",
        "Nett_Cashflow_HKD_M",
        "Risk_Exposure_HKD_M",
        "RAG_Status",
    ],
    "07_Risk_Action_Decision": [
        "Issue_ID",
        "Category",
        "Linked_Records",
        "Description",
        "Decision_Required",
        "Recommendation",
        "Owner",
        "Due_Date",
        "Status",
        "RAG_Status",
        "Human_Review_Gate",
    ],
    "08_Metric_Dictionary": ["Metric_ID", "Metric_Name", "Source_Sheet", "Formula_or_Logic", "RAG_Rule"],
    "09_Review_Gates": [
        "Review_Gate_ID",
        "Report_Section",
        "Reviewer",
        "What_To_Check",
        "Decision",
        "Stop_Condition",
        "Output_Status",
    ],
}


@dataclass
class ValidationIssue:
    id: str
    severity: str
    section: str
    message: str
    record_id: str = ""
    reviewer: str = ""


def _period_end(period: str | None) -> str | None:
    if not period:
        return None
    year, month = [int(part) for part in period.split("-", 1)]
    return f"{year:04d}-{month:02d}-{monthrange(year, month)[1]:02d}"


def _derive_report_as_of(data_pack: DataPack, period: str | None, override: str | None) -> str:
    explicit = to_date(override)
    if explicit:
        return explicit.isoformat()
    profile = get_profile_map(data_pack)
    for key in ("Report_As_Of_Date", "Report_As_Of", "Reporting_Month"):
        value = to_date(profile.get(key))
        if value:
            return value.isoformat()
    period_end = _period_end(period)
    if period_end:
        return period_end
    return pd.Timestamp.today().date().isoformat()


def _issue(
    issues: list[ValidationIssue],
    issue_id: str,
    severity: str,
    section: str,
    message: str,
    record_id: object = "",
    reviewer: str = "",
) -> None:
    issues.append(
        ValidationIssue(
            id=issue_id,
            severity=severity,
            section=section,
            message=message,
            record_id=clean_text(record_id),
            reviewer=reviewer,
        )
    )


def _approx_equal(actual: object, expected: object, tolerance: float = 0.001) -> bool:
    if expected is None and is_blank(actual):
        return True
    actual_number = to_float(actual)
    expected_number = to_float(expected)
    if actual_number is not None and expected_number is not None:
        return abs(actual_number - expected_number) <= tolerance
    return clean_text(actual).lower() == clean_text(expected).lower()


def _compare_formula(
    issues: list[ValidationIssue],
    section: str,
    record_id: object,
    field: str,
    actual: object,
    expected: object,
) -> None:
    if not _approx_equal(actual, expected):
        _issue(
            issues,
            "FORMULA_MISMATCH",
            "blocker",
            section,
            f"{field} cached value '{clean_text(actual)}' does not match recomputed value '{clean_text(expected)}'.",
            record_id,
            "PM / Project Controls",
        )


def expected_progress_rag(actual_pct: object, planned_pct: object) -> str:
    actual = percent(actual_pct)
    planned = percent(planned_pct)
    if actual is None:
        return "Data Gap"
    if planned is None:
        return "Data Gap"
    variance = actual - planned
    if variance <= -0.10:
        return "Red"
    if variance <= -0.05:
        return "Yellow"
    return "Green"


def expected_milestone_rag(critical_path: object, variance_days: object) -> str:
    variance = to_float(variance_days)
    if variance is None:
        return "Data Gap"
    if clean_text(critical_path).lower() == "yes" and variance > 7:
        return "Red"
    if variance > 0:
        return "Yellow"
    return "Green"


def expected_rfi_rag(response_due: object, days_open: object, programme_impact_days: object) -> str:
    if to_date(response_due) is None:
        return "Data Gap"
    days = to_float(days_open, 0) or 0
    impact = to_float(programme_impact_days, 0) or 0
    if days > 14 or impact >= 10:
        return "Red"
    if days > 0 or impact > 0:
        return "Yellow"
    return "Green"


def expected_procurement_rag(row) -> str:
    forecast = to_date(row.get("Forecast_Delivery_Date"))
    if forecast is None:
        return "Data Gap"
    if clean_text(row.get("Approval_Status")) != "Approved" or clean_text(row.get("PO_Status")) != "Issued":
        return "Red"
    variance = days_between(row.get("Forecast_Delivery_Date"), row.get("Required_Onsite_Date"))
    if variance is None:
        return "Data Gap"
    if variance > 0:
        return "Yellow"
    return "Green"


def expected_commercial_rag(row) -> str:
    gp_delta = to_float(row.get("GP_vs_Objective_HKD_M"), 0) or 0
    cashflow = to_float(row.get("Nett_Cashflow_HKD_M"), 0) or 0
    risk = to_float(row.get("Risk_Exposure_HKD_M"), 0) or 0
    commitment_pct = to_float(row.get("Commitment_%"), 0) or 0
    if gp_delta < -0.5 or cashflow < 0 or risk > 2:
        return "Red"
    if gp_delta < 0 or commitment_pct > 0.9 or risk > 0.5:
        return "Yellow"
    return "Green"


def _validate_schema(data_pack: DataPack, issues: list[ValidationIssue]) -> None:
    for sheet, columns in REQUIRED_COLUMNS.items():
        if not data_pack.has_sheet(sheet):
            _issue(issues, "MISSING_SHEET", "blocker", sheet, f"Required sheet '{sheet}' is missing.")
            continue
        frame = data_pack.get(sheet)
        missing = [column for column in columns if column not in frame.columns]
        if missing:
            _issue(
                issues,
                "MISSING_COLUMN",
                "blocker",
                sheet,
                f"Missing required columns: {', '.join(missing)}.",
            )


def _validate_formula_integrity(data_pack: DataPack, issues: list[ValidationIssue], report_as_of: str) -> None:
    report_date = to_date(report_as_of)

    if data_pack.has_sheet("01_Area_Progress"):
        progress = data_pack.get("01_Area_Progress")
        for _, row in progress.iterrows():
            variance = None
            actual = percent(row.get("Actual_%_This_Month"))
            planned = percent(row.get("Planned_%_This_Month"))
            if actual is not None and planned is not None:
                variance = actual - planned
            _compare_formula(issues, "Progress", row.get("Progress_ID"), "Variance_%", row.get("Variance_%"), variance)
            _compare_formula(
                issues,
                "Progress",
                row.get("Progress_ID"),
                "RAG_Status",
                row.get("RAG_Status"),
                expected_progress_rag(row.get("Actual_%_This_Month"), row.get("Planned_%_This_Month")),
            )

    if data_pack.has_sheet("02_Programme_Milestones"):
        milestones = data_pack.get("02_Programme_Milestones")
        for _, row in milestones.iterrows():
            variance = days_between(row.get("Current_Forecast_Date"), row.get("Baseline_Date"))
            _compare_formula(issues, "Programme", row.get("Milestone_ID"), "Variance_Days", row.get("Variance_Days"), variance)
            _compare_formula(
                issues,
                "Programme",
                row.get("Milestone_ID"),
                "RAG_Status",
                row.get("RAG_Status"),
                expected_milestone_rag(row.get("Critical_Path"), variance),
            )

    if data_pack.has_sheet("03_Submission_RFI"):
        rfi = data_pack.get("03_Submission_RFI")
        for _, row in rfi.iterrows():
            due = to_date(row.get("Response_Due_Date"))
            received = to_date(row.get("Response_Received_Date"))
            days_open = None
            if due and received:
                days_open = (received - due).days
            elif due and report_date:
                days_open = (report_date - due).days
            escalation = "Yes" if (to_float(days_open, 0) or 0) > 7 or (to_float(row.get("Programme_Impact_Days"), 0) or 0) >= 7 else "No"
            _compare_formula(issues, "Submission/RFI", row.get("Record_ID"), "Days_Open_Overdue", row.get("Days_Open_Overdue"), days_open)
            _compare_formula(issues, "Submission/RFI", row.get("Record_ID"), "Status_Normalized", row.get("Status_Normalized"), normalize_status(row.get("Status_Raw")))
            _compare_formula(issues, "Submission/RFI", row.get("Record_ID"), "Escalation_Required", row.get("Escalation_Required"), escalation)
            _compare_formula(
                issues,
                "Submission/RFI",
                row.get("Record_ID"),
                "RAG_Status",
                row.get("RAG_Status"),
                expected_rfi_rag(row.get("Response_Due_Date"), days_open, row.get("Programme_Impact_Days")),
            )

    if data_pack.has_sheet("04_Procurement"):
        procurement = data_pack.get("04_Procurement")
        for _, row in procurement.iterrows():
            variance = days_between(row.get("Forecast_Delivery_Date"), row.get("Required_Onsite_Date"))
            _compare_formula(issues, "Procurement", row.get("Item_ID"), "Variance_Days", row.get("Variance_Days"), variance)
            _compare_formula(
                issues,
                "Procurement",
                row.get("Item_ID"),
                "Risk_Status",
                row.get("Risk_Status"),
                expected_procurement_rag(row),
            )

    if data_pack.has_sheet("05_Safety_Quality"):
        safety = data_pack.get("05_Safety_Quality")
        for _, row in safety.iterrows():
            due = to_date(row.get("Due_Date"))
            if due is None:
                days_overdue = None
            elif clean_text(row.get("Status")).lower() == "closed":
                days_overdue = 0
            elif report_date:
                days_overdue = (report_date - due).days
            else:
                days_overdue = None
            _compare_formula(issues, "Safety/Quality", row.get("Record_ID"), "Days_Overdue", row.get("Days_Overdue"), days_overdue)

    if data_pack.has_sheet("06_Commercial_Cost"):
        commercial = data_pack.get("06_Commercial_Cost")
        for _, row in commercial.iterrows():
            contract_sum = to_float(row.get("Contract_Sum_with_VO_HKD_M"))
            current_gp = to_float(row.get("Current_GP_HKD_M"))
            obj_gp = to_float(row.get("Obj_GP_HKD_M"))
            obj_gp_pct = to_float(row.get("Obj_GP_%"))
            vo_net = (to_float(row.get("Accounted_VO_Income_HKD_M"), 0) or 0) - (to_float(row.get("Accounted_VO_Cost_HKD_M"), 0) or 0)
            current_gp_pct = current_gp / contract_sum if current_gp is not None and contract_sum else None
            gp_delta = current_gp - obj_gp if current_gp is not None and obj_gp is not None else None
            gp_delta_pct = current_gp_pct - obj_gp_pct if current_gp_pct is not None and obj_gp_pct is not None else None
            cashflow = (to_float(row.get("Payment_Received_HKD_M"), 0) or 0) - (to_float(row.get("Actual_Expenditure_HKD_M"), 0) or 0)
            certified_pct = (to_float(row.get("Cost_Certified_HKD_M")) / contract_sum) if to_float(row.get("Cost_Certified_HKD_M")) is not None and contract_sum else None
            commitment_pct = (to_float(row.get("Commitment_HKD_M")) / contract_sum) if to_float(row.get("Commitment_HKD_M")) is not None and contract_sum else None
            record_id = row.get("Reporting_Month")
            for field, expected in [
                ("VO_Net_HKD_M", vo_net),
                ("Current_GP_%", current_gp_pct),
                ("GP_vs_Objective_HKD_M", gp_delta),
                ("GP_vs_Objective_%", gp_delta_pct),
                ("Nett_Cashflow_HKD_M", cashflow),
                ("Cost_Certified_%", certified_pct),
                ("Commitment_%", commitment_pct),
                ("RAG_Status", expected_commercial_rag(row)),
            ]:
                _compare_formula(issues, "Commercial", record_id, field, row.get(field), expected)


def _validate_links(data_pack: DataPack, issues: list[ValidationIssue]) -> None:
    progress_ids = set(data_pack.get("01_Area_Progress").get("Progress_ID", pd.Series(dtype=object)).dropna().astype(str)) if data_pack.has_sheet("01_Area_Progress") else set()
    milestone_ids = set(data_pack.get("02_Programme_Milestones").get("Milestone_ID", pd.Series(dtype=object)).dropna().astype(str)) if data_pack.has_sheet("02_Programme_Milestones") else set()
    rfi_ids = set(data_pack.get("03_Submission_RFI").get("Record_ID", pd.Series(dtype=object)).dropna().astype(str)) if data_pack.has_sheet("03_Submission_RFI") else set()
    procurement_ids = set(data_pack.get("04_Procurement").get("Item_ID", pd.Series(dtype=object)).dropna().astype(str)) if data_pack.has_sheet("04_Procurement") else set()

    def check_refs(sheet: str, id_col: str, field: str, valid_ids: set[str], label: str) -> None:
        if not data_pack.has_sheet(sheet):
            return
        frame = data_pack.get(sheet)
        if field not in frame.columns:
            return
        for _, row in frame.iterrows():
            for ref in split_refs(row.get(field)):
                if ref and ref not in valid_ids:
                    _issue(
                        issues,
                        "MISSING_LINK",
                        "blocker",
                        "Cross-Link Integrity",
                        f"{field} references missing {label} ID '{ref}'.",
                        row.get(id_col),
                        "PM / Project Controls",
                    )

    check_refs("01_Area_Progress", "Progress_ID", "Linked_RFI", rfi_ids, "RFI/submission")
    check_refs("01_Area_Progress", "Progress_ID", "Linked_Milestone", milestone_ids, "milestone")
    check_refs("02_Programme_Milestones", "Milestone_ID", "Linked_Progress_Item", progress_ids, "progress")
    check_refs("02_Programme_Milestones", "Milestone_ID", "Linked_RFI_Submission", rfi_ids, "RFI/submission")
    check_refs("03_Submission_RFI", "Record_ID", "Linked_Area_Activity", progress_ids, "progress")
    check_refs("03_Submission_RFI", "Record_ID", "Linked_Milestone", milestone_ids, "milestone")
    check_refs("04_Procurement", "Item_ID", "Linked_Milestone", milestone_ids, "milestone")

    if data_pack.has_sheet("07_Risk_Action_Decision"):
        risks = data_pack.get("07_Risk_Action_Decision")
        known_prefixes: dict[str, set[str]] = {
            "PRG": progress_ids,
            "M": milestone_ids,
            "RFI": rfi_ids,
            "SUB": rfi_ids,
            "MAT": procurement_ids,
        }
        for _, row in risks.iterrows():
            for ref in split_refs(row.get("Linked_Records")):
                if "-" not in ref:
                    continue
                prefix = ref.split("-", 1)[0]
                if prefix in known_prefixes and ref not in known_prefixes[prefix]:
                    _issue(
                        issues,
                        "MISSING_LINK",
                        "blocker",
                        "Risk Action Decision",
                        f"Risk linked record references missing ID '{ref}'.",
                        row.get("Issue_ID"),
                        "PM / Project Controls",
                    )


def _validate_quality_notes(data_pack: DataPack, issues: list[ValidationIssue]) -> None:
    for sheet in data_pack.sheet_names:
        frame = data_pack.get(sheet)
        note_columns = [column for column in ("Data_Quality_Note", "Raw_Source_Issue") if column in frame.columns]
        for _, row in frame.iterrows():
            for column in note_columns:
                if not is_blank(row.get(column)):
                    _issue(
                        issues,
                        "SOURCE_DATA_NOTE",
                        "warning",
                        sheet,
                        f"{column}: {clean_text(row.get(column))}",
                        row.get("Progress_ID") or row.get("Record_ID") or row.get("Item_ID") or row.get("Issue_ID"),
                        "PM / Project Admin",
                    )


def _validate_safety_and_evidence(data_pack: DataPack, issues: list[ValidationIssue]) -> None:
    if data_pack.has_sheet("05_Safety_Quality"):
        safety = data_pack.get("05_Safety_Quality")
        for _, row in safety.iterrows():
            if normalize_rag(row.get("RAG_Status")) == "Red":
                missing = [
                    field
                    for field in ("Owner", "Due_Date", "Evidence_Ref")
                    if field not in safety.columns or is_blank(row.get(field))
                ]
                if missing:
                    _issue(
                        issues,
                        "SAFETY_RED_INCOMPLETE",
                        "blocker",
                        "Safety/Quality",
                        f"Red safety item is missing required fields: {', '.join(missing)}.",
                        row.get("Record_ID"),
                        "Safety Officer / PM",
                    )

    for sheet, field, id_col in [
        ("01_Area_Progress", "Photo_Refs", "Progress_ID"),
        ("05_Safety_Quality", "Evidence_Ref", "Record_ID"),
    ]:
        if not data_pack.has_sheet(sheet):
            continue
        frame = data_pack.get(sheet)
        if field not in frame.columns:
            continue
        for _, row in frame.iterrows():
            if not is_blank(row.get(field)):
                _issue(
                    issues,
                    "EVIDENCE_UNVERIFIED",
                    "warning",
                    "Evidence",
                    f"{field} '{clean_text(row.get(field))}' is referenced but not verified as an attached file/link.",
                    row.get(id_col),
                    "PM / Project Admin",
                )


def _base_review_gates(data_pack: DataPack) -> list[dict[str, object]]:
    if not data_pack.has_sheet("09_Review_Gates"):
        return []
    gates = data_pack.get("09_Review_Gates")
    result = []
    for _, row in gates.iterrows():
        result.append(
            {
                "gate_id": clean_text(row.get("Review_Gate_ID")),
                "section": clean_text(row.get("Report_Section")),
                "reviewer": clean_text(row.get("Reviewer")),
                "what_to_check": clean_text(row.get("What_To_Check")),
                "decision": clean_text(row.get("Decision")),
                "stop_condition": clean_text(row.get("Stop_Condition")),
                "status": "Pending Review",
                "blocker_count": 0,
            }
        )
    return result


def _build_review_gates(data_pack: DataPack, issues: list[ValidationIssue]) -> list[dict[str, object]]:
    gates = _base_review_gates(data_pack)
    blockers = [issue for issue in issues if issue.severity == "blocker"]
    formula_blockers = [issue for issue in blockers if issue.id == "FORMULA_MISMATCH"]
    link_blockers = [issue for issue in blockers if issue.id == "MISSING_LINK"]
    safety_blockers = [issue for issue in blockers if issue.id == "SAFETY_RED_INCOMPLETE"]
    evidence_warnings = [issue for issue in issues if issue.id == "EVIDENCE_UNVERIFIED"]

    def status_for(count: int, pending_only: bool = False) -> str:
        if count:
            return "Blocked"
        return "Pending Review" if pending_only else "Ready for Review"

    gates.extend(
        [
            {
                "gate_id": "RG-AUTO-001",
                "section": "Data Provenance",
                "reviewer": "PM / Project Admin",
                "what_to_check": "Confirm source workbook, report period, report-as-of date, and ODD branding before publishing.",
                "decision": "Accept / request correction",
                "stop_condition": "Wrong source file, reporting period, or missing brand asset.",
                "status": "Pending Review",
                "blocker_count": 0,
            },
            {
                "gate_id": "RG-AUTO-002",
                "section": "Formula Integrity",
                "reviewer": "PM / Project Controls",
                "what_to_check": "Cached workbook formula values agree with Python recomputation for report-critical KPI fields.",
                "decision": "Fix workbook or accept Python recomputation",
                "stop_condition": "Formula mismatch in critical KPI or RAG field.",
                "status": status_for(len(formula_blockers)),
                "blocker_count": len(formula_blockers),
            },
            {
                "gate_id": "RG-AUTO-003",
                "section": "Cross-Link Integrity",
                "reviewer": "PM / Project Controls",
                "what_to_check": "Linked progress, RFI, milestone, procurement, and risk IDs exist.",
                "decision": "Fix source register links",
                "stop_condition": "Report narrative depends on a missing linked record.",
                "status": status_for(len(link_blockers)),
                "blocker_count": len(link_blockers),
            },
            {
                "gate_id": "RG-AUTO-004",
                "section": "Claims / Commercial Language",
                "reviewer": "PM / QS / Technical Manager",
                "what_to_check": "Review EOT, VO, RFI escalation, GP, cashflow, and risk exposure wording.",
                "decision": "Approve wording / revise before issue",
                "stop_condition": "Claim-sensitive wording not reviewed.",
                "status": "Pending Review",
                "blocker_count": 0,
            },
            {
                "gate_id": "RG-AUTO-005",
                "section": "Safety Red Items",
                "reviewer": "Safety Officer / PM",
                "what_to_check": "Every red safety item has owner, due date, evidence reference, and closure action.",
                "decision": "Approve / require closure plan",
                "stop_condition": "Red safety item lacks owner, due date, or evidence reference.",
                "status": status_for(len(safety_blockers), pending_only=True),
                "blocker_count": len(safety_blockers),
            },
            {
                "gate_id": "RG-AUTO-006",
                "section": "Evidence Verification",
                "reviewer": "PM / Project Admin",
                "what_to_check": "Referenced photos and evidence IDs are attached or traceable.",
                "decision": "Attach evidence / mark as unavailable",
                "stop_condition": "Critical claim or safety statement lacks evidence.",
                "status": "Pending Review" if evidence_warnings else "Ready for Review",
                "blocker_count": 0,
            },
            {
                "gate_id": "RG-AUTO-007",
                "section": "Final Sign-Off",
                "reviewer": "Project Director",
                "what_to_check": "All section reviewers clear their gates before external issue.",
                "decision": "Approve final issue",
                "stop_condition": "Any section remains pending or blocked.",
                "status": "Blocked",
                "blocker_count": 1,
            },
        ]
    )
    return gates


def validate_data_pack(
    data_pack: DataPack,
    period: str | None = None,
    report_as_of: str | None = None,
    brand_logo_path: str | Path | None = None,
) -> dict[str, object]:
    issues: list[ValidationIssue] = []
    as_of = _derive_report_as_of(data_pack, period, report_as_of)

    _validate_schema(data_pack, issues)
    if brand_logo_path and not Path(brand_logo_path).exists():
        _issue(
            issues,
            "MISSING_BRAND_ASSET",
            "blocker",
            "Branding",
            f"Brand logo is missing: {brand_logo_path}",
            reviewer="PM / Project Admin",
        )

    if not any(issue.id in {"MISSING_SHEET", "MISSING_COLUMN"} and issue.severity == "blocker" for issue in issues):
        _validate_formula_integrity(data_pack, issues, as_of)
        _validate_links(data_pack, issues)
        _validate_quality_notes(data_pack, issues)
        _validate_safety_and_evidence(data_pack, issues)

    gates = _build_review_gates(data_pack, issues)
    issue_counts = {
        "blocker": sum(1 for issue in issues if issue.severity == "blocker"),
        "warning": sum(1 for issue in issues if issue.severity == "warning"),
        "info": sum(1 for issue in issues if issue.severity == "info"),
    }
    has_blockers = issue_counts["blocker"] > 0 or any(gate["status"] == "Blocked" for gate in gates)
    return {
        "source_path": str(data_pack.source_path),
        "period": period,
        "report_as_of": as_of,
        "report_status": "Draft with blockers" if has_blockers else "Draft pending review",
        "issue_counts": issue_counts,
        "issues": [asdict(issue) for issue in issues],
        "review_gates": gates,
    }
