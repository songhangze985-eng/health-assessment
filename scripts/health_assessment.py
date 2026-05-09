#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


SCRIPT_DIR = Path(__file__).resolve().parent
FOOD_SEED_PATH = SCRIPT_DIR.parent / "references" / "food-seed.json"
DEFAULT_TIMEZONE = "Asia/Shanghai"
DISCLAIMER = "本结果仅用于生活方式记录和健康教育，不构成医疗建议。"

NUMBER_WORDS = {
    "半": 0.5,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}

EXERCISE_ALIASES = {
    "跑步": ("running", "vigorous", False),
    "慢跑": ("jogging", "vigorous", False),
    "快走": ("brisk_walking", "moderate", False),
    "走路": ("walking", "moderate", False),
    "步行": ("walking", "moderate", False),
    "骑车": ("cycling", "moderate", False),
    "骑行": ("cycling", "moderate", False),
    "游泳": ("swimming", "moderate", False),
    "跳绳": ("jump_rope", "vigorous", False),
    "hiit": ("hiit", "vigorous", False),
    "HIIT": ("hiit", "vigorous", False),
    "力量": ("strength_training", "strength", True),
    "抗阻": ("resistance_training", "strength", True),
    "举铁": ("weight_training", "strength", True),
    "健身": ("workout", "moderate", False),
    "瑜伽": ("yoga", "moderate", False),
}


@dataclass(frozen=True)
class ParsedTime:
    value: datetime
    source: str


def load_foods() -> list[dict[str, Any]]:
    data = json.loads(FOOD_SEED_PATH.read_text(encoding="utf-8"))
    return data["foods"]


def load_events(store: Path) -> list[dict[str, Any]]:
    if not store.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in store.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def append_event(store: Path, event: dict[str, Any]) -> None:
    store.parent.mkdir(parents=True, exist_ok=True)
    with store.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def parse_now(raw_now: str | None, timezone: str) -> datetime:
    tz = ZoneInfo(timezone)
    if raw_now is None:
        return datetime.now(tz)
    parsed = datetime.fromisoformat(raw_now)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


def parse_number(raw: str) -> float:
    if raw in NUMBER_WORDS:
        return NUMBER_WORDS[raw]
    return float(raw)


def parse_event_time(text: str, now: datetime, timezone: str) -> ParsedTime:
    tz = ZoneInfo(timezone)
    iso_match = re.search(
        r"(?P<date>\d{4}-\d{1,2}-\d{1,2})(?:[T\s]+(?P<hour>\d{1,2}):(?P<minute>\d{1,2}))?",
        text,
    )
    if iso_match:
        y, m, d = [int(part) for part in iso_match.group("date").split("-")]
        hour = int(iso_match.group("hour") or 0)
        minute = int(iso_match.group("minute") or 0)
        return ParsedTime(datetime(y, m, d, hour, minute, tzinfo=tz), "explicit_user_time")

    time_match = re.search(
        r"(?P<period>凌晨|早上|上午|中午|下午|晚上|今晚|昨晚)?\s*"
        r"(?P<hour>[01]?\d|2[0-3])\s*(?:[:：点时])\s*(?P<minute>[0-5]?\d)?",
        text,
    )
    if not time_match:
        return ParsedTime(now, "implicit_now")

    event_date = now.date()
    if "前天" in text:
        event_date -= timedelta(days=2)
    elif "昨天" in text or "昨晚" in text:
        event_date -= timedelta(days=1)
    elif "明天" in text:
        event_date += timedelta(days=1)

    hour = int(time_match.group("hour"))
    minute = int(time_match.group("minute") or 0)
    period = time_match.group("period") or ""
    if period in {"下午", "晚上", "今晚", "昨晚"} and hour < 12:
        hour += 12
    if period == "中午" and hour < 11:
        hour += 12
    if period == "凌晨" and hour == 12:
        hour = 0

    return ParsedTime(
        datetime.combine(event_date, time(hour, minute), tzinfo=ZoneInfo(timezone)),
        "explicit_user_time",
    )


