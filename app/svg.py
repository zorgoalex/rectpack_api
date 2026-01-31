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
    max_height = 0.0
    for sol in solutions:
        positions.append(x_cursor)
        x_cursor += sol.width_mm + margin
        if sol.height_mm > max_height:
            max_height = sol.height_mm

    total_width = max(1.0, x_cursor - margin)
    total_height = max(1.0, max_height)

    parts = [
        f"<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{total_width}\" height=\"{total_height}\" viewBox=\"0 0 {total_width} {total_height}\">",
        "<style>",
        ".sheet{fill:none;stroke:#1f2937;stroke-width:1}",
        ".item{fill:#93c5fd;stroke:#1e3a8a;stroke-width:0.8}",
        ".label{font-family:Arial, sans-serif;font-size:10px;fill:#111827}",
        "</style>",
    ]

    for sol, x_offset in zip(solutions, positions):
        parts.append(f"<g transform=\"translate({x_offset} 0)\">")
        parts.append(
            f"<rect class=\"sheet\" x=\"0\" y=\"0\" width=\"{sol.width_mm}\" height=\"{sol.height_mm}\" />"
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
