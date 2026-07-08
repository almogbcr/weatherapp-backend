from typing import Any, Dict, Optional
import httpx
from .settings import Settings

class OpenWeatherClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def current_weather(
        self,
        lat: float,
        lon: float,
        units: str = "metric",
        lang: Optional[str] = None,
    ) -> Dict[str, Any]:
        url = f"{self.settings.base_url}/data/2.5/weather"
        params = {"lat": lat, "lon": lon, "appid": self.settings.api_key, "units": units}
        if lang:
            params["lang"] = lang

        async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
            r = await client.get(url, params=params)

        r.raise_for_status()
        return r.json()

def normalize_current(payload: Dict[str, Any]) -> Dict[str, Any]:
    w0 = (payload.get("weather") or [{}])[0] or {}
    main = payload.get("main") or {}
    wind = payload.get("wind") or {}
    coord = payload.get("coord") or {}

    return {
        "lat": coord.get("lat"),
        "lon": coord.get("lon"),
        "timezone": None,
        "current": {
            "temp": main.get("temp"),
            "feels_like": main.get("feels_like"),
            "humidity": main.get("humidity"),
            "wind_speed": wind.get("speed"),
            "description": w0.get("description"),
            "icon": w0.get("icon"),
        },
    }
