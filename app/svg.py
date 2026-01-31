from typing import List

from .models import Solution


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def render_svg(solutions: List[Solution]) -> str:
    if not solutions:
        return "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"1\" height=\"1\"></svg>"

    margin = 20.0
    x_cursor = 0.0
    positions = []
    min_x = None
    min_y = None
    max_x = None
    max_y = None
    for sol in solutions:
        positions.append(x_cursor)
        trim = sol.trim_mm
        sheet_min_x = x_cursor - trim.left
        sheet_max_x = x_cursor + sol.width_mm - trim.left
        sheet_min_y = -trim.top
        sheet_max_y = sol.height_mm - trim.top
        min_x = sheet_min_x if min_x is None else min(min_x, sheet_min_x)
        min_y = sheet_min_y if min_y is None else min(min_y, sheet_min_y)
        max_x = sheet_max_x if max_x is None else max(max_x, sheet_max_x)
        max_y = sheet_max_y if max_y is None else max(max_y, sheet_max_y)
        x_cursor += sol.width_mm + margin

    if min_x is None or min_y is None or max_x is None or max_y is None:
        return "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"1\" height=\"1\"></svg>"

    total_width = max(1.0, max_x - min_x)
    total_height = max(1.0, max_y - min_y)

    parts = [
        f"<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{total_width}\" height=\"{total_height}\" viewBox=\"{min_x} {min_y} {total_width} {total_height}\">",
        "<style>",
        ".sheet{fill:none;stroke:#1f2937;stroke-width:1}",
        ".item{fill:#93c5fd;stroke:#1e3a8a;stroke-width:0.8}",
        ".label{font-family:Arial, sans-serif;font-size:10px;fill:#111827}",
        "</style>",
    ]

    for sol, x_offset in zip(solutions, positions):
        trim = sol.trim_mm
        parts.append(f"<g transform=\"translate({x_offset} 0)\">")
        parts.append(
            f"<rect class=\"sheet\" x=\"{-trim.left}\" y=\"{-trim.top}\" width=\"{sol.width_mm}\" height=\"{sol.height_mm}\" />"
        )
        for plc in sol.placements:
            label = _escape(f"{plc.item_id}#{plc.instance}")
            parts.append(
                f"<rect class=\"item\" x=\"{plc.x_mm}\" y=\"{plc.y_mm}\" width=\"{plc.width_mm}\" height=\"{plc.height_mm}\" />"
            )
            text_x = plc.x_mm + 2
            text_y = plc.y_mm + 12
            parts.append(
                f"<text class=\"label\" x=\"{text_x}\" y=\"{text_y}\">{label}</text>"
            )
        parts.append("</g>")

    parts.append("</svg>")
    return "".join(parts)
