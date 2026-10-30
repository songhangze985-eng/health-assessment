"""Checks for the local health API. Stdlib only."""

from __future__ import annotations

import base64
import datetime
import http.client
import json
import os
import sys
import tempfile
import threading
import time
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


def test_dashboard_settings_switch_memory_without_touching_login_items() -> None:
    import plistlib
    import pwd

    import generate_mac_assets

    real_home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    real_plist = real_home / "Library" / "LaunchAgents" / "com.songhangze.healthassessment.plist"
    existed = real_plist.exists()
    home = Path(tempfile.mkdtemp(prefix="health-mac-home-"))
    work = Path(tempfile.mkdtemp(prefix="health-mac-work-"))
    origin = Path.cwd()
    saved_env = {
        key: os.environ.get(key)
        for key in ("HOME", "HEALTH_MEMORY_PATH", "LLM_API_KEY", "LLM_API_URL", "LLM_MODEL", "HEALTH_SKIP_LAUNCH_AGENT")
    }
    server = None
    try:
        os.environ["HOME"] = str(home)
        os.environ["HEALTH_SKIP_LAUNCH_AGENT"] = "1"
        os.environ.pop("HEALTH_MEMORY_PATH", None)
        os.chdir(work)
        repo = health_api_server.MemoryRepository(str(work / "initial"))
        server = health_api_server.make_server("127.0.0.1", 0, repo)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_address[1]}"

        with urllib.request.urlopen(base + "/ui", timeout=5) as response:
            html = response.read().decode("utf-8")
            assert "text/html" in response.headers.get("Content-Type", "")
        assert "薄肌与黄毛" in html
        assert "data.scores && data.scores[key]" in html
        assert "total_score" not in html
        assert "llm_api_key_set" in html
        assert "llm_api_key_last4" in html
        assert "clear_api_key" in html
        assert "settings.llm_api_key = typedKey" in html
        assert ".value = cfgRes.llm_api_key" not in html

        status, settings = request_json(base, "GET", "/api/settings")
        assert status == 200
        assert str(home) in settings["memory_path"]

        library = home / "custom-memory"
        status, saved = request_json(
            base,
            "POST",
            "/api/settings",
            {
                "memory_path": str(library),
                "llm_api_key": "test-key",
                "auto_start_on_login": True,
                "profile": profile_body(),
            },
        )
        assert status == 200, saved
        assert saved["memory_path"] == str(library.resolve())
        config_path = home / "Library" / "Application Support" / "HealthAssessment" / "config.json"
        stored = json.loads(config_path.read_text(encoding="utf-8"))
        assert stored["llm_api_key"] == "test-key"
        assert stored["profile"]["height_cm"] == 172
        assert os.environ["HEALTH_MEMORY_PATH"] == str(library.resolve())
        assert "llm_api_key" not in saved["settings"]
        assert saved["settings"]["llm_api_key_set"] is True
        assert saved["settings"]["llm_api_key_last4"] == "-key"
        status, visible = request_json(base, "GET", "/api/settings")
        assert status == 200, visible
        assert "llm_api_key" not in visible
        assert visible["llm_api_key_last4"] == "-key"
        plist_path = home / "Library" / "LaunchAgents" / "com.songhangze.healthassessment.plist"
        if sys.platform == "darwin":
            plist = plistlib.loads(plist_path.read_bytes())
            assert plist["Label"] == "com.songhangze.healthassessment"
            assert plist["RunAtLoad"] is True
            assert plist["KeepAlive"] is False
            assert any(str(item).endswith("mac_menubar_pet.py") for item in plist["ProgramArguments"])
        else:
            assert not plist_path.exists()
        assert real_plist.exists() is existed

        status, saved_profile = request_json(base, "POST", "/api/profile", profile_body())
        assert status == 200, saved_profile
        assert saved_profile["mode"] == "under7"
        assert (library / "profile.json").is_file()
        assert "llm_api_key" not in (library / "profile.json").read_text(encoding="utf-8")

        png = generate_mac_assets.generate_squircle_png(32, is_template=False)
        assert png.startswith(b"\x89PNG\r\n\x1a\n")
        assert png[16:24] == (32).to_bytes(4, "big") + (32).to_bytes(4, "big")
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        os.chdir(origin)
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        _remove_tree(work)
        _remove_tree(home)


