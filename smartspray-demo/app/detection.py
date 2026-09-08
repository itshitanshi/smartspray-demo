"""
detection.py
------------
Baseline crop-health detector used by the SmartSpray demo.

This is a deliberately simple, dependency-light heuristic — it looks at each
cell of a grid overlaid on the field image and classifies it using color
statistics (an Excess Green Index + HSV hue/saturation), rather than a
trained neural network. That keeps the demo runnable with zero downloads
and no GPU.

IMPORTANT: This is a stand-in for the real model described in the project
plan (YOLOv8-nano / MobileNet fine-tuned on labeled crop imagery). The
`analyze_image()` function is the one place that would change when you swap
in a real trained model on the Raspberry Pi 5 — everything else in the app
(API, frontend, flight-path logic) stays the same, because they only depend
on the GridCell list this function returns.

Classification rule of thumb:
  - HEALTHY:  strong, saturated green (high Excess Green Index)
  - DISEASED: yellow/brown hue with lower saturation (classic stress/wilt
              color signature)
  - WEED:     green but with high local texture variance (weeds tend to
              break the uniform canopy pattern of a planted crop row)
"""
from dataclasses import dataclass
from io import BytesIO
from typing import List, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.schemas import GridCell

# Overlay colors (RGBA)
COLOR_HEALTHY = (46, 158, 82, 90)
COLOR_DISEASED = (214, 62, 62, 130)
COLOR_WEED = (232, 163, 61, 130)
COLOR_GRID_LINE = (255, 255, 255, 60)


def _excess_green_index(rgb_cell: np.ndarray) -> float:
    """2G - R - B, normalized to 0..1. A simple, well-known vegetation index."""
    r = rgb_cell[..., 0].astype(np.float32)
    g = rgb_cell[..., 1].astype(np.float32)
    b = rgb_cell[..., 2].astype(np.float32)
    exg = (2 * g - r - b).mean()
    return float(np.clip((exg + 255) / 510, 0, 1))


def _hsv_stats(rgb_cell: np.ndarray) -> Tuple[float, float, float]:
    """Returns (mean hue in degrees, mean saturation 0..1, texture score 0..1)."""
    img = Image.fromarray(rgb_cell).convert("HSV")
    arr = np.array(img).astype(np.float32)
    hue = arr[..., 0].mean() / 255.0 * 360.0
    sat = arr[..., 1].mean() / 255.0
    # texture proxy: local standard deviation of the value channel
    texture = float(np.std(arr[..., 2]) / 255.0)
    return hue, sat, texture


def _classify_cell(rgb_cell: np.ndarray) -> Tuple[str, float, float]:
    exg = _excess_green_index(rgb_cell)
    hue, sat, texture = _hsv_stats(rgb_cell)

    is_green = 60 <= hue <= 170 and exg > 0.52
    is_yellow_brown = (hue < 60 or hue > 300) and sat > 0.15

    if is_yellow_brown and exg < 0.55:
        return "diseased", exg, hue
    if is_green and texture > 0.16:
        return "weed", exg, hue
    if is_green:
        return "healthy", exg, hue
    # Fallback: low vegetation signal but not clearly yellow/brown either —
    # treat as diseased/stressed since it's not a confident "healthy" read.
    return "diseased", exg, hue


def analyze_image(
    image_bytes: bytes, grid_rows: int = 5, grid_cols: int = 6
) -> Tuple[List[GridCell], str, dict]:
    """
    Runs the grid-based health analysis over an uploaded field image.

    Returns:
        cells: list of GridCell (row, col, status, excess_green, hue_mean)
        overlay_png_base64: the original image with a color-coded grid
                             overlay drawn on top, base64-encoded PNG
        stats: dict with healthy_pct, target_pct, diseased_count, weed_count
    """
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    # Cap image size for speed — this is a demo, not a production pipeline.
    img.thumbnail((900, 900))
    arr = np.array(img)
    h, w, _ = arr.shape

    cell_h = h // grid_rows
    cell_w = w // grid_cols

    cells: List[GridCell] = []
    counts = {"healthy": 0, "diseased": 0, "weed": 0}

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for row in range(grid_rows):
        for col in range(grid_cols):
            y0, y1 = row * cell_h, (row + 1) * cell_h if row < grid_rows - 1 else h
            x0, x1 = col * cell_w, (col + 1) * cell_w if col < grid_cols - 1 else w
            cell_arr = arr[y0:y1, x0:x1]

            status, exg, hue = _classify_cell(cell_arr)
            counts[status] += 1
            cells.append(
                GridCell(row=row, col=col, status=status, excess_green=round(exg, 3), hue_mean=round(hue, 1))
            )

            color = {"healthy": COLOR_HEALTHY, "diseased": COLOR_DISEASED, "weed": COLOR_WEED}[status]
            draw.rectangle([x0, y0, x1 - 1, y1 - 1], fill=color, outline=COLOR_GRID_LINE, width=1)

    composed = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    buf = BytesIO()
    composed.save(buf, format="PNG")
    import base64

    overlay_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    total = grid_rows * grid_cols
    healthy_pct = round(100 * counts["healthy"] / total, 1)
    target_pct = round(100 * (counts["diseased"] + counts["weed"]) / total, 1)

    stats = {
        "healthy_pct": healthy_pct,
        "target_pct": target_pct,
        "diseased_count": counts["diseased"],
        "weed_count": counts["weed"],
    }
    return cells, overlay_b64, stats
