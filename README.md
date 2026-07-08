# Weather App Backend

FastAPI backend for the Weather App project. This service receives requests from the frontend, calls external weather/location APIs, normalizes the response, and enforces a daily usage limit.

## What This Service Does

- Exposes a health check endpoint for sanity testing.
- Fetches current weather by latitude and longitude from OpenWeather.
- Normalizes weather data into a compact response for the frontend.
- Searches for coordinates from typed location names with Nominatim.
- Reverse-geocodes coordinates with Nominatim.
- Forces reverse-geocoded place and country names to English, regardless of browser locale.
- Requires a client device id for weather requests.
- Tracks daily request usage by IP, device id, and IP/device pair.
- Stores rate-limit counters in PostgreSQL.
- Auto-creates database tables on application startup.

## Tech Stack

- Python 3.12
- FastAPI
- Uvicorn
- HTTPX
- SQLAlchemy 2
- PostgreSQL
- Docker

## Environment Variables

Required:

```env
OPENWEATHER_API_KEY=your_openweather_key
DATABASE_URL=postgresql+psycopg://weatherapp:weatherapp@db:5432/weatherapp
DAILY_REQUEST_LIMIT=999
```

`DAILY_REQUEST_LIMIT` defaults to `999` when not provided.

## Run With Docker Compose

The full project is intended to run from the parent `weatherapp/` folder with the root `docker-compose.yml`.

```bash
docker compose up --build
```

Backend URL:

```text
http://localhost:8000
```

## API Endpoints

### `GET /health`

Returns service status.

Example response:

```json
{
  "status": "ok"
}
```

### `GET /weather`

Fetches current weather for coordinates.

Query parameters:

- `lat`: latitude
- `lon`: longitude
- `units`: `metric`, `imperial`, or `standard`

Required header:

```http
X-Device-Id: unique-client-device-id
```

The endpoint increments usage counters and returns weather data with rate-limit information.

### `GET /reverse-geocode`

Returns location data for coordinates.

Query parameters:

- `lat`: latitude
- `lon`: longitude

The backend always sends `Accept-Language: en` to Nominatim so country and place names are returned in English.

### `GET /geocode`

Searches for locations by text and returns matching coordinates.

Query parameters:

- `q`: location search text, such as a city, country, or address
- `limit`: optional result limit from `1` to `10`, defaults to `5`

The backend also sends `Accept-Language: en` for this endpoint so search result names are returned in English.

## Rate Limiting

Each successful `/weather` request is counted for:

- The request IP address.
- The device id from `X-Device-Id`.
- The IP and device id pair.

If any of those counters reaches the configured daily limit, the request is blocked with HTTP `429`.

## Notes

- Missing `OPENWEATHER_API_KEY` or `DATABASE_URL` will prevent the backend from starting.
- Missing `X-Device-Id` on `/weather` returns HTTP `400`.
- Upstream OpenWeather or Nominatim failures are returned as HTTP `502`.
- Local SQLite data files are ignored and should not be committed.
