from __future__ import annotations

from pathlib import Path
import shutil

from PIL import Image, ImageDraw, ImageFont

try:
    from .report_utils import clean_text
except ImportError:  # pragma: no cover
    from report_utils import clean_text


WIDTH = 1200
HEIGHT = 720
MARGIN_LEFT = 110
MARGIN_RIGHT = 70
MARGIN_TOP = 130
MARGIN_BOTTOM = 90


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "arialbd.ttf" if bold else "arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_brand_header(draw: ImageDraw.ImageDraw, image: Image.Image, title: str, brand: dict[str, str], logo_path: Path | None = None) -> None:
    primary = _hex_to_rgb(brand.get("primary_color", "#F36B15"))
    secondary = _hex_to_rgb(brand.get("secondary_color", "#9B0A68"))
    dark = _hex_to_rgb(brand.get("dark_color", "#231F20"))
    draw.rectangle([0, 0, WIDTH, 16], fill=primary)
    draw.rectangle([WIDTH // 2, 0, WIDTH, 16], fill=secondary)
    if logo_path and logo_path.exists():
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo.thumbnail((320, 76))
            image.paste(logo, (42, 32), logo)
        except Exception:
            draw.text((42, 40), brand.get("name", "OpenDeedigital"), fill=primary, font=_font(32, True))
    else:
        draw.text((42, 40), brand.get("name", "OpenDeedigital"), fill=primary, font=_font(32, True))
    draw.text((400, 42), title, fill=dark, font=_font(31, True))


def _blank_chart(title: str, output_path: Path, brand: dict[str, str], logo_path: Path | None = None, message: str = "No data available") -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(image)
    _draw_brand_header(draw, image, title, brand, logo_path)
    draw.rounded_rectangle([300, 300, 900, 390], radius=12, outline=_hex_to_rgb(brand.get("secondary_color", "#9B0A68")), width=2)
    draw.text((390, 330), message, fill=_hex_to_rgb(brand.get("dark_color", "#231F20")), font=_font(28, True))
    image.save(output_path)


def _format_value(value: float, percent: bool = False) -> str:
    if percent:
        return f"{value * 100:.0f}%"
    if abs(value) >= 100:
        return f"{value:.0f}"
    return f"{value:.1f}"


def _draw_grouped_bars(
    title: str,
    categories: list[str],
    series: list[dict[str, object]],
    output_path: Path,
    brand: dict[str, str],
    logo_path: Path | None = None,
    percent: bool = False,
) -> None:
    if not categories or not series:
        _blank_chart(title, output_path, brand, logo_path)
        return

    image = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(image)
    _draw_brand_header(draw, image, title, brand, logo_path)

    chart_left, chart_top = MARGIN_LEFT, MARGIN_TOP
    chart_right, chart_bottom = WIDTH - MARGIN_RIGHT, HEIGHT - MARGIN_BOTTOM
    values = [float(value or 0) for item in series for value in item["values"]]
    min_value = min(0, min(values))
    max_value = max(values + [1])
    if percent:
        max_value = max(max_value, 1)
    if max_value == min_value:
        max_value += 1
    zero_y = chart_bottom - (0 - min_value) / (max_value - min_value) * (chart_bottom - chart_top)

    axis_color = (190, 190, 190)
    draw.line([chart_left, chart_bottom, chart_right, chart_bottom], fill=axis_color, width=2)
    draw.line([chart_left, chart_top, chart_left, chart_bottom], fill=axis_color, width=2)
    if min_value < 0:
        draw.line([chart_left, zero_y, chart_right, zero_y], fill=(150, 150, 150), width=2)

    group_width = (chart_right - chart_left) / max(len(categories), 1)
    bar_gap = 8
    bar_width = max(18, (group_width * 0.72 - bar_gap * (len(series) - 1)) / max(len(series), 1))
    for index, category in enumerate(categories):
        group_x = chart_left + index * group_width + group_width * 0.14
        label = category[:18] + ("..." if len(category) > 18 else "")
        draw.text((group_x, chart_bottom + 18), label, fill=(80, 80, 80), font=_font(17))
        for series_index, item in enumerate(series):
            value = float(item["values"][index] or 0)
            color = item["color"]
            x0 = group_x + series_index * (bar_width + bar_gap)
            y = chart_bottom - (value - min_value) / (max_value - min_value) * (chart_bottom - chart_top)
            y0, y1 = (y, zero_y) if value >= 0 else (zero_y, y)
            draw.rounded_rectangle([x0, y0, x0 + bar_width, y1], radius=5, fill=color)
            draw.text((x0, min(y0, y1) - 24), _format_value(value, percent), fill=(60, 60, 60), font=_font(15))

    legend_x = chart_left
    for item in series:
        draw.rounded_rectangle([legend_x, HEIGHT - 52, legend_x + 22, HEIGHT - 30], radius=4, fill=item["color"])
        draw.text((legend_x + 30, HEIGHT - 54), item["label"], fill=(70, 70, 70), font=_font(18))
        legend_x += 210
    image.save(output_path)


def _draw_stacked_bars(
    title: str,
    categories: list[str],
    stacks: list[dict[str, int]],
    output_path: Path,
    brand: dict[str, str],
    logo_path: Path | None = None,
) -> None:
    if not categories:
        _blank_chart(title, output_path, brand, logo_path)
        return

    image = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(image)
    _draw_brand_header(draw, image, title, brand, logo_path)
    chart_left, chart_top = 260, MARGIN_TOP
    chart_right, chart_bottom = WIDTH - MARGIN_RIGHT, HEIGHT - MARGIN_BOTTOM
    row_height = (chart_bottom - chart_top) / max(len(categories), 1)
    max_total = max([sum(stack.values()) for stack in stacks] + [1])
    colors = {
        "Red": _hex_to_rgb("#C83D3D"),
        "Yellow": _hex_to_rgb("#F36B15"),
        "Green": _hex_to_rgb("#27845C"),
        "Data Gap": _hex_to_rgb("#7C3AED"),
        "Check": _hex_to_rgb("#6B7280"),
    }
    for index, category in enumerate(categories):
        y0 = chart_top + index * row_height + 13
        y1 = y0 + min(36, row_height * 0.55)
        draw.text((60, y0 + 4), category, fill=(60, 60, 60), font=_font(20, True))
        cursor = chart_left
        for label in ("Red", "Yellow", "Green", "Data Gap", "Check"):
            value = stacks[index].get(label, 0)
            if not value:
                continue
            width = (chart_right - chart_left) * value / max_total
            draw.rounded_rectangle([cursor, y0, cursor + width, y1], radius=6, fill=colors[label])
            if width > 30:
                draw.text((cursor + 8, y0 + 7), str(value), fill="white", font=_font(16, True))
            cursor += width

    legend_x = 60
    for label in ("Red", "Yellow", "Green", "Data Gap", "Check"):
        draw.rounded_rectangle([legend_x, HEIGHT - 52, legend_x + 22, HEIGHT - 30], radius=4, fill=colors[label])
        draw.text((legend_x + 30, HEIGHT - 54), label, fill=(70, 70, 70), font=_font(18))
        legend_x += 150
    image.save(output_path)


def _copy_logo(config: dict[str, object], assets_dir: Path) -> Path | None:
    brand = config.get("brand", {})
    logo_path = Path(clean_text(brand.get("logo_path")))
    if not logo_path.is_absolute():
        logo_path = Path.cwd() / logo_path
    if not logo_path.exists():
        return None
    target = assets_dir / logo_path.name
    if logo_path.resolve() != target.resolve():
        shutil.copy2(logo_path, target)
    return target


def generate_report_charts(report_model: dict[str, object], config: dict[str, object], output_dir: str | Path) -> dict[str, dict[str, str]]:
    output_dir = Path(output_dir)
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    brand = config.get("brand", {})
    logo_target = _copy_logo(config, assets_dir)

    primary = _hex_to_rgb(brand.get("primary_color", "#F36B15"))
    secondary = _hex_to_rgb(brand.get("secondary_color", "#9B0A68"))
    accent = _hex_to_rgb(brand.get("accent_color", "#C83D3D"))
    green = _hex_to_rgb("#27845C")
    metrics = report_model.get("metrics", {})
    chart_defs = {chart["id"]: chart for chart in config.get("charts", [])}
    charts: dict[str, dict[str, str]] = {}

    progress = metrics.get("progress", {})
    zones = progress.get("zone_summary", [])
    output = assets_dir / chart_defs["progress_by_zone"]["filename"]
    _draw_grouped_bars(
        chart_defs["progress_by_zone"]["title"],
        [item["zone"] for item in zones],
        [
            {"label": "Planned", "values": [item.get("planned_pct") for item in zones], "color": secondary},
            {"label": "Actual", "values": [item.get("actual_pct") for item in zones], "color": primary},
        ],
        output,
        brand,
        logo_target,
        percent=True,
    )
    charts["progress_by_zone"] = {"title": chart_defs["progress_by_zone"]["title"], "path": str(output), "relative_path": f"assets/{output.name}"}

    milestones = metrics.get("programme_milestones", {}).get("delayed", [])[:8]
    output = assets_dir / chart_defs["milestone_delay"]["filename"]
    _draw_grouped_bars(
        chart_defs["milestone_delay"]["title"],
        [item["id"] for item in milestones],
        [{"label": "Delay days", "values": [item.get("variance_days") for item in milestones], "color": accent}],
        output,
        brand,
        logo_target,
    )
    charts["milestone_delay"] = {"title": chart_defs["milestone_delay"]["title"], "path": str(output), "relative_path": f"assets/{output.name}"}

    rfi = metrics.get("submission_rfi", {}).get("bottlenecks", [])[:8]
    output = assets_dir / chart_defs["rfi_aging"]["filename"]
    _draw_grouped_bars(
        chart_defs["rfi_aging"]["title"],
        [item["id"] for item in rfi],
        [{"label": "Open / overdue days", "values": [item.get("days_open_overdue") for item in rfi], "color": secondary}],
        output,
        brand,
        logo_target,
    )
    charts["rfi_aging"] = {"title": chart_defs["rfi_aging"]["title"], "path": str(output), "relative_path": f"assets/{output.name}"}

    procurement = metrics.get("procurement", {}).get("risks", [])[:8]
    output = assets_dir / chart_defs["procurement_variance"]["filename"]
    _draw_grouped_bars(
        chart_defs["procurement_variance"]["title"],
        [item["id"] for item in procurement],
        [{"label": "Variance days", "values": [item.get("variance_days") for item in procurement], "color": primary}],
        output,
        brand,
        logo_target,
    )
    charts["procurement_variance"] = {"title": chart_defs["procurement_variance"]["title"], "path": str(output), "relative_path": f"assets/{output.name}"}

    commercial = metrics.get("commercial_cost", {})
    previous = commercial.get("previous") or {}
    current = commercial.get("current") or {}
    output = assets_dir / chart_defs["commercial_movement"]["filename"]
    _draw_grouped_bars(
        chart_defs["commercial_movement"]["title"],
        ["Previous", "Current"],
        [
            {"label": "Current GP HK$M", "values": [previous.get("current_gp_hkd_m"), current.get("current_gp_hkd_m")], "color": green},
            {"label": "Risk Exposure HK$M", "values": [previous.get("risk_exposure_hkd_m"), current.get("risk_exposure_hkd_m")], "color": accent},
        ],
        output,
        brand,
        logo_target,
    )
    charts["commercial_movement"] = {"title": chart_defs["commercial_movement"]["title"], "path": str(output), "relative_path": f"assets/{output.name}"}

    rag_sources = [
        ("Progress", metrics.get("progress", {}).get("rag_counts", {})),
        ("Programme", metrics.get("programme_milestones", {}).get("rag_counts", {})),
        ("RFI/Sub.", metrics.get("submission_rfi", {}).get("rag_counts", {})),
        ("Procurement", metrics.get("procurement", {}).get("rag_counts", {})),
        ("Safety", metrics.get("safety_quality", {}).get("rag_counts", {})),
        ("Commercial", metrics.get("commercial_cost", {}).get("rag_counts", {})),
        ("Risks", metrics.get("risk_action_decision", {}).get("rag_counts", {})),
    ]
    output = assets_dir / chart_defs["rag_mix"]["filename"]
    _draw_stacked_bars(chart_defs["rag_mix"]["title"], [name for name, _ in rag_sources], [counts for _, counts in rag_sources], output, brand, logo_target)
    charts["rag_mix"] = {"title": chart_defs["rag_mix"]["title"], "path": str(output), "relative_path": f"assets/{output.name}"}

    report_model["charts"] = charts
    if logo_target:
        report_model.setdefault("brand", {})["logo_asset"] = f"assets/{logo_target.name}"
    return charts
