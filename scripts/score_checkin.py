"""Deterministic scorer for the personal-development health skill.

The model must not recompute these points. Run this script and report its JSON.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date, datetime
from typing import Any

REQUIRED_PROFILE = (
    "height_cm",
    "weight_kg",
    "age",
    "sex",
    "training_years",
    "injury",
)
RED_FLAGS = ("胸痛", "昏厥", "自伤", "自行停药", "急性剧痛")
EXTENDED_RED_FLAGS = ("呼吸困难", "异常心悸", "晕厥", "轻生", "骨裂", "关节急性肿胀")
ALL_RED_FLAGS = RED_FLAGS + EXTENDED_RED_FLAGS
NEGATION_MARKS = ("没有", "无", "否认", "未出现", "未诉")
TEXT_FIELDS = ("raw_text", "text", "note")
VALID_CLASSIFICATION = {"kept_and_changed", "discarded_insult"}
OPTIONAL_ALIASES = {
    "sleep_quality": "睡眠时长",
    "anti_inflammatory_diet": "饮食质量",
    "hydration": "总饮水量",
    "cardio_activity": "日常步数",
    "load_recovery": "恢复干预",
    "vital_signs": "基础机能",
    "emotional_stability": "情绪波动",
    "stress_relief": "日常压力",
    "focus_state": "注意力",
    "self_care": "自我照顾",
}
GAP_LABELS = {
    "蛋白质": "protein_g (今日蛋白质摄入克数)",
    "抗阻": "resistance_done (今日抗阻训练情况)",
    "超负荷": "progressive_overload (是否实现渐进超负荷)",
    "黄毛自评分": "self_rating_1_to_5 (今日执行力/心理状态 1-5 自评)",
    "评价分类": "feedback_category (外界评价处理分类)",
}
BODY_SHARE = 80.0 / 3.0
PSYCH_PART = 40.0
OPTIONAL_POOL = 20.0

BODY_OPTIONAL = (
    "睡眠时长",
    "作息节律",
    "睡眠深度",
    "睡前行为",
    "结构均衡",
    "三餐规律",
    "饮食质量",
    "进食习惯",
    "总饮水量",
    "饮水节奏",
    "饮品结构",
    "有氧运动",
    "户外日照",
    "柔韧拉伸",
    "运动过载",
    "疾病伤痛",
    "生理透支",
    "恢复干预",
    "久坐时长",
    "日常步数",
    "体态习惯",
    "动作模式",
    "体重/BMI",
    "排便规律",
    "基础机能",
    "小症状频次",
    "口腔卫生",
    "用眼卫生",
    "个人卫生",
    "健康管理",
)
PSYCH_OPTIONAL = (
    "情绪波动",
    "负面情绪持续",
    "情绪表达",
    "情绪底色",
    "日常压力",
    "躯体化表现",
    "耗竭感",
    "压力叠加",
    "挫折应对",
    "心态弹性",
    "归因方式",
    "恢复速度",
    "人际互动",
    "支持系统",
    "关系质量",
    "归属感",
    "日常满意度",
    "目标感",
    "自我接纳",
    "掌控感",
    "注意力",
    "记忆力",
    "思维清晰度",
    "杂念水平",
    "放松时间",
    "自我照顾",
    "兴趣滋养",
    "边界感",
)


def parse_day(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def r2(value: float) -> float:
    return round(value + 0.0, 2)


def likert_ratio(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value < 1 or value > 5:
        return None
    return float(value) / 5.0


def protein_target(profile: dict[str, Any]) -> tuple[float, str]:
    weight = float(profile["weight_kg"])
    targets = profile.get("targets") or {}
    grams_per_kg = float(targets.get("protein_g_per_kg", 1.6))
    source = str(targets.get("protein_source", "literature_default_1.6_within_1.4_2.0"))
    return weight * grams_per_kg, source


def resistance_per_7d(profile: dict[str, Any]) -> float:
    targets = profile.get("targets") or {}
    return float(targets.get("resistance_sessions_per_7d", 3))


def session_protein_ratio(session: dict[str, Any], target_g: float) -> tuple[float | None, str]:
    body = session.get("body_required") or {}
    if body.get("protein_g") is not None:
        grams = float(body["protein_g"])
        ratio = 1.0 if target_g <= 0 else min(1.0, grams / target_g)
        return ratio, "number"
    if body.get("protein_ratio") is not None:
        return min(1.0, max(0.0, float(body["protein_ratio"]))), "ratio"
    ratio = likert_ratio(body.get("protein_likert"))
    if ratio is None:
        return None, "missing"
    return ratio, "likert"


def session_has_resistance(session: dict[str, Any]) -> tuple[bool, str]:
    body = session.get("body_required") or {}
    sets = body.get("resistance_sets")
    load = body.get("resistance_load_kg")
    if sets is not None and load is not None:
        return True, "number"
    if likert_ratio(body.get("resistance_likert")) is not None:
        return True, "likert"
    if body.get("resistance_done") is True:
        return True, "done"
    minutes = body.get("resistance_minutes")
    if isinstance(minutes, (int, float)) and not isinstance(minutes, bool) and float(minutes) > 0:
        return True, "minutes"
    return False, "missing"


def overload_value(body: dict[str, Any]) -> float | None:
    if isinstance(body.get("overload"), bool):
        return 1.0 if body["overload"] else 0.0
    if isinstance(body.get("progressive_overload"), bool):
        return 1.0 if body["progressive_overload"] else 0.0
    if isinstance(body.get("progressive_overload"), (int, float)) and not isinstance(body.get("progressive_overload"), bool):
        return min(1.0, max(0.0, float(body["progressive_overload"])))
    likert = likert_ratio(body.get("overload_likert"))
    if likert is not None:
        return float(likert)
    return None


def overload_observations(sessions: list[dict[str, Any]]) -> list[float]:
    ratios: list[float] = []
    previous_load: float | None = None
    for session in sessions:
        body = session.get("body_required") or {}
        observed = overload_value(body)
        if observed is not None:
            ratios.append(observed)
        elif body.get("resistance_load_kg") is not None and previous_load is not None:
            current = float(body["resistance_load_kg"])
            ratios.append(1.0 if current > previous_load else 0.0)
        if body.get("resistance_load_kg") is not None:
            previous_load = float(body["resistance_load_kg"])
    return ratios


def optional_ratio(key: str, raw: Any) -> float | None:
    if isinstance(raw, dict):
        if raw.get("likert") is not None:
            return likert_ratio(raw.get("likert"))
        if raw.get("actual") is not None and raw.get("target") not in (None, 0):
            return min(1.0, float(raw["actual"]) / float(raw["target"]))
        if key == "睡眠时长" and raw.get("hours") is not None:
            hours = float(raw["hours"])
            return 1.0 if hours >= 7 else max(0.0, hours / 7.0)
        return None
    if key == "睡眠时长" and isinstance(raw, (int, float)) and not isinstance(raw, bool) and raw > 5:
        hours = float(raw)
        return 1.0 if hours >= 7 else max(0.0, hours / 7.0)
    return likert_ratio(raw)


def mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def missing_profile(profile: dict[str, Any]) -> list[str]:
    missing = []
    for key in REQUIRED_PROFILE:
        if key not in profile or profile[key] is None or profile[key] == "":
            missing.append(key)
    return missing


def in_window(day: date, window: dict[str, Any] | None) -> bool:
    if not window:
        return True
    if window.get("start") and day < parse_day(window["start"]):
        return False
    if window.get("end") and day > parse_day(window["end"]):
        return False
    return True


def keyword_is_asserted(text: str, keyword: str) -> bool:
    start = 0
    while True:
        index = text.find(keyword, start)
        if index < 0:
            return False
        prefix = text[max(0, index - 3) : index]
        if any(prefix.endswith(mark) for mark in NEGATION_MARKS):
            start = index + len(keyword)
            continue
        return True


def collect_red_flag_details(sessions: list[dict[str, Any]]) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for session in sessions:
        day = str(session.get("date", "unknown"))
        for flag in session.get("red_flags") or []:
            flag_text = str(flag).strip()
            if flag_text in ALL_RED_FLAGS and (day, flag_text) not in seen:
                seen.add((day, flag_text))
                found.append({"date": day, "flag": flag_text, "source": "explicit"})
        blobs = [str(session.get(field) or "") for field in TEXT_FIELDS]
        combined = " ".join(part for part in blobs if part.strip())
        if not combined.strip():
            continue
        for keyword in ALL_RED_FLAGS:
            if keyword_is_asserted(combined, keyword) and (day, keyword) not in seen:
                seen.add((day, keyword))
                found.append({"date": day, "flag": keyword, "source": "text_scan"})
    return found


def collect_red_flags(sessions: list[dict[str, Any]]) -> list[str]:
    flags: list[str] = []
    for item in collect_red_flag_details(sessions):
        if item["flag"] not in flags:
            flags.append(item["flag"])
    return flags


def compute_calendar_span(
    sessions: list[dict[str, Any]],
    window: dict[str, Any] | None = None,
) -> tuple[int, int]:
    parsed: list[date] = []
    raw_days: set[str] = set()
    for item in sessions:
        raw = str(item.get("date", "")).strip()[:10]
        if not raw:
            continue
        raw_days.add(raw)
        parsed.append(parse_day(raw))
    distinct = len(raw_days)
    if not parsed:
        return distinct, max(distinct, 1)
    earliest = min(parsed)
    latest = max(parsed)
    if window:
        if window.get("start"):
            window_start = parse_day(str(window["start"])[:10])
            if window_start < earliest:
                earliest = window_start
        if window.get("end"):
            window_end = parse_day(str(window["end"])[:10])
            if window_end > latest:
                latest = window_end
    span = max((latest - earliest).days + 1, distinct, 1)
    return distinct, span


def alias_optional_value(canonical: str, raw: Any) -> Any:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return raw
    number = float(raw)
    if canonical == "睡眠时长" and 0 <= number <= 1:
        return {"hours": number * 7.0}
    if 0 <= number <= 1:
        return {"actual": number, "target": 1}
    return raw


def normalize_session(session: dict[str, Any]) -> dict[str, Any]:
    item = dict(session)
    if item.get("date"):
        item["date"] = str(item["date"]).strip()[:10]
    body = dict(item.get("body_required") or {})
    if "overload" not in body and "progressive_overload" in body:
        body["overload"] = body["progressive_overload"]
    item["body_required"] = body
    psych = dict(item.get("psych_required") or {})
    if psych.get("execution_likert") is None:
        if psych.get("self_rating_1_to_5") is not None:
            psych["execution_likert"] = psych["self_rating_1_to_5"]
        elif psych.get("likert") is not None:
            psych["execution_likert"] = psych["likert"]
    if not psych.get("classification") and psych.get("feedback_category"):
        psych["classification"] = psych["feedback_category"]
    item["psych_required"] = psych
    optional = dict(item.get("optional") or {})
    for side in ("body_optional", "psych_optional"):
        extra = item.get(side) or {}
        if isinstance(extra, dict):
            for key, value in extra.items():
                if key not in optional and value is not None:
                    optional[key] = value
    for alias, canonical in OPTIONAL_ALIASES.items():
        if alias not in optional or optional[alias] is None:
            continue
        if optional.get(canonical) is None:
            optional[canonical] = alias_optional_value(canonical, optional[alias])
    item["optional"] = optional
    return item


def execution_ratio(psych: dict[str, Any]) -> float | None:
    for key in ("execution_likert", "self_rating_1_to_5", "likert"):
        ratio = likert_ratio(psych.get(key))
        if ratio is not None:
            return ratio
    return None


def inspect_daily_gaps(
    sessions: list[dict[str, Any]],
    target_date: str | None = None,
) -> dict[str, Any]:
    normalized = [normalize_session(item) for item in sessions]
    if not target_date:
        dated = [str(item.get("date")) for item in normalized if item.get("date")]
        target_date = max(dated) if dated else ""
    day_sessions = [item for item in normalized if item.get("date") == target_date]
    gaps = required_gaps(day_sessions, 1.0)
    recorded: list[str] = []
    for item in day_sessions:
        for key, value in (item.get("optional") or {}).items():
            if value is not None and key not in OPTIONAL_ALIASES and key not in recorded:
                recorded.append(key)
    return {
        "target_date": target_date,
        "required_completion_ratio": r2((5 - len(gaps)) / 5.0),
        "missing_required_fields": [GAP_LABELS[gap] for gap in gaps],
        "recorded_optional_fields": recorded,
    }


def required_gaps(sessions: list[dict[str, Any]], target_g: float) -> list[str]:
    gaps = []
    if not any(session_protein_ratio(item, target_g)[0] is not None for item in sessions):
        gaps.append("蛋白质")
    if not any(session_has_resistance(item)[0] for item in sessions):
        gaps.append("抗阻")
    if not overload_observations(sessions):
        gaps.append("超负荷")
    if not any(execution_ratio(item.get("psych_required") or {}) is not None for item in sessions):
        gaps.append("黄毛自评分")
    if not any(
        (item.get("psych_required") or {}).get("classification")
        or (item.get("psych_required") or {}).get("feedback_category")
        for item in sessions
    ):
        gaps.append("评价分类")
    return gaps


def score_optional(sessions: list[dict[str, Any]], keys: tuple[str, ...]) -> dict[str, Any]:
    # 写过的小项平分 20。单项封顶会让「每侧只有一个选填」的 200 分验收失效，所以这里不封顶。
    grouped: dict[str, list[float]] = defaultdict(list)
    for session in sessions:
        optional = session.get("optional") or {}
        for key in keys:
            if key not in optional:
                continue
            ratio = optional_ratio(key, optional[key])
            if ratio is not None:
                grouped[key].append(ratio)
    if not grouped:
        return {"status": "无法评分", "score": None, "items": []}
    share = OPTIONAL_POOL / len(grouped)
    items = []
    total = 0.0
    for key in keys:
        if key not in grouped:
            continue
        ratio = mean(grouped[key]) or 0.0
        points = ratio * share
        total += points
        items.append({"item": key, "mean_ratio": r2(ratio), "points": r2(points)})
    return {"status": "scored", "score": r2(total), "items": items}


def score_body_required(
    sessions: list[dict[str, Any]],
    profile: dict[str, Any],
    calendar_span_days: int | None = None,
) -> dict[str, Any]:
    target_g, source = protein_target(profile)
    protein = [session_protein_ratio(item, target_g)[0] for item in sessions]
    protein = [item for item in protein if item is not None]
    resistance_days = sum(1 for item in sessions if session_has_resistance(item)[0])
    if calendar_span_days is None:
        _distinct, calendar_span_days = compute_calendar_span(sessions)
    expected = resistance_per_7d(profile) * (calendar_span_days / 7.0)
    overload = overload_observations(sessions)
    parts = {
        "蛋白质": None if not protein else mean(protein),
        "抗阻": None if resistance_days == 0 or expected <= 0 else min(1.0, resistance_days / expected),
        "超负荷": None if not overload else mean(overload),
    }
    if any(value is None for value in parts.values()):
        return {
            "status": "无法评分",
            "score": None,
            "target_protein_g": r2(target_g),
            "protein_source": source,
            "parts": {key: None if value is None else r2(value) for key, value in parts.items()},
        }
    raw_points = {key: (value or 0.0) * BODY_SHARE for key, value in parts.items()}
    return {
        "status": "scored",
        "score": r2(sum(raw_points.values())),
        "target_protein_g": r2(target_g),
        "protein_source": source,
        "parts": {key: r2(value or 0.0) for key, value in parts.items()},
        "points": {key: r2(value) for key, value in raw_points.items()},
    }


def score_psych_required(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    ratings = []
    classes = []
    for session in sessions:
        psych = session.get("psych_required") or {}
        ratio = execution_ratio(psych)
        if ratio is not None:
            ratings.append(ratio)
        label = psych.get("classification") or psych.get("feedback_category")
        if label in VALID_CLASSIFICATION:
            classes.append(1.0)
        elif label == "invalid":
            classes.append(0.0)
    if not ratings or not classes:
        return {"status": "无法评分", "score": None, "execution": None, "classification": None}
    execution = mean(ratings) or 0.0
    classification = mean(classes) or 0.0
    points = {"自评分": r2(execution * PSYCH_PART), "评价分类": r2(classification * PSYCH_PART)}
    return {
        "status": "scored",
        "score": r2(sum(points.values())),
        "execution": r2(execution),
        "classification": r2(classification),
        "points": points,
    }


def combine(required: dict[str, Any], optional: dict[str, Any]) -> dict[str, Any]:
    if required["status"] != "scored" or optional["status"] != "scored":
        return {"status": "不合成", "score": None}
    return {"status": "scored", "score": r2(required["score"] + optional["score"])}


def next_steps(mode: str, gaps: list[str], body: dict[str, Any], psych: dict[str, Any]) -> list[str]:
    if mode == "redflag":
        return ["先按红旗处理：就医或当地紧急帮助。本轮不打分，不给训练建议。"]
    if mode == "blocked_profile":
        return ["补齐建库字段后再记。缺的字段不能估算。"]
    steps: list[str] = []
    if mode == "under7":
        steps.append("继续记到满 7 个不同日期。")
        if gaps:
            steps.append("补上缺的必填：" + "、".join(gaps) + "。")
        return steps[:2]
    if gaps:
        steps.append("补上缺的必填：" + "、".join(gaps) + "。")
    if body.get("status") == "scored" and psych.get("status") == "scored":
        protein_ratio = (body.get("parts") or {}).get("蛋白质")
        if isinstance(protein_ratio, (int, float)) and protein_ratio < 1:
            steps.append(
                "下一次把蛋白质记到克数，并对照本人目标 "
                + str(body.get("target_protein_g"))
                + " 克。这是记录目标，不是处方。"
            )
        elif (psych.get("execution") or 1) < 1:
            steps.append("下一次打卡写明 1–5 自评分，并给评价分类一个结果。")
        else:
            steps.append("保持必填三项和评价分类连续记录，满窗后再看选填。")
    return steps[:3]


def conclusion(body: dict[str, Any], psych: dict[str, Any]) -> dict[str, str]:
    protein = (body.get("parts") or {}).get("蛋白质")
    resistance = (body.get("parts") or {}).get("抗阻")
    overload = (body.get("parts") or {}).get("超负荷")
    if body.get("status") != "scored":
        bomi = "薄肌：蛋白质、抗阻或超负荷还有缺口，这一窗不把身体必填合成。"
    else:
        bomi = (
            "薄肌：蛋白质完成 "
            + str(protein)
            + "，抗阻完成 "
            + str(resistance)
            + "，超负荷完成 "
            + str(overload)
            + "。"
        )
    if psych.get("status") != "scored":
        huangmao = "黄毛：自评分或评价分类还有缺口，这一窗不把心理必填合成。"
    else:
        huangmao = (
            "黄毛：自评分比例 "
            + str(psych.get("execution"))
            + "，评价分类比例 "
            + str(psych.get("classification"))
            + "。可测量的评价应留下并改行为；人身攻击应丢弃。"
        )
    return {"薄肌": bomi, "黄毛": huangmao}


def score_payload(payload: dict[str, Any]) -> dict[str, Any]:
    profile = payload.get("profile") or {}
    missing = missing_profile(profile)
    if missing:
        result = {
            "mode": "blocked_profile",
            "missing_profile": missing,
            "scores": None,
            "next_steps": next_steps("blocked_profile", [], {}, {}),
        }
        return result
    window = payload.get("window")
    sessions = []
    for item in payload.get("sessions") or []:
        normalized = normalize_session(item)
        day = parse_day(normalized["date"])
        if in_window(day, window):
            sessions.append(normalized)
    sessions.sort(key=lambda item: item["date"])
    flag_details = collect_red_flag_details(sessions)
    flags = []
    for item in flag_details:
        if item["flag"] not in flags:
            flags.append(item["flag"])
    target_g, _source = protein_target(profile)
    gaps = required_gaps(sessions, target_g)
    dates = sorted({item["date"] for item in sessions})
    distinct_dates, calendar_span_days = compute_calendar_span(sessions, window)
    if flags:
        return {
            "mode": "redflag",
            "red_flags": flags,
            "red_flag_details": flag_details,
            "dates": dates,
            "distinct_dates": distinct_dates,
            "calendar_span_days": calendar_span_days,
            "scores": None,
            "next_steps": next_steps("redflag", gaps, {}, {}),
            "note": "有伤病只作档案备注，不在这里停分。停分只来自红旗。",
        }
    if len(dates) < 7:
        return {
            "mode": "under7",
            "distinct_dates": distinct_dates,
            "calendar_span_days": calendar_span_days,
            "dates": dates,
            "raw_sessions": [
                {
                    "date": item["date"],
                    "date_defaulted": bool(item.get("date_defaulted")),
                    "body_required": item.get("body_required") or {},
                    "psych_required": item.get("psych_required") or {},
                }
                for item in sessions
            ],
            "required_gaps": gaps,
            "daily_progress": inspect_daily_gaps(sessions, dates[-1] if dates else None),
            "scores": None,
            "label": "未满 7 天，不可统计分析",
            "next_steps": next_steps("under7", gaps, {}, {}),
        }
    body_required = score_body_required(sessions, profile, calendar_span_days)
    psych_required = score_psych_required(sessions)
    body_optional = score_optional(sessions, BODY_OPTIONAL)
    psych_optional = score_optional(sessions, PSYCH_OPTIONAL)
    body_total = combine(body_required, body_optional)
    psych_total = combine(psych_required, psych_optional)
    if body_total["status"] == "scored" and psych_total["status"] == "scored":
        total = {"status": "scored", "score": r2(body_total["score"] + psych_total["score"])}
    else:
        total = {"status": "不合成", "score": None}
    names = conclusion(body_required, psych_required)
    gap_keys = []
    if body_required["status"] != "scored":
        gap_keys.extend([key for key in ("蛋白质", "抗阻", "超负荷") if body_required["parts"][key] is None])
    if psych_required["status"] != "scored":
        if psych_required.get("execution") is None:
            gap_keys.append("黄毛自评分")
        if psych_required.get("classification") is None:
            gap_keys.append("评价分类")
    return {
        "mode": "scored",
        "distinct_dates": distinct_dates,
        "calendar_span_days": calendar_span_days,
        "dates": dates,
        "scores": {
            "body_required": body_required,
            "body_optional": body_optional,
            "body": body_total,
            "psych_required": psych_required,
            "psych_optional": psych_optional,
            "psych": psych_total,
            "total": total,
        },
        "conclusion": names,
        "next_steps": next_steps("scored", gap_keys, body_required, psych_required),
        "daily_progress": inspect_daily_gaps(sessions, dates[-1] if dates else None),
        "injury_note": "档案写了有伤病，只作备注，本轮不因此停分。" if profile.get("injury") else "",
    }


def evaluate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return score_payload(payload)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raw = sys.stdin.read() if len(sys.argv) == 1 else open(sys.argv[1], encoding="utf-8").read()
    payload = json.loads(raw)
    json.dump(score_payload(payload), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