def event_base(
    user_id: str,
    event_type: str,
    timestamp: datetime,
    timezone: str,
    raw_text: str,
    source: str,
) -> dict[str, Any]:
    return {
        "event_id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": event_type,
        "timestamp": timestamp.isoformat(),
        "timezone": timezone,
        "raw_text": raw_text,
        "source": source,
        "created_at": datetime.now(ZoneInfo(timezone)).isoformat(),
        "schema_version": 1,
    }


def is_sleep_start(text: str) -> bool:
    return any(token in text for token in ["睡觉了", "睡了", "入睡", "上床睡觉", "准备睡"])


def is_sleep_end(text: str) -> bool:
    return any(token in text for token in ["起床", "醒了", "睡醒"])


def time_float(value: datetime) -> float:
    return value.hour + value.minute / 60


def evaluate_sleep(start_at: datetime, end_at: datetime) -> dict[str, Any]:
    if end_at <= start_at:
        end_at += timedelta(days=1)
    duration = round((end_at - start_at).total_seconds() / 3600, 2)
    if duration < 7:
        duration_status = "short"
        duration_text = "低于成人常见建议下限"
    elif duration <= 9:
        duration_status = "target"
        duration_text = "在成人常见建议范围内"
    else:
        duration_status = "long"
        duration_text = "高于成人常见建议范围"

    bedtime = time_float(start_at)
    wake_time = time_float(end_at)
    bedtime_normal = bedtime >= 21 or bedtime <= 0.5
    wake_normal = 5.5 <= wake_time <= 9

    schedule_notes: list[str] = []
    if not bedtime_normal:
        schedule_notes.append("入睡时段偏离常见作息窗口")
    if not wake_normal:
        schedule_notes.append("起床时段偏离常见作息窗口")

    if not schedule_notes:
        schedule_status = "normal"
        schedule_notes.append("入睡和起床时段较规律")
    elif not bedtime_normal and not wake_normal:
        schedule_status = "irregular"
    elif not bedtime_normal:
        schedule_status = "late"
    else:
        schedule_status = "early"

    return {
        "duration_hours": duration,
        "duration_status": duration_status,
        "schedule_status": schedule_status,
        "assessment": [f"睡眠时长{duration_text}", *schedule_notes],
    }


def find_open_sleep_start(events: list[dict[str, Any]], user_id: str) -> dict[str, Any] | None:
    sessions = {
        event.get("start_event_id")
        for event in events
        if event.get("user_id") == user_id and event.get("type") == "sleep_session"
    }
    starts = [
        event
        for event in events
        if event.get("user_id") == user_id
        and event.get("type") == "sleep_start"
        and event.get("event_id") not in sessions
    ]
    return starts[-1] if starts else None


def record_sleep_start(args: argparse.Namespace, now: datetime) -> dict[str, Any]:
    parsed_time = parse_event_time(args.text, now, args.timezone)
    event = event_base(
        args.user,
        "sleep_start",
        parsed_time.value,
        args.timezone,
        args.text,
        parsed_time.source,
    )
    append_event(Path(args.store), event)
    return {
        "recorded": event,
        "reply": f"已记录：入睡时间 {parsed_time.value.strftime('%Y-%m-%d %H:%M')}。等待起床记录后计算睡眠时长。",
    }


def record_sleep_end(args: argparse.Namespace, now: datetime) -> dict[str, Any]:
    store = Path(args.store)
    events = load_events(store)
    open_start = find_open_sleep_start(events, args.user)
    if open_start is None:
        return {
            "status": "needs_sleep_start",
            "reply": "没有找到未闭合的入睡记录。请补充入睡时间，例如：昨晚23:30睡的。",
        }

    parsed_time = parse_event_time(args.text, now, args.timezone)
    start_at = datetime.fromisoformat(open_start["timestamp"])
    end_at = parsed_time.value
    sleep_result = evaluate_sleep(start_at, end_at)
    event = event_base(
        args.user,
        "sleep_session",
        end_at,
        args.timezone,
        args.text,
        parsed_time.source,
    )
    event.update(
        {
            "start_event_id": open_start["event_id"],
            "start_at": start_at.isoformat(),
            "end_at": end_at.isoformat(),
            **sleep_result,
        }
    )
    append_event(store, event)
    assessment = "；".join(sleep_result["assessment"])
    return {
        "recorded": event,
        "reply": (
            f"已记录：睡眠 {start_at.strftime('%H:%M')}-{end_at.strftime('%H:%M')}，"
            f"共 {sleep_result['duration_hours']} 小时。\n\n评估：{assessment}。"
        ),
    }


