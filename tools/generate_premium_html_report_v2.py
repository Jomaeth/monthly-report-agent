"""Premium HTML monthly report — V2 "director-first" edition.

Same data pipeline as generate_premium_html_report.py (imports its loaders,
KPI engine and deterministic AI-summary rules) but a fully redesigned render:

  - Course-brand look: navy #1e293b bands, amber #f59e0b accent, Inter type
    (matches the AI2C Day 1/Day 2 deck the demo runs inside).
  - Director-first hierarchy: STOP/CONTROL/GO banner -> draft-governance strip
    -> 5-second director summary -> KPI band -> decision pack -> charts -> detail.
  - Charts are inline SVG/HTML (no matplotlib PNGs): crisp on a projector,
    print-clean, and the file drops from ~900 KB to ~150 KB.
  - Governance is visible: DRAFT banner with review-gate progress at the top,
    review-gate wall + sign-off block at the bottom.

Usage (identical CLI to v1):
    python tools/generate_premium_html_report_v2.py
        --input "demo-data/AI2C_Day2_Monthly_Report_Data_Pack_Demo.xlsx"
        --period 2026-04
        --output "outputs/monthly_report/2026-04/monthly_report_premium_v2.html"
"""

from __future__ import annotations

import argparse
import html
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_premium_html_report as base  # noqa: E402  (v1 module, untouched)


# -----------------------------------------------------------------------------
# Palette — AI2C course brand + traffic-light RAG
# -----------------------------------------------------------------------------

NAVY = "#1e293b"
NAVY_DEEP = "#0f172a"
AMBER = "#f59e0b"
INK = "#334155"
MUTED = "#64748b"
LINE = "#e2e8f0"
BG = "#f1f5f9"

RAG = {
    "Green":    {"c": "#166534", "bg": "#f0fdf4", "chip": "#dcfce7", "ink": "#166534"},
    "Yellow":   {"c": "#d97706", "bg": "#fffbeb", "chip": "#fef3c7", "ink": "#92400e"},
    "Red":      {"c": "#991b1b", "bg": "#fef2f2", "chip": "#fee2e2", "ink": "#991b1b"},
    "Data Gap": {"c": "#64748b", "bg": "#f8fafc", "chip": "#e2e8f0", "ink": "#475569"},
    "Unknown":  {"c": "#94a3b8", "bg": "#f8fafc", "chip": "#e2e8f0", "ink": "#475569"},
}

STATUS_GOOD = {"Approved", "Answered", "Closed", "Issued", "Ready for internal issue"}
STATUS_BAD = {"Open", "Not Issued", "Blocked"}


def _rag(v: Any) -> dict:
    return RAG.get(str(v or "").strip(), RAG["Unknown"])


def esc(v: Any) -> str:
    return html.escape(str(v)) if v not in (None, "") else "&mdash;"


def _trunc(s: Any, n: int) -> str:
    s = str(s or "")
    return s if len(s) <= n else s[: n - 1] + "…"


# -----------------------------------------------------------------------------
# Small components
# -----------------------------------------------------------------------------

def rag_chip(value: Any) -> str:
    v = str(value or "").strip() or "—"
    r = _rag(v)
    return (f'<span class="chip" style="background:{r["chip"]};color:{r["ink"]}">'
            f'<i style="background:{r["c"]}"></i>{html.escape(v)}</span>')


def status_chip(value: Any) -> str:
    v = str(value or "").strip()
    if v in STATUS_GOOD:
        r = RAG["Green"]
    elif v in STATUS_BAD:
        r = RAG["Red"]
    elif v in ("", None):
        return "&mdash;"
    else:
        r = RAG["Yellow"]
    return (f'<span class="chip" style="background:{r["chip"]};color:{r["ink"]}">'
            f'{html.escape(v)}</span>')


def owner_due(owner: Any, due: Any) -> str:
    parts = []
    if owner not in (None, ""):
        parts.append(f'<span class="tag tag-owner">{html.escape(str(owner))}</span>')
    d = base.to_date_str(due)
    if d:
        parts.append(f'<span class="tag tag-due">Due {html.escape(d)}</span>')
    return " ".join(parts)


# -----------------------------------------------------------------------------
# SVG / HTML charts
# -----------------------------------------------------------------------------

def svg_diverging_bars(items: list[dict], axis_label: str) -> str:
    """items: {label, value(int), rag, cp(bool)} — horizontal +/- bars from zero."""
    items = [i for i in items if i.get("value") is not None]
    if not items:
        return '<p class="nodata">No data.</p>'
    n = len(items)
    row_h, top, bottom = 30, 10, 36
    W, label_w, pad_r = 1060, 320, 64
    H = top + n * row_h + bottom
    plot_w = W - label_w - pad_r
    vals = [i["value"] for i in items]
    vmin, vmax = min(0, min(vals)), max(0, max(vals))
    if vmax == vmin:
        vmax = vmin + 1
    scale = plot_w / (vmax - vmin)
    x_zero = label_w + (0 - vmin) * scale

    p = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="Inter,\'Segoe UI\',Arial,sans-serif" class="svgchart">']
    # gridlines at integer-ish ticks
    span = vmax - vmin
    step = max(1, round(span / 6))
    t = (vmin // step) * step
    while t <= vmax:
        x = label_w + (t - vmin) * scale
        p.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{H-bottom+4}" '
                 f'stroke="{LINE}" stroke-width="1"/>')
        p.append(f'<text x="{x:.1f}" y="{H-bottom+18}" font-size="11" fill="{MUTED}" '
                 f'text-anchor="middle">{t:+d}</text>')
        t += step
    # zero axis
    p.append(f'<line x1="{x_zero:.1f}" y1="{top-2}" x2="{x_zero:.1f}" y2="{H-bottom+4}" '
             f'stroke="#94a3b8" stroke-width="1.5"/>')

    for idx, it in enumerate(items):
        y = top + idx * row_h
        cy = y + row_h / 2
        v = it["value"]
        r = _rag(it.get("rag"))
        bw = abs(v) * scale
        bx = x_zero if v >= 0 else x_zero - bw
        stroke = (f' stroke="{NAVY}" stroke-width="1.6"' if it.get("cp") else "")
        p.append(f'<rect x="{bx:.1f}" y="{cy-8:.1f}" width="{max(bw,1.5):.1f}" height="16" '
                 f'rx="3" fill="{r["c"]}"{stroke}/>')
        # value text
        tv = f"{v:+d}d"
        if v >= 0:
            p.append(f'<text x="{x_zero+bw+7:.1f}" y="{cy+4:.1f}" font-size="11.5" '
                     f'fill="{INK}" font-weight="600">{tv}</text>')
        elif bx - 7 > label_w + 34:
            p.append(f'<text x="{bx-7:.1f}" y="{cy+4:.1f}" font-size="11.5" '
                     f'fill="{INK}" font-weight="600" text-anchor="end">{tv}</text>')
        else:  # not enough room left of the bar — label right of the zero axis
            p.append(f'<text x="{x_zero+7:.1f}" y="{cy+4:.1f}" font-size="11.5" '
                     f'fill="{INK}" font-weight="600">{tv}</text>')
        # label (+ CP badge)
        lx = label_w - 12
        if it.get("cp"):
            p.append(f'<rect x="6" y="{cy-8:.1f}" width="26" height="16" rx="3" fill="{NAVY}"/>')
            p.append(f'<text x="19" y="{cy+3.5:.1f}" font-size="9.5" fill="#fff" '
                     f'font-weight="700" text-anchor="middle">CP</text>')
        p.append(f'<text x="{lx}" y="{cy+4:.1f}" font-size="12" fill="{INK}" '
                 f'text-anchor="end">{html.escape(_trunc(it["label"], 44))}</text>')

    p.append(f'<text x="{label_w + plot_w/2:.0f}" y="{H-4}" font-size="11" fill="{MUTED}" '
             f'text-anchor="middle">{html.escape(axis_label)}</text>')
    p.append('</svg>')
    return "".join(p)


