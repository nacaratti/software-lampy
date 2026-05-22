# Lampy — Fiber Laser Studio

A modern, full-stack platform for designing and simulating fiber laser systems — from individual component solvers to a complete visual system builder.

Built on top of the **fibersim** Python physics library (inspired by RP Fiber Power), with a FastAPI backend and a React + TypeScript UI.

---

## What you can do

### Individual solvers
| Page | Description |
|---|---|
| **Mode Solver** | Guided LP modes via analytical (step-index), radial FD, or full 2D eigenvalue methods. Field intensity, V-number, effective indices. |
| **Power & ASE** | Bidirectional steady-state rate equations for Yb, Er, Tm fibers. Multiple pumps/signals, full ASE band, end mirrors for cavity simulation. |
| **FBG Solver** | Reflection spectra for uniform, chirped, apodized, tilted gratings and LPGs. Phase mask calculation for UV inscription geometry. |
| **BPM** | Paraxial split-step Fourier BPM in 3D. Tilt/misalign the launch, observe coupling efficiency and beat patterns. |
| **Thermal Simulator** | 3-layer heat conduction (core / cladding / coating) coupled to the longitudinal power and gain profile. |
| **Splicing Loss** | Splice loss via field overlap integral — lateral, angular, and waist misalignment. |

### Platform
| Feature | Description |
|---|---|
| **Device Library** | Store and manage active/passive fibers, FBGs, WDM couplers, and pump sources. Built-in catalogue of commercial off-the-shelf components (Nufern, Corning, standard pump diodes). Mix shelf and custom devices. Backed by a local SQLite database. |
| **Laser System Builder** | Visual drag-and-drop canvas to assemble complete fiber laser schematics. Connect optical ports between fiber segments, FBGs, couplers, and pump sources. System saved automatically to `localStorage`. |

---

## Quick start

### 1. Backend (Python ≥ 3.10)

```bash
# from the project root
pip install -e ".[backend,dev]"
uvicorn backend.app.main:app --reload
```

The API is available at <http://127.0.0.1:8000> with interactive docs at <http://127.0.0.1:8000/docs>.

On first startup, the backend creates `devices.db` (SQLite) and seeds it with the off-the-shelf device catalogue automatically.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. Vite proxies `/api` and `/ws` to the FastAPI server on port 8000.

### 3. One-shot dev (with `just`)

```bash
just install      # Python + JS deps
just dev          # uvicorn + vite in parallel
```

---

## Architecture

```
software-lamp/
├── src/fibersim/              Physics library (pure Python)
│   ├── core/                  Fiber geometry, materials (Sellmeier), active ions
│   └── solvers/
│       ├── modes/             Analytical, radial FD, full 2D eigenvalue
│       ├── power/             Bidirectional steady-state ASE, dynamic rate eqs.
│       ├── fbg/               TMM: uniform, chirped, apodized, tilted, LPG, phase mask
│       ├── bpm/               Split-step Fourier BPM
│       ├── thermal/           3-layer cylindrical heat conduction
│       └── splicing/          Field overlap integral
│
├── backend/app/
│   ├── main.py                FastAPI app — CORS, GZip, router registration, DB init
│   ├── config.py              Pydantic-settings (CORS origins, etc.)
│   ├── database.py            SQLAlchemy engine + session (SQLite: devices.db)
│   ├── models/device.py       Device ORM model
│   ├── schemas/               Pydantic request/response models
│   ├── routers/               /api/modes  /api/power  /api/bpm
│   │                          /api/fbg    /api/thermal /api/splicing
│   │                          /api/devices  /api/jobs
│   ├── services/              Fiber builder, base64 encoders, solver runners
│   ├── jobs.py                In-memory JobManager (semaphore, TTL, cancel)
│   └── ws.py                  WebSocket /ws/jobs/{job_id}
│
└── frontend/src/
    ├── pages/                 HomePage, ModeSolverPage, PowerSimPage, BPMPage,
    │                          FBGPage, ThermalPage, SplicingPage,
    │                          DeviceLibraryPage, SystemBuilderPage
    ├── components/            ui/ (shadcn), layout/, fiber/, plots/, jobs/
    ├── lib/                   api.ts, ws.ts, encoding.ts
    ├── stores/                Zustand: theme, jobs
    └── types/                 TS mirrors of Pydantic schemas + device types
```

