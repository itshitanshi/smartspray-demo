"""
spraymap.py
-----------
Turns a farmer-drawn field boundary + the detection grid from detection.py
into an ordered list of flight waypoints, the way a real survey mission
would: a "boustrophedon" (lawnmower / snake) pattern that visits every cell
in the grid, row by row, alternating direction each row.

Each waypoint carries a `spray` flag — True only over cells flagged
diseased/weed — which is exactly the signal you'd send to the ESP32 pump
controller on the real hardware (see the build plan: Pi 5 -> ESP32 relay).

Coordinates are mapped from the field's bounding box using simple linear
interpolation. That's an approximation (real fields aren't perfect
rectangles), which is fine for a demo — swap in a proper geodesic/grid
library if this becomes a real product.
"""
import math
from typing import List, Tuple

from app.schemas import LatLng, GridCell, Waypoint

# Rough constant for hectare estimation from a lat/lng shoelace-formula area.
# 1 degree latitude ~= 111,320 m. Longitude scale depends on latitude.
_METERS_PER_DEG_LAT = 111_320.0


def _bounding_box(polygon: List[LatLng]) -> Tuple[float, float, float, float]:
    lats = [p.lat for p in polygon]
    lngs = [p.lng for p in polygon]
    return min(lats), max(lats), min(lngs), max(lngs)


def _polygon_area_hectares(polygon: List[LatLng]) -> float:
    """Shoelace formula on an equirectangular projection — good enough for small fields."""
    if len(polygon) < 3:
        return 0.0
    mean_lat = sum(p.lat for p in polygon) / len(polygon)
    meters_per_deg_lng = _METERS_PER_DEG_LAT * math.cos(math.radians(mean_lat))

    coords_m = [(p.lng * meters_per_deg_lng, p.lat * _METERS_PER_DEG_LAT) for p in polygon]
    area = 0.0
    n = len(coords_m)
    for i in range(n):
        x1, y1 = coords_m[i]
        x2, y2 = coords_m[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    area_m2 = abs(area) / 2.0
    return round(area_m2 / 10_000.0, 3)  # hectares


def generate_flight_path(
    boundary: List[LatLng], grid_rows: int, grid_cols: int, cells: List[GridCell]
) -> Tuple[List[Waypoint], float, float]:
    """
    Returns (waypoints, area_hectares, spray_used_ml).

    Waypoint ordering is boustrophedon: row 0 left-to-right, row 1
    right-to-left, etc. — matching a realistic autonomous survey pattern.
    """
    min_lat, max_lat, min_lng, max_lng = _bounding_box(boundary)
    lat_span = max_lat - min_lat or 1e-6
    lng_span = max_lng - min_lng or 1e-6

    by_pos = {(c.row, c.col): c for c in cells}

    waypoints: List[Waypoint] = []
    order = 0
    ml_per_target_cell = 35.0  # illustrative constant for the demo's "spray used" stat

    for row in range(grid_rows):
        col_range = range(grid_cols) if row % 2 == 0 else range(grid_cols - 1, -1, -1)
        for col in col_range:
            cell = by_pos.get((row, col))
            status = cell.status if cell else "healthy"
            spray = status in ("diseased", "weed")

            # Cell center as a fraction of the grid, mapped into the bounding box.
            frac_row = (row + 0.5) / grid_rows
            frac_col = (col + 0.5) / grid_cols
            lat = max_lat - frac_row * lat_span  # image row 0 is the "top" (north)
            lng = min_lng + frac_col * lng_span

            waypoints.append(
                Waypoint(order=order, lat=lat, lng=lng, row=row, col=col, status=status, spray=spray)
            )
            order += 1

    area_ha = _polygon_area_hectares(boundary)
    spray_used_ml = round(sum(1 for wp in waypoints if wp.spray) * ml_per_target_cell, 1)

    return waypoints, area_ha, spray_used_ml