def html_bullet_progress(rows: list[dict]) -> str:
    """Bullet-style progress: coloured actual bar + dark planned tick."""
    out = ['<div class="bullet-wrap">',
           '<div class="bullet-legend">'
           f'<span><i class="sw" style="background:{RAG["Green"]["c"]}"></i>Actual (RAG colour)</span>'
           f'<span><i class="sw tick"></i>Planned this month</span>'
           f'<span><i class="sw" style="background:repeating-linear-gradient(45deg,{LINE},{LINE} 4px,#fff 4px,#fff 8px)"></i>Data gap</span>'
           '</div>']
    for r in rows:
        planned = base.safe_float(r.get("Planned_%_This_Month"))
        actual = base.safe_float(r.get("Actual_%_This_Month"))
        var = base.safe_float(r.get("Variance_%"))
        rag = _rag(r.get("RAG_Status"))
        label = (f'<b>{esc(r.get("Progress_ID"))}</b> '
                 f'{esc(r.get("Zone_Area"))} · {esc(r.get("Trade"))}')
        if actual is None:
            bar = ('<div class="btrack"><div class="bgap"></div>'
                   + (f'<div class="btick" style="left:{planned*100:.1f}%"></div>' if planned is not None else "")
                   + '</div>')
            vtxt = '<span class="bvar" style="color:#64748b">no data</span>'
        else:
            bar = (f'<div class="btrack">'
                   f'<div class="bfill" style="width:{actual*100:.1f}%;background:{rag["c"]}"></div>'
                   + (f'<div class="btick" style="left:{planned*100:.1f}%"></div>' if planned is not None else "")
                   + '</div>')
            if var is None:
                vtxt = '<span class="bvar">&mdash;</span>'
            else:
                col = RAG["Red"]["c"] if var < -0.05 else (RAG["Yellow"]["c"] if var < 0 else RAG["Green"]["c"])
                vtxt = f'<span class="bvar" style="color:{col}">{var*100:+.1f}%</span>'
        out.append(f'<div class="brow"><div class="blabel">{label}</div>{bar}{vtxt}</div>')
    out.append('</div>')
    return "".join(out)


def html_rag_mix(data: dict[str, list[dict]]) -> str:
    """One 100% stacked bar per workstream — replaces the donut."""
    streams = [
        ("Area Progress", "01_Area_Progress", "RAG_Status"),
        ("Programme Milestones", "02_Programme_Milestones", "RAG_Status"),
        ("Submission / RFI", "03_Submission_RFI", "RAG_Status"),
        ("Procurement", "04_Procurement", "Risk_Status"),
        ("Safety / Quality / Env", "05_Safety_Quality", "RAG_Status"),
        ("Risk / Action / Decision", "07_Risk_Action_Decision", "RAG_Status"),
    ]
    order = ["Red", "Yellow", "Green", "Data Gap"]
    out = ['<div class="mix-wrap">',
           '<div class="bullet-legend">' + "".join(
               f'<span><i class="sw" style="background:{RAG[k]["c"]}"></i>{k}</span>'
               for k in order) + '</div>']
    for label, sheet, key in streams:
        rows = data.get(sheet, [])
        counts = {k: 0 for k in order}
        for r in rows:
            v = str(r.get(key, "")).strip()
            if v in counts:
                counts[v] += 1
        total = sum(counts.values())
        if not total:
            continue
        segs = []
        for k in order:
            n = counts[k]
            if not n:
                continue
            segs.append(f'<div class="seg" style="flex:{n};background:{RAG[k]["c"]}">'
                        f'{n if n / total > 0.07 else ""}</div>')
        red_note = (f'<span class="mix-red">{counts["Red"]} Red</span>'
                    if counts["Red"] else '<span class="mix-ok">clear</span>')
        out.append(f'<div class="mix-row"><div class="mix-label">{html.escape(label)}</div>'
                   f'<div class="mix-bar">{"".join(segs)}</div>'
                   f'<div class="mix-total">{total} items · {red_note}</div></div>')
    out.append('</div>')
    return "".join(out)


