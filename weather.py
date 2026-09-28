"""
Weather lookup — called once when an event is created/edited, result
stored on the Event row (see models.Event). Not called again at
recommendation time, so a stale event date just keeps its last-known
snapshot rather than erroring out.
"""

import os
import requests

OPENWEATHER_API_KEY = os.environ["OPENWEATHER_API_KEY"]
GEOCODE_URL = "https://api.openweathermap.org/geo/1.0/direct"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"


def _geocode(location: str) -> tuple[float, float]:
    resp = requests.get(GEOCODE_URL, params={"q": location, "limit": 1, "appid": OPENWEATHER_API_KEY})
    resp.raise_for_status()
    results = resp.json()
    if not results:
        raise ValueError(f"Could not geocode location: {location}")
    return results[0]["lat"], results[0]["lon"]


def get_weather_snapshot(location: str, event_date) -> dict:
    """
    Returns {"temp_c": float, "condition": str} for the closest forecast slot
    to event_date. OpenWeatherMap's free tier only forecasts 5 days out —
    for events further out, this returns None values and you re-check closer
    to the date (surface that in the UI rather than silently failing).
    """
    lat, lon = _geocode(location)
    resp = requests.get(FORECAST_URL, params={
        "lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY, "units": "metric",
    })
    resp.raise_for_status()
    forecasts = resp.json().get("list", [])
    if not forecasts:
        return {"temp_c": None, "condition": None}

    closest = min(forecasts, key=lambda f: abs(_parse_dt(f["dt_txt"]) - event_date).total_seconds())
    return {
        "temp_c": closest["main"]["temp"],
        "condition": closest["weather"][0]["main"].lower(),  # e.g. "rain", "clear", "clouds"
    }


def _parse_dt(dt_txt: str):
    from datetime import datetime
    return datetime.strptime(dt_txt, "%Y-%m-%d %H:%M:%S")
