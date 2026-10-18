"""Acceptance checks for score_checkin.py. Stdlib only."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCORER = ROOT / "scripts" / "score_checkin.py"
FIXTURES = ROOT / "evals" / "fixtures"


def run(payload: dict) -> dict:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    completed = subprocess.run(
        [sys.executable, str(SCORER)],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
        env=env,
    )
    return json.loads(completed.stdout)


def profile(**overrides):
    base = {
        "codename": "fixture",
        "height_cm": 172,
        "weight_kg": 75,
        "age": 36,
        "sex": "male",
        "training_years": 0,
        "injury": False,
    }
    base.update(overrides)
    return base


def day(index: int, **overrides) -> dict:
    item = {
        "date": f"2026-10-{index:02d}",
        "date_defaulted": False,
        "red_flags": [],
        "body_required": {
            "protein_g": 120,
            "resistance_sets": 3,
            "resistance_load_kg": 40 + index,
            "overload": True,
        },
        "psych_required": {
            "execution_likert": 5,
            "classification": "kept_and_changed",
        },
        "optional": {"睡眠时长": 5, "边界感": 5},
    }
    item.update(overrides)
    return item


def test_full_window_totals_200() -> None:
    payload = {"profile": profile(), "sessions": [day(i) for i in range(1, 8)]}
    result = run(payload)
    assert result["mode"] == "scored", result
    assert result["scores"]["body"]["score"] == 100
    assert result["scores"]["psych"]["score"] == 100
    assert result["scores"]["total"]["score"] == 200
    assert "薄肌" in result["conclusion"]["薄肌"]
    assert "黄毛" in result["conclusion"]["黄毛"]
    assert len(result["next_steps"]) <= 3


def test_under_seven_has_no_score_and_two_steps_when_gap() -> None:
    sessions = [day(1), day(2), day(3)]
    for item in sessions:
        item["body_required"].pop("protein_g", None)
    payload = {"profile": profile(), "sessions": sessions}
    result = run(payload)
    assert result["mode"] == "under7"
    assert result["scores"] is None
    assert result["label"] == "未满 7 天，不可统计分析"
    assert result["next_steps"][0].startswith("继续记到满 7")
    assert "蛋白质" in result["next_steps"][1]
    assert "深蹲" not in " ".join(result["next_steps"])


def test_missing_required_does_not_zero() -> None:
    sessions = [day(i) for i in range(1, 8)]
    for item in sessions:
        item["body_required"].pop("protein_g")
    result = run({"profile": profile(), "sessions": sessions})
    assert result["scores"]["body_required"]["status"] == "无法评分"
    assert result["scores"]["body_required"]["score"] is None
    assert result["scores"]["body"]["status"] == "不合成"
    assert result["scores"]["total"]["status"] == "不合成"
    assert any("蛋白质" in step for step in result["next_steps"])


def test_red_flag_stops() -> None:
    sessions = [day(i) for i in range(1, 8)]
    sessions[0]["red_flags"] = ["胸痛"]
    result = run({"profile": profile(injury=True), "sessions": sessions})
    assert result["mode"] == "redflag"
    assert result["scores"] is None
    assert "就医" in result["next_steps"][0]
    assert "训练" in result["next_steps"][0]


def test_custom_protein_target_is_used() -> None:
    custom = profile(
        targets={
            "protein_g_per_kg": 3.0,
            "protein_source": "user_outside_literature",
        }
    )
    sessions = [day(i) for i in range(1, 8)]
    for item in sessions:
        item["body_required"]["protein_g"] = 150
    result = run({"profile": custom, "sessions": sessions})
    assert result["scores"]["body_required"]["target_protein_g"] == 225
    assert result["scores"]["body_required"]["parts"]["蛋白质"] == 0.67


def test_likert_fallback_marked_by_ratio() -> None:
    sessions = [day(i) for i in range(1, 8)]
    for item in sessions:
        item["body_required"].pop("protein_g")
        item["body_required"]["protein_likert"] = 5
    result = run({"profile": profile(), "sessions": sessions})
    assert result["scores"]["body_required"]["parts"]["蛋白质"] == 1


def test_invalid_classification_lowers_psych() -> None:
    sessions = [day(i) for i in range(1, 8)]
    for item in sessions:
        item["psych_required"]["classification"] = "invalid"
    result = run({"profile": profile(), "sessions": sessions})
    assert result["scores"]["psych_required"]["points"]["评价分类"] == 0
    assert result["scores"]["psych_required"]["points"]["自评分"] == 40


def test_blank_optional_is_not_zero() -> None:
    sessions = [day(i) for i in range(1, 8)]
    for item in sessions:
        item["optional"] = {}
    result = run({"profile": profile(), "sessions": sessions})
    assert result["scores"]["body_optional"]["status"] == "无法评分"
    assert result["scores"]["body_optional"]["score"] is None
    assert result["scores"]["total"]["status"] == "不合成"


def test_defaulted_date_counts_as_one_day() -> None:
    only = day(1, date_defaulted=True)
    result = run({"profile": profile(), "sessions": [only]})
    assert result["distinct_dates"] == 1
    assert result["raw_sessions"][0]["date_defaulted"] is True


def test_blocked_profile() -> None:
    incomplete = profile()
    del incomplete["height_cm"]
    result = run({"profile": incomplete, "sessions": [day(1)]})
    assert result["mode"] == "blocked_profile"
    assert "height_cm" in result["missing_profile"]


def test_injury_note_does_not_stop_score() -> None:
    result = run({"profile": profile(injury=True), "sessions": [day(i) for i in range(1, 8)]})
    assert result["mode"] == "scored"
    assert result["scores"]["total"]["score"] == 200
    assert "备注" in result["injury_note"]


def test_calendar_span_lowers_resistance_expectation() -> None:
    sessions = [day(index) for index in (1, 2, 3, 4, 5, 6, 19)]
    result = run({"profile": profile(), "sessions": sessions})
    assert result["mode"] == "scored", result
    assert result["distinct_dates"] == 7
    assert result["calendar_span_days"] == 19
    assert result["scores"]["body_required"]["parts"]["抗阻"] < 1


def test_window_span_counts_when_sessions_are_dense() -> None:
    result = run(
        {
            "profile": profile(),
            "window": {"start": "2026-09-18", "end": "2026-10-07"},
            "sessions": [day(index) for index in range(1, 8)],
        }
    )
    assert result["calendar_span_days"] == 20
    assert result["scores"]["body_required"]["parts"]["抗阻"] < 1


def test_raw_text_red_flag_stops() -> None:
    sessions = [day(index) for index in range(1, 8)]
    sessions[0]["red_flags"] = []
    sessions[0]["note"] = "今天胸痛，先停一下"
    result = run({"profile": profile(), "sessions": sessions})
    assert result["mode"] == "redflag"
    assert result["scores"] is None
    assert "胸痛" in result["red_flags"]


def test_negated_red_flag_does_not_stop() -> None:
    sessions = [day(index) for index in range(1, 8)]
    sessions[0]["note"] = "无胸痛，没有呼吸困难"
    result = run({"profile": profile(), "sessions": sessions})
    assert result["mode"] == "scored"
    assert result["scores"]["total"]["score"] == 200


def test_extended_red_flag_in_raw_text() -> None:
    sessions = [day(index) for index in range(1, 8)]
    sessions[3]["raw_text"] = "膝盖出现关节急性肿胀"
    result = run({"profile": profile(), "sessions": sessions})
    assert result["mode"] == "redflag"
    assert "关节急性肿胀" in result["red_flags"]


def test_under7_reports_daily_gaps() -> None:
    result = run({"profile": profile(), "sessions": [day(1), day(2)]})
    progress = result["daily_progress"]
    assert progress["target_date"] == "2026-10-02"
    assert progress["required_completion_ratio"] == 1
    assert progress["missing_required_fields"] == []


def test_alias_fields_still_total_200() -> None:
    sessions = []
    for index in range(1, 8):
        sessions.append(
            day(
                index,
                body_required={
                    "protein_g": 120,
                    "resistance_done": True,
                    "progressive_overload": True,
                },
                psych_required={
                    "self_rating_1_to_5": 5,
                    "feedback_category": "kept_and_changed",
                },
                optional={"sleep_quality": 1, "stress_relief": 1},
            )
        )
    result = run({"profile": profile(), "sessions": sessions})
    assert result["mode"] == "scored", result
    assert result["scores"]["total"]["score"] == 200


def test_fixture_file_matches_full_score() -> None:
    fixture = json.loads((FIXTURES / "full-7.json").read_text(encoding="utf-8"))
    result = run(fixture)
    assert result["scores"]["total"]["score"] == 200


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    (FIXTURES / "full-7.json").write_text(
        json.dumps({"profile": profile(), "sessions": [day(i) for i in range(1, 8)]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tests = [
        test_full_window_totals_200,
        test_under_seven_has_no_score_and_two_steps_when_gap,
        test_missing_required_does_not_zero,
        test_red_flag_stops,
        test_custom_protein_target_is_used,
        test_likert_fallback_marked_by_ratio,
        test_invalid_classification_lowers_psych,
        test_blank_optional_is_not_zero,
        test_defaulted_date_counts_as_one_day,
        test_blocked_profile,
        test_injury_note_does_not_stop_score,
        test_calendar_span_lowers_resistance_expectation,
        test_window_span_counts_when_sessions_are_dense,
        test_raw_text_red_flag_stops,
        test_negated_red_flag_does_not_stop,
        test_extended_red_flag_in_raw_text,
        test_under7_reports_daily_gaps,
        test_alias_fields_still_total_200,
        test_fixture_file_matches_full_score,
    ]
    for test in tests:
        test()
        print("ok", test.__name__)
    print("passed", len(tests))


if __name__ == "__main__":
    main()
