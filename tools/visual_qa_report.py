"""Visual QA gate for the Monthly Report Agent.

Reads the rendered monthly_report_premium.html, extracts every embedded chart
(inline base64 PNG), and sends each chart to Gemini 2.5 Flash Vision asking
ONE focused question:

    "Is every label, number, axis tick, and legend item in this chart
    clearly readable and not clipped by any other graphic element?"

Gemini returns a structured per-chart verdict (pass | fail) plus a one-line
finding. The tool aggregates these into:

  - visual_qa_status.json    Machine-readable. status: pass | fail.
                              Used by send_report_email.py as a hard gate.
  - visual_qa_report.html    Human-readable QA review with thumbnails of every
                              chart and the model's finding beside each.

If status != 'pass', send_report_email.py refuses to send the monthly report
to management — exactly mirroring the existing blockers gate.

Three modes:
  --execute    Calls Gemini Vision (requires GEMINI_API_KEY in .env).
  --dry-run    No API call. Prints the prompt that WOULD be sent for the
               first chart and writes a 'pending' status. Useful in class
               for offline demos when the projection laptop has no network.
  --simulate   No API call. Returns deterministic findings hand-coded into
               this script — used for unit tests and as a reproducible
               classroom fallback so the demo story always lands.

Usage:
    python tools/visual_qa_report.py \
        --report-dir outputs/monthly_report/2026-04 --execute

    python tools/visual_qa_report.py \
        --report-dir outputs/monthly_report/2026-04 --dry-run
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from ._common import load_env_file, project_path
except ImportError:  # pragma: no cover
    from _common import load_env_file, project_path


DEFAULT_VISION_MODEL = "gemini-2.5-flash"

VISION_PROMPT = """\
You are reviewing a chart from a construction monthly project health report
that will be emailed to senior management.

Inspect the attached chart image and answer ONE question only:

  Is EVERY label, number, axis tick, legend item, title, and annotation
  in the image clearly readable AND not clipped, overlapped, or obscured
  by any other graphic element (such as a donut hole, another bar, or
  an edge)?

You are NOT judging:
  - Data correctness or business meaning.
  - Aesthetic preferences (colour, font, layout taste).
  - Whether the chart conveys the right message.

You ARE judging:
  - Are letters or digits cut off?
  - Are labels overlapping each other to the point of unreadability?
  - Is any value visually hidden behind another element?
  - Are required tick labels missing?

Return STRICTLY this JSON, nothing else:

{
  "verdict": "pass" | "fail",
  "finding": "<one sentence, plain English, what you see; if pass, say 'All labels and numbers are clearly readable.'>",
  "issues": ["<short concrete issue 1>", "<short concrete issue 2>", ...]
}

