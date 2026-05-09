from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parents[1]
REFERENCES = ROOT / "references"
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import health_assessment as core  # noqa: E402


APP_NAME = "health-assessment"
DEFAULT_TIMEZONE = "Asia/Shanghai"
DEFAULT_STORE = ROOT / "data" / "events.jsonl"
WEATHER_TIMEOUT_SECONDS = 6

app = FastAPI(title=APP_NAME, version="0.2.0")


class MessageRequest(BaseModel):
    user_id: str = Field(default="default")
    text: str
    timezone: str = Field(default=DEFAULT_TIMEZONE)
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    now: str | None = None


class SeasonalRequest(BaseModel):
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    timezone: str = Field(default=DEFAULT_TIMEZONE)
    month: int | None = Field(default=None, ge=1, le=12)


class ConditionRequest(BaseModel):
    text: str
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    timezone: str = Field(default=DEFAULT_TIMEZONE)


def store_path() -> Path:
    return Path(os.environ.get("HEALTH_STORE", str(DEFAULT_STORE))).resolve()


def read_json(name: str) -> dict[str, Any]:
    return json.loads((REFERENCES / name).read_text(encoding="utf-8"))


def current_month(timezone: str, raw_now: str | None = None) -> int:
    tz = ZoneInfo(timezone)
    if raw_now:
        parsed = datetime.fromisoformat(raw_now)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=tz)
        return parsed.astimezone(tz).month
    return datetime.now(tz).month