### Device Library — data model

```
Device
  id            UUID (primary key)
  name          string
  description   text
  device_type   fiber_active | fiber_passive | fbg | coupler_wdm | pump_source
  category      custom | shelf
  manufacturer  string
  part_number   string
  parameters    JSON (type-specific fields)
  created_at    datetime (UTC)
  updated_at    datetime (UTC)
```

**Shelf catalogue** (seeded automatically on first run):
- Nufern SM-YSF-HI, LMA-YDF-10/125-M (active fibers)
- Corning HI 1060, SMF-28e+ (passive fibers)
- 976 nm / 915 nm pump diodes
- WDM 976/1064 nm, WDM 976/1550 nm couplers
- FBG HR 1064 nm (R = 99%), FBG OC 1064 nm (R = 10%)

### Job protocol (long-running solvers)

```
POST /api/power/ase   {request}   →  { job_id, status: queued }
WS   /ws/jobs/{job_id}            →  { type: 'progress', value: 0.42 } *
                                  →  { type: 'result',   data: {...} }
POST /api/jobs/{job_id}/cancel
GET  /api/jobs/{job_id}/result     (polling fallback)
```

Progress events are throttled to ~10 Hz on the server side.

---

## UX shortcuts

| Shortcut | Action |
|---|---|
| `Cmd/Ctrl + K` | Open command palette |
| `Cmd/Ctrl + Enter` | Run current simulation |
| `G H` | Go to Home |
| `G M` | Go to Mode Solver |
| `G P` | Go to Power & ASE |
| `G B` | Go to BPM |
| `Delete` | Remove selected node in System Builder |

---

## Using `fibersim` directly (no UI)

The physics library is fully usable from scripts and notebooks:

```python
from fibersim.core.fiber import StepIndexFiber
from fibersim.core.materials import Silica, Germanosilicate
from fibersim.solvers.modes.analytical import find_modes

fiber = StepIndexFiber(
    core_radius=4e-6,
    cladding_radius=62.5e-6,
    core_material=Germanosilicate(0.035),
    cladding_material=Silica(),
)
modes = find_modes(fiber.core_radius, n_core=1.4485, n_cladding=1.444, wavelength=1.55e-6)
print(f"Found {len(modes)} guided modes")
```

```python
from fibersim.solvers.fbg.solver import calculate_phase_mask

result = calculate_phase_mask(
    grating_type="uniform",
    n_eff=1.45,
    length_mm=10.0,
    dn=5e-4,
    period_nm=535.0,
    lambda_uv_nm=248.0,
)
print(f"Phase mask period: {result['params']['period_pm_center_nm']:.2f} nm")
print(f"Diffraction angle: {result['params']['diffraction_angle_deg']:.2f}°")
```

---

## Roadmap

- [ ] System-level simulation — chain solvers across the laser schematic graph
- [ ] Run comparison — side-by-side overlay of two simulations from history
- [ ] GNLSE — ultrashort pulse propagation (Raman, self-steepening, HOD)
- [ ] Report export — PDF with parameters, plots, and metadata
- [ ] Parameter sweep — N configurations in one click, results on a single chart

---

## Project status

| Layer | Status |
|---|---|
| `fibersim` physics library | Complete (Phases 1–5) |
| FastAPI backend + REST/WS API | Complete |
| Individual solver UIs | Complete (6 solvers) |
| FBG phase mask calculator | Complete |
| Device Library (SQLite + CRUD UI) | Complete |
| Laser System Builder (canvas) | In progress — visual assembly done, system simulation pending |
| MkDocs documentation | Planned |
