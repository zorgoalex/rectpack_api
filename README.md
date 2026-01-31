# Rectpack MVP Service

Rectpack MVP is a Python service for 2D rectangular packing with an HTTP API and SVG output.
It uses FastAPI and the `rectpack` engine and always returns an SVG artifact for successful optimizations.

## Features
- 2D rectangle packing with spacing and trim support
- Rotation constraints and basic pattern-direction rules
- Multi-start optimization with deterministic seeds
- JSON API with OpenAPI + Swagger UI
- Docker-ready single-container service

## Tech Stack
- Python 3.11+
- FastAPI + Uvicorn (HTTP)
- rectpack (layout engine)
- Pydantic (validation)

## Quick Start (Local)
```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 18088
```

Service listens on `0.0.0.0:18088` for the command above.

## Quick Start (Docker)
```bash
docker build -t rectpack-mvp .
docker run --rm -p 18088:8080 --name rectpack-mvp rectpack-mvp
```

Note: examples below use external port `18088`.

## Health & Docs
- `GET /health/live`
- `GET /health/ready`
- `GET /version`
- `GET /openapi.json`
- `GET /docs`

## Main Endpoint
`POST /v1/optimize`

- Request/response are JSON.
- All dimensions are in millimeters (`mm`).
- Successful responses include SVG in `artifacts.svg`.
- Coordinate system in placements and SVG: origin (0,0) is the top-left of the stock sheet;
  the usable area starts at `(trim.left, trim.top)`, X to the right, Y down.

### Example Request
```json
{
  "units": "mm",
  "params": {
    "mode": "nested",
    "spacing_mm": 2.0,
    "trim_mm": {
      "left": 10.0,
      "right": 10.0,
      "top": 10.0,
      "bottom": 10.0
    },
    "time_limit_ms": 500,
    "restarts": 3,
    "objective": "min_waste",
    "seed": 12345
  },
  "stock": [
    { "id": "sheet-1000", "width_mm": 1000.0, "height_mm": 800.0, "qty": 1 }
  ],
  "items": [
    { "id": "A", "width_mm": 200.0, "height_mm": 300.0, "qty": 2, "rotation": "allow_90", "pattern_direction": "none" },
    { "id": "B", "width_mm": 150.0, "height_mm": 150.0, "qty": 3, "rotation": "forbid", "pattern_direction": "none" }
  ]
}
```

### Example Request (Guillotine Default)
If `params.mode` is omitted, the service uses `guillotine`.
```json
{
  "units": "mm",
  "params": {
    "spacing_mm": 1.0,
    "trim_mm": { "left": 5.0, "right": 5.0, "top": 5.0, "bottom": 5.0 },
    "time_limit_ms": 300,
    "restarts": 2,
    "objective": "min_sheets"
  },
  "stock": [
    { "id": "sheet-1200", "width_mm": 1200.0, "height_mm": 1000.0, "qty": 2 }
  ],
  "items": [
    { "id": "P1", "width_mm": 400.0, "height_mm": 300.0, "qty": 3, "rotation": "allow_90", "pattern_direction": "none" },
    { "id": "P2", "width_mm": 500.0, "height_mm": 200.0, "qty": 2, "rotation": "forbid", "pattern_direction": "along_width" }
  ]
}
```

### Field-by-Field Explanation
- `units`: Measurement units; must be `"mm"`.
- `params`: Optimization parameters.
  - `mode`: Layout mode: `"guillotine"` (default) or `"nested"` (explicit only).
  - `spacing_mm`: Clearance between parts (implemented by inflating part sizes).
  - `trim_mm`: Unusable margins around the sheet in mm (`left`, `right`, `top`, `bottom`).
  - `time_limit_ms`: Total time budget in ms. The budget is split across restarts.
  - `restarts`: Number of optimization restarts (multi-start).
  - `objective`: Optimization goal: `"min_waste"` or `"min_sheets"`.
  - `seed`: Optional deterministic seed; if omitted, a seed is generated per request.
  - `engine`: Optional low-level packer settings.
    - `packer`: `"guillotine"`, `"maxrects"`, or `"skyline"`.
    - `bin_select`: `"best_fit"` or `"first_fit"`.
    - `sort`: `"area_desc"`, `"maxside_desc"`, or `"none"`.
  - `unit_scale`: Optional scale for integer geometry (default `100`).
- `stock`: Available sheet materials.
  - `id`: Stock identifier.
  - `width_mm`, `height_mm`: Sheet dimensions in mm.
  - `qty`: Quantity of sheets of this size.
- `items`: Parts to be cut.
  - `id`: Part identifier.
  - `width_mm`, `height_mm`: Part dimensions in mm.
  - `qty`: Quantity of this part.
  - `rotation`: Rotation rule: `"forbid"` or `"allow_90"`.
  - `pattern_direction`: Grain/pattern direction: `"none"`, `"along_width"`, `"along_height"`.

