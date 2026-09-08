"""
Shared request/response models for the SmartSpray demo API.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class LatLng(BaseModel):
    lat: float
    lng: float


class GridCell(BaseModel):
    row: int
    col: int
    status: str  # "healthy" | "diseased" | "weed"
    excess_green: float
    hue_mean: float


class AnalyzeResponse(BaseModel):
    grid_rows: int
    grid_cols: int
    cells: List[GridCell]
    healthy_pct: float
    target_pct: float
    diseased_count: int
    weed_count: int
    overlay_image_base64: str  # PNG, ready to drop into an <img src="data:image/png;base64,...">


class FlightPathRequest(BaseModel):
    boundary: List[LatLng] = Field(..., min_items=3, description="Field polygon drawn by the farmer")
    grid_rows: int
    grid_cols: int
    cells: List[GridCell]


class Waypoint(BaseModel):
    order: int
    lat: float
    lng: float
    row: int
    col: int
    status: str
    spray: bool


class FlightPathResponse(BaseModel):
    waypoints: List[Waypoint]
    area_hectares: float
    spray_used_ml: float
    target_pct: float


class HistoryEntry(BaseModel):
    id: int
    timestamp: str
    field_name: str
    area_hectares: float
    target_pct: float
    spray_used_ml: float
    status: str