If verdict is "pass", the "issues" array MUST be empty.
"""


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@dataclass
class ChartFinding:
    chart_id: str           # eg "rag", "progress", "milestones"
    chart_title: str        # human-readable title parsed from HTML <h3>
    verdict: str            # pass | fail | pending
    finding: str            # one-line plain English
    issues: list[str] = field(default_factory=list)
    image_b64_thumbnail: str = ""   # smaller thumbnail for QA HTML


@dataclass
class QAStatus:
    status: str             # pass | fail | pending
    mode: str               # execute | dry-run | simulate
    model: str
    report_html: str
    generated_at: str
    total_charts: int
    pass_count: int
    fail_count: int
    findings: list[ChartFinding]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "mode": self.mode,
            "model": self.model,
            "report_html": self.report_html,
            "generated_at": self.generated_at,
            "total_charts": self.total_charts,
            "pass_count": self.pass_count,
            "fail_count": self.fail_count,
            "findings": [asdict(f) for f in self.findings],
        }


# ---------------------------------------------------------------------------
# Chart extraction from premium HTML
# ---------------------------------------------------------------------------

# matches an <h3>title</h3>...<img class="chart" src="data:image/png;base64,XXXX">
CHART_PATTERN = re.compile(
    r'<h3>([^<]+)</h3>\s*<img class="chart" src="data:image/png;base64,([^"]+)"',
    re.DOTALL,
)


def extract_charts_from_html(html_path: Path) -> list[tuple[str, str, bytes]]:
    """Return list of (chart_id, title, png_bytes) for every chart in the HTML."""
    text = html_path.read_text(encoding="utf-8")
    out: list[tuple[str, str, bytes]] = []
    for m in CHART_PATTERN.finditer(text):
        title = m.group(1).strip()
        b64 = m.group(2)
        try:
            png = base64.b64decode(b64)
        except Exception:
            continue
        # derive a slug
        slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:48]
        out.append((slug, title, png))
    return out


# ---------------------------------------------------------------------------
# Gemini API call
# ---------------------------------------------------------------------------

def call_gemini_vision(api_key: str, model: str, png_bytes: bytes,
                      prompt: str) -> dict[str, Any]:
    endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {"text": prompt},
                {
                    "inlineData": {
                        "mimeType": "image/png",
                        "data": base64.b64encode(png_bytes).decode("ascii"),
                    }
                },
            ],
        }],
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "application/json",
        },
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_gemini_response(resp: dict[str, Any]) -> tuple[str, str, list[str]]:
    """Extract (verdict, finding, issues) from a Gemini generateContent response."""
    try:
        text = resp["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        return ("fail", f"Could not parse Gemini response: {e}", ["malformed-response"])

    text = text.strip()
    # the model occasionally wraps in ```json ... ```
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return ("fail", f"Non-JSON response: {text[:200]}", ["non-json-response"])

    verdict = str(data.get("verdict", "fail")).lower().strip()
    if verdict not in ("pass", "fail"):
        verdict = "fail"
    finding = str(data.get("finding", "")).strip() or "(no finding text)"
    issues = data.get("issues", []) or []
    if not isinstance(issues, list):
        issues = [str(issues)]
    return (verdict, finding, [str(x) for x in issues])


# ---------------------------------------------------------------------------
# Simulated findings (for offline classroom demo)
# ---------------------------------------------------------------------------

# Pretends Gemini reviewed the charts. Used by --simulate.
# Keyed by chart slug. The slugs match what extract_charts_from_html() yields
# from the premium HTML — keep them in sync if titles change.
SIMULATED_FINDINGS: dict[str, dict[str, Any]] = {
    "overall_rag_mix_across_all_dimensions": {
        "verdict": "pass",
        "finding": "Donut shows centre total clearly; every wedge has an external "
                   "label with leader line; all counts and percentages are unclipped.",
        "issues": [],
    },
    "area_progress_planned_vs_actual": {
        "verdict": "pass",
        "finding": "Horizontal bars and y-axis labels are fully visible; legend "
                   "in the lower-right does not overlap any bar.",
        "issues": [],
    },
    "programme_milestones_variance_days": {
        "verdict": "pass",
        "finding": "Bar values, milestone names on y-axis, and the 'Critical Path' "
                   "legend swatch are all readable; thick purple edges visible.",
        "issues": [],
    },
    "submission_rfi_aging": {
        "verdict": "pass",
        "finding": "RFI IDs on y-axis and overdue-day labels on x-axis are clear; "
                   "zero line is visible.",
        "issues": [],
    },
    "procurement_variance": {
        "verdict": "pass",
        "finding": "Item IDs and descriptions are visible; MAT-026 has no bar as "
                   "expected (Data Gap) which is intentional, not a clipping issue.",
        "issues": [],
    },
    "safety_quality_environmental_rag_mix": {
        "verdict": "pass",
        "finding": "Stacked bars are clear; category labels on x-axis and legend "
                   "are unclipped.",
        "issues": [],
    },
    "commercial_gp_and_gp_hk_current_vs_objective": {
        "verdict": "pass",
        "finding": "Both side-by-side panels show month tick labels and bar pairs "
                   "with legible legends.",
        "issues": [],
    },
    "cashflow_snapshot": {
        "verdict": "pass",
        "finding": "All six bars labelled with HK$ values on top; x-axis category "
                   "names are fully visible.",
        "issues": [],
    },
}


def simulated_review(slug: str, title: str) -> tuple[str, str, list[str]]:
    rec = SIMULATED_FINDINGS.get(slug)
    if rec is None:
        return (
            "pending",
            f"No simulated finding registered for chart '{title}' (slug '{slug}'). "
            "Run with --execute for a live Gemini review.",
            ["unknown-chart-slug"],
        )
    return (rec["verdict"], rec["finding"], list(rec["issues"]))


# ---------------------------------------------------------------------------
# HTML output
# ---------------------------------------------------------------------------

QA_HTML_CSS = """
:root {
  --brand-orange: #F36B15;
  --brand-purple: #9B0A68;
  --brand-dark:   #231F20;
  --pass:         #1F9D55;
  --fail:         #D7263D;
  --pending:      #E58E26;
  --border:       #E5E7EB;
}
* { box-sizing: border-box; }
body { margin: 0; font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
       color: var(--brand-dark); background: #F4F5F7; }
.brand-strip { height: 12px;
       background: linear-gradient(90deg, var(--brand-orange), var(--brand-purple)); }
main { max-width: 1100px; margin: 0 auto; padding: 0 24px 60px; }
.page-header { background: white; padding: 22px 28px;
       border-radius: 0 0 12px 12px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);
       display: flex; justify-content: space-between; align-items: center;
       flex-wrap: wrap; gap: 14px; margin-bottom: 22px; }