def html_commercial(com: dict) -> str:
    """GP bullet + cash position bars as % of contract-incl-VO."""
    f = base.safe_float
    contract = f(com.get("Contract_Sum_with_VO_HKD_M"))
    obj_gp = f(com.get("Obj_GP_%"))
    cur_gp = f(com.get("Current_GP_%"))
    gp_delta = f(com.get("GP_vs_Objective_HKD_M"))

    rows = [
        ("Cost certified", f(com.get("Cost_Certified_HKD_M"))),
        ("Commitment", f(com.get("Commitment_HKD_M"))),
        ("Payment received", f(com.get("Payment_Received_HKD_M"))),
        ("Actual expenditure", f(com.get("Actual_Expenditure_HKD_M"))),
    ]
    bars = []
    if contract:
        for label, v in rows:
            if v is None:
                continue
            w = min(100.0, v / contract * 100)
            bars.append(
                f'<div class="crow"><div class="clabel">{label}</div>'
                f'<div class="ctrack"><div class="cfill" style="width:{w:.1f}%"></div></div>'
                f'<div class="cval">{v:,.1f}M <span>({v/contract*100:.0f}%)</span></div></div>')
    gp_html = ""
    if cur_gp is not None and obj_gp is not None:
        worst = max(cur_gp, obj_gp) * 1.35 or 1
        cw = cur_gp / worst * 100
        ow = obj_gp / worst * 100
        gp_col = RAG["Red"]["c"] if cur_gp < obj_gp * 0.8 else (
            RAG["Yellow"]["c"] if cur_gp < obj_gp else RAG["Green"]["c"])
        delta_txt = f' · Δ HK${gp_delta:+.2f}M vs objective' if gp_delta is not None else ""
        gp_html = (
            f'<div class="crow"><div class="clabel"><b>Current GP</b></div>'
            f'<div class="ctrack"><div class="cfill" style="width:{cw:.1f}%;background:{gp_col}"></div>'
            f'<div class="btick" style="left:{ow:.1f}%"></div></div>'
            f'<div class="cval">{cur_gp*100:.2f}% <span>(objective {obj_gp*100:.2f}%{delta_txt})</span></div></div>')
    note = (f'<p class="chart-note">Bars shown as share of contract sum incl. VO '
            f'(HK${contract:,.1f}M). Dark tick on the GP bar marks the objective.</p>'
            if contract else "")
    return f'<div class="cash-wrap">{gp_html}{"".join(bars)}</div>{note}'


# -----------------------------------------------------------------------------
# Table rendering (house-style)
# -----------------------------------------------------------------------------

