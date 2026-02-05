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

    ip = request.headers.get("x-forwarded-for")
    if ip:
        ip = ip.split(",")[0].strip()
    else:
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