.page-header h1 { margin: 0; font-size: 24px; }
.page-header .sub { color: #555; font-size: 13px; margin-top: 4px; }
.status-pill { padding: 9px 22px; border-radius: 999px; font-weight: 700;
       color: white; font-size: 14px; letter-spacing: 0.3px; }
.status-pill.pass { background: var(--pass); }
.status-pill.fail { background: var(--fail); }
.status-pill.pending { background: var(--pending); }
.summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
       gap: 12px; margin-bottom: 22px; }
.summary .card { background: white; padding: 14px 18px; border-radius: 10px;
       box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
.summary .card .label { font-size: 11px; text-transform: uppercase;
       letter-spacing: 0.5px; color: #888; }
.summary .card .value { margin-top: 4px; font-size: 26px; font-weight: 700; }
.findings { background: white; border-radius: 12px; padding: 22px 28px;
       box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
.findings h2 { margin: 0 0 18px; padding-bottom: 10px;
       border-bottom: 3px solid var(--brand-orange); color: var(--brand-purple);
       font-size: 18px; }
.finding { display: grid; grid-template-columns: 260px 1fr;
       gap: 18px; padding: 16px 0; border-bottom: 1px dashed var(--border); }
.finding:last-child { border-bottom: none; }
.finding .thumb { background: #F8F8F8; border-radius: 6px;
       padding: 6px; max-width: 260px; }
.finding .thumb img { width: 100%; height: auto; display: block; border-radius: 4px; }
.finding .detail .verdict { display: inline-block; padding: 3px 10px;
       border-radius: 999px; font-size: 11px; font-weight: 700; color: white;
       letter-spacing: 0.4px; margin-bottom: 8px; }
.finding .detail .verdict.pass { background: var(--pass); }
.finding .detail .verdict.fail { background: var(--fail); }
.finding .detail .verdict.pending { background: var(--pending); }
.finding .detail h3 { margin: 0 0 6px; font-size: 15px; }
.finding .detail p { margin: 0 0 6px; color: #333; line-height: 1.5; font-size: 13px; }
.finding .detail ul { margin: 6px 0 0; padding-left: 20px; }
.finding .detail ul li { color: var(--fail); font-size: 13px; margin: 3px 0; }
.footer { margin-top: 30px; text-align: center; font-size: 12px; color: #888; }
.tagline { color: var(--brand-purple); font-weight: 600; }
"""


def render_qa_html(status: QAStatus, report_html_filename: str) -> str:
    pill_class = status.status
    rows = []
    for f in status.findings:
        issues_html = ""
        if f.issues:
            items = "".join(f"<li>{html.escape(i)}</li>" for i in f.issues)
            issues_html = f"<ul>{items}</ul>"
        rows.append(f"""
<div class="finding">
  <div class="thumb">
    <img src="data:image/png;base64,{f.image_b64_thumbnail}" alt="{html.escape(f.chart_title)}">
  </div>
  <div class="detail">
    <span class="verdict {f.verdict}">{f.verdict.upper()}</span>
    <h3>{html.escape(f.chart_title)}</h3>
    <p>{html.escape(f.finding)}</p>
    {issues_html}
  </div>
</div>
""")

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Visual QA Report · Monthly Report Agent</title>
<style>{QA_HTML_CSS}</style>
</head>
<body>
<div class="brand-strip"></div>
<main>

<div class="page-header">
  <div>
    <h1>Visual QA Report · 視覺品質審查報告</h1>
    <div class="sub">
      Source: <strong>{html.escape(report_html_filename)}</strong> · Mode:
      <strong>{html.escape(status.mode)}</strong> · Model:
      <strong>{html.escape(status.model)}</strong> · Generated:
      {html.escape(status.generated_at)}
    </div>
  </div>
  <div class="status-pill {pill_class}">{status.status.upper()}</div>
</div>

<div class="summary">
  <div class="card"><div class="label">Charts Reviewed</div>
    <div class="value">{status.total_charts}</div></div>
  <div class="card"><div class="label">Pass</div>
    <div class="value" style="color:var(--pass)">{status.pass_count}</div></div>
  <div class="card"><div class="label">Fail</div>
    <div class="value" style="color:var(--fail)">{status.fail_count}</div></div>
  <div class="card"><div class="label">Overall</div>
    <div class="value" style="color:var(--{pill_class})">{status.status.upper()}</div></div>
</div>

<section class="findings">
<h2>Per-chart Findings · 各圖表審查結果</h2>
{''.join(rows)}
</section>

<div class="footer">
  <p class="tagline">AI Drafts · Vision-QA Checks · Human Signs</p>
  <p>This QA report was produced by tools/visual_qa_report.py. Each chart was
  reviewed by {html.escape(status.model)} answering ONE question: are all
  labels, numbers, and text clearly readable and unclipped? Pass means
  the report is visually safe to email. Fail means do NOT send until the
  flagged charts are fixed and the QA is re-run.</p>
  <p>© OpenDeedigital × HKIC 2026 · Monthly Report Agent · Visual QA Gate</p>
</div>

</main>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Thumbnail generation (resize PNG to ~520px wide)
# ---------------------------------------------------------------------------

def make_thumbnail_b64(png_bytes: bytes, max_width: int = 520) -> str:
    """Resize image to <= max_width px wide; returns base64 PNG."""
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(png_bytes))
        if img.width > max_width:
            ratio = max_width / img.width
            new_size = (max_width, int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        # fallback: just return the original
        return base64.b64encode(png_bytes).decode("ascii")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--report-dir", required=True,
                        help="Output dir containing monthly_report_premium.html")
    parser.add_argument("--html-name", default="monthly_report_premium.html",
                        help="Filename of the rendered report HTML inside --report-dir")
    parser.add_argument("--model", default=os.environ.get("GEMINI_VISION_MODEL",
                                                          DEFAULT_VISION_MODEL))
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--execute", action="store_true",
                      help="Call Gemini Vision (needs GEMINI_API_KEY).")
    mode.add_argument("--dry-run", action="store_true",
                      help="No API call. Prints the prompt and writes a 'pending' status.")
    mode.add_argument("--simulate", action="store_true",
                      help="No API call. Uses hand-coded findings for reproducible demos.")
    args = parser.parse_args(argv)

    load_env_file()

    report_dir = Path(args.report_dir).resolve()
    html_path = report_dir / args.html_name
    if not html_path.exists():
        print(f"ERROR: report HTML not found: {html_path}", file=sys.stderr)
        return 1

    print(f"Reading: {html_path}")
    charts = extract_charts_from_html(html_path)
    print(f"  Found {len(charts)} embedded charts")
    if not charts:
        print("ERROR: No charts found. Did the report render correctly?", file=sys.stderr)
        return 1

    mode_label = "execute" if args.execute else ("dry-run" if args.dry_run else "simulate")
    findings: list[ChartFinding] = []

    if args.execute:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("ERROR: GEMINI_API_KEY not set. Use --dry-run or --simulate "
                  "for offline demos.", file=sys.stderr)
            return 1
        print(f"Mode: EXECUTE - calling {args.model} for {len(charts)} charts")

    if args.dry_run:
        print("Mode: DRY-RUN - no API call. Sample prompt:")
        print("-" * 70)
        print(VISION_PROMPT)
        print("-" * 70)

    if args.simulate:
        print("Mode: SIMULATE - using hand-coded findings")

    for slug, title, png in charts:
        thumb_b64 = make_thumbnail_b64(png)
        if args.execute:
            try:
                resp = call_gemini_vision(api_key, args.model, png, VISION_PROMPT)
                verdict, finding, issues = parse_gemini_response(resp)
            except (RuntimeError, urllib.error.URLError, urllib.error.HTTPError) as e:
                verdict = "fail"
                finding = f"Gemini API error: {e}"
                issues = ["api-error"]
        elif args.simulate:
            verdict, finding, issues = simulated_review(slug, title)
        else:
            # dry-run
            verdict = "pending"
            finding = "Dry-run mode — no review performed. Re-run with --execute or --simulate."
            issues = []

        findings.append(ChartFinding(
            chart_id=slug,
            chart_title=title,
            verdict=verdict,
            finding=finding,
            issues=issues,
            image_b64_thumbnail=thumb_b64,
        ))
        marker = {"pass": "OK", "fail": "FAIL", "pending": "..."}.get(verdict, "?")
        print(f"  [{marker}] {title[:55]:<55} {verdict.upper()}")

    pass_n = sum(1 for f in findings if f.verdict == "pass")
    fail_n = sum(1 for f in findings if f.verdict == "fail")
    pending_n = sum(1 for f in findings if f.verdict == "pending")

    if args.dry_run or pending_n > 0:
        overall = "pending"
    elif fail_n > 0:
        overall = "fail"
    else:
        overall = "pass"

    status = QAStatus(
        status=overall,
        mode=mode_label,
        model=args.model if args.execute else "(no model called)",
        report_html=args.html_name,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        total_charts=len(findings),
        pass_count=pass_n,
        fail_count=fail_n,
        findings=findings,
    )

    # Write JSON
    json_path = report_dir / "visual_qa_status.json"
    json_path.write_text(json.dumps(status.to_dict(), indent=2, ensure_ascii=False),
                         encoding="utf-8")

    # Write HTML
    html_out = render_qa_html(status, args.html_name)
    html_out_path = report_dir / "visual_qa_report.html"
    html_out_path.write_text(html_out, encoding="utf-8")

    print()
    print(f"Charts: {len(findings)} total / pass {pass_n} / fail {fail_n}"
          f" / pending {pending_n}")
    print(f"Overall: {overall.upper()}")
    print(f"  JSON: {json_path}")
    print(f"  HTML: {html_out_path}")

    return 0 if overall == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
