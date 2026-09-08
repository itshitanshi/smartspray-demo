// SmartSpray demo — frontend logic
// No build step needed: plain JS + Leaflet, served as static files by FastAPI.

const API_BASE = ""; // same-origin (FastAPI serves both API and frontend)

// ---------------------------------------------------------------------
// State
// ---------------------------------------------------------------------
const state = {
  boundaryLayer: null, // Leaflet polygon the farmer drew
  lastAnalysis: null,  // { grid_rows, grid_cols, cells, ... } from /api/analyze
  droneMarker: null,
  pathLine: null,
};

// ---------------------------------------------------------------------
// Map + draw control
// ---------------------------------------------------------------------
const map = L.map("map", { zoomControl: true }).setView([28.6139, 77.2090], 15); // default: New Delhi-ish farmland

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

const drawnItems = new L.FeatureGroup();
map.addLayer(drawnItems);

const drawControl = new L.Control.Draw({
  draw: {
    polygon: {
      allowIntersection: false,
      showArea: true,
      shapeOptions: { color: "#39d97a", weight: 2, fillOpacity: 0.12 },
    },
    marker: false,
    circle: false,
    circlemarker: false,
    rectangle: false,
    polyline: false,
  },
  edit: { featureGroup: drawnItems, remove: false },
});
map.addControl(drawControl);

map.on(L.Draw.Event.CREATED, (e) => {
  drawnItems.clearLayers();
  drawnItems.addLayer(e.layer);
  state.boundaryLayer = e.layer;
  setStep(2);
  updateRunButton();
});

document.getElementById("clearBoundaryBtn").addEventListener("click", () => {
  drawnItems.clearLayers();
  state.boundaryLayer = null;
  clearFlightVisuals();
  updateRunButton();
});

// ---------------------------------------------------------------------
// Upload + analyze
// ---------------------------------------------------------------------
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const analyzeResult = document.getElementById("analyzeResult");
const overlayImg = document.getElementById("overlayImg");

dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("dragover");
});
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener("change", () => {
  if (fileInput.files.length) handleFile(fileInput.files[0]);
});

async function handleFile(file) {
  setStep(3);
  dropzone.querySelector("p").textContent = "Analyzing…";

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch(`${API_BASE}/api/analyze?grid_rows=5&grid_cols=6`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) throw new Error((await res.json()).detail || "Analysis failed");
    const data = await res.json();

    state.lastAnalysis = data;
    overlayImg.src = `data:image/png;base64,${data.overlay_image_base64}`;
    analyzeResult.classList.remove("hidden");

    document.getElementById("mTarget").textContent = `${data.target_pct}%`;
    document.getElementById("mStatus").textContent =
      data.target_pct > 0 ? "TREATMENT REQUIRED" : "HEALTHY";

    dropzone.querySelector("p").innerHTML = "<strong>Click to upload</strong> or drag another image";
    updateRunButton();
  } catch (err) {
    dropzone.querySelector("p").textContent = `Error: ${err.message}`;
  }
}

// ---------------------------------------------------------------------
// Flight path simulation
// ---------------------------------------------------------------------
const runFlightBtn = document.getElementById("runFlightBtn");
runFlightBtn.addEventListener("click", runFlightSimulation);

function updateRunButton() {
  runFlightBtn.disabled = !(state.boundaryLayer && state.lastAnalysis);
}

function clearFlightVisuals() {
  if (state.droneMarker) { map.removeLayer(state.droneMarker); state.droneMarker = null; }
  if (state.pathLine) { map.removeLayer(state.pathLine); state.pathLine = null; }
}

async function runFlightSimulation() {
  if (!state.boundaryLayer || !state.lastAnalysis) return;
  setStep(4);
  clearFlightVisuals();

  const latlngs = state.boundaryLayer.getLatLngs()[0].map((p) => ({ lat: p.lat, lng: p.lng }));

  const payload = {
    boundary: latlngs,
    grid_rows: state.lastAnalysis.grid_rows,
    grid_cols: state.lastAnalysis.grid_cols,
    cells: state.lastAnalysis.cells,
  };

  const res = await fetch(`${API_BASE}/api/flightpath`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    alert("Flight path generation failed: " + (await res.text()));
    return;
  }
  const data = await res.json();

  document.getElementById("mArea").textContent = `${data.area_hectares} ha`;
  document.getElementById("mSpray").textContent = `${data.spray_used_ml} mL`;
  document.getElementById("mTarget").textContent = `${data.target_pct}%`;

  animateFlightPath(data.waypoints);
  refreshHistory();
}

function animateFlightPath(waypoints) {
  const fullLatLngs = waypoints.map((w) => [w.lat, w.lng]);
  state.pathLine = L.polyline(fullLatLngs, {
    color: "#2be0d6",
    weight: 2,
    dashArray: "4 6",
    opacity: 0.7,
  }).addTo(map);

  state.droneMarker = L.circleMarker(fullLatLngs[0], {
    radius: 7,
    color: "#c6ff3d",
    fillColor: "#c6ff3d",
    fillOpacity: 1,
  }).addTo(map);

  let i = 0;
  const sprayCircles = [];
  const interval = setInterval(() => {
    if (i >= waypoints.length) {
      clearInterval(interval);
      return;
    }
    const wp = waypoints[i];
    state.droneMarker.setLatLng([wp.lat, wp.lng]);

    if (wp.spray) {
      const c = L.circleMarker([wp.lat, wp.lng], {
        radius: 9,
        color: "#ff5c63",
        fillColor: "#ff5c63",
        fillOpacity: 0.35,
        weight: 1,
      }).addTo(map);
      sprayCircles.push(c);
    }
    i += 1;
  }, 90);
}

// ---------------------------------------------------------------------
// History table
// ---------------------------------------------------------------------
async function refreshHistory() {
  const res = await fetch(`${API_BASE}/api/history`);
  if (!res.ok) return;
  const rows = await res.json();

  const tbody = document.querySelector("#historyTable tbody");
  const emptyMsg = document.getElementById("historyEmpty");
  tbody.innerHTML = "";

  if (rows.length === 0) {
    emptyMsg.style.display = "block";
    return;
  }
  emptyMsg.style.display = "none";

  for (const r of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${r.field_name}</td>
      <td>${r.area_hectares} ha</td>
      <td>${r.target_pct}%</td>
      <td>${r.spray_used_ml} mL</td>
      <td>${r.timestamp}</td>
    `;
    tbody.appendChild(tr);
  }
}

// ---------------------------------------------------------------------
// Step indicator
// ---------------------------------------------------------------------
function setStep(n) {
  document.querySelectorAll(".step").forEach((el) => {
    el.classList.toggle("active", Number(el.dataset.step) <= n);
  });
}