def http_get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "health-assessment/0.2"})
    with urllib.request.urlopen(request, timeout=WEATHER_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def geocode_city(city: str) -> dict[str, Any] | None:
    params = urllib.parse.urlencode({"name": city, "count": 1, "language": "zh", "format": "json"})
    data = http_get_json(f"https://geocoding-api.open-meteo.com/v1/search?{params}")
    results = data.get("results") or []
    return results[0] if results else None


def resolve_location(
    city: str | None,
    latitude: float | None,
    longitude: float | None,
) -> tuple[float, float, str | None]:
    if latitude is not None and longitude is not None:
        return latitude, longitude, city
    if city:
        result = geocode_city(city)
        if result:
            label = result.get("name") or city
            admin = result.get("admin1")
            country = result.get("country")
            full_label = " / ".join(part for part in [label, admin, country] if part)
            return float(result["latitude"]), float(result["longitude"]), full_label
    raise ValueError("location_missing")


def fetch_weather(
    city: str | None,
    latitude: float | None,
    longitude: float | None,
    timezone: str,
) -> dict[str, Any] | None:
    try:
        lat, lon, label = resolve_location(city, latitude, longitude)
    except Exception:
        return None

    params = urllib.parse.urlencode(
        {
            "latitude": lat,
            "longitude": lon,
            "timezone": timezone,
            "current": ",".join(
                [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "apparent_temperature",
                    "precipitation",
                    "weather_code",
                    "wind_speed_10m",
                ]
            ),
        }
    )
    try:
        data = http_get_json(f"https://api.open-meteo.com/v1/forecast?{params}")
    except Exception:
        return None
    current = data.get("current") or {}
    return {
        "location": label,
        "temperature_c": current.get("temperature_2m"),
        "apparent_temperature_c": current.get("apparent_temperature"),
        "relative_humidity_percent": current.get("relative_humidity_2m"),
        "precipitation_mm": current.get("precipitation"),
        "weather_code": current.get("weather_code"),
        "wind_speed_kmh": current.get("wind_speed_10m"),
        "source": "Open-Meteo",
    }


def season_for_month(seasonal: dict[str, Any], month: int) -> tuple[str, dict[str, Any]]:
    for season_id, season in seasonal["seasons"].items():
        if month in season["months"]:
            return season_id, season
    return "unknown", {"focus": "按当前月份选择新鲜、易获得水果。", "fruits": []}


def weather_advice(seasonal: dict[str, Any], weather: dict[str, Any] | None) -> list[str]:
    if not weather:
        return ["未取得实时天气，按季节日历给出建议。"]
    advice: list[str] = []
    temp = weather.get("temperature_c")
    humidity = weather.get("relative_humidity_percent")
    precipitation = weather.get("precipitation_mm")
    if isinstance(temp, (int, float)) and temp >= 30:
        advice.append(next(rule["advice"] for rule in seasonal["weather_rules"] if rule["id"] == "hot"))
    if isinstance(temp, (int, float)) and temp <= 5:
        advice.append(next(rule["advice"] for rule in seasonal["weather_rules"] if rule["id"] == "cold"))
    if isinstance(precipitation, (int, float)) and precipitation > 0:
        advice.append(next(rule["advice"] for rule in seasonal["weather_rules"] if rule["id"] == "rain"))
    if isinstance(humidity, (int, float)) and humidity < 35:
        advice.append(next(rule["advice"] for rule in seasonal["weather_rules"] if rule["id"] == "dry"))
    return advice or ["天气无明显特殊提醒，按每日200-350g鲜果目标安排即可。"]


def seasonal_fruit_advice(payload: SeasonalRequest, raw_now: str | None = None) -> dict[str, Any]:
    seasonal = read_json("seasonal-fruits.json")
    month = payload.month or current_month(payload.timezone, raw_now)
    season_id, season = season_for_month(seasonal, month)
    fruits = seasonal["monthly"].get(str(month), season.get("fruits", []))
    weather = fetch_weather(payload.city, payload.latitude, payload.longitude, payload.timezone)
    weather_notes = weather_advice(seasonal, weather)
    target = seasonal["metadata"]["daily_fruit_target_g"]
    reply = [
        f"{month}月当季水果参考：{'、'.join(fruits[:8])}。",
        season["focus"],
        f"每日鲜果参考量：{target[0]}-{target[1]}g，优先完整鲜果，果汁不能替代鲜果。",
        *weather_notes,
    ]
    return {
        "month": month,
        "season": season_id,
        "fruits": fruits,
        "weather": weather,
        "advice": weather_notes,
        "reply": "\n".join(reply),
        "source": ["seasonal-fruits.json", "Open-Meteo when location is available"],
    }


def match_condition(text: str) -> dict[str, Any] | None:
    guidance = read_json("condition-guidance.json")
    lowered = text.lower()
    for condition in guidance["conditions"]:
        for alias in condition["aliases"]:
            if alias.lower() in lowered:
                return condition
    return None


def red_flags_for(text: str, condition: dict[str, Any]) -> list[str]:
    guidance = read_json("condition-guidance.json")
    flags = list(guidance.get("global_emergency_flags", [])) + list(condition.get("emergency", []))
    seen: set[str] = set()
    matched: list[str] = []
    for flag in flags:
        if flag in text and flag not in seen:
            matched.append(flag)
            seen.add(flag)
    return matched


def condition_advice(payload: ConditionRequest) -> dict[str, Any]:
    guidance = read_json("condition-guidance.json")
    condition = match_condition(payload.text)
    if not condition:
        raise HTTPException(status_code=404, detail="No supported condition matched")

    weather = fetch_weather(payload.city, payload.latitude, payload.longitude, payload.timezone)
    flags = red_flags_for(payload.text, condition)
    lines = [
        f"已识别：{condition['display_name']}。这不是诊断，我会先按健康教育和分诊提示处理。",
    ]
    if flags:
        lines.append(f"警示：你提到了 {'、'.join(flags)}。建议立即联系急救或尽快就医。")
    else:
        lines.append("目前未从文本中识别到明确急症词，但如果症状严重或让你担心，应及时就医。")

    lines.extend(
        [
            "",
            "可能原因：",
            *[f"- {item}" for item in condition["possible_causes"]],
            "",
            "建议补充的信息：",
            *[f"- {item}" for item in condition["questions"]],
            "",
            "可先注意：",
            *[f"- {item}" for item in condition["self_care"]],
        ]
    )
    if condition.get("avoid"):
        lines.extend(["", "避免：", *[f"- {item}" for item in condition["avoid"]]])
    if weather:
        lines.extend(
            [
                "",
                f"天气参考：{weather.get('location') or '当前位置'}约 {weather.get('temperature_c')}°C，湿度 {weather.get('relative_humidity_percent')}%。天气只作为生活提醒，不用于诊断。",
            ]
        )
    lines.extend(["", guidance["metadata"]["disclaimer"]])

    return {
        "condition_id": condition["id"],
        "display_name": condition["display_name"],
        "red_flags": flags,
        "questions": condition["questions"],
        "self_care": condition["self_care"],
        "seek_medical_care": condition["seek_medical_care"],
        "emergency": condition["emergency"],
        "weather": weather,
        "reply": "\n".join(lines),
        "source_ids": condition.get("source_ids", []),
    }


def wants_seasonal_fruit(text: str) -> bool:
    return any(token in text for token in ["当季水果", "应季水果", "这个季节吃什么水果", "水果建议"])


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": APP_NAME}


@app.post("/v1/health/messages")
def handle_message(payload: MessageRequest) -> dict[str, Any]:
    condition = match_condition(payload.text)
    if condition:
        result = condition_advice(
            ConditionRequest(
                text=payload.text,
                city=payload.city,
                latitude=payload.latitude,
                longitude=payload.longitude,
                timezone=payload.timezone,
            )
        )
        return {"type": "condition_guidance", **result}

    if wants_seasonal_fruit(payload.text):
        result = seasonal_fruit_advice(
            SeasonalRequest(
                city=payload.city,
                latitude=payload.latitude,
                longitude=payload.longitude,
                timezone=payload.timezone,
            ),
            payload.now,
        )
        return {"type": "seasonal_fruit", **result}

    args = argparse.Namespace(
        user=payload.user_id,
        text=payload.text,
        store=str(store_path()),
        timezone=payload.timezone,
        now=payload.now,
    )
    return {"type": "lifestyle_record", **core.record(args)}


@app.post("/v1/health/seasonal-fruits")
def post_seasonal_fruits(payload: SeasonalRequest) -> dict[str, Any]:
    return seasonal_fruit_advice(payload)


@app.get("/v1/health/seasonal-fruits")
def get_seasonal_fruits(
    city: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    timezone: str = DEFAULT_TIMEZONE,
    month: int | None = Query(default=None, ge=1, le=12),
) -> dict[str, Any]:
    return seasonal_fruit_advice(
        SeasonalRequest(city=city, latitude=latitude, longitude=longitude, timezone=timezone, month=month)
    )


@app.post("/v1/health/conditions")
def post_condition(payload: ConditionRequest) -> dict[str, Any]:
    return condition_advice(payload)


@app.get("/v1/health/conditions")
def list_conditions() -> dict[str, Any]:
    guidance = read_json("condition-guidance.json")
    return {
        "conditions": [
            {
                "id": item["id"],
                "display_name": item["display_name"],
                "aliases": item["aliases"],
                "source_ids": item.get("source_ids", []),
            }
            for item in guidance["conditions"]
        ],
        "disclaimer": guidance["metadata"]["disclaimer"],
    }


@app.get("/v1/health/reports/weekly")
def weekly_report(
    user_id: str = "default",
    week_start: str | None = None,
    timezone: str = DEFAULT_TIMEZONE,
    now: str | None = None,
) -> dict[str, str]:
    args = argparse.Namespace(
        user=user_id,
        store=str(store_path()),
        timezone=timezone,
        week_start=week_start,
        now=now,
    )
    return {"reply": core.weekly(args)}


@app.get("/v1/health/reports/monthly")
def monthly_report(
    user_id: str = "default",
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    timezone: str = DEFAULT_TIMEZONE,
) -> dict[str, str]:
    args = argparse.Namespace(user=user_id, store=str(store_path()), timezone=timezone, month=month)
    return {"reply": core.monthly(args)}