def raw_request(
    base: str,
    method: str,
    path: str,
    body: bytes | None = None,
    headers: dict | None = None,
) -> tuple[int, dict]:
    request = urllib.request.Request(base + path, data=body, method=method)
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            raw = response.read().decode("utf-8")
            code = response.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        code = exc.code
    try:
        parsed = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        parsed = {"raw": raw}
    return code, parsed


def test_loopback_request_parsers() -> None:
    assert health_api_server.host_header_is_loopback("127.0.0.1:8765", 8765)
    assert health_api_server.host_header_is_loopback("localhost:8765", 8765)
    assert health_api_server.host_header_is_loopback("[::1]:8765", 8765)
    assert health_api_server.host_header_is_loopback("127.0.0.1", 80)
    assert not health_api_server.host_header_is_loopback("127.0.0.1", 8765)
    assert not health_api_server.host_header_is_loopback("evil.example:8765", 8765)
    assert not health_api_server.host_header_is_loopback("127.0.0.1.evil.example", 8765)
    assert not health_api_server.host_header_is_loopback("127.0.0.1:9", 8765)
    assert not health_api_server.host_header_is_loopback(None, 8765)
    assert health_api_server.origin_matches_loopback_port(None, 8765)
    assert health_api_server.origin_matches_loopback_port("http://127.0.0.1:8765", 8765)
    assert health_api_server.origin_matches_loopback_port("http://localhost:8765", 8765)
    assert not health_api_server.origin_matches_loopback_port("http://127.0.0.1:80", 8765)
    assert not health_api_server.origin_matches_loopback_port("https://127.0.0.1:8765", 8765)
    assert not health_api_server.origin_matches_loopback_port("http://evil.example", 8765)
    assert not health_api_server.origin_matches_loopback_port("null", 8765)
    assert health_api_server.content_type_is_json("application/json; charset=utf-8")
    assert not health_api_server.content_type_is_json("text/plain")
    assert not health_api_server.content_type_is_json(None)


