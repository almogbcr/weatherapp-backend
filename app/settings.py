import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str = "https://api.openweathermap.org"
    timeout_seconds: float = 10.0

def get_settings() -> Settings:
    api_key = os.getenv("OPENWEATHER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENWEATHER_API_KEY not set. Put it in .env")
    return Settings(api_key=api_key)
