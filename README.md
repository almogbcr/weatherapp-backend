# WeatherApp Backend

## Overview

The WeatherApp Backend manages requests to the OpenWeather API and enforces daily request limits.
It improves security by keeping sensitive information, such as the API key, on the server instead of exposing it to the frontend.
It also processes and normalizes the JSON responses received from OpenWeather, providing the frontend with only the data it needs.

### Tech Stack

| Technology | Purpose |
|------------|---------|
| Python 3.12 | Programming language used to develop the backend |
| FastAPI | Framework used to build the REST API and handle application logic |
| Uvicorn | ASGI server used to run FastAPI and handle incoming HTTP requests |
| HTTPX | HTTP client used to communicate with external APIs |
| SQLAlchemy 2 | Database toolkit and ORM used to interact with PostgreSQL |
| PostgreSQL | Database used to store daily request counters and rate limit data |
| Docker | Packages the backend and its dependencies into a portable container image |

### API Endpoints
```
GET /health
check whether the back application is running and responding to HTTP requests
```
```
GET /metrics
Expose application metrics for Prometheus, including HTTP request counts, response times , and status codes
```
```
GET /weather
Returns currect weather data for the location selected by the user on the map 
Query Parameters:
- `lat`: Latitude
- `lon`: Longitude
- `units`: metric, imperial, or standard
```
```
GET /geocode
Searchs for locations by name and return their geographic coordinates
```
```
GET /reverse-geocode
Converts geographic coordinates (lat and long) into a location name
```
## Environment Variables

| Variable | Description |
|---|---|
| `OPENWEATHER_API_KEY` | API key used to authenticate requests to OpenWeather. |
| `DATABASE_URL` | Connection string used to connect to PostgreSQL. |
| `DAILY_REQUEST_LIMIT` | Maximum number of requests allowed per day. Defaults to 999. |

The repository include an `.exmaple.env` file containing example environment  variables
copy the example file to create your local `.env` file:

```bash
cp .example.env .env
```
## Rate Limiting
In order to prevent additional charges, we limit the number of daily requests to the OpenWeather API by configuring the `DAILY_REQUEST_LIMIT` environment variable.