def amount_from_window(window: str, default_portion_g: float) -> tuple[float, str, bool]:
    amount_match = re.search(
        r"(?P<number>\d+(?:\.\d+)?|半|一|二|两|三|四|五|六|七|八|九|十)\s*"
        r"(?P<unit>千克|公斤|kg|克|g|斤|两|毫升|ml|mL|个|根|份|碗|杯)",
        window,
    )
    if not amount_match:
        return float(default_portion_g), "default_portion", True

    value = parse_number(amount_match.group("number"))
    unit = amount_match.group("unit")
    if unit in {"千克", "公斤", "kg"}:
        return value * 1000, "explicit", False
    if unit in {"克", "g", "毫升", "ml", "mL"}:
        return value, "explicit", False
    if unit == "斤":
        return value * 500, "explicit", False
    if unit == "两":
        return value * 50, "explicit", False
    return value * float(default_portion_g), "explicit_portion_count", True


def scale_nutrients(food: dict[str, Any], amount_g: float) -> dict[str, float]:
    nutrients = food["nutrients_per_100g"]
    return {key: round(value * amount_g / 100, 2) for key, value in nutrients.items()}


def parse_food_items(text: str, foods: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matches: list[tuple[int, int, dict[str, Any], str]] = []
    occupied: list[range] = []
    alias_rows: list[tuple[str, dict[str, Any]]] = []
    for food in foods:
        for alias in food["aliases"]:
            alias_rows.append((alias, food))

    for alias, food in sorted(alias_rows, key=lambda row: len(row[0]), reverse=True):
        for match in re.finditer(re.escape(alias), text, re.IGNORECASE):
            span = range(match.start(), match.end())
            if any(set(span).intersection(existing) for existing in occupied):
                continue
            matches.append((match.start(), match.end(), food, alias))
            occupied.append(span)

    items: list[dict[str, Any]] = []
    seen_foods: set[str] = set()
    for start, end, food, _alias in sorted(matches):
        if food["id"] in seen_foods:
            continue
        seen_foods.add(food["id"])
        window = text[max(0, start - 12) : min(len(text), end + 12)]
        amount_g, amount_source, estimated = amount_from_window(
            window, float(food["default_portion_g"])
        )
        items.append(
            {
                "food_id": food["id"],
                "display_name": food["display_name"],
                "amount_g": round(amount_g, 1),
                "amount_source": amount_source,
                "estimated": estimated,
                "category": food["category"],
                "nutrients": scale_nutrients(food, amount_g),
            }
        )
    return items


def meal_from_text(text: str) -> str:
    if any(token in text for token in ["早餐", "早饭", "早上"]):
        return "breakfast"
    if any(token in text for token in ["午餐", "午饭", "中午"]):
        return "lunch"
    if any(token in text for token in ["晚餐", "晚饭", "晚上"]):
        return "dinner"
    if any(token in text for token in ["加餐", "零食", "宵夜"]):
        return "snack"
    return "unknown"


def record_food(args: argparse.Namespace, now: datetime) -> dict[str, Any]:
    foods = load_foods()
    items = parse_food_items(args.text, foods)
    if not items:
        return {
            "status": "unknown_food",
            "reply": "没有在内置种子库中匹配到食物。请补充食物名称和重量，服务端应进入营养数据库解析流程。",
        }

    event = event_base(args.user, "food_intake", now, args.timezone, args.text, "implicit_now")
    totals = sum_food_nutrients(items)
    event.update({"meal": meal_from_text(args.text), "items": items, "totals": totals})
    append_event(Path(args.store), event)

    fruit_g = sum(item["amount_g"] for item in items if item["category"] == "fruit")
    veg_g = sum(item["amount_g"] for item in items if item["category"] == "vegetable")
    estimates = [item["display_name"] for item in items if item["estimated"]]
    summary = "、".join(f"{item['display_name']} {item['amount_g']:g}g" for item in items)
    assessment_parts = [f"本次约 {totals.get('energy_kcal', 0):g} kcal"]
    if fruit_g:
        assessment_parts.append(evaluate_daily_range("水果", fruit_g, 200, 350))
    if veg_g:
        assessment_parts.append(evaluate_minimum("蔬菜", veg_g, 300))
    if estimates:
        assessment_parts.append(f"{'、'.join(estimates)}使用默认份量估算")

    return {
        "recorded": event,
        "reply": f"已记录：{summary}。\n\n评估：{'；'.join(assessment_parts)}。",
    }


def sum_food_nutrients(items: list[dict[str, Any]]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for item in items:
        for key, value in item["nutrients"].items():
            totals[key] = round(totals.get(key, 0) + value, 2)
    return totals


def evaluate_daily_range(name: str, amount_g: float, low: float, high: float) -> str:
    if low <= amount_g <= high:
        return f"{name}已在每日参考范围 {low:g}-{high:g}g 内"
    if amount_g < low:
        return f"{name}已记录 {amount_g:g}g，距离每日参考下限还差约 {low - amount_g:g}g"
    return f"{name}已记录 {amount_g:g}g，高于每日参考上限 {high:g}g"


def evaluate_minimum(name: str, amount_g: float, minimum: float) -> str:
    if amount_g >= minimum:
        return f"{name}已达到每日参考量 {minimum:g}g"
    return f"{name}已记录 {amount_g:g}g，距离每日参考量还差约 {minimum - amount_g:g}g"


def parse_duration_minutes(text: str) -> float | None:
    match = re.search(
        r"(?P<number>\d+(?:\.\d+)?|半|一|二|两|三|四|五|六|七|八|九|十)\s*"
        r"(?P<unit>小时|钟头|h|分钟|分|min|m)",
        text,
    )
    if not match:
        return None
    value = parse_number(match.group("number"))
    if match.group("unit") in {"小时", "钟头", "h"}:
        return value * 60
    return value


def parse_exercise(text: str) -> dict[str, Any] | None:
    matched = None
    activity_label = "运动"
    for alias, data in sorted(EXERCISE_ALIASES.items(), key=lambda row: len(row[0]), reverse=True):
        if alias in text:
            matched = data
            activity_label = alias
            break
    if matched is None and any(token in text for token in ["运动", "锻炼", "训练"]):
        matched = ("exercise", "unknown", False)
    if matched is None:
        return None

    activity, intensity, strength = matched
    if any(token in text for token in ["高强度", "剧烈"]):
        intensity = "vigorous"
    elif any(token in text for token in ["中等强度", "适中"]):
        intensity = "moderate"

    duration = parse_duration_minutes(text)
    if duration is None:
        return {
            "activity": activity,
            "activity_label": activity_label,
            "intensity": intensity,
            "strength_training": strength,
            "needs_duration": True,
        }

    if intensity == "vigorous":
        moderate_equivalent = duration * 2
    elif intensity in {"moderate", "strength"}:
        moderate_equivalent = duration
    else:
        moderate_equivalent = 0

    return {
        "activity": activity,
        "activity_label": activity_label,
        "duration_minutes": round(duration, 1),
        "intensity": intensity,
        "moderate_equivalent_minutes": round(moderate_equivalent, 1),
        "strength_training": strength,
    }


def record_exercise(args: argparse.Namespace, now: datetime) -> dict[str, Any]:
    parsed = parse_exercise(args.text)
    if parsed is None:
        return {"status": "unknown_exercise", "reply": "没有识别到运动记录。"}
    if parsed.get("needs_duration"):
        return {
            "status": "needs_duration",
            "reply": "已识别运动类型，但缺少时长。请补充例如：跑步30分钟。",
        }

    event = event_base(args.user, "exercise", now, args.timezone, args.text, "implicit_now")
    event.update(parsed)
    append_event(Path(args.store), event)

    target_note = "本周可累计到 150 分钟中等强度等效目标"
    if parsed["intensity"] == "vigorous":
        target_note = "按等效规则计入较高强度运动，本周目标可按 75 分钟高强度或等效组合评估"
    if parsed["strength_training"]:
        target_note = "已计入力量训练天数，本周目标为 2 天及以上"

    return {
        "recorded": event,
        "reply": (
            f"已记录：{parsed['activity_label']} {parsed['duration_minutes']:g} 分钟。"
            f"\n\n评估：中等强度等效 {parsed['moderate_equivalent_minutes']:g} 分钟，{target_note}。"
        ),
    }


def record(args: argparse.Namespace) -> dict[str, Any]:
    now = parse_now(args.now, args.timezone)
    if is_sleep_end(args.text):
        return record_sleep_end(args, now)
    if is_sleep_start(args.text):
        return record_sleep_start(args, now)
    exercise = parse_exercise(args.text)
    if exercise is not None:
        return record_exercise(args, now)
    return record_food(args, now)


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def week_start_from_args(args: argparse.Namespace) -> date:
    if args.week_start:
        return date.fromisoformat(args.week_start)
    now = parse_now(args.now, args.timezone)
    return now.date() - timedelta(days=now.weekday())


def in_range(event: dict[str, Any], start: datetime, end: datetime) -> bool:
    timestamp = parse_dt(event["timestamp"])
    return start <= timestamp < end


def weekly(args: argparse.Namespace) -> str:
    tz = ZoneInfo(args.timezone)
    start_date = week_start_from_args(args)
    start = datetime.combine(start_date, time.min, tzinfo=tz)
    end = start + timedelta(days=7)
    events = [
        event
        for event in load_events(Path(args.store))
        if event.get("user_id") == args.user and in_range(event, start, end)
    ]

    fruit_g = sum(
        item["amount_g"]
        for event in events
        if event.get("type") == "food_intake"
        for item in event.get("items", [])
        if item.get("category") == "fruit"
    )
    moderate_minutes = sum(
        event.get("moderate_equivalent_minutes", 0)
        for event in events
        if event.get("type") == "exercise"
    )
    strength_days = {
        parse_dt(event["timestamp"]).date()
        for event in events
        if event.get("type") == "exercise" and event.get("strength_training")
    }

    return "\n".join(
        [
            "本周健康目标：",
            "",
            "| 模块 | 建议目标 | 当前进度 |",
            "| --- | ---: | ---: |",
            f"| 水果 | 1400-2450g | {fruit_g:g}g |",
            f"| 中等强度运动 | >=150分钟 | {moderate_minutes:g}分钟 |",
            f"| 抗阻/力量训练 | >=2天 | {len(strength_days)}天 |",
            "",
            f"周期：{start_date.isoformat()} 至 {(end.date() - timedelta(days=1)).isoformat()}。",
            DISCLAIMER,
        ]
    )


def month_range(month: str, timezone: str) -> tuple[datetime, datetime]:
    year, month_number = [int(part) for part in month.split("-")]
    tz = ZoneInfo(timezone)
    start = datetime(year, month_number, 1, tzinfo=tz)
    if month_number == 12:
        end = datetime(year + 1, 1, 1, tzinfo=tz)
    else:
        end = datetime(year, month_number + 1, 1, tzinfo=tz)
    return start, end


def monthly(args: argparse.Namespace) -> str:
    start, end = month_range(args.month, args.timezone)
    events = [
        event
        for event in load_events(Path(args.store))
        if event.get("user_id") == args.user and in_range(event, start, end)
    ]
    sleep_events = [event for event in events if event.get("type") == "sleep_session"]
    food_events = [event for event in events if event.get("type") == "food_intake"]
    exercise_events = [event for event in events if event.get("type") == "exercise"]

    lines = [f"# {args.month} 健康评估表", "", f"数据覆盖：共 {len(events)} 条结构化记录。", ""]

    if sleep_events:
        avg_sleep = sum(event["duration_hours"] for event in sleep_events) / len(sleep_events)
        target_days = sum(1 for event in sleep_events if event["duration_status"] == "target")
        late_count = sum(1 for event in sleep_events if event["schedule_status"] in {"late", "irregular"})
        lines.extend(
            [
                "## 睡眠",
                "",
                "| 指标 | 结果 |",
                "| --- | ---: |",
                f"| 记录天数 | {len(sleep_events)} |",
                f"| 平均时长 | {avg_sleep:.1f} 小时 |",
                f"| 达标天数 | {target_days} |",
                f"| 偏晚或不规律次数 | {late_count} |",
                "",
                f"结论：{target_days}/{len(sleep_events)} 天睡眠时长在成人常见建议范围内。",
                "",
            ]
        )

    if food_events:
        all_items = [item for event in food_events for item in event.get("items", [])]
        fruit_g = sum(item["amount_g"] for item in all_items if item.get("category") == "fruit")
        veg_g = sum(item["amount_g"] for item in all_items if item.get("category") == "vegetable")
        energy = sum(event.get("totals", {}).get("energy_kcal", 0) for event in food_events)
        estimated_count = sum(1 for item in all_items if item.get("estimated"))
        estimated_ratio = estimated_count / len(all_items) if all_items else 0
        record_days = {parse_dt(event["timestamp"]).date() for event in food_events}
        avg_energy = energy / len(record_days) if record_days else 0
        lines.extend(
            [
                "## 饮食",
                "",
                "| 指标 | 结果 |",
                "| --- | ---: |",
                f"| 水果总量 | {fruit_g:g} g |",
                f"| 蔬菜总量 | {veg_g:g} g |",
                f"| 记录日均能量 | {avg_energy:.0f} kcal |",
                f"| 估算记录比例 | {estimated_ratio:.0%} |",
                "",
                "结论：仅对已记录食物评估；包装食品、调味料和未知菜品需要补充标签或重量。",
                "",
            ]
        )

    if exercise_events:
        moderate_minutes = sum(event.get("moderate_equivalent_minutes", 0) for event in exercise_events)
        exercise_days = {parse_dt(event["timestamp"]).date() for event in exercise_events}
        strength_days = {
            parse_dt(event["timestamp"]).date()
            for event in exercise_events
            if event.get("strength_training")
        }
        lines.extend(
            [
                "## 运动",
                "",
                "| 指标 | 结果 |",
                "| --- | ---: |",
                f"| 中等强度等效总量 | {moderate_minutes:g} 分钟 |",
                f"| 运动天数 | {len(exercise_days)} |",
                f"| 力量训练天数 | {len(strength_days)} |",
                "",
                "结论：按周评估运动目标；月度结果用于观察持续性。",
                "",
            ]
        )

    lines.append(DISCLAIMER)
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reference health assessment recorder")
    subparsers = parser.add_subparsers(dest="command", required=True)

    record_parser = subparsers.add_parser("record")
    record_parser.add_argument("--user", required=True)
    record_parser.add_argument("--text", required=True)
    record_parser.add_argument("--store", required=True)
    record_parser.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    record_parser.add_argument("--now")

    weekly_parser = subparsers.add_parser("weekly")
    weekly_parser.add_argument("--user", required=True)
    weekly_parser.add_argument("--store", required=True)
    weekly_parser.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    weekly_parser.add_argument("--week-start")
    weekly_parser.add_argument("--now")

    monthly_parser = subparsers.add_parser("monthly")
    monthly_parser.add_argument("--user", required=True)
    monthly_parser.add_argument("--store", required=True)
    monthly_parser.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    monthly_parser.add_argument("--month", required=True)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "record":
        print(json.dumps(record(args), ensure_ascii=False, indent=2, sort_keys=True))
    elif args.command == "weekly":
        print(weekly(args))
    elif args.command == "monthly":
        print(monthly(args))
    else:
        parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
