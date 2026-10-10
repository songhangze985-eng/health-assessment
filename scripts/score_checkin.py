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
VALID_CLASSIFICATION = {"kept_and_changed", "discarded_insult"}
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
    return False, "missing"


def overload_observations(sessions: list[dict[str, Any]]) -> list[float]:
    ratios: list[float] = []
    previous_load: float | None = None
    for session in sessions:
        body = session.get("body_required") or {}
        if isinstance(body.get("overload"), bool):
            ratios.append(1.0 if body["overload"] else 0.0)
        elif likert_ratio(body.get("overload_likert")) is not None:
            ratios.append(float(likert_ratio(body.get("overload_likert"))))
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


def collect_red_flags(sessions: list[dict[str, Any]]) -> list[str]:
    found: list[str] = []
    for session in sessions:
        for flag in session.get("red_flags") or []:
            if flag in RED_FLAGS and flag not in found:
                found.append(flag)
    return found


def required_gaps(sessions: list[dict[str, Any]], target_g: float) -> list[str]:
    gaps = []
    if not any(session_protein_ratio(item, target_g)[0] is not None for item in sessions):
        gaps.append("蛋白质")
    if not any(session_has_resistance(item)[0] for item in sessions):
        gaps.append("抗阻")
    if not overload_observations(sessions):
        gaps.append("超负荷")
    if not any(likert_ratio((item.get("psych_required") or {}).get("execution_likert")) is not None for item in sessions):
        gaps.append("黄毛自评分")
    if not any((item.get("psych_required") or {}).get("classification") for item in sessions):
        gaps.append("评价分类")
    return gaps


def score_optional(sessions: list[dict[str, Any]], keys: tuple[str, ...]) -> dict[str, Any]:
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


def score_body_required(sessions: list[dict[str, Any]], profile: dict[str, Any]) -> dict[str, Any]:
    target_g, source = protein_target(profile)
    protein = [session_protein_ratio(item, target_g)[0] for item in sessions]
    protein = [item for item in protein if item is not None]
    resistance_days = sum(1 for item in sessions if session_has_resistance(item)[0])
    span = max(len({item["date"] for item in sessions}), 1)
    expected = resistance_per_7d(profile) * (span / 7.0)
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
        ratio = likert_ratio(psych.get("execution_likert"))
        if ratio is not None:
            ratings.append(ratio)
        label = psych.get("classification")
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
    sessions = []
    for item in payload.get("sessions") or []:
        day = parse_day(item["date"])
        if in_window(day, payload.get("window")):
            sessions.append(item)
    sessions.sort(key=lambda item: item["date"])
    flags = collect_red_flags(sessions)
    target_g, _source = protein_target(profile)
    gaps = required_gaps(sessions, target_g)
    dates = sorted({item["date"] for item in sessions})
    if flags:
        return {
            "mode": "redflag",
            "red_flags": flags,
            "dates": dates,
            "distinct_dates": len(dates),
            "scores": None,
            "next_steps": next_steps("redflag", gaps, {}, {}),
            "note": "有伤病只作档案备注，不在这里停分。停分只来自红旗。",
        }
    if len(dates) < 7:
        return {
            "mode": "under7",
            "distinct_dates": len(dates),
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
            "scores": None,
            "label": "未满 7 天，不可统计分析",
            "next_steps": next_steps("under7", gaps, {}, {}),
        }
    body_required = score_body_required(sessions, profile)
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
        "distinct_dates": len(dates),
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
        "injury_note": "档案写了有伤病，只作备注，本轮不因此停分。" if profile.get("injury") else "",
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raw = sys.stdin.read() if len(sys.argv) == 1 else open(sys.argv[1], encoding="utf-8").read()
    payload = json.loads(raw)
    json.dump(score_payload(payload), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
