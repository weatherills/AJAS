"""City/state/country → lat/lon with an in-process cache."""

from __future__ import annotations

from functools import lru_cache

KNOWN: dict[str, tuple[float, float]] = {
    "seattle|wa|us": (47.6062, -122.3321),
    "seattle|washington|us": (47.6062, -122.3321),
    "new york|ny|us": (40.7128, -74.006),
    "austin|tx|us": (30.2672, -97.7431),
    "london||gb": (51.5074, -0.1278),
    "london||uk": (51.5074, -0.1278),
    "toronto|on|ca": (43.6532, -79.3832),
    "berlin||de": (52.52, 13.405),
    "remote||": (0.0, 0.0),
}


def _key(city: str, state: str, country: str) -> str:
    return "|".join(part.strip().lower() for part in (city, state, country))


@lru_cache(maxsize=2048)
def geocode_cached(city: str, state: str = "", country: str = "US") -> tuple[float, float] | None:
    key = _key(city, state, country)
    if key in KNOWN:
        return KNOWN[key]
    country_key = _key(city, "", country)
    if country_key in KNOWN:
        return KNOWN[country_key]
    return None


def geocode(city: str, state: str = "", country: str = "US") -> dict[str, object]:
    coords = geocode_cached(city or "", state or "", country or "")
    if coords is None:
        return {
            "city": city,
            "state": state,
            "country": country,
            "lat": None,
            "lon": None,
            "cached": False,
            "found": False,
        }
    return {
        "city": city,
        "state": state,
        "country": country,
        "lat": coords[0],
        "lon": coords[1],
        "cached": True,
        "found": True,
    }


def cache_info() -> dict[str, int]:
    info = geocode_cached.cache_info()
    return {"hits": info.hits, "misses": info.misses, "size": info.currsize}


def clear_cache() -> None:
    geocode_cached.cache_clear()