def render_table(rows: list[dict], columns: list[tuple[str, str, str]]) -> str:
    out = ['<div class="tblwrap"><table class="data"><thead><tr>']
    for header, _, _ in columns:
        out.append(f"<th>{html.escape(header)}</th>")
    out.append("</tr></thead><tbody>")
    for row in rows:
        rag_value = str(row.get("RAG_Status") or row.get("Risk_Status") or "").strip()
        cls = ""
        if rag_value == "Red":
            cls = ' class="row-red"'
        elif rag_value == "Data Gap":
            cls = ' class="row-gap"'
        out.append(f"<tr{cls}>")
        for _, key, ftype in columns:
            v = row.get(key)
            if ftype == "date":
                cell = html.escape(base.to_date_str(v)) or "&mdash;"
            elif ftype == "pct":
                cell = base.pct(v, 1)
            elif ftype == "rag":
                cell = rag_chip(v)
            elif ftype == "status":
                cell = status_chip(v)
            elif ftype == "int":
                fv = base.safe_float(v)
                cell = "&mdash;" if fv is None else f"{int(fv):,}"
            else:
                cell = esc(v)
            out.append(f"<td>{cell}</td>")
        out.append("</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


# -----------------------------------------------------------------------------
# CSS
# -----------------------------------------------------------------------------

CSS = """
:root{
  --navy:#1e293b; --navy-deep:#0f172a; --amber:#f59e0b;
  --ink:#334155; --muted:#64748b; --line:#e2e8f0; --bg:#f1f5f9;
  --green:#16a34a; --yellow:#d97706; --red:#dc2626; --gap:#64748b;
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Inter,'Segoe UI',-apple-system,'Helvetica Neue',Arial,'Noto Sans HK',sans-serif;
  color:var(--ink);background:var(--bg);font-size:14px;line-height:1.5;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:1180px;margin:0 auto;padding:0 28px}

/* ---------- masthead ---------- */
.topline{height:4px;background:var(--amber)}
header.mast{background:linear-gradient(135deg,var(--navy-deep) 0%,var(--navy) 60%,#27364d 100%);color:#fff;padding:26px 0 22px}
.mast-grid{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;flex-wrap:wrap}
.mast .doctype{font-size:11px;letter-spacing:2.2px;text-transform:uppercase;color:var(--amber);font-weight:700;margin-bottom:8px}
.mast h1{font-size:26px;font-weight:700;letter-spacing:-.3px;line-height:1.25;max-width:760px}
.mast .sub{margin-top:8px;font-size:13.5px;color:#cbd5e1}
.mast .sub b{color:#fff;font-weight:600}
.mast .gov-tag{margin-top:12px;font-size:11px;letter-spacing:1.6px;text-transform:uppercase;color:#94a3b8}
.mast .gov-tag b{color:var(--amber)}
.mast-right{display:flex;flex-direction:column;align-items:flex-end;gap:12px}
.logochip{background:#fff;border-radius:8px;padding:7px 14px;display:flex;align-items:center}
.wordmark{display:flex;flex-direction:column;align-items:flex-end;gap:2px;text-align:right}
.wm-name{font-size:15px;font-weight:800;letter-spacing:0.06em;text-transform:uppercase;color:#f8fafc;border-bottom:2px solid #f59e0b;padding-bottom:3px}
.wm-sub{font-size:9.5px;letter-spacing:0.18em;text-transform:uppercase;color:#94a3b8}
.logochip img{height:30px;width:auto;display:block}
.statusbadge{font-size:13px;font-weight:700;letter-spacing:.6px;color:#fff;
  padding:9px 18px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.25)}

/* ---------- draft governance banner ---------- */
.draftbar{background:#fffbeb;border-bottom:1px solid #fde68a}
.draftbar .in{display:flex;gap:14px;align-items:center;padding:10px 0;flex-wrap:wrap}
.draftbar .dchip{background:var(--amber);color:#fff;font-weight:800;font-size:11px;
  letter-spacing:1.5px;padding:4px 10px;border-radius:5px;text-transform:uppercase}
.draftbar p{font-size:13px;color:#92400e}
.draftbar b{font-weight:700}
.draftbar .gatecount{margin-left:auto;font-size:12px;color:#92400e;font-weight:600}

/* ---------- 5-second director row ---------- */
.hero{display:grid;grid-template-columns:1.1fr 1fr 1fr 1fr;gap:14px;margin:22px 0 8px}
.hero .tile{background:#fff;border:1px solid var(--line);border-radius:10px;padding:16px 18px;
  border-top:3px solid var(--line)}
.hero .tile .k{font-size:10.5px;letter-spacing:1.4px;text-transform:uppercase;color:var(--muted);font-weight:700;margin-bottom:8px}
.hero .tile .v{font-size:15px;font-weight:600;color:var(--navy);line-height:1.45}
.hero .tile .v .big{font-size:24px;font-weight:800;display:block;margin-bottom:2px}
.hero .tile .m{margin-top:6px;font-size:12px;color:var(--muted)}

/* ---------- KPI band ---------- */
.kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:14px;margin:16px 0 26px}
.kpi{background:#fff;border:1px solid var(--line);border-left:4px solid var(--line);
  border-radius:10px;padding:14px 16px}
.kpi .k{font-size:10px;letter-spacing:1.2px;text-transform:uppercase;color:var(--muted);font-weight:700}
.kpi .v{font-size:26px;font-weight:800;color:var(--navy);margin-top:4px;letter-spacing:-.5px}
.kpi .v small{font-size:13px;font-weight:600;color:var(--muted);letter-spacing:0}
.kpi .s{font-size:11.5px;color:var(--muted);margin-top:3px;line-height:1.4}

/* ---------- sections ---------- */
section.card{background:#fff;border:1px solid var(--line);border-radius:12px;
  padding:22px 26px;margin-bottom:20px}
.sechead{display:flex;align-items:baseline;gap:10px;border-left:4px solid var(--amber);
  padding-left:12px;margin-bottom:16px}
.sechead h2{font-size:16.5px;font-weight:700;color:var(--navy);letter-spacing:-.2px}
.sechead .zh{font-size:13px;color:var(--muted);font-weight:500}
.sechead .right{margin-left:auto;font-size:12px;color:var(--muted)}
section.card h3{font-size:13px;font-weight:700;color:var(--navy);margin:18px 0 8px}
.chart-note{font-size:11.5px;color:var(--muted);margin-top:6px}

/* ---------- AI summary ---------- */
.ai-head{display:flex;align-items:center;gap:10px;margin-bottom:12px;flex-wrap:wrap}
.ai-chip{background:var(--navy);color:#fff;font-size:10px;font-weight:700;letter-spacing:1.4px;
  text-transform:uppercase;padding:4px 10px;border-radius:5px}
.ai-note{font-size:12px;color:var(--muted)}
ul.ai{list-style:none}
ul.ai li{padding:8px 0 8px 16px;border-bottom:1px dashed var(--line);font-size:13.5px;position:relative}
ul.ai li:last-child{border-bottom:none}
ul.ai li::before{content:"";position:absolute;left:0;top:15px;width:6px;height:6px;border-radius:2px;background:var(--amber)}
ul.ai li b{color:var(--navy)}
.signoff{margin-top:14px;padding-top:12px;border-top:1px solid var(--line);
  display:flex;gap:36px;flex-wrap:wrap;font-size:12px;color:var(--muted)}
.signoff .line{border-bottom:1px solid #94a3b8;min-width:200px;display:inline-block;height:16px}

/* ---------- decision pack ---------- */
.dp{display:flex;flex-direction:column;gap:10px}
.dp .item{display:flex;gap:14px;align-items:flex-start;background:#fef2f2;
  border:1px solid #fecaca;border-left:4px solid var(--red);border-radius:8px;padding:12px 16px}
.dp .num{background:var(--red);color:#fff;font-weight:800;font-size:13px;min-width:26px;height:26px;
  border-radius:50%;display:flex;align-items:center;justify-content:center;margin-top:2px}
.dp .body{font-size:13.5px}
.dp .body .what{color:var(--navy)}
.dp .body .ask{font-weight:700;color:#991b1b}
.dp .meta{margin-top:6px;display:flex;gap:8px;flex-wrap:wrap}
.tag{font-size:11px;font-weight:600;padding:2.5px 9px;border-radius:999px}
.tag-owner{background:#e2e8f0;color:var(--navy)}
.tag-due{background:#fee2e2;color:#991b1b}
.tag-id{background:var(--navy);color:#fff}

/* ---------- chips ---------- */
.chip{display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:600;
  padding:2.5px 9px;border-radius:999px;white-space:nowrap}
.chip i{width:7px;height:7px;border-radius:50%;display:inline-block}

/* ---------- charts ---------- */
.svgchart{width:100%;height:auto;display:block}
.bullet-wrap,.mix-wrap,.cash-wrap{display:flex;flex-direction:column;gap:7px}
.bullet-legend{display:flex;gap:18px;font-size:11.5px;color:var(--muted);margin-bottom:6px}
.bullet-legend .sw{width:12px;height:9px;border-radius:2px;display:inline-block;margin-right:5px}
.bullet-legend .sw.tick{width:3px;height:12px;background:var(--navy);border-radius:1px}
.brow{display:grid;grid-template-columns:280px 1fr 64px;gap:12px;align-items:center}
.blabel{font-size:12px;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.blabel b{color:var(--navy)}
.btrack{position:relative;height:15px;background:#eef2f6;border-radius:4px;overflow:visible}
.bfill{height:100%;border-radius:4px 0 0 4px}
.bgap{height:100%;border-radius:4px;background:repeating-linear-gradient(45deg,#e2e8f0,#e2e8f0 4px,#f8fafc 4px,#f8fafc 8px)}
.btick{position:absolute;top:-3px;width:3px;height:21px;background:var(--navy);border-radius:1px}
.bvar{font-size:12px;font-weight:700;text-align:right}
.mix-row{display:grid;grid-template-columns:200px 1fr 150px;gap:12px;align-items:center}
.mix-label{font-size:12.5px;font-weight:600;color:var(--navy)}
.mix-bar{display:flex;height:20px;border-radius:5px;overflow:hidden;gap:2px;background:#f8fafc}
.mix-bar .seg{display:flex;align-items:center;justify-content:center;color:#fff;font-size:11px;font-weight:700;min-width:2px}
.mix-total{font-size:11.5px;color:var(--muted)}
.mix-red{color:var(--red);font-weight:700}
.mix-ok{color:var(--green);font-weight:600}
.crow{display:grid;grid-template-columns:150px 1fr 230px;gap:12px;align-items:center}
.clabel{font-size:12.5px;color:var(--ink)}
.ctrack{position:relative;height:15px;background:#eef2f6;border-radius:4px}
.cfill{height:100%;border-radius:4px 0 0 4px;background:var(--navy)}
.cval{font-size:12.5px;font-weight:700;color:var(--navy)}
.cval span{font-weight:500;color:var(--muted);font-size:11.5px}
.nodata{font-size:12.5px;color:var(--muted)}

/* ---------- tables ---------- */
.tblwrap{overflow-x:auto}
table.data{width:100%;border-collapse:collapse;font-size:12.5px}
table.data th{background:var(--navy);color:#fff;text-align:left;padding:8px 10px;
  font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:.7px;white-space:nowrap}
table.data td{padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:top}
table.data tr:nth-child(even) td{background:#f8fafc}
table.data tr.row-red td{background:#fef2f2}
table.data tr.row-gap td{background:#f8fafc;color:var(--muted)}

/* ---------- review gates ---------- */
.gatebar{background:#065f46;color:#fff;border-radius:8px;padding:10px 16px;display:flex;
  gap:12px;align-items:center;margin-bottom:14px;font-size:13px}
.gatebar b{font-weight:700}
.gatebar .prog{margin-left:auto;font-weight:700}
.gates{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.gate{border:1px solid var(--line);border-radius:9px;padding:12px 14px;background:#fff}
.gate .gid{font-size:10px;letter-spacing:1.2px;text-transform:uppercase;color:var(--muted);font-weight:700}
.gate .gsec{font-size:13px;font-weight:700;color:var(--navy);margin:3px 0 4px}
.gate .grev{font-size:11.5px;color:var(--muted);margin-bottom:4px}
.gate .gchk{font-size:11px;color:var(--muted);line-height:1.45;margin-bottom:8px}

/* ---------- meta + footer ---------- */
.metaline{display:flex;gap:26px;flex-wrap:wrap;padding:14px 0 2px;font-size:12.5px;color:var(--muted)}
.metaline b{color:var(--navy);font-weight:600}
footer{margin:30px 0 50px;text-align:center;font-size:12px;color:var(--muted);line-height:1.7}
footer .steps{display:inline-flex;gap:8px;align-items:center;margin-bottom:10px;font-weight:700;color:var(--navy);font-size:12.5px}
footer .steps .arrow{color:var(--amber)}

@media(max-width:900px){
  .hero{grid-template-columns:1fr 1fr}
  .kpis{grid-template-columns:repeat(3,1fr)}
  .gates{grid-template-columns:repeat(2,1fr)}
  .brow{grid-template-columns:150px 1fr 56px}
  .mix-row{grid-template-columns:130px 1fr 120px}
  .crow{grid-template-columns:110px 1fr 150px}
}
@media print{
  @page{size:A4;margin:11mm}
  body{background:#fff;font-size:12px}
  .wrap{max-width:none;padding:0}
  header.mast{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  section.card,.hero .tile,.kpi,.gate{border:1px solid var(--line);box-shadow:none;break-inside:avoid}
  section.card{page-break-inside:auto}
  .sechead,.dp .item,.brow,.mix-row,.crow,table.data tr{break-inside:avoid}
  *{-webkit-print-color-adjust:exact;print-color-adjust:exact}
}
"""


# -----------------------------------------------------------------------------
# Page assembly
# -----------------------------------------------------------------------------

def sec(title_en: str, title_zh: str, body: str, right: str = "", anchor: str = "") -> str:
    a = f' id="{anchor}"' if anchor else ""
    r = f'<span class="right">{right}</span>' if right else ""
    return (f'<section class="card"{a}><div class="sechead">'
            f'<h2>{html.escape(title_en)}</h2><span class="zh">{html.escape(title_zh)}</span>{r}'
            f'</div>{body}</section>')


def render_html_v2(
    data: dict[str, list[dict[str, Any]]],
    kpis: "base.KPIs",
    summary: list[str],
    period: str,
    source_path: Path,
    logo_b64: str | None,
) -> str:
    profile = {r["Field"]: r["Value"] for r in data.get("00_Project_Profile", [])
               if isinstance(r, dict) and r.get("Field")}
    project_name = profile.get("Project_Name", "—")
    project_id = profile.get("Project_ID", "—")
    contract_no = profile.get("Contract_No", "—")
    subcontractor = profile.get("Subcontractor", "") or profile.get("Subcontractor_Name", "—")
    report_as_of = base.to_date_str(profile.get("Report_As_Of", profile.get("Reporting_Date", period)))
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    # --- status ---
    st = kpis.overall_status
    st_style = {"GO": RAG["Green"]["c"], "CONTROL": RAG["Yellow"]["c"], "STOP": RAG["Red"]["c"]}
    st_label = {"GO": "GO — Confirm & Proceed",
                "CONTROL": "CONTROL — PM / QS / Planner Review",
                "STOP": "STOP — Director / Safety Escalation"}
    reasons = []
    if kpis.milestone_critical_red:
        reasons.append(f"{kpis.milestone_critical_red} critical-path milestones Red (max {kpis.milestone_max_delay_days}d)")
    if kpis.safety_red:
        reasons.append(f"{kpis.safety_red} safety Red")
    if kpis.procurement_red:
        reasons.append(f"{kpis.procurement_red} procurement Red")
    if kpis.decision_red:
        reasons.append(f"{kpis.decision_red} Red decisions open")
    status_reason = " · ".join(reasons) or "No Red exceptions this cycle"

    # --- review gate progress ---
    gates = data.get("09_Review_Gates", [])
    gates_total = len(gates)
    gates_ready = sum(1 for g in gates
                      if str(g.get("Output_Status", "")).strip() in STATUS_GOOD)
    gates_out = gates_total - gates_ready

    # --- decisions ---
    decisions = data.get("07_Risk_Action_Decision", [])
    red_open = [d for d in decisions
                if str(d.get("RAG_Status", "")).strip() == "Red"
                and str(d.get("Status", "")).strip() == "Open"]

    # --- hero tiles ---
    top_signal = "—"
    ms_red_cp = [m for m in data.get("02_Programme_Milestones", [])
                 if str(m.get("RAG_Status", "")).strip() == "Red"
                 and str(m.get("Critical_Path", "")).strip().lower() == "yes"]
    if ms_red_cp:
        worst = max(ms_red_cp, key=lambda m: base.safe_float(m.get("Variance_Days")) or 0)
        top_signal = (f'{esc(worst.get("Milestone_Name"))} forecast '
                      f'<b>{int(base.safe_float(worst.get("Variance_Days")) or 0):+d} days</b> vs baseline')
    money_signal = "—"
    if kpis.commercial_gp_delta_hkd_m is not None:
        money_signal = (f'GP <b>{base.pct(kpis.commercial_current_gp_pct,2)}</b> vs objective '
                        f'{base.pct(kpis.commercial_objective_gp_pct,2)} '
                        f'(&Delta; HK${kpis.commercial_gp_delta_hkd_m:+.2f}M)')
    move_signal = "—"
    if red_open:
        d0 = red_open[0]
        move_signal = (f'{esc(d0.get("Decision_Required"))} '
                       f'<span class="m">Owner: {esc(d0.get("Owner"))} · Due {base.to_date_str(d0.get("Due_Date"))}</span>')

    hero = f"""
<div class="hero">
  <div class="tile" style="border-top-color:{st_style[st]}">
    <div class="k">Overall Status 整體狀態</div>
    <div class="v"><span class="big" style="color:{st_style[st]}">{st}</span>{html.escape(status_reason)}</div>
  </div>
  <div class="tile" style="border-top-color:{RAG['Red']['c']}">
    <div class="k">Top Programme Signal</div>
    <div class="v" style="font-weight:500">{top_signal}</div>
  </div>
  <div class="tile" style="border-top-color:{_rag(kpis.commercial_rag)['c']}">
    <div class="k">Commercial Signal</div>
    <div class="v" style="font-weight:500">{money_signal}</div>
  </div>
  <div class="tile" style="border-top-color:{NAVY}">
    <div class="k">Required Management Move</div>
    <div class="v" style="font-weight:500">{move_signal}</div>
  </div>
</div>"""

    # --- KPI band ---
    def kpi_tile(label, value, sub, rag_key):
        return (f'<div class="kpi" style="border-left-color:{RAG[rag_key]["c"]}">'
                f'<div class="k">{html.escape(label)}</div>'
                f'<div class="v">{value}</div>'
                f'<div class="s">{html.escape(sub)}</div></div>')

    kpi_band = '<div class="kpis">' + "".join([
        kpi_tile("Programme", f'{kpis.milestone_red}<small> Red</small>',
                 f"{kpis.milestone_critical_red} on critical path · max delay {kpis.milestone_max_delay_days}d",
                 "Red" if kpis.milestone_critical_red else ("Yellow" if kpis.milestone_amber else "Green")),
        kpi_tile("Progress", f'{kpis.progress_red}<small> Red</small>',
                 f"{kpis.progress_amber} Yellow · {kpis.progress_data_gap} data gap · avg {base.pct(kpis.progress_avg_variance,1)}",
                 "Red" if kpis.progress_red else ("Yellow" if kpis.progress_amber else "Green")),
        kpi_tile("RFI / Submission", f'{kpis.rfi_overdue}<small> overdue</small>',
                 f"{kpis.rfi_red} Red · worst {kpis.rfi_max_overdue}d past due",
                 "Red" if kpis.rfi_red else ("Yellow" if kpis.rfi_overdue else "Green")),
        kpi_tile("Procurement", f'{kpis.procurement_red}<small> Red</small>',
                 f"{kpis.procurement_amber} Yellow · worst slip {kpis.procurement_max_delay}d",
                 "Red" if kpis.procurement_red else ("Yellow" if kpis.procurement_amber else "Green")),
        kpi_tile("Safety / Quality", f'{kpis.safety_red}<small> Red</small>',
                 f"{kpis.safety_open} open · {kpis.safety_overdue} overdue · {kpis.quality_open_ncr} NCR",
                 "Red" if kpis.safety_red else ("Yellow" if kpis.safety_open else "Green")),
        kpi_tile("Commercial",
                 base.pct(kpis.commercial_current_gp_pct, 2) if kpis.commercial_current_gp_pct is not None else "&mdash;",
                 (f"Δ HK${kpis.commercial_gp_delta_hkd_m:+.2f}M vs objective"
                  if kpis.commercial_gp_delta_hkd_m is not None else "no data"),
                 kpis.commercial_rag if kpis.commercial_rag in RAG else "Yellow"),
    ]) + '</div>'

    # --- AI summary ---
    items = []
    for s in summary:
        text = s.replace("**", "")
        if text.startswith("Overall management status"):
            continue  # already the hero
        head, _, rest = text.partition(":")
        if rest:
            items.append(f"<li><b>{html.escape(head)}:</b>{html.escape(rest)}</li>")
        else:
            items.append(f"<li>{html.escape(text)}</li>")
    ai_html = (
        '<div class="ai-head"><span class="ai-chip">AI-Drafted</span>'
        '<span class="ai-note">Deterministic rules over the data pack — same data in, same findings out. '
        'No number below was authored by a free-text model.</span></div>'
        f'<ul class="ai">{"".join(items)}</ul>'
        '<div class="signoff">'
        '<span>Reviewed by (PM / QS): <span class="line"></span></span>'
        '<span>Approved by (Director): <span class="line"></span></span>'
        f'<span>Date: <span class="line" style="min-width:110px"></span></span>'
        '</div>')

    # --- decision pack ---
    dp_items = []
    for i, d in enumerate(red_open, 1):
        dp_items.append(
            f'<div class="item"><div class="num">{i}</div><div class="body">'
            f'<span class="tag tag-id">{esc(d.get("Issue_ID"))}</span> '
            f'<span class="what">{esc(d.get("Description"))} — {esc(d.get("Impact"))}</span><br>'
            f'<span class="ask">Decision required: {esc(d.get("Decision_Required"))}</span>'
            f'<div class="meta">{owner_due(d.get("Owner"), d.get("Due_Date"))}</div>'
            f'</div></div>')
    dp_html = ('<div class="dp">' + "".join(dp_items) + '</div>') if dp_items else \
        '<p class="nodata">No Red decision items this cycle.</p>'

    # --- charts ---
    ms_items = []
    for m in data.get("02_Programme_Milestones", []):
        v = base.safe_float(m.get("Variance_Days"))
        if v is None:
            continue
        ms_items.append({
            "label": f'{m.get("Milestone_ID")} {m.get("Milestone_Name")}',
            "value": int(v),
            "rag": m.get("RAG_Status"),
            "cp": str(m.get("Critical_Path", "")).strip().lower() == "yes",
        })
    ms_items.sort(key=lambda i: -i["value"])
    milestones_chart = svg_diverging_bars(
        ms_items, "Variance vs baseline (days) — CP = critical path · positive = behind")

    rfi_items = []
    for r in data.get("03_Submission_RFI", []):
        v = base.safe_float(r.get("Days_Open_Overdue"))
        rfi_items.append({
            "label": f'{r.get("Record_ID")} {_trunc(r.get("Description"), 34)}',
            "value": int(v) if v is not None else None,
            "rag": r.get("RAG_Status"), "cp": False})
    rfi_items = [i for i in rfi_items if i["value"] is not None]
    rfi_items.sort(key=lambda i: -i["value"])
    rfi_chart = svg_diverging_bars(rfi_items, "Days past response-due · negative = ahead of due date")

    proc_items = []
    for r in data.get("04_Procurement", []):
        v = base.safe_float(r.get("Variance_Days"))
        proc_items.append({
            "label": f'{r.get("Item_ID")} {_trunc(r.get("Item_Description"), 34)}',
            "value": int(v) if v is not None else None,
            "rag": r.get("Risk_Status"), "cp": False})
    proc_items = [i for i in proc_items if i["value"] is not None]
    proc_items.sort(key=lambda i: -i["value"])
    proc_chart = svg_diverging_bars(proc_items, "Forecast delivery vs required on-site date (days)")

    com_rows = data.get("06_Commercial_Cost", [])
    com = com_rows[-1] if com_rows else {}

    # --- detail tables (reuse column specs of v1, restyled) ---
    progress_table = render_table(data.get("01_Area_Progress", []), [
        ("ID", "Progress_ID", "text"), ("Zone / Area", "Zone_Area", "text"),
        ("Activity", "Activity", "text"), ("Planned %", "Planned_%_This_Month", "pct"),
        ("Actual %", "Actual_%_This_Month", "pct"), ("Variance", "Variance_%", "pct"),
        ("RAG", "RAG_Status", "rag"), ("Reason", "Delay_Variance_Reason", "text"),
        ("Owner", "Owner", "text"), ("Due", "Due_Date", "date")])
    milestone_table = render_table(data.get("02_Programme_Milestones", []), [
        ("ID", "Milestone_ID", "text"), ("Milestone", "Milestone_Name", "text"),
        ("Baseline", "Baseline_Date", "date"), ("Forecast", "Current_Forecast_Date", "date"),
        ("Δ days", "Variance_Days", "int"), ("Critical Path", "Critical_Path", "text"),
        ("RAG", "RAG_Status", "rag"), ("Reason", "Reason", "text"), ("Owner", "Owner", "text")])
    rfi_table = render_table(data.get("03_Submission_RFI", []), [
        ("ID", "Record_ID", "text"), ("Type", "Type", "text"),
        ("Trade", "Package_Trade", "text"), ("Description", "Description", "text"),
        ("Days Open / Overdue", "Days_Open_Overdue", "int"),
        ("Status", "Status_Normalized", "status"),
        ("Prog. Impact (d)", "Programme_Impact_Days", "int"),
        ("RAG", "RAG_Status", "rag"), ("Owner", "Responsible_Person", "text")])
    procurement_table = render_table(data.get("04_Procurement", []), [
        ("ID", "Item_ID", "text"), ("Item", "Item_Description", "text"),
        ("Package", "Package", "text"), ("Required On-site", "Required_Onsite_Date", "date"),
        ("Approval", "Approval_Status", "status"), ("PO", "PO_Status", "status"),
        ("Forecast Delivery", "Forecast_Delivery_Date", "date"), ("Δ days", "Variance_Days", "int"),
        ("Risk", "Risk_Status", "rag"), ("Owner", "Owner", "text")])
    safety_table = render_table(data.get("05_Safety_Quality", []), [
        ("ID", "Record_ID", "text"), ("Category", "Category", "text"),
        ("Metric / Issue", "Metric_or_Issue", "text"), ("Actual", "Actual_Result", "text"),
        ("Target", "Target", "text"), ("Status", "Status", "status"),
        ("Area", "Area", "text"), ("Days Overdue", "Days_Overdue", "int"),
        ("RAG", "RAG_Status", "rag"), ("Owner", "Owner", "text")])
    decision_table = render_table(decisions, [
        ("ID", "Issue_ID", "text"), ("Category", "Category", "text"),
        ("Linked", "Linked_Records", "text"), ("Description", "Description", "text"),
        ("Impact", "Impact", "text"), ("Decision Required", "Decision_Required", "text"),
        ("Owner", "Owner", "text"), ("Due", "Due_Date", "date"),
        ("Status", "Status", "status"), ("RAG", "RAG_Status", "rag")])

    # commercial stat grid
    f = base.safe_float
    com_stats = [
        ("Contract incl. VO", f(com.get("Contract_Sum_with_VO_HKD_M")), "HK$M"),
        ("VO Net", f(com.get("VO_Net_HKD_M")), "HK$M"),
        ("Nett Cashflow", f(com.get("Nett_Cashflow_HKD_M")), "HK$M"),
        ("Risk Exposure", f(com.get("Risk_Exposure_HKD_M")), "HK$M"),
        ("Performance Score", f(com.get("Performance_Score_0_to_10")), "/10"),
    ]
    com_stat_html = '<div class="kpis" style="grid-template-columns:repeat(5,1fr);margin:0 0 16px">'
    for label, v, unit in com_stats:
        disp = "&mdash;" if v is None else (f"{v:,.2f}" if unit == "HK$M" else f"{v:.1f}")
        com_stat_html += (f'<div class="kpi"><div class="k">{html.escape(label)}</div>'
                          f'<div class="v">{disp}<small> {unit}</small></div></div>')
    com_stat_html += '</div>'

    # review gates
    gate_cards = []
    for g in gates:
        gate_cards.append(
            '<div class="gate">'
            f'<div class="gid">{esc(g.get("Review_Gate_ID"))}</div>'
            f'<div class="gsec">{esc(g.get("Report_Section"))}</div>'
            f'<div class="grev">Reviewer: <b>{esc(g.get("Reviewer"))}</b></div>'
            f'<div class="gchk">{html.escape(_trunc(g.get("What_To_Check"), 140))}</div>'
            f'{status_chip(g.get("Output_Status"))}</div>')
    gates_html = (
        f'<div class="gatebar"><b>AI Drafts &rarr; Human Checks &rarr; Human Signs</b>'
        f'<span>every section below carries a named human reviewer before this report can leave the project.</span>'
        f'<span class="prog">{gates_ready} of {gates_total} gates cleared</span></div>'
        f'<div class="gates">{"".join(gate_cards)}</div>')

    reporting_entity = str(profile.get("Subcontractor")
                           or profile.get("Client_or_Main_Contractor")
                           or project_name or "").strip()
    if logo_b64:
        logo_html = (f'<div class="logochip"><img src="data:image/png;base64,{logo_b64}" '
                     f'alt="{html.escape(reporting_entity)}"></div>')
    elif reporting_entity:
        logo_html = (f'<div class="wordmark"><span class="wm-name">{html.escape(reporting_entity)}</span>'
                     f'<span class="wm-sub">Monthly Project Health Report</span></div>')
    else:
        logo_html = ""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(str(project_name))} · Monthly Project Health Report · {html.escape(period)}</title>
