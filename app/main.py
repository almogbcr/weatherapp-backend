from typing import Literal, Optional
import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .settings import get_settings
from .weather_client import OpenWeatherClient, normalize_current

app = FastAPI(title="Weather Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # base app only
    allow_methods=["*"],
    allow_headers=["*"],
)

settings = get_settings()
client = OpenWeatherClient(settings)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/weather")
async def weather(
    lat: float = Query(...),
    lon: float = Query(...),
    units: Literal["metric", "imperial", "standard"] = "metric",
    lang: Optional[str] = None,
):
    try:
        raw = await client.current_weather(lat=lat, lon=lon, units=units, lang=lang)
        return normalize_current(raw)
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail={"upstream_status": e.response.status_code, "upstream_body": e.response.text},
        )
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Upstream request failed: {e}")
