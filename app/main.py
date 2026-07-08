from typing import Literal, Optional
import httpx
from fastapi import FastAPI, HTTPException, Query, Request, Header
from fastapi.middleware.cors import CORSMiddleware

from .settings import get_settings
from .db import build_engine, build_session_factory
from .models import Base
from .limit_store import check_and_increment
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
engine = build_engine(settings.database_url)
SessionLocal = build_session_factory(engine)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/weather")
async def weather(
    request: Request,
    lat: float = Query(...),
    lon: float = Query(...),
    units: Literal["metric", "imperial", "standard"] = "metric",
    lang: Optional[str] = None,
    device_id: Optional[str] = Header(None, alias="X-Device-Id"),
):
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-Id header required")

    # Do not trust client-supplied x-forwarded-for directly.
    ip = request.client.host if request.client else "unknown"

    with SessionLocal.begin() as session:
        rate_info = check_and_increment(
            session=session, ip=ip, device_id=device_id, limit=settings.daily_limit
        )
    if rate_info.blocked:
        raise HTTPException(
            status_code=429,
            detail={
                "message": f"Daily request limit reached ({settings.daily_limit}).",
                "rate_limit": rate_info.to_dict(),
            },
        )

    try:
        raw = await client.current_weather(lat=lat, lon=lon, units=units, lang=lang)
        payload = normalize_current(raw)
        payload["rate_limit"] = rate_info.to_dict()
        return payload
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail={"upstream_status": e.response.status_code, "upstream_body": e.response.text},
        )
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Upstream request failed: {e}")
    

@app.get("/reverse-geocode")
async def reverse_geocode(
    lat: float = Query(...),
    lon: float = Query(...),
):
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {"format": "jsonv2", "lat": lat, "lon": lon}

    # Keep place and country names stable in the UI regardless of browser locale.
    headers = {
        "User-Agent": "weatherapp-backend/1.0",
        "Accept-Language": "en",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(url, params=params, headers=headers)
            r.raise_for_status()
            return r.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail={"upstream_status": e.response.status_code, "upstream_body": e.response.text},
        )
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Upstream request failed: {e}")


@app.get("/geocode")
async def geocode(
    q: str = Query(..., min_length=2),
    limit: int = Query(5, ge=1, le=10),
):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "format": "jsonv2",
        "q": q,
        "limit": limit,
        "addressdetails": 1,
    }
    headers = {
        "User-Agent": "weatherapp-backend/1.0",
        "Accept-Language": "en",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(url, params=params, headers=headers)
            r.raise_for_status()
            return r.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail={"upstream_status": e.response.status_code, "upstream_body": e.response.text},
        )
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Upstream request failed: {e}")