<style>{CSS}</style>
</head>
<body>
<div class="topline"></div>
<header class="mast"><div class="wrap mast-grid">
  <div>
    <div class="doctype">Monthly Project Health Report · {html.escape(period)}</div>
    <h1>{html.escape(str(project_name))}</h1>
    <div class="sub">Project <b>{html.escape(str(project_id))}</b> · Contract <b>{html.escape(str(contract_no))}</b>
      · Subcontractor <b>{html.escape(str(subcontractor))}</b> · As of <b>{html.escape(report_as_of)}</b></div>
    <div class="gov-tag"><b>AI drafts</b> &rarr; human checks &rarr; human signs</div>
  </div>
  <div class="mast-right">
    {logo_html}
    <div class="statusbadge" style="background:{st_style[st]}">{html.escape(st_label[st])}</div>
  </div>
</div></header>

<div class="draftbar"><div class="wrap in">
  <span class="dchip">Draft</span>
  <p><b>內部審閱版 · Internal review draft.</b> AI-drafted from
  <b>{html.escape(source_path.name)}</b> — not for external issue until all review gates are cleared.</p>
  <span class="gatecount">{gates_out} of {gates_total} review gates outstanding &darr;</span>
</div></div>

<div class="wrap">

{hero}

{sec("AI Executive Summary", "行政摘要", ai_html, right=f"Period {html.escape(period)}", anchor="summary")}

