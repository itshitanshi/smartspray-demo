# SmartSpray — Software-Only Demo

A working, hardware-free demo of the SmartSpray pipeline: draw a field boundary on a
map, upload a crop/field photo, get an AI-style detection overlay, then watch a
simulated drone fly a grid pattern and spray only the flagged zones.

This is designed so **nothing here is throwaway work** — the same detection function
and the same Pi 5 ↔ ESP32 command pattern carry straight over once you have hardware.

```
smartspray-demo/
├── app/
│   ├── main.py          FastAPI app — all API routes + serves the frontend
│   ├── detection.py     Crop health detector (color-heuristic baseline)
│   ├── spraymap.py      Boundary + grid -> simulated flight path
│   └── schemas.py       Shared request/response models
├── frontend/
│   ├── index.html       Map + upload + dashboard UI
│   ├── style.css        Dark theme matching the pitch deck
│   └── app.js           Leaflet map, upload flow, flight simulation, history
├── requirements.txt
└── README.md
```

## 1. Setup

```bash
cd smartspray-demo
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Run

```bash
uvicorn app.main:app --reload --port 8000
```

Open **http://localhost:8000** in a browser.

## 3. Using the demo

1. **Draw a field** — use the polygon tool (top-left of the map) to draw a boundary
   anywhere on the map. It defaults to a New Delhi-area view; pan/zoom to wherever
   you like, real location doesn't matter for the demo.
2. **Upload a crop/field photo** — any field or plant photo works. The backend
   grid-analyzes it (5×6 cells by default) and returns a color-coded overlay:
   green = healthy, red = diseased/stressed, amber = weed-like texture.
3. **Simulate Flight** — once you've drawn a boundary *and* analyzed an image, the
   button activates. It requests a boustrophedon (lawnmower) flight path from the
   backend, then animates a drone marker across your field boundary, only
   "spraying" (red pulse) over the cells the detector flagged.
4. **Dashboard** — area (from your drawn polygon), spray volume, target %, and a
   history table update after each run, mirroring the pitch deck's dashboard slide.

## 4. What's real vs. simulated

| Piece | Status |
|---|---|
| Image upload + grid analysis | **Real** — actual color/texture analysis of your uploaded image |
| Overlay rendering | **Real** — generated server-side from the analysis |
| Field area (hectares) | **Real** — computed from the polygon you draw (shoelace formula) |
| Flight path shape | **Simulated** — a real boustrophedon pattern, but animated, not flown |
| Spray volume (mL) | **Illustrative** — a constant-per-cell estimate, not a calibrated flow measurement |

## 5. Swapping in the real model later

`app/detection.py` has one function, `analyze_image()`, that does all the
classification work. When you're ready to use a trained model (YOLOv8-nano,
MobileNet, etc. as discussed in the project plan) on the Raspberry Pi 5, that's the
only function you need to replace — it already returns the same `GridCell` list
shape that the rest of the app (API, flight path, frontend) depends on.

Similarly, `spraymap.py`'s `spray: true/false` flag per waypoint is exactly the
signal you'd forward from the Pi 5 to the ESP32 over serial/I2C to fire the pump
relay on real hardware.

## 6. API reference (for testing without the UI)

```
POST /api/analyze?grid_rows=5&grid_cols=6      multipart/form-data: file=<image>
POST /api/flightpath                           JSON: { boundary, grid_rows, grid_cols, cells }
GET  /api/history
GET  /api/health
```

FastAPI also serves interactive docs at **http://localhost:8000/docs**.
