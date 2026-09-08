"""
SmartSpray demo backend.

Run with:
    uvicorn app.main:app --reload --port 8000

Then open http://localhost:8000 in a browser.

Endpoints:
    POST /api/analyze      -> upload a field/crop image, get back a
                               grid-based health analysis + overlay image
    POST /api/flightpath   -> given a drawn field boundary + the grid from
                               /api/analyze, get back a simulated flight path
    GET  /api/history      -> list of past demo runs (in-memory)
    GET  /api/health       -> simple liveness check
"""
from datetime import datetime, timezone
from typing import List

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.detection import analyze_image
from app.schemas import (
    AnalyzeResponse,
    FlightPathRequest,
    FlightPathResponse,
    GridCell,
    HistoryEntry,
)
from app.spraymap import generate_flight_path

app = FastAPI(title="SmartSpray Demo API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo only — lock this down for a real deployment
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- in-memory "database" for the demo -------------------------------------
_HISTORY: List[HistoryEntry] = []
_NEXT_ID = 1


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(file: UploadFile = File(...), grid_rows: int = 5, grid_cols: int = 6):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload an image file.")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file was empty.")

    try:
        cells, overlay_b64, stats = analyze_image(image_bytes, grid_rows=grid_rows, grid_cols=grid_cols)
    except Exception as exc:  # pragma: no cover - defensive for a demo
        raise HTTPException(status_code=422, detail=f"Could not process image: {exc}")

    return AnalyzeResponse(
        grid_rows=grid_rows,
        grid_cols=grid_cols,
        cells=cells,
        healthy_pct=stats["healthy_pct"],
        target_pct=stats["target_pct"],
        diseased_count=stats["diseased_count"],
        weed_count=stats["weed_count"],
        overlay_image_base64=overlay_b64,
    )


@app.post("/api/flightpath", response_model=FlightPathResponse)
def flightpath(req: FlightPathRequest):
    if req.grid_rows * req.grid_cols != len(req.cells):
        raise HTTPException(status_code=400, detail="grid_rows * grid_cols must match len(cells).")

    waypoints, area_ha, spray_ml = generate_flight_path(
        req.boundary, req.grid_rows, req.grid_cols, req.cells
    )

    target_cells = sum(1 for c in req.cells if c.status in ("diseased", "weed"))
    target_pct = round(100 * target_cells / len(req.cells), 1) if req.cells else 0.0

    global _NEXT_ID
    _HISTORY.insert(
        0,
        HistoryEntry(
            id=_NEXT_ID,
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            field_name=f"Field {_NEXT_ID}",
            area_hectares=area_ha,
            target_pct=target_pct,
            spray_used_ml=spray_ml,
            status="Simulated",
        ),
    )
    _NEXT_ID += 1

    return FlightPathResponse(
        waypoints=waypoints, area_hectares=area_ha, spray_used_ml=spray_ml, target_pct=target_pct
    )


@app.get("/api/history", response_model=List[HistoryEntry])
def history():
    return _HISTORY


# --- static frontend ---------------------------------------------------
# Mounted last so it doesn't shadow the /api/* routes above.
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
