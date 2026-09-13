"""Haversine location-radius boosts for matching."""

from __future__ import annotations

from math import atan2, cos, radians, sin, sqrt

from app.job_sources.geocode import geocode


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlmb = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlmb / 2) ** 2
    return 2 * r * atan2(sqrt(a), sqrt(1 - a))


def radius_boost(
    resume_city: str,
    job_city: str,
    *,
    resume_state: str = "",
    job_state: str = "",
    country: str = "US",
    radius_km: float = 50.0,
) -> dict[str, object]:
    resume = geocode(resume_city, resume_state, country)
    job = geocode(job_city, job_state, country)
    if not resume["found"] or not job["found"]:
        return {"boost": 0.0, "km": None, "within": False}
    if resume["lat"] == 0.0 and resume["lon"] == 0.0:
        return {"boost": 4.0, "km": 0.0, "within": True, "remote": True}
    km = haversine_km(float(resume["lat"]), float(resume["lon"]), float(job["lat"]), float(job["lon"]))
    within = km <= radius_km
    boost = 5.0 if km <= 15 else 3.0 if within else max(-4.0, 2.0 - km / radius_km)
    return {"boost": round(boost, 2), "km": round(km, 1), "within": within}
