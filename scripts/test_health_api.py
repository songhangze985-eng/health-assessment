"""Checks for the local health API. Stdlib only."""

from __future__ import annotations

import base64
import datetime
import json
import os
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

import health_api_server
import mac_menubar_pet


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


def profile_body() -> dict:
    return {
        "height_cm": 172,
        "weight_kg": 75,
        "age": 36,
        "sex": "male",
        "training_years": 0,
        "injury": False,
    }


def request_json(base: str, method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(base + path, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_default_port_and_memory_fallback() -> None:
    plugin = (Path(__file__).resolve().parents[1] / "vpet_bridge" / "VPetHealthPlugin.cs").read_text(encoding="utf-8")
    assert "127.0.0.1" in plugin
    assert "8765" in plugin
    assert "HEALTH_API_PORT" in plugin
    assert health_api_server.DEFAULT_PORT == 8765
    origin = Path.cwd()
    work = Path(tempfile.mkdtemp(prefix="health-api-root-"))
    saved = os.environ.pop("HEALTH_MEMORY_PATH", None)
    try:
        os.chdir(work)
        assert health_api_server.resolve_memory_root() == Path("memory_store")
        repo = health_api_server.MemoryRepository()
        assert (work / "memory_store" / "sessions").is_dir()
        assert (work / "memory_store" / "analyses").is_dir()
        assert repo.bound
    finally:
        os.chdir(origin)
        if saved is not None:
            os.environ["HEALTH_MEMORY_PATH"] = saved
        _remove_tree(work)


def test_profile_bind_and_rejection() -> None:
    origin = Path.cwd()
    work = Path(tempfile.mkdtemp(prefix="health-api-profile-"))
    server = None
    try:
        os.chdir(work)
        initial = work / "initial"
        repo = health_api_server.MemoryRepository(str(initial))
        server = health_api_server.make_server("127.0.0.1", 0, repo)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"

        status, rejected = request_json(base, "POST", "/api/profile", {"height_cm": 172})
        assert status == 400
        assert "weight_kg" in rejected["missing_profile"]
        assert not (initial / "profile.json").exists()

        library = work / "person-a"
        status, bound = request_json(base, "POST", "/api/bind-library", {"memory_path": str(library)})
        assert status == 200, bound
        assert Path(".memory-path").is_file()
        assert (library / "sessions").is_dir()

        status, saved = request_json(base, "POST", "/api/profile", profile_body())
        assert status == 200, saved
        assert saved["mode"] == "under7"
        assert saved["profile"]["sex"] == "male"
        assert (library / "profile.json").is_file()
        assert (library / "settings" / "config.json").is_file()

        status, loaded = request_json(base, "GET", "/api/profile")
        assert status == 200
        assert loaded["complete"] is True
        assert loaded["profile"]["height_cm"] == 172
    finally:
        os.chdir(origin)
        if server is not None:
            server.shutdown()
            server.server_close()
        _remove_tree(work)


def test_multiday_csv_same_day_priority_and_red_flag() -> None:
    root = Path(tempfile.mkdtemp(prefix="health-api-import-"))
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    server = None
    try:
        write_profile(root)
        repo = health_api_server.MemoryRepository(str(root))
        server = health_api_server.make_server("127.0.0.1", 0, repo)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        table = (
            "日期,蛋白质,力量训练,渐进超负荷,自评,评价分类,睡眠时长,抗炎饮食,压力缓解,专注力,步数,静息心率\n"
            f"{yesterday.isoformat()},120,30,是,5,kept_and_changed,8,1,4,5,9000,60\n"
            f"{today.isoformat()},110,40,否,4,discarded_insult,7,0.8,3,4,6000,70\n"
        )
        status, imported = request_json(
            base,
            "POST",
            "/api/checkin/file",
            {
                "filename": "watch.csv",
                "file_base64": base64.b64encode(table.encode("utf-8")).decode("ascii"),
            },
        )
        assert status == 200, imported
        assert imported["imported_days"] == 2
        assert imported["evaluation"]["mode"] == "under7"
        assert imported["evaluation"]["distinct_dates"] == 2
        today_session = json.loads((root / "sessions" / f"{today.isoformat()}.json").read_text(encoding="utf-8"))
        assert today_session["body_required"]["resistance_minutes"] == 40
        assert today_session["body_required"]["progressive_overload"] is False
        assert today_session["psych_required"]["feedback_category"] == "discarded_insult"
        assert "sleep_quality" in today_session["optional"]
        assert "focus_state" in today_session["optional"]

        status, checked = request_json(
            base,
            "POST",
            "/api/checkin/text",
            {"text": "力量训练 5 分钟，加重了，心情 5分，听取建议", "date": today.isoformat()},
        )
        assert status == 200, checked
        merged = json.loads((root / "sessions" / f"{today.isoformat()}.json").read_text(encoding="utf-8"))
        assert merged["body_required"]["resistance_minutes"] == 40
        assert merged["body_required"]["progressive_overload"] is True
        assert merged["psych_required"]["self_rating_1_to_5"] == 5
        assert merged["psych_required"]["feedback_category"] == "kept_and_changed"

        status, flagged = request_json(
            base,
            "POST",
            "/api/checkin/text",
            {"text": "今天胸痛", "date": today.isoformat()},
        )
        assert status == 200, flagged
        assert flagged["evaluation"]["mode"] == "redflag"
        assert flagged["vpet_state"]["animation_state"] == "Ill"
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        _remove_tree(root)


def test_spoken_checkin_covers_core_fields() -> None:
    extracted = health_api_server.LLMExtractor().extract_from_text_or_image(
        "今天练背加了重量，蛋白145g，心情5分，无视喷子，睡了7小时，很专注，压力缓解了",
        date_str="2026-10-18",
    )
    assert extracted["body_required"]["protein_g"] == 145
    assert extracted["body_required"]["resistance_done"] is True
    assert extracted["body_required"]["progressive_overload"] is True
    assert extracted["psych_required"]["self_rating_1_to_5"] == 5
    assert extracted["psych_required"]["feedback_category"] == "discarded_insult"
    assert extracted["optional"]["sleep_quality"] > 0
    assert extracted["optional"]["focus_state"] == 1.0
    assert extracted["optional"]["stress_relief"] == 1.0


def test_menubar_title_uses_score_payload() -> None:
    assert mac_menubar_pet.API_PORT == 8765 or "HEALTH_API_PORT" in os.environ
    assert mac_menubar_pet.format_menubar_title({"mode": "redflag"}) == "🚨 红旗预警"
    assert mac_menubar_pet.format_menubar_title({"mode": "blocked_profile"}) == "📋 待建档"
    assert (
        mac_menubar_pet.format_menubar_title(
            {
                "mode": "under7",
                "distinct_dates": 4,
                "daily_progress": {"required_completion_ratio": 0.8},
            }
        )
        == "😄 4/7天(80%)"
    )
    assert (
        mac_menubar_pet.format_menubar_title(
            {"mode": "scored", "scores": {"total": {"score": 168}, "body": {"score": 90}, "psych": {"score": 78}}}
        )
        == "💪 168/200分"
    )
    report = mac_menubar_pet.format_score_report(
        {
            "mode": "under7",
            "distinct_dates": 1,
            "daily_progress": {
                "required_completion_ratio": 0.4,
                "missing_required_fields": ["protein_g (今日蛋白质摄入克数)"],
                "target_date": "2026-10-18",
            },
        }
    )
    assert "1 / 7" in report
    assert "蛋白质" in report


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
        test_default_port_and_memory_fallback,
        test_profile_bind_and_rejection,
        test_multiday_csv_same_day_priority_and_red_flag,
        test_spoken_checkin_covers_core_fields,
        test_menubar_title_uses_score_payload,
        test_non_loopback_host_is_rejected,
    ]
    for test in tests:
        test()
        print("ok", test.__name__)
    print("passed", len(tests))


if __name__ == "__main__":
    main()