### Example Response
```json
{
  "status": "ok",
  "summary": {
    "mode": "nested",
    "objective": "min_waste",
    "used_stock_count": 1,
    "total_waste_area_mm2": 594600.0,
    "waste_percent": 76.0261,
    "time_ms": 3,
    "restarts_used": 3,
    "seed": 12345,
    "engine": {
      "packer": "maxrects",
      "bin_select": "best_fit",
      "sort": "area_desc"
    }
  },
  "solutions": [
    {
      "stock_id": "sheet-1000",
      "index": 0,
      "width_mm": 1000.0,
      "height_mm": 800.0,
      "trim_mm": { "left": 10.0, "right": 10.0, "top": 10.0, "bottom": 10.0 },
      "placements": [
        {
          "item_id": "A",
          "instance": 1,
          "x_mm": 10.0,
          "y_mm": 10.0,
          "width_mm": 200.0,
          "height_mm": 300.0,
          "rotated": false,
          "pattern_direction": "none"
        }
      ]
    }
  ],
  "artifacts": {
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 1000 800\">...</svg>"
  }
}
```

### Response Keys (Summary)
- `status`: `"ok"` on success.
- `summary`: Aggregated optimization metrics.
  - `mode`: Layout mode actually used.
  - `objective`: Chosen objective.
  - `used_stock_count`: Number of sheets used.
  - `total_waste_area_mm2`: Total waste area in mm^2.
  - `waste_percent`: Waste percentage of used stock.
  - `time_ms`: Total runtime in milliseconds.
  - `restarts_used`: Number of restarts actually used.
  - `seed`: Seed actually used (user-provided or auto-generated).
  - `engine`: Packer settings actually used.
- `solutions`: Per-sheet layouts.
- `artifacts.svg`: Full SVG document of the layout.

## Limits and Validation
- `sum(items.qty) <= 5000` (also bounded by `MAX_INSTANCES`).
- `stock.length <= 50`.
- `units` must be `"mm"`.
- Trim must not consume the entire sheet.
- Each item must fit at least one stock sheet (considering trim, spacing, and rotation rules).
- Mode default: if `params.mode` is omitted, the service uses `"guillotine"`.
- `mode="nested"` is applied only when explicitly provided in the request.
- Engine compatibility:
  - `mode="guillotine"` requires `engine.packer="guillotine"` if provided.
  - `mode="nested"` forbids `engine.packer="guillotine"` if provided.

## Error Format
Errors are returned as:
```json
{
  "status": "error",
  "error_code": "VALIDATION_ERROR",
  "message": "...",
  "details": { "...": "..." }
}
```

## Error Codes
- `VALIDATION_ERROR` (422): invalid fields/ranges, item does not fit, conflict between `rotation` and `pattern_direction`, or incompatible `mode` + `engine.packer`.
- `CONSTRAINT_ERROR` (400): request is too large or violates service constraints.
- `TIMEOUT` (408): exceeded `time_limit_ms`.
- `INTERNAL` (500): unexpected server error.

## Environment Variables
- `PORT` (default `8080`)
- `LOG_LEVEL` (default `info`)
- `MAX_BODY_BYTES` (default `5242880`)
- `MAX_INSTANCES` (default `5000`)
- `DEFAULT_TIME_LIMIT_MS` (default `800`)
- `DEFAULT_RESTARTS` (default `5`)
- `MAX_CONCURRENT_JOBS` (default `1`)
- `DEFAULT_UNIT_SCALE` (default `100`)

## Docker Smoke Tests
These tests validate the running container via a host-network curl image.

```bash
# Start the container first
docker run --rm -p 18088:8080 rectpack-mvp
```

In another terminal:
```bash
# Health check
docker run --rm --network host curlimages/curl:8.5.0 -s http://127.0.0.1:18088/health/live

# Optimize request
cat > /tmp/optimize.json <<'JSON'
{
  "units": "mm",
  "params": {
    "spacing_mm": 2,
    "trim_mm": {"left": 5, "right": 5, "top": 5, "bottom": 5},
    "time_limit_ms": 500,
    "restarts": 3,
    "objective": "min_waste",
    "seed": 123
  },
  "stock": [
    {"id": "S1", "width_mm": 1000, "height_mm": 800, "qty": 1}
  ],
  "items": [
    {"id": "A", "width_mm": 300, "height_mm": 200, "qty": 2, "rotation": "allow_90", "pattern_direction": "none"},
    {"id": "B", "width_mm": 150, "height_mm": 150, "qty": 3, "rotation": "forbid", "pattern_direction": "none"}
  ]
}
JSON

docker run --rm --network host -v /tmp/optimize.json:/data.json:ro \
  curlimages/curl:8.5.0 -s -X POST -H 'Content-Type: application/json' \
  --data @/data.json http://127.0.0.1:18088/v1/optimize
```
