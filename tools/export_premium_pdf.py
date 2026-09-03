#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""EXPORT PDF — print the OpenDeedigital premium dashboard (HTML) to an A4 PDF.

Deterministic. Uses headless Chrome / Edge (found automatically; override with
CHROME_PATH). No model, no network.
Usage:
    python tools/export_premium_pdf.py --report-dir outputs/monthly_report/2026-04
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _resolve(p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() else ROOT / path


def find_chrome() -> str | None:
    env = os.environ.get("CHROME_PATH")
    if env and Path(env).exists():
        return env
    cands: list[str] = []
    sysname = platform.system()
    if sysname == "Windows":
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                     os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                     os.environ.get("LocalAppData", "")):
            cands += [rf"{base}\Google\Chrome\Application\chrome.exe",
                      rf"{base}\Microsoft\Edge\Application\msedge.exe"]
    elif sysname == "Darwin":
        cands += ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "msedge"):
        p = shutil.which(name)
        if p:
            cands.append(p)
    for c in cands:
        if c and Path(c).exists():
            return c
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report-dir", required=True, help="e.g. outputs/monthly_report/2026-04")
    ap.add_argument("--html-name", default="monthly_report_premium.html")
    ap.add_argument("--out", default=None, help="PDF path (default: <report-dir>/monthly_report_premium.pdf)")
    ap.add_argument("--landscape", action="store_true", help="A4 landscape instead of portrait")
    ap.add_argument("--zoom", type=float, default=0.8, help="CSS zoom applied for print (default 0.8)")
    a = ap.parse_args()

    rdir = _resolve(a.report_dir)
    src = rdir / a.html_name
    if not src.exists():
        sys.exit(f"ERROR: report HTML not found: {src}")
    out = _resolve(a.out) if a.out else rdir / "monthly_report_premium.pdf"

    # print copy with page setup injected (screen dashboard -> A4 pages)
    orientation = "landscape" if a.landscape else "portrait"
    page_css = (f"<style>@page{{size:A4 {orientation};margin:8mm}}"
                f" html{{zoom:{a.zoom}}} body{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}"
                " img,svg,table,figure,.kpi,.tile{page-break-inside:avoid;break-inside:avoid}"
                " img{max-height:118mm!important;width:auto!important;max-width:100%!important;display:block;margin:0 auto}"
                " h1,h2,h3{page-break-after:avoid}</style>")
    html = src.read_text(encoding="utf-8")
    html = html.replace("</head>", page_css + "</head>", 1) if "</head>" in html else page_css + html
    tmp = rdir / "_print_copy.html"
    tmp.write_text(html, encoding="utf-8")

    chrome = find_chrome()
    if not chrome:
        tmp.unlink(missing_ok=True)
        print("EXPORT   PDF skipped: no Chrome/Edge in this environment (set CHROME_PATH if one exists).")
        print("         monthly_report.pdf (reportlab) is the PDF deliverable here; the dashboard stays as HTML. Do not install anything to work around this.")
        return 0
    ok = False
    for headless in ("--headless=new", "--headless"):
        cmd = [chrome, headless, "--disable-gpu", "--no-pdf-header-footer",
               f"--print-to-pdf={out.resolve()}", tmp.resolve().as_uri()]
        try:
            subprocess.run(cmd, capture_output=True, timeout=120)
        except Exception:
            continue
        if out.exists() and out.stat().st_size > 1000:
            ok = True
            break
    tmp.unlink(missing_ok=True)
    if not ok:
        print("EXPORT   PDF failed — Chrome ran but produced no file.")
        return 1
    print(f"EXPORT   PDF -> {out}  ({out.stat().st_size // 1024} KB, A4 {orientation}, OpenDeedigital style)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