def test_cross_site_writes_are_rejected() -> None:
    home = Path(tempfile.mkdtemp(prefix="health-api-csrf-"))
    work = Path(tempfile.mkdtemp(prefix="health-api-csrf-work-"))
    origin_cwd = Path.cwd()
    saved_env = {
        key: os.environ.get(key)
        for key in ("HOME", "HEALTH_MEMORY_PATH", "LLM_API_KEY", "LLM_API_URL", "LLM_MODEL", "HEALTH_SKIP_LAUNCH_AGENT")
    }
    server = None
    try:
        os.environ["HOME"] = str(home)
        os.environ["HEALTH_SKIP_LAUNCH_AGENT"] = "1"
        os.environ.pop("HEALTH_MEMORY_PATH", None)
        os.chdir(work)
        memory = work / "mem"
        repo = health_api_server.MemoryRepository(str(memory))
        server = health_api_server.make_server("127.0.0.1", 0, repo)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        port = server.server_address[1]
        base = f"http://127.0.0.1:{port}"
        config_path = home / "Library" / "Application Support" / "HealthAssessment" / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            json.dumps(
                {
                    "memory_path": str(memory),
                    "llm_api_key": "super-secret-key-1234",
                    "llm_api_url": "https://example.test/v1",
                    "llm_model": "gemini-2.5-flash",
                    "auto_start_on_login": False,
                }
            ),
            encoding="utf-8",
        )

        status, settings = request_json(base, "GET", "/api/settings")
        assert status == 200, settings
        assert "llm_api_key" not in settings
        assert settings["llm_api_key_set"] is True
        assert settings["llm_api_key_last4"] == "1234"
        assert settings["llm_api_url"] == "https://example.test/v1"

        attack = json.dumps({"llm_api_url": "https://attacker.example/steal"}).encode("utf-8")
        status, denied = raw_request(
            base,
            "POST",
            "/api/settings",
            attack,
            {"Content-Type": "text/plain"},
        )
        assert status == 415, denied
        status, denied = raw_request(
            base,
            "POST",
            "/api/bind-library",
            json.dumps({"memory_path": str(work / "elsewhere")}).encode("utf-8"),
            {"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert status == 415, denied
        assert not (work / ".memory-path").exists()
        status, denied = raw_request(
            base,
            "POST",
            "/api/checkin/text",
            json.dumps({"text": "蛋白质 1 克", "date": "2026-10-18"}).encode("utf-8"),
            {"Content-Type": "text/plain", "Origin": "https://evil.example"},
        )
        assert status == 403, denied
        status, denied = raw_request(
            base,
            "POST",
            "/api/profile",
            json.dumps(profile_body()).encode("utf-8"),
            {
                "Content-Type": "application/json",
                "Origin": "http://evil.example",
                "Sec-Fetch-Site": "cross-site",
            },
        )
        assert status == 403, denied
        status, denied = raw_request(
            base,
            "GET",
            "/api/settings",
            headers={"Host": "evil.example"},
        )
        assert status == 403, denied
        status, denied = raw_request(
            base,
            "POST",
            "/api/settings",
            attack,
            {"Content-Type": "application/json", "Host": "evil.example:8765"},
        )
        assert status == 403, denied
        status, denied = raw_request(
            base,
            "POST",
            "/api/settings",
            attack,
            {"Content-Type": "application/json", "Origin": "null"},
        )
        assert status == 403, denied
        stored = json.loads(config_path.read_text(encoding="utf-8"))
        assert stored["llm_api_url"] == "https://example.test/v1"
        assert stored["llm_api_key"] == "super-secret-key-1234"
        assert not (memory / "sessions").joinpath("2026-10-18.json").exists()

        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request(
            "POST",
            "/api/settings",
            body=attack,
            headers={"Content-Type": "text/plain"},
        )
        first = conn.getresponse()
        first.read()
        assert first.status == 415
        conn.request("GET", "/api/greeting")
        second = conn.getresponse()
        greeting = json.loads(second.read().decode("utf-8"))
        assert second.status == 200
        assert "vpet_bubble_text" in greeting
        conn.close()

        status, saved = request_json(
            base,
            "POST",
            "/api/settings",
            {"llm_api_url": "https://example.test/v1", "memory_path": str(memory)},
        )
        assert status == 200, saved
        assert "llm_api_key" not in saved["settings"]
        assert saved["settings"]["llm_api_key_set"] is True
        assert json.loads(config_path.read_text(encoding="utf-8"))["llm_api_key"] == "super-secret-key-1234"

        status, replaced = raw_request(
            base,
            "POST",
            "/api/settings",
            json.dumps({"llm_api_key": "next-secret-9999"}).encode("utf-8"),
            {
                "Content-Type": "application/json; charset=utf-8",
                "Origin": f"http://127.0.0.1:{port}",
                "Sec-Fetch-Site": "same-origin",
            },
        )
        assert status == 200, replaced
        assert replaced["settings"]["llm_api_key_last4"] == "9999"
        assert "next-secret-9999" not in json.dumps(replaced)
        assert json.loads(config_path.read_text(encoding="utf-8"))["llm_api_key"] == "next-secret-9999"

        status, kept = request_json(base, "POST", "/api/settings", {"llm_model": "gemini-2.5-flash"})
        assert status == 200, kept
        assert json.loads(config_path.read_text(encoding="utf-8"))["llm_api_key"] == "next-secret-9999"

        status, cleared = request_json(base, "POST", "/api/settings", {"llm_api_key": ""})
        assert status == 200, cleared
        assert cleared["settings"]["llm_api_key_set"] is False
        assert json.loads(config_path.read_text(encoding="utf-8"))["llm_api_key"] == ""

        status, short = request_json(base, "POST", "/api/settings", {"llm_api_key": "ab"})
        assert status == 200, short
        assert short["settings"]["llm_api_key_set"] is True
        assert short["settings"]["llm_api_key_last4"] == ""
        assert short["settings"].get("llm_api_key") in {None, ""}
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        os.chdir(origin_cwd)
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        _remove_tree(work)
        _remove_tree(home)


def test_session_dates_stay_inside_sessions_dir() -> None:
    root = Path(tempfile.mkdtemp(prefix="health-api-day-"))
    nested = root / "memory"
    server = None
    try:
        repo = health_api_server.MemoryRepository(str(nested))
        for bad in ("../../evil", r"..\..\evil", "2026-10-18/../../tmp/x", "2026-02-31", "2026-1-8", "....//evil"):
            try:
                repo.merge_and_save_session({"date": bad, "raw_text": "nope"}, source_type="self_report")
            except ValueError as exc:
                assert "YYYY-MM-DD" in str(exc)
            else:
                raise AssertionError(f"accepted date {bad}")
        try:
            repo.write_analysis("../../evil", {"ok": False})
        except ValueError:
            pass
        else:
            raise AssertionError("analysis date escaped validation")
        assert not (root / "evil.json").exists()
        assert list(nested.rglob("evil.json")) == []
        assert list(root.rglob("*.tmp")) == []

        saved = repo.merge_and_save_session(
            {"date": "2024-02-29", "raw_text": "闰日", "optional": {"sleep_quality": 1}},
            source_type="self_report",
        )
        assert saved["date"] == "2024-02-29"
        assert (nested / "sessions" / "2024-02-29.json").is_file()
        repo.write_analysis("2024-02-29", {"mode": "under7"})
        analyses = list((nested / "analyses").glob("2024-02-29-*.json"))
        assert len(analyses) == 1

        write_profile(nested)
        server = health_api_server.make_server("127.0.0.1", 0, repo)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        status, rejected = request_json(
            base,
            "POST",
            "/api/checkin/text",
            {"text": "蛋白质 130克", "date": "../../evil"},
        )
        assert status == 400, rejected
        assert not (root / "evil.json").exists()
        assert not (nested / "sessions" / "evil.json").exists()
        today = datetime.date.today().isoformat()
        status, accepted = request_json(base, "POST", "/api/checkin/text", {"text": "蛋白质 130克"})
        assert status == 200, accepted
        assert (nested / "sessions" / f"{today}.json").is_file()
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        _remove_tree(root)


def test_concurrent_session_saves_keep_every_update() -> None:
    root = Path(tempfile.mkdtemp(prefix="health-api-race-"))
    try:
        repo = health_api_server.MemoryRepository(str(root))
        count = 12
        barrier = threading.Barrier(count)
        errors: list[BaseException] = []
        seen: list[str] = []
        target = root / "sessions" / "2026-10-18.json"

        def writer(index: int) -> None:
            try:
                barrier.wait(timeout=5)
                repo.merge_and_save_session(
                    {
                        "date": "2026-10-18",
                        "raw_text": f"note-{index}",
                        "optional": {f"k{index}": index},
                    },
                    source_type="self_report",
                )
            except BaseException as exc:
                errors.append(exc)

        def reader() -> None:
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                if target.is_file():
                    try:
                        parsed = json.loads(target.read_text(encoding="utf-8"))
                    except json.JSONDecodeError as exc:
                        errors.append(exc)
                        return
                    if isinstance(parsed, dict):
                        seen.append(str(parsed.get("date")))
                time.sleep(0.01)

        threads = [threading.Thread(target=writer, args=(index,)) for index in range(count)]
        threads.append(threading.Thread(target=reader))
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        assert errors == [], errors
        saved = json.loads(target.read_text(encoding="utf-8"))
        for index in range(count):
            assert saved["optional"][f"k{index}"] == index
            assert f"note-{index}" in saved["raw_text"]
        assert list(root.rglob("*.tmp")) == []
        assert seen, "reader never observed a session file"
    finally:
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
        test_default_port_and_memory_fallback,
        test_profile_bind_and_rejection,
        test_multiday_csv_same_day_priority_and_red_flag,
        test_spoken_checkin_covers_core_fields,
        test_menubar_title_uses_score_payload,
        test_dashboard_settings_switch_memory_without_touching_login_items,
        test_loopback_request_parsers,
        test_cross_site_writes_are_rejected,
        test_session_dates_stay_inside_sessions_dir,
        test_concurrent_session_saves_keep_every_update,
        test_non_loopback_host_is_rejected,
    ]
    for test in tests:
        test()
        print("ok", test.__name__)
    print("passed", len(tests))


if __name__ == "__main__":
    main()
