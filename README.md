# Rectpack MVP Service

Сервис для эвристической раскладки прямоугольных деталей на прямоугольных листах (stock) с возвратом результата в JSON и SVG.

## Возможности
- Режимы раскладки: `guillotine` (по умолчанию) и `nested` (по запросу).
- Учёт технологических параметров: `spacing_mm`, `trim_mm`, ограничения поворота, простое правило направления рисунка.
- Multi-start с `restarts` и `seed` для воспроизводимости.
- HTTP API на FastAPI + обязательная визуализация SVG.
- Docker-рантайм без внешних сервисов.

## Быстрый старт (Docker)
```bash
docker build -t rectpack-mvp .
docker run --rm -p 8080:8080 --name rectpack-mvp rectpack-mvp
```

Проверка:
```bash
curl -s http://127.0.0.1:8080/health/live
```

## Локальный запуск (Python 3.11+)
```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

## API
- `POST /v1/optimize` — расчёт раскладки
- `GET /health/live` — liveness probe
- `GET /health/ready` — readiness probe
- `GET /version` — версии сервиса/зависимостей
- `GET /openapi.json` — OpenAPI
- `GET /docs` — Swagger UI

## Пример запроса
```json
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
```

Отправка:
```bash
curl -s -X POST http://127.0.0.1:8080/v1/optimize \
  -H 'Content-Type: application/json' \
  --data @request.json
```

## Ответ
- `summary` — агрегированные метрики (использованные листы, отходы, время, seed, engine).
- `solutions[]` — размещения по каждому использованному листу.
- `artifacts.svg` — SVG документ с контурами листов и прямоугольниками деталей.

## Переменные окружения
- `PORT` (default `8080`)
- `LOG_LEVEL` (default `info`)
- `MAX_BODY_BYTES` (default `5242880`)
- `MAX_INSTANCES` (default `5000`)
- `DEFAULT_TIME_LIMIT_MS` (default `800`)
- `DEFAULT_RESTARTS` (default `5`)
- `MAX_CONCURRENT_JOBS` (default `1`)
- `DEFAULT_UNIT_SCALE` (default `100`)
