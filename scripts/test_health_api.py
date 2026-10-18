"""Checks for the local health API. Stdlib only."""

from __future__ import annotations

import base64
import datetime
import json
import tempfile
import threading
import urllib.request
from pathlib import Path

import health_api_server


def write_profile(root: Path) -> None:
    config = root / "settings"
    config.mkdir(parents=True)
    (config / "config.json").write_text(
        json.dumps(
            {
                "height_cm": 172,
                "weight_kg": 75,
                "age": 36,
                "sex": "male",
                "training_years": 0,
                "injury": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_csv_parser_maps_wearable_columns() -> None:
    raw = "日期,睡眠时长,步数,静息心率,力量训练,蛋白质\n2026-10-18,8,9000,60,40,130\n".encode("utf-8")
    sessions = health_api_server.parse_health_table_bytes(raw, "watch.csv")
    assert len(sessions) == 1
    session = sessions[0]
    assert session["date"] == "2026-10-18"
    assert session["body_required"]["protein_g"] == 130
    assert session["body_required"]["resistance_done"] is True
    assert session["optional"]["睡眠时长"] == {"hours": 8.0}


def test_same_day_merge_keeps_wearable_duration_and_self_report_overload() -> None:
    root = Path(tempfile.mkdtemp(prefix="health-api-merge-"))
    try:
        repo = health_api_server.MemoryRepository(str(root))
        repo.merge_and_save_session(
            {
                "date": "2026-10-18",
                "body_required": {"resistance_minutes": 40, "resistance_done": True, "progressive_overload": False},
            },
            source_type="wearable_table",
        )
        merged = repo.merge_and_save_session(
            {
                "date": "2026-10-18",
                "raw_text": "今天加重了",
                "body_required": {"resistance_minutes": 5, "progressive_overload": True},
                "psych_required": {"self_rating_1_to_5": 4, "feedback_category": "kept_and_changed"},
            },
            source_type="self_report",
        )
        assert merged["body_required"]["resistance_minutes"] == 40
        assert merged["body_required"]["progressive_overload"] is True
        assert merged["psych_required"]["self_rating_1_to_5"] == 4
        assert "wearable_table" in merged["sources"]
        assert "self_report" in merged["sources"]
    finally:
        _remove_tree(root)


def test_heuristic_extracts_protein_and_red_flag() -> None:
    extracted = health_api_server.LLMExtractor().extract_from_text_or_image(
        "蛋白质 130克，练了腿，状态 4分，听取建议改了，但是胸痛",
        date_str="2026-10-18",
    )
    assert extracted["body_required"]["protein_g"] == 130
    assert extracted["body_required"]["resistance_done"] is True
    assert extracted["psych_required"]["self_rating_1_to_5"] == 4
    assert "胸痛" in extracted["red_flags"]


def _remove_tree(root: Path) -> None:
    if not root.exists():
        return
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
        else:
            path.rmdir()
    root.rmdir()


def test_http_greeting_and_table_import() -> None:
    root = Path(tempfile.mkdtemp(prefix="health-api-http-"))
    today = datetime.date.today().isoformat()
    server = None
    try:
        write_profile(root)
        repo = health_api_server.MemoryRepository(str(root))
        server = health_api_server.make_server("127.0.0.1", 0, repo)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_address[1]
        base = f"http://127.0.0.1:{port}"

        with urllib.request.urlopen(base + "/api/greeting", timeout=5) as response:
            greeting = json.loads(response.read().decode("utf-8"))
        assert greeting["distinct_dates_collected"] == 0
        assert "记忆库" not in greeting["vpet_bubble_text"]
        assert len(greeting["missing_required_fields"]) == 5

        payload = json.dumps(
            {
                "filename": "watch.csv",
                "file_base64": base64.b64encode(
                    f"日期,蛋白质,力量训练\n{today},130,40\n".encode("utf-8")
                ).decode("ascii"),
                "date": today,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            base + "/api/checkin/file",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            imported = json.loads(response.read().decode("utf-8"))
        assert imported["imported_days"] == 1
        assert imported["evaluation"]["mode"] == "under7"
        assert imported["evaluation"]["distinct_dates"] == 1
        assert imported["vpet_state"]["animation_state"] in {"Nomal", "Happy"}
        saved = json.loads((root / "sessions" / f"{today}.json").read_text(encoding="utf-8"))
        assert saved["body_required"]["protein_g"] == 130
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        _remove_tree(root)


def test_non_loopback_host_is_rejected() -> None:
    try:
        health_api_server.make_server("0.0.0.0", 0)
    except SystemExit as exc:
        assert "回环" in str(exc)
    else:
        raise AssertionError("non-loopback host was accepted")


def main() -> None:
    tests = [
        test_csv_parser_maps_wearable_columns,
        test_same_day_merge_keeps_wearable_duration_and_self_report_overload,
        test_heuristic_extracts_protein_and_red_flag,
        test_http_greeting_and_table_import,
        test_non_loopback_host_is_rejected,
    ]
    for test in tests:
        test()
        print("ok", test.__name__)
    print("passed", len(tests))


if __name__ == "__main__":
    main()