{kpi_band}

{sec("Top Decision Pack", "須決策事項", dp_html,
     right=f"{len(red_open)} Red items need Director sign-off", anchor="decisions")}

{sec("Health by Workstream", "各工作流健康狀況", html_rag_mix(data),
     right="every item in the pack, one bar per workstream", anchor="mix")}

{sec("Programme Milestones — Variance", "程序里程碑 — 偏差", milestones_chart, anchor="programme-chart")}

{sec("Area Progress — Planned vs Actual", "區域進度 — 計劃對實際",
     html_bullet_progress(data.get("01_Area_Progress", [])), anchor="progress-chart")}

{sec("Submission / RFI Aging", "提交與 RFI 逾期情況", rfi_chart, anchor="rfi-chart")}

{sec("Procurement Delivery Risk", "採購交付風險", proc_chart, anchor="proc-chart")}

{sec("Commercial Position", "商業狀況", com_stat_html + html_commercial(com), anchor="commercial")}

{sec("Area Progress Register", "區域施工進度", progress_table, anchor="progress")}
{sec("Programme Milestones Register", "程序里程碑", milestone_table, anchor="programme")}
{sec("Submission / RFI Register", "提交與 RFI 登記", rfi_table, anchor="rfi")}
{sec("Procurement Tracker", "採購追蹤", procurement_table, anchor="procurement")}
{sec("Safety / Quality / Environmental", "安全、品質、環境", safety_table, anchor="safety")}
{sec("Risk · Action · Decision Log", "風險、行動、決策紀錄", decision_table, anchor="actions")}

