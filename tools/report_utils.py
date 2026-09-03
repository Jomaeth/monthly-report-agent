from __future__ import annotations

from datetime import date, datetime
import math
import re
from typing import Iterable

import pandas as pd


RAG_ORDER = ["Red", "Yellow", "Green", "Data Gap", "Check", "Pending", "Open", "Closed"]


def is_blank(value: object) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return isinstance(value, str) and value.strip() == ""


def clean_text(value: object, default: str = "") -> str:
    if is_blank(value):
        return default
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")
    return str(value).strip()


def to_float(value: object, default: float | None = None) -> float | None:
    if is_blank(value):
        return default
    if isinstance(value, str):
        value = value.replace("%", "").replace(",", "").strip()
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_date(value: object) -> date | None:
    if is_blank(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        parsed = pd.to_datetime(value, errors="coerce")
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed.date()


def days_between(later: object, earlier: object) -> int | None:
    later_date = to_date(later)
    earlier_date = to_date(earlier)
    if later_date is None or earlier_date is None:
        return None
    return (later_date - earlier_date).days


def percent(value: object) -> float | None:
    number = to_float(value)
    if number is None:
        return None
    return number / 100 if abs(number) > 1.5 else number


def normalize_status(value: object) -> str:
    text = clean_text(value)
    upper = text.upper()
    if "NOT YET" in upper:
        return "Not Yet Submitted"
    if "PEND" in upper:
        return "Pending"
    if "OPEN" in upper:
        return "Open"
    if "ANSWER" in upper:
        return "Answered"
    if "APPROV" in upper:
        return "Approved"
    if "CLOSED" in upper or "CLOSE" in upper:
        return "Closed"
    return text or "Check"


def normalize_rag(value: object) -> str:
    text = clean_text(value)
    lookup = {
        "red": "Red",
        "yellow": "Yellow",
        "amber": "Yellow",   # legacy alias — older data packs may still use "Amber"
        "green": "Green",
        "data gap": "Data Gap",
        "check": "Check",
    }
    return lookup.get(text.lower(), text)


def split_refs(value: object) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    return [part.strip() for part in re.split(r"[,/;|]+", text) if part.strip()]


def sorted_rag_counts(counts: dict[str, int]) -> dict[str, int]:
    order = {name: index for index, name in enumerate(RAG_ORDER)}
    return dict(sorted(counts.items(), key=lambda item: (order.get(item[0], 99), item[0])))


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return json_ready(value.item())
        except Exception:
            pass
    if isinstance(value, float) and math.isnan(value):
        return None
    if is_blank(value):
        return None
    return value


def records_from_frame(frame: pd.DataFrame, limit: int | None = None) -> list[dict[str, object]]:
    rows = frame.head(limit).to_dict(orient="records") if limit else frame.to_dict(orient="records")
    return [json_ready(row) for row in rows]


def count_values(values: Iterable[object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        label = clean_text(value)
        if not label:
            continue
        label = normalize_rag(label)
        counts[label] = counts.get(label, 0) + 1
    return sorted_rag_counts(counts)
