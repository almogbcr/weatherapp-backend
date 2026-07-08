# Weather App Backend

FastAPI service for weather data with:
- Current weather proxy from OpenWeather.
- Reverse geocoding via Nominatim.
- Daily request limiting by IP, device ID, and IP+device pair.
- PostgreSQL persistence for rate-limit counters.

## Tech Stack
- Python 3.12
- FastAPI + Uvicorn
- SQLAlchemy 2
- PostgreSQL

## Environment Variables
Required:
- `OPENWEATHER_API_KEY`
- `DATABASE_URL`
- `DAILY_REQUEST_LIMIT` (default: `999`)

Example:

```env
OPENWEATHER_API_KEY=your_key_here
DAILY_REQUEST_LIMIT=999
DATABASE_URL=postgresql+psycopg://user:password@db:5432/weatherapp
```

Copy .example.env is optional

## Run via Root Compose
From `weatherapp/`:

```bash
docker compose up --build
```

Backend will be available at:
- `http://localhost:8000`

## API Endpoints
- `GET /health`
  - Returns service status.
- `GET /weather?lat=<float>&lon=<float>&units=metric|imperial|standard`
  - Requires header `X-Device-Id`.
  - Returns normalized weather + `rate_limit` info.
- `GET /reverse-geocode?lat=<float>&lon=<float>`
  - Returns English place and country names regardless of client locale.

## Notes
- DB tables are auto-created on app startup.
- If `X-Device-Id` is missing on `/weather`, API returns `400`.
- When daily limit is exceeded, API returns `429`.