{sec("Human Review Gates", "人手審閱閘門", gates_html, anchor="gates")}

<div class="metaline">
  <span>Generated <b>{html.escape(generated_at)}</b></span>
  <span>Source <b>{html.escape(source_path.name)}</b></span>
  <span>KPIs recomputed by deterministic Python tools — no free-text model authored any number</span>
</div>

<footer>
  <div class="steps">AI Drafts <span class="arrow">&rarr;</span> Human Checks <span class="arrow">&rarr;</span> Human Signs</div>
  <p>This is a training demonstration built on fictional data. Review gates above must be cleared and the
  report wet-signed by the named signatories before any external issue.</p>
  <p>&copy; OpenDeedigital &times; HKIC 2026 · AI2C Monthly Report Agent · Premium HTML edition V2</p>
</footer>

</div>
</body>
</html>
"""


# -----------------------------------------------------------------------------
# Entry point (same CLI as v1)
# -----------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="demo-data/AI2C_Day2_Monthly_Report_Data_Pack_Demo.xlsx")
    parser.add_argument("--period", default="2026-04")
    parser.add_argument("--output", default=None)
    parser.add_argument("--logo", default="", help="optional logo PNG; default = text wordmark from the data pack")
    args = parser.parse_args(argv)

    project_root = Path(__file__).resolve().parent.parent
    input_path = (project_root / args.input).resolve()
    logo_path = (project_root / args.logo).resolve() if args.logo else None
    if args.output:
        out_path = (project_root / args.output).resolve()
    else:
        out_path = (project_root / "outputs" / "monthly_report" / args.period
                    / "monthly_report_premium_v2.html").resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        print(f"ERROR: input not found: {input_path}", file=sys.stderr)
        return 1

    print(f"Loading workbook: {input_path}")
    data = base.load_workbook_as_dict(input_path)
    kpis = base.compute_kpis(data)
    print(f"  Overall: {kpis.overall_status}")
    summary = base.build_ai_summary(data, kpis, args.period)

    logo_b64 = base.file_to_base64(logo_path) if (logo_path and logo_path.exists()) else None

    rendered = render_html_v2(
        data=data, kpis=kpis, summary=summary, period=args.period,
        source_path=input_path, logo_b64=logo_b64)
    out_path.write_text(rendered, encoding="utf-8")
    print(f"OK - wrote {out_path.stat().st_size/1024:,.1f} KB -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
