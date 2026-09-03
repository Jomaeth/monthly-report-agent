from __future__ import annotations

from collections import Counter
from datetime import date, datetime

import pandas as pd

try:
    from .load_data_pack import DataPack, get_profile_map
    from .report_utils import (
        clean_text,
        count_values,
        days_between,
        is_blank,
        json_ready,
        normalize_rag,
        normalize_status,
        percent,
        records_from_frame,
        to_date,
        to_float,
    )
    from .validate_data_pack import (
        expected_milestone_rag,
        expected_procurement_rag,
        expected_progress_rag,
        expected_rfi_rag,
    )
except ImportError:  # pragma: no cover
    from load_data_pack import DataPack, get_profile_map
    from report_utils import (
        clean_text,
        count_values,
        days_between,
        is_blank,
        json_ready,
        normalize_rag,
        normalize_status,
        percent,
        records_from_frame,
        to_date,
        to_float,
    )
    from validate_data_pack import (
        expected_milestone_rag,
        expected_procurement_rag,
        expected_progress_rag,
        expected_rfi_rag,
    )


def _round(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(value, digits)


def _avg(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    return sum(clean) / len(clean) if clean else None


def _rag_rank(value: object) -> int:
    return {"Red": 0, "Yellow": 1, "Data Gap": 2, "Check": 3, "Green": 4}.get(normalize_rag(value), 9)


def _report_date(validation: dict[str, object]) -> date:
    parsed = to_date(validation.get("report_as_of"))
    return parsed or pd.Timestamp.today().date()


def _frame(data_pack: DataPack, sheet: str) -> pd.DataFrame:
    return data_pack.get(sheet) if data_pack.has_sheet(sheet) else pd.DataFrame()


def _progress_metrics(data_pack: DataPack) -> dict[str, object]:
    frame = _frame(data_pack, "01_Area_Progress")
    records: list[dict[str, object]] = []
    actuals: list[float | None] = []
    planned: list[float | None] = []
    for _, row in frame.iterrows():
        actual = percent(row.get("Actual_%_This_Month"))
        plan = percent(row.get("Planned_%_This_Month"))
        variance = actual - plan if actual is not None and plan is not None else None
        rag = expected_progress_rag(row.get("Actual_%_This_Month"), row.get("Planned_%_This_Month"))
        actuals.append(actual)
        planned.append(plan)
        records.append(
            {
                "id": clean_text(row.get("Progress_ID")),
                "zone": clean_text(row.get("Zone_Area")),
                "level": clean_text(row.get("Level")),
                "trade": clean_text(row.get("Trade")),
                "activity": clean_text(row.get("Activity")),
                "planned_pct": _round(plan),
                "actual_pct": _round(actual),
                "variance_pct": _round(variance),
                "rag": rag,
                "reason": clean_text(row.get("Delay_Variance_Reason")),
                "impact": clean_text(row.get("Impact")),
                "action": clean_text(row.get("Action")),
                "owner": clean_text(row.get("Owner")),
                "due_date": clean_text(row.get("Due_Date")),
                "linked_rfi": clean_text(row.get("Linked_RFI")),
                "linked_milestone": clean_text(row.get("Linked_Milestone")),
            }
        )
    by_zone: dict[str, dict[str, float | int]] = {}
    for record in records:
        zone = record["zone"] or "Unassigned"
        bucket = by_zone.setdefault(zone, {"planned_total": 0.0, "actual_total": 0.0, "count": 0})
        if record["planned_pct"] is not None and record["actual_pct"] is not None:
            bucket["planned_total"] += record["planned_pct"]
            bucket["actual_total"] += record["actual_pct"]
            bucket["count"] += 1
    zone_summary = [
        {
            "zone": zone,
            "planned_pct": _round(values["planned_total"] / values["count"]) if values["count"] else None,
            "actual_pct": _round(values["actual_total"] / values["count"]) if values["count"] else None,
        }
        for zone, values in by_zone.items()
    ]
    exceptions = sorted(
        [record for record in records if record["rag"] in {"Red", "Yellow", "Data Gap"}],
        key=lambda item: (_rag_rank(item["rag"]), item["variance_pct"] if item["variance_pct"] is not None else 0),
    )
    return {
        "row_count": len(records),
        "planned_avg_pct": _round(_avg(planned)),
        "actual_avg_pct": _round(_avg(actuals)),
        "variance_avg_pct": _round((_avg(actuals) or 0) - (_avg(planned) or 0)) if actuals and planned else None,
        "rag_counts": count_values(record["rag"] for record in records),
        "zone_summary": zone_summary,
        "exceptions": exceptions[:8],
        "records": records,
    }


def _milestone_metrics(data_pack: DataPack) -> dict[str, object]:
    frame = _frame(data_pack, "02_Programme_Milestones")
    records: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        variance = days_between(row.get("Current_Forecast_Date"), row.get("Baseline_Date"))
        rag = expected_milestone_rag(row.get("Critical_Path"), variance)
        records.append(
            {
                "id": clean_text(row.get("Milestone_ID")),
                "name": clean_text(row.get("Milestone_Name")),
                "baseline_date": clean_text(row.get("Baseline_Date")),
                "forecast_date": clean_text(row.get("Current_Forecast_Date")),
                "variance_days": variance,
                "critical_path": clean_text(row.get("Critical_Path")),
                "rag": rag,
                "reason": clean_text(row.get("Reason")),
                "recovery_action": clean_text(row.get("Recovery_Action")),
                "owner": clean_text(row.get("Owner")),
            }
        )
    delayed = sorted([record for record in records if (record["variance_days"] or 0) > 0], key=lambda item: item["variance_days"], reverse=True)
    return {
        "row_count": len(records),
        "rag_counts": count_values(record["rag"] for record in records),
        "critical_path_delays": [record for record in delayed if record["critical_path"].lower() == "yes"],
        "delayed": delayed[:8],
        "records": records,
    }


def _rfi_metrics(data_pack: DataPack, report_as_of: date) -> dict[str, object]:
    frame = _frame(data_pack, "03_Submission_RFI")
    records: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        due = to_date(row.get("Response_Due_Date"))
        received = to_date(row.get("Response_Received_Date"))
        if due and received:
            days_open = (received - due).days
        elif due:
            days_open = (report_as_of - due).days
        else:
            days_open = None
        status = normalize_status(row.get("Status_Raw"))
        rag = expected_rfi_rag(row.get("Response_Due_Date"), days_open, row.get("Programme_Impact_Days"))
        impact_days = to_float(row.get("Programme_Impact_Days"), 0) or 0
        records.append(
            {
                "id": clean_text(row.get("Record_ID")),
                "type": clean_text(row.get("Type")),
                "trade": clean_text(row.get("Package_Trade")),
                "description": clean_text(row.get("Description")),
                "due_date": clean_text(row.get("Response_Due_Date")),
                "received_date": clean_text(row.get("Response_Received_Date")),
                "days_open_overdue": days_open,
                "status": status,
                "programme_impact_days": impact_days,
                "commercial_impact": clean_text(row.get("Commercial_Impact")),
                "responsible_person": clean_text(row.get("Responsible_Person")),
                "escalation_required": "Yes" if (days_open or 0) > 7 or impact_days >= 7 else "No",
                "rag": rag,
                "linked_area_activity": clean_text(row.get("Linked_Area_Activity")),
                "linked_milestone": clean_text(row.get("Linked_Milestone")),
            }
        )
    bottlenecks = sorted(
        [record for record in records if record["rag"] in {"Red", "Yellow"}],
        key=lambda item: (_rag_rank(item["rag"]), item["days_open_overdue"] or 0, item["programme_impact_days"]),
        reverse=False,
    )
    bottlenecks = sorted(bottlenecks, key=lambda item: (item["rag"] != "Red", -(item["days_open_overdue"] or 0), -item["programme_impact_days"]))
    return {
        "row_count": len(records),
        "rag_counts": count_values(record["rag"] for record in records),
        "status_counts": dict(Counter(record["status"] for record in records if record["status"])),
        "bottlenecks": bottlenecks[:8],
        "records": records,
    }


def _procurement_metrics(data_pack: DataPack) -> dict[str, object]:
    frame = _frame(data_pack, "04_Procurement")
    records: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        variance = days_between(row.get("Forecast_Delivery_Date"), row.get("Required_Onsite_Date"))
        rag = expected_procurement_rag(row)
        records.append(
            {
                "id": clean_text(row.get("Item_ID")),
                "description": clean_text(row.get("Item_Description")),
                "package": clean_text(row.get("Package")),
                "required_onsite_date": clean_text(row.get("Required_Onsite_Date")),
                "approval_status": clean_text(row.get("Approval_Status")),
                "po_status": clean_text(row.get("PO_Status")),
                "forecast_delivery_date": clean_text(row.get("Forecast_Delivery_Date")),
                "variance_days": variance,
                "linked_milestone": clean_text(row.get("Linked_Milestone")),
                "rag": rag,
                "action": clean_text(row.get("Action")),
                "owner": clean_text(row.get("Owner")),
            }
        )
    risks = sorted([record for record in records if record["rag"] in {"Red", "Yellow", "Data Gap"}], key=lambda item: (_rag_rank(item["rag"]), -(item["variance_days"] or 0)))
    return {
        "row_count": len(records),
        "rag_counts": count_values(record["rag"] for record in records),
        "risks": risks[:8],
        "records": records,
    }


def _safety_quality_metrics(data_pack: DataPack, report_as_of: date) -> dict[str, object]:
    frame = _frame(data_pack, "05_Safety_Quality")
    records: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        due = to_date(row.get("Due_Date"))
        if due is None:
            overdue = None
        elif clean_text(row.get("Status")).lower() == "closed":
            overdue = 0
        else:
            overdue = (report_as_of - due).days
        records.append(
            {
                "id": clean_text(row.get("Record_ID")),
                "category": clean_text(row.get("Category")),
                "metric_or_issue": clean_text(row.get("Metric_or_Issue")),
                "count_value": to_float(row.get("Count_Value")),
                "status": clean_text(row.get("Status")),
                "area": clean_text(row.get("Area")),
                "description": clean_text(row.get("Description")),
                "action_required": clean_text(row.get("Action_Required")),
                "owner": clean_text(row.get("Owner")),
                "due_date": clean_text(row.get("Due_Date")),
                "days_overdue": overdue,
                "rag": normalize_rag(row.get("RAG_Status")),
                "evidence_ref": clean_text(row.get("Evidence_Ref")),
            }
        )
    exceptions = sorted([record for record in records if record["rag"] in {"Red", "Yellow"}], key=lambda item: (_rag_rank(item["rag"]), -(item["days_overdue"] or 0)))
    return {
        "row_count": len(records),
        "rag_counts": count_values(record["rag"] for record in records),
        "exceptions": exceptions[:8],
        "records": records,
    }


def _commercial_metrics(data_pack: DataPack, report_as_of: date) -> dict[str, object]:
    frame = _frame(data_pack, "06_Commercial_Cost")
    records = []
    for _, row in frame.iterrows():
        contract_sum = to_float(row.get("Contract_Sum_with_VO_HKD_M"))
        current_gp = to_float(row.get("Current_GP_HKD_M"))
        obj_gp = to_float(row.get("Obj_GP_HKD_M"))
        vo_net = (to_float(row.get("Accounted_VO_Income_HKD_M"), 0) or 0) - (to_float(row.get("Accounted_VO_Cost_HKD_M"), 0) or 0)
        current_gp_pct = current_gp / contract_sum if current_gp is not None and contract_sum else None
        gp_delta = current_gp - obj_gp if current_gp is not None and obj_gp is not None else None
        cashflow = (to_float(row.get("Payment_Received_HKD_M"), 0) or 0) - (to_float(row.get("Actual_Expenditure_HKD_M"), 0) or 0)
        records.append(
            {
                "reporting_month": clean_text(row.get("Reporting_Month")),
                "reporting_date": to_date(row.get("Reporting_Month")),
                "contract_sum_with_vo_hkd_m": contract_sum,
                "vo_net_hkd_m": _round(vo_net),
                "objective_gp_hkd_m": obj_gp,
                "current_gp_hkd_m": current_gp,
                "current_gp_pct": _round(current_gp_pct, 4),
                "gp_vs_objective_hkd_m": _round(gp_delta),
                "nett_cashflow_hkd_m": _round(cashflow),
                "commitment_pct": _round(to_float(row.get("Commitment_%")), 4),
                "risk_exposure_hkd_m": to_float(row.get("Risk_Exposure_HKD_M")),
                "performance_score_0_to_10": to_float(row.get("Performance_Score_0_to_10")),
                "rag": normalize_rag(row.get("RAG_Status")),
                "raw_source_issue": clean_text(row.get("Raw_Source_Issue")),
            }
        )
    records = sorted(records, key=lambda item: item["reporting_date"] or date.min)
    eligible = [record for record in records if record["reporting_date"] is None or record["reporting_date"] <= report_as_of]
    current = eligible[-1] if eligible else (records[-1] if records else {})
    previous = eligible[-2] if len(eligible) >= 2 else {}
    movement = {}
    for key in ("current_gp_hkd_m", "gp_vs_objective_hkd_m", "nett_cashflow_hkd_m", "risk_exposure_hkd_m"):
        if current and previous and current.get(key) is not None and previous.get(key) is not None:
            movement[key] = _round(current[key] - previous[key])
    return {
        "row_count": len(records),
        "current": json_ready(current),
        "previous": json_ready(previous),
        "movement": movement,
        "rag_counts": count_values(record["rag"] for record in records),
        "records": json_ready(records),
    }


def _risk_metrics(data_pack: DataPack) -> dict[str, object]:
    frame = _frame(data_pack, "07_Risk_Action_Decision")
    records: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        records.append(
            {
                "id": clean_text(row.get("Issue_ID")),
                "category": clean_text(row.get("Category")),
                "linked_records": clean_text(row.get("Linked_Records")),
                "description": clean_text(row.get("Description")),
                "impact": clean_text(row.get("Impact")),
                "decision_required": clean_text(row.get("Decision_Required")),
                "recommendation": clean_text(row.get("Recommendation")),
                "owner": clean_text(row.get("Owner")),
                "due_date": clean_text(row.get("Due_Date")),
                "status": clean_text(row.get("Status")),
                "rag": normalize_rag(row.get("RAG_Status")),
                "human_review_gate": clean_text(row.get("Human_Review_Gate")),
            }
        )
    open_items = sorted([record for record in records if record["status"].lower() != "closed"], key=lambda item: _rag_rank(item["rag"]))
    return {
        "row_count": len(records),
        "rag_counts": count_values(record["rag"] for record in records),
        "open_items": open_items[:10],
        "records": records,
    }


def _metric_dictionary(data_pack: DataPack) -> dict[str, object]:
    frame = _frame(data_pack, "08_Metric_Dictionary")
    return {
        "row_count": len(frame),
        "records": records_from_frame(frame),
    }


def _findings(metrics: dict[str, object], validation: dict[str, object]) -> list[str]:
    findings: list[str] = []
    progress = metrics["progress"]
    rfi = metrics["submission_rfi"]
    commercial = metrics["commercial_cost"]
    safety = metrics["safety_quality"]
    risk = metrics["risk_action_decision"]

    progress_rag = progress.get("rag_counts", {})
    if progress_rag.get("Red", 0):
        findings.append(f"{progress_rag['Red']} progress item(s) are Red and need management attention.")
    elif progress_rag.get("Yellow", 0):
        findings.append(f"{progress_rag['Yellow']} progress item(s) are Yellow and should be monitored.")

    if rfi.get("bottlenecks"):
        top = rfi["bottlenecks"][0]
        findings.append(f"{top['id']} is the leading submission/RFI bottleneck with {top['days_open_overdue']} overdue/open day(s).")

    current = commercial.get("current") or {}
    if current:
        findings.append(
            f"Commercial status is {current.get('rag', 'Check')}: current GP is HK${current.get('current_gp_hkd_m')}M "
            f"against objective delta HK${current.get('gp_vs_objective_hkd_m')}M."
        )

    safety_rag = safety.get("rag_counts", {})
    if safety_rag.get("Red", 0):
        findings.append(f"{safety_rag['Red']} safety/quality item(s) are Red and require review before issue.")

    risk_rag = risk.get("rag_counts", {})
    if risk_rag.get("Red", 0):
        findings.append(f"{risk_rag['Red']} decision/risk item(s) are Red and remain in the action log.")

    blockers = validation.get("issue_counts", {}).get("blocker", 0)
    warnings = validation.get("issue_counts", {}).get("warning", 0)
    findings.append(f"Validation found {blockers} blocker(s) and {warnings} warning(s); package status remains {validation.get('report_status')}.")
    return findings


def calculate_monthly_kpis(data_pack: DataPack, validation: dict[str, object]) -> dict[str, object]:
    report_date = _report_date(validation)
    profile = get_profile_map(data_pack)
    metrics = {
        "progress": _progress_metrics(data_pack),
        "programme_milestones": _milestone_metrics(data_pack),
        "submission_rfi": _rfi_metrics(data_pack, report_date),
        "procurement": _procurement_metrics(data_pack),
        "safety_quality": _safety_quality_metrics(data_pack, report_date),
        "commercial_cost": _commercial_metrics(data_pack, report_date),
        "risk_action_decision": _risk_metrics(data_pack),
        "metric_dictionary": _metric_dictionary(data_pack),
    }
    report_model = {
        "meta": {
            "source_path": str(data_pack.source_path),
            "period": validation.get("period"),
            "report_as_of": validation.get("report_as_of"),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "report_status": validation.get("report_status"),
        },
        "profile": {str(key): json_ready(value) for key, value in profile.items()},
        "validation": validation,
        "metrics": json_ready(metrics),
        "executive_summary": {
            "findings": _findings(metrics, validation),
        },
        "charts": {},
    }
    return json_ready(report_model)
