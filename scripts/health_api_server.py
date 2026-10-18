#!/usr/bin/env python3
"""Local check-in API for CSV/Excel import, text extraction, and the VPet bridge.

Bind address is loopback only. Run from the repository root:

    py -3 scripts/health_api_server.py
"""

from __future__ import annotations

import base64
import csv
import datetime
import io
import json
import os
import re
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlsplit
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import mac_dashboard_ui
import score_checkin

MAX_BODY_BYTES = 12 * 1024 * 1024
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
VALID_SEX = {"female", "male", "other"}
VALID_FEEDBACK = {"kept_and_changed", "discarded_insult", "invalid"}

COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "date": ("记录日期", "日期", "date", "start_time"),
    "sleep_hours": ("总睡眠时长", "睡眠时长", "睡眠(小时)", "sleep_duration", "sleep_hours", "sleep_quality"),
    "steps": ("今日步数", "日常步数", "步数", "step_count", "steps", "cardio_activity"),
    "resting_hr": ("静息心率", "平均心率", "resting_heart_rate", "resting_hr", "vital_signs"),
    "resistance_minutes": ("无氧训练(分钟)", "抗阻时长", "力量训练", "strength_training", "resistance_minutes"),
    "resistance_done": ("是否抗阻", "抗阻完成", "resistance_done"),
    "protein_g": ("蛋白质(g)", "蛋白质", "protein_g", "protein"),
    "progressive_overload": ("渐进超负荷", "超负荷", "progressive_overload"),
    "self_rating": ("执行力自评", "心情评分", "自评", "self_rating_1_to_5"),
    "feedback_category": ("评价分类", "feedback_category"),
    "anti_inflammatory_diet": ("抗炎饮食", "anti_inflammatory_diet"),
    "stress_relief": ("压力缓解", "stress_relief"),
    "focus_state": ("专注力状态", "专注力", "focus_state"),
}

WEARABLE_BODY = {"resistance_minutes", "resistance_done", "protein_g", "protein_ratio"}
SELF_REPORT_BODY = {"progressive_overload", "overload"}
WEARABLE_OPTIONAL = {"sleep_quality", "cardio_activity", "vital_signs", "hydration", "睡眠时长", "日常步数", "基础机能", "总饮水量"}
SELF_REPORT_OPTIONAL = {
    "stress_relief",
    "focus_state",
    "anti_inflammatory_diet",
    "emotional_stability",
    "self_care",
    "日常压力",
    "注意力",
    "饮食质量",
    "情绪波动",
    "自我照顾",
}

EXTRACTION_SYSTEM_PROMPT = """你是健康打卡的结构化提取器。
把用户自述或图片里已经出现的内容提取成 JSON。不要计算分数，不要编造没提到的数字，不要下诊断。
红旗只在原文确实出现胸痛、昏厥、晕厥、自伤、轻生、自行停药、急性剧痛、呼吸困难、异常心悸、骨裂、关节急性肿胀时写入 red_flags。
输出 JSON:
{
  "date": "YYYY-MM-DD",
  "red_flags": [],
  "body_required": {"protein_g": null, "resistance_done": null, "progressive_overload": null},
  "psych_required": {"self_rating_1_to_5": null, "feedback_category": null},
  "optional": {"sleep_quality": null, "anti_inflammatory_diet": null, "stress_relief": null, "focus_state": null},
  "pet_reply": "30字以内的桌宠回应，不给医疗建议"
}
"""


def resolve_memory_root(base_dir: str | None = None) -> Path | None:
    if base_dir:
        return Path(base_dir).expanduser()
    env_path = os.environ.get("HEALTH_MEMORY_PATH", "").strip()
    if env_path:
        return Path(env_path).expanduser()
    pointer = Path(".memory-path")
    if pointer.is_file():
        text = pointer.read_text(encoding="utf-8").strip()
        if text:
            return Path(text).expanduser()
    return Path("memory_store")


def empty_session(date_str: str) -> dict[str, Any]:
    return {
        "date": date_str,
        "sources": [],
        "raw_text": "",
        "red_flags": [],
        "body_required": {},
        "psych_required": {},
        "optional": {},
    }


def _keep_existing(key: str, bucket: str, existing_sources: set[str], incoming_source: str, current: dict[str, Any]) -> bool:
    if key not in current or current.get(key) is None:
        return False
    if incoming_source == "self_report" and "wearable_table" in existing_sources:
        protected = WEARABLE_BODY if bucket == "body" else WEARABLE_OPTIONAL
        return key in protected
    if incoming_source in {"wearable_table", "image_ocr"} and "self_report" in existing_sources:
        protected = SELF_REPORT_BODY if bucket == "body" else SELF_REPORT_OPTIONAL
        return key in protected
    if incoming_source == "image_ocr" and "wearable_table" in existing_sources:
        protected = WEARABLE_BODY if bucket == "body" else WEARABLE_OPTIONAL
        return key in protected
    return False


def merge_records(existing: dict[str, Any], incoming: dict[str, Any], source_type: str) -> dict[str, Any]:
    date_str = str(incoming.get("date") or existing.get("date") or datetime.date.today().isoformat())[:10]
    merged = existing or empty_session(date_str)
    merged["date"] = date_str
    sources = set(merged.get("sources") or [])
    for flag_name in incoming.get("sources") or []:
        sources.add(str(flag_name))
    sources.add(source_type)
    merged["sources"] = sorted(sources)

    incoming_text = str(incoming.get("raw_text") or "").strip()
    if incoming_text and incoming_text not in str(merged.get("raw_text") or ""):
        previous = str(merged.get("raw_text") or "")
        merged["raw_text"] = (previous + " | " + incoming_text).strip(" |")

    flags = set(str(flag) for flag in (merged.get("red_flags") or []))
    for flag in incoming.get("red_flags") or []:
        if str(flag).strip():
            flags.add(str(flag).strip())
    merged["red_flags"] = sorted(flags)

    prior_sources = set(merged.get("sources") or []) - {source_type}
    for bucket, incoming_key in (
        ("body", "body_required"),
        ("psych", "psych_required"),
        ("optional", "optional"),
    ):
        current = dict(merged.get(incoming_key) or {})
        for key, value in (incoming.get(incoming_key) or {}).items():
            if value is None:
                continue
            if bucket == "psych":
                if source_type != "self_report" and "self_report" in prior_sources and key in current:
                    continue
            elif _keep_existing(key, bucket, prior_sources, source_type, current):
                continue
            current[key] = value
        merged[incoming_key] = current
    return merged


class MemoryRepository:
    def __init__(self, base_dir: str | None = None) -> None:
        self.root = resolve_memory_root(base_dir)
        self.bound = self.root is not None
        if self.root is not None:
            self.sessions_dir = self.root / "sessions"
            self.analyses_dir = self.root / "analyses"
            self.sessions_dir.mkdir(parents=True, exist_ok=True)
            self.analyses_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.sessions_dir = None
            self.analyses_dir = None

    def load_profile(self) -> dict[str, Any]:
        if self.root is None:
            return {}
        for path in (self.root / "settings" / "config.json", self.root / "profile.json"):
            if not path.is_file():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            if isinstance(data.get("profile"), dict):
                profile = dict(data["profile"])
                if "targets" in data and "targets" not in profile:
                    profile["targets"] = data["targets"]
                return profile
            return data
        return {}

    def _read_session_file(self, path: Path) -> dict[str, Any] | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        return data

    def load_recent_sessions(self, days: int = 14) -> list[dict[str, Any]]:
        if self.sessions_dir is None:
            return []
        grouped: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        for path in sorted(self.sessions_dir.glob("*.json")):
            data = self._read_session_file(path)
            if data is None:
                continue
            date_str = str(data.get("date") or path.name[:10])[:10]
            grouped.setdefault(date_str, []).append((path.name, data))
        sessions: list[dict[str, Any]] = []
        for date_str in sorted(grouped):
            files = grouped[date_str]
            canonical = next((data for name, data in files if name == f"{date_str}.json"), None)
            merged = canonical or empty_session(date_str)
            for name, extra in files:
                if name == f"{date_str}.json":
                    continue
                source = str((extra.get("sources") or ["self_report"])[-1])
                merged = merge_records(merged, extra, source)
            sessions.append(merged)
        if days > 0:
            cutoff = datetime.date.today() - datetime.timedelta(days=days - 1)
            kept = []
            for item in sessions:
                parsed = None
                if item.get("date"):
                    try:
                        parsed = score_checkin.parse_day(str(item.get("date"))[:10])
                    except ValueError:
                        parsed = None
                if parsed is not None and parsed >= cutoff:
                    kept.append(item)
            sessions = kept
        return sessions

    def merge_and_save_session(self, incoming: dict[str, Any], source_type: str = "self_report") -> dict[str, Any]:
        if self.sessions_dir is None:
            raise RuntimeError("记忆库未绑定。写入 .memory-path，或设置 HEALTH_MEMORY_PATH。")
        date_str = str(incoming.get("date") or datetime.date.today().isoformat())[:10]
        target = self.sessions_dir / f"{date_str}.json"
        existing = self._read_session_file(target) if target.exists() else empty_session(date_str)
        if existing is None:
            existing = empty_session(date_str)
        merged = merge_records(existing, incoming, source_type)
        target.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        return merged

    def save_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        if self.root is None:
            raise RuntimeError("记忆库未绑定。")
        stored = dict(profile)
        (self.root / "profile.json").write_text(
            json.dumps(stored, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        settings = self.root / "settings"
        settings.mkdir(parents=True, exist_ok=True)
        config_path = settings / "config.json"
        if config_path.is_file():
            try:
                previous = json.loads(config_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                previous = {}
            if isinstance(previous, dict) and "targets" in previous and "targets" not in stored:
                stored["targets"] = previous["targets"]
        config_path.write_text(json.dumps(stored, ensure_ascii=False, indent=2), encoding="utf-8")
        return stored

    def write_analysis(self, date_str: str, payload: dict[str, Any]) -> None:
        if self.analyses_dir is None:
            return
        stamp = datetime.datetime.now().strftime("%H%M%S")
        path = self.analyses_dir / f"{date_str}-{stamp}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _match_column(header: str) -> str | None:
    cleaned = header.strip().lower()
    best: str | None = None
    best_length = -1
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            needle = alias.lower()
            if needle in cleaned and len(needle) > best_length:
                best = canonical
                best_length = len(needle)
    return best


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "是", "完成", "有"}:
        return True
    if text in {"0", "false", "no", "n", "否", "没有", "无"}:
        return False
    return None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = re.sub(r"[^0-9.\-]", "", str(value).strip().replace(",", "").replace("，", ""))
    if text in {"", "-", ".", "-."}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _as_date(value: Any, default_date: str | None) -> str:
    if isinstance(value, datetime.datetime):
        return value.date().isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    text = str(value or "").strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    return default_date or datetime.date.today().isoformat()


def _table_rows(file_bytes: bytes, filename: str) -> list[dict[str, Any]]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".xlsx":
        try:
            import openpyxl  # type: ignore
        except ImportError as exc:
            raise RuntimeError("读取 .xlsx 需要安装 openpyxl，或先导出成 .csv。") from exc
        workbook = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
        try:
            sheet = workbook.active
            raw_rows = list(sheet.iter_rows(values_only=True))
        finally:
            workbook.close()
        if not raw_rows:
            return []
        headers = [str(cell or "") for cell in raw_rows[0]]
        rows = []
        for raw in raw_rows[1:]:
            rows.append({headers[index]: raw[index] for index in range(min(len(headers), len(raw)))})
        return rows
    text = file_bytes.decode("utf-8-sig", errors="replace")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
    except csv.Error:
        dialect = csv.excel
    return [dict(row) for row in csv.DictReader(io.StringIO(text), dialect=dialect)]


def parse_health_table_bytes(
    file_bytes: bytes,
    filename: str,
    default_date: str | None = None,
) -> list[dict[str, Any]]:
    sessions: dict[str, dict[str, Any]] = {}
    for raw_row in _table_rows(file_bytes, filename):
        mapped: dict[str, Any] = {}
        for key, value in raw_row.items():
            if not key or value is None or str(value).strip() == "":
                continue
            canonical = _match_column(str(key))
            if canonical:
                mapped[canonical] = value
        if not mapped:
            continue
        date_str = _as_date(mapped.get("date"), default_date)
        session = sessions.setdefault(
            date_str,
            {"date": date_str, "body_required": {}, "psych_required": {}, "optional": {}},
        )
        minutes = _as_float(mapped.get("resistance_minutes"))
        if minutes is not None:
            session["body_required"]["resistance_minutes"] = minutes
            session["body_required"]["resistance_done"] = minutes >= 20
        elif "resistance_done" in mapped:
            done = _as_bool(mapped.get("resistance_done"))
            if done is not None:
                session["body_required"]["resistance_done"] = done
        protein = _as_float(mapped.get("protein_g"))
        if protein is not None:
            session["body_required"]["protein_g"] = protein
        if "progressive_overload" in mapped:
            overload = _as_bool(mapped.get("progressive_overload"))
            if overload is not None:
                session["body_required"]["progressive_overload"] = overload
        rating = _as_float(mapped.get("self_rating"))
        if rating is not None and 1 <= rating <= 5:
            session["psych_required"]["self_rating_1_to_5"] = rating
        feedback = str(mapped.get("feedback_category") or "").strip()
        if feedback in VALID_FEEDBACK:
            session["psych_required"]["feedback_category"] = feedback
        _store_scaled_optional(session, "anti_inflammatory_diet", "饮食质量", mapped.get("anti_inflammatory_diet"))
        _store_scaled_optional(session, "stress_relief", "日常压力", mapped.get("stress_relief"))
        _store_scaled_optional(session, "focus_state", "注意力", mapped.get("focus_state"))
        sleep_hours = _as_float(mapped.get("sleep_hours"))
        if sleep_hours is not None:
            session["optional"]["睡眠时长"] = {"hours": sleep_hours}
            session["optional"]["sleep_quality"] = round(min(max(sleep_hours / 7.5, 0.0), 1.0), 3)
        steps = _as_float(mapped.get("steps"))
        if steps is not None:
            session["optional"]["日常步数"] = {"actual": steps, "target": 8000}
            session["optional"]["cardio_activity"] = round(min(max(steps / 8000.0, 0.0), 1.0), 3)
        heart_rate = _as_float(mapped.get("resting_hr"))
        if heart_rate is not None:
            ratio = 1.0 if 48 <= heart_rate <= 75 else round(max(1.0 - (heart_rate - 75) / 40.0, 0.2), 3)
            session["optional"]["基础机能"] = {"actual": ratio, "target": 1}
            session["optional"]["vital_signs"] = ratio
    return list(sessions.values())


def _store_scaled_optional(session: dict[str, Any], english: str, chinese: str, value: Any) -> None:
    number = _as_float(value)
    if number is None:
        return
    if 1 < number <= 5:
        session["optional"][chinese] = number
        session["optional"][english] = round(number / 5.0, 3)
        return
    ratio = min(max(number, 0.0), 1.0)
    session["optional"][english] = round(ratio, 3)
    session["optional"][chinese] = {"actual": ratio, "target": 1}


class LLMExtractor:
    def __init__(self) -> None:
        self.api_url = os.environ.get(
            "LLM_API_URL",
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        )
        self.api_key = os.environ.get("LLM_API_KEY", "")
        self.model = os.environ.get("LLM_MODEL", "gemini-2.5-flash")

    def extract_from_text_or_image(
        self,
        text: str,
        date_str: str | None = None,
        image_base64: str | None = None,
        image_mime: str = "image/jpeg",
    ) -> dict[str, Any]:
        target_date = (date_str or datetime.date.today().isoformat())[:10]
        if self.api_key:
            try:
                extracted = self._call_remote_api(text, target_date, image_base64, image_mime)
            except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError, ValueError):
                extracted = self._heuristic_extract(text, target_date)
                extracted["api_warning"] = "远程 API 异常，已降级为本地规则提取。"
        else:
            extracted = self._heuristic_extract(text, target_date)
            if image_base64:
                extracted["image_note"] = "未配置 LLM_API_KEY，图片没有识别，只保留了说明文字。"
        return _attach_known_flags(extracted)

    def _call_remote_api(
        self,
        text: str,
        target_date: str,
        image_base64: str | None,
        image_mime: str,
    ) -> dict[str, Any]:
        user_content: list[dict[str, Any]] = [
            {"type": "text", "text": f"打卡日期: {target_date}\n用户自述: {text}"}
        ]
        if image_base64:
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{image_mime};base64,{image_base64}"},
                }
            )
        body = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.1,
        }
        request = urllib.request.Request(
            self.api_url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        content = payload["choices"][0]["message"]["content"]
        parsed = json.loads(_strip_json_fence(content))
        if not isinstance(parsed, dict):
            raise ValueError("extractor returned a non-object")
        parsed["date"] = str(parsed.get("date") or target_date)[:10]
        parsed["raw_text"] = text
        return parsed

    def _heuristic_extract(self, text: str, target_date: str) -> dict[str, Any]:
        body: dict[str, Any] = {}
        psych: dict[str, Any] = {}
        optional: dict[str, Any] = {}
        protein = re.search(r"蛋白(?:质)?\s*[:：约]?\s*(\d+(?:\.\d+)?)\s*(?:g|克)?", text, re.I)
        if protein:
            body["protein_g"] = float(protein.group(1))
        trained = re.search(r"练了?(腿|胸|背)|撸铁|抗阻|力量训练|深蹲|卧推|硬拉", text)
        minutes = re.search(r"(?:力量训练|抗阻|练了)\s*(\d+(?:\.\d+)?)\s*分钟", text)
        if minutes:
            body["resistance_minutes"] = float(minutes.group(1))
            body["resistance_done"] = body["resistance_minutes"] >= 20
        elif trained:
            body["resistance_done"] = True
        elif any(word in text for word in ("没练", "休息日", "未训练")):
            body["resistance_done"] = False
        if re.search(r"超负荷|加了?重量|破纪录|PR|多做了一组|加重", text):
            body["progressive_overload"] = True
        rating = re.search(r"(?:状态|心情|执行力|自评)\s*[:：打]?\s*([1-5](?:\.\d+)?)\s*分?", text)
        if rating:
            psych["self_rating_1_to_5"] = float(rating.group(1))
        if any(word in text for word in ("听取建议", "改了", "采纳", "复盘改进", "kept_and_changed")):
            psych["feedback_category"] = "kept_and_changed"
        elif any(word in text for word in ("无视喷子", "左耳进右耳出", "不内耗", "屏蔽恶意", "discarded_insult")):
            psych["feedback_category"] = "discarded_insult"
        elif any(word in text for word in ("内耗", "钻牛角尖", "invalid")):
            psych["feedback_category"] = "invalid"
        sleep = re.search(r"睡了?\s*(\d+(?:\.\d+)?)\s*小时", text)
        if sleep:
            hours = float(sleep.group(1))
            optional["睡眠时长"] = {"hours": hours}
            optional["sleep_quality"] = round(min(hours / 7.5, 1.0), 3)
        if any(word in text for word in ("抗炎", "深海鱼", "蓝莓", "西兰花", "少油少糖", "沙拉")):
            optional["anti_inflammatory_diet"] = 1.0
            optional["饮食质量"] = 5
        if any(word in text for word in ("压力缓解", "放松了", "不焦虑", "冥想")):
            optional["stress_relief"] = 1.0
            optional["日常压力"] = 5
        if any(word in text for word in ("很专注", "专注力好", "注意力集中")):
            optional["focus_state"] = 1.0
            optional["注意力"] = 5
        return {
            "date": target_date,
            "raw_text": text,
            "red_flags": [],
            "body_required": body,
            "psych_required": psych,
            "optional": optional,
            "pet_reply": "收到啦，今天的记录我先归档。",
        }


def _strip_json_fence(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    return text


def _attach_known_flags(extracted: dict[str, Any]) -> dict[str, Any]:
    flags = [str(flag) for flag in extracted.get("red_flags") or [] if str(flag).strip()]
    for item in score_checkin.collect_red_flag_details([extracted]):
        if item["flag"] not in flags:
            flags.append(item["flag"])
    extracted["red_flags"] = flags
    return extracted


def score_library(repo: MemoryRepository) -> dict[str, Any]:
    if not repo.bound:
        return {
            "mode": "blocked_profile",
            "missing_profile": list(score_checkin.REQUIRED_PROFILE),
            "scores": None,
            "error": "记忆库未绑定。在仓库根写入 .memory-path，或设置 HEALTH_MEMORY_PATH。",
        }
    return score_checkin.score_payload(
        {"profile": repo.load_profile(), "sessions": repo.load_recent_sessions(14)}
    )


def build_vpet_greeting(repo: MemoryRepository, target_date: str | None = None) -> dict[str, Any]:
    date_str = (target_date or datetime.date.today().isoformat())[:10]
    if not repo.bound:
        return {
            "date": date_str,
            "error": "记忆库未绑定。在仓库根写入 .memory-path，或设置 HEALTH_MEMORY_PATH。",
            "vpet_bubble_text": "还没有绑定记忆库，我先不记今天的打卡。",
            "vpet_suggested_action": "Nomal",
        }
    sessions = repo.load_recent_sessions(14)
    flags = score_checkin.collect_red_flags(sessions)
    distinct_dates, _span = score_checkin.compute_calendar_span(sessions)
    if flags:
        return {
            "date": date_str,
            "distinct_dates_collected": distinct_dates,
            "red_flags": flags,
            "vpet_bubble_text": "记录里有需要马上处理的信号。先联系医疗或当地紧急帮助，我先不打分。",
            "vpet_suggested_action": "Ill",
        }
    gaps = score_checkin.inspect_daily_gaps(sessions, date_str)
    missing = gaps["missing_required_fields"]
    if not missing:
        bubble = f"今天 5 项核心记录都在。目前累计 {distinct_dates}/7 天。"
        action = "Happy"
    elif len(missing) == 5:
        bubble = (
            f"今天还没有健康记录（当前累计 {distinct_dates}/7 天）。"
            "可以告诉我蛋白质、力量训练和今天的状态，也可以拖入手表或手机导出的表格。"
        )
        action = "Nomal"
    else:
        first_missing = missing[0].split("(", 1)[1].rstrip(")") if "(" in missing[0] else missing[0]
        bubble = (
            f"今天完成了 {int(gaps['required_completion_ratio'] * 100)}%。"
            f"还差【{first_missing}】。"
        )
        action = "Nomal"
    return {
        "date": date_str,
        "distinct_dates_collected": distinct_dates,
        "days_needed_for_full_score": max(7 - distinct_dates, 0),
        "today_completion_ratio": gaps["required_completion_ratio"],
        "missing_required_fields": missing,
        "vpet_bubble_text": bubble,
        "vpet_suggested_action": action,
    }


def map_score_to_vpet_state(eval_result: dict[str, Any]) -> dict[str, Any]:
    mode = eval_result.get("mode")
    if mode == "redflag":
        message = (eval_result.get("next_steps") or ["先联系医疗或当地紧急帮助。本轮不打分。"])[0]
        return {
            "animation_state": "Ill",
            "mood_delta": -20,
            "health_buff": "红旗：先停止加练，并联系医疗或当地紧急帮助",
            "bubble_message": message,
        }
    if mode == "under7":
        ratio = float((eval_result.get("daily_progress") or {}).get("required_completion_ratio") or 0)
        return {
            "animation_state": "Happy" if ratio >= 0.8 else "Nomal",
            "mood_delta": int(ratio * 10),
            "health_buff": f"周期收集中 ({eval_result.get('distinct_dates', 0)}/7天)",
            "bubble_message": eval_result.get("label") or "",
        }
    if mode == "scored":
        scores = eval_result.get("scores") or {}
        total = (scores.get("total") or {}).get("score")
        if total is None:
            return {
                "animation_state": "Nomal",
                "mood_delta": 0,
                "health_buff": "必填未齐，总分不合成",
                "bubble_message": "这一窗还不能合成总分。",
            }
        body = (scores.get("body") or {}).get("score")
        psych = (scores.get("psych") or {}).get("score")
        return {
            "animation_state": "Happy" if total >= 150 else "Nomal",
            "mood_delta": 25 if total >= 150 else 10,
            "health_buff": f"薄肌+黄毛周评: {total}/200分",
            "bubble_message": f"满 7 天的评估出来了。总分 {total}/200（身体 {body} / 心理 {psych}）。",
        }
    return {
        "animation_state": "PoorCondition",
        "mood_delta": 0,
        "health_buff": "个人档案还没补齐",
        "bubble_message": "档案缺字段，先补齐再记。缺的字段不能估算。",
    }


class HealthAssistantHTTPHandler(BaseHTTPRequestHandler):
    repo: MemoryRepository | None = None
    extractor: LLMExtractor | None = None

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, data: dict[str, Any], status_code: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _path(self) -> str:
        return self.path.split("?", 1)[0]

    def _read_json(self) -> dict[str, Any] | None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length < 0 or length > MAX_BODY_BYTES:
            self._send_json({"error": "请求体过大。"}, 413)
            return None
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json({"error": "请求体不是 JSON。"}, 400)
            return None
        if not isinstance(data, dict):
            self._send_json({"error": "请求体必须是 JSON 对象。"}, 400)
            return None
        return data

    def _ready(self) -> MemoryRepository | None:
        if self.repo is None or self.extractor is None or self.repo.root is None:
            self._send_json({"error": "服务还没准备好。"}, 500)
            return None
        return self.repo

    def do_GET(self) -> None:
        path = self._path()
        repo = self._ready()
        if repo is None:
            return
        if path == "/api/greeting":
            query = parse_qs(urlsplit(self.path).query)
            requested = query.get("date") or [None]
            self._send_json(build_vpet_greeting(repo, requested[0]))
            return
        if path == "/api/score":
            result = score_library(repo)
            result["vpet_state"] = map_score_to_vpet_state(result)
            self._send_json(result)
            return
        if path == "/api/profile":
            profile = repo.load_profile()
            missing = score_checkin.missing_profile(profile)
            self._send_json({"profile": profile, "missing_profile": missing, "complete": not missing})
            return
        if path == "/api/settings":
            self._send_json(mac_dashboard_ui.read_app_config())
            return
        if path == "/ui":
            self._send_html(mac_dashboard_ui.DASHBOARD_HTML)
            return
        self._send_json({"error": "Not Found"}, 404)

    def do_POST(self) -> None:
        path = self._path()
        req_json = self._read_json()
        if req_json is None:
            return
        repo = self._ready()
        if repo is None:
            return
        try:
            if path == "/api/checkin/text":
                self._handle_text(req_json)
            elif path == "/api/checkin/file":
                self._handle_file(req_json)
            elif path == "/api/bind-library":
                self._handle_bind(req_json)
            elif path == "/api/profile":
                self._handle_profile(req_json)
            elif path == "/api/settings":
                self._handle_settings(req_json)
            else:
                self._send_json({"error": "Unknown POST endpoint"}, 404)
        except RuntimeError as exc:
            self._send_json({"error": str(exc)}, 409)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, 400)

    def _handle_bind(self, req_json: dict[str, Any]) -> None:
        raw_path = str(req_json.get("memory_path") or "").strip()
        if not raw_path or "\x00" in raw_path:
            raise ValueError("memory_path 不能为空。")
        target = Path(raw_path).expanduser()
        if not target.is_absolute():
            target = Path.cwd() / target
        target = target.resolve()
        if target == Path(target.anchor):
            raise ValueError("不能把记忆库绑到磁盘根目录。")
        Path(".memory-path").write_text(str(target) + "\n", encoding="utf-8")
        repo = MemoryRepository(str(target))
        type(self).repo = repo
        self.repo = repo
        self._send_json({"memory_path": str(target), "bound": True})

    def _handle_profile(self, req_json: dict[str, Any]) -> None:
        repo = self.repo
        if repo is None:
            return
        incoming = req_json.get("profile") if isinstance(req_json.get("profile"), dict) else req_json
        if not isinstance(incoming, dict):
            self._send_json({"error": "档案必须是 JSON 对象。"}, 400)
            return
        profile, missing, invalid = validate_profile_payload(incoming)
        if profile is None:
            self._send_json(
                {"error": "档案缺字段或字段不合法，不能估算。", "missing_profile": missing, "invalid_fields": invalid},
                400,
            )
            return
        saved = repo.save_profile(profile)
        evaluation = score_library(repo)
        evaluation["vpet_state"] = map_score_to_vpet_state(evaluation)
        evaluation["profile"] = saved
        self._send_json(evaluation)

    def _handle_settings(self, req_json: dict[str, Any]) -> None:
        saved = mac_dashboard_ui.save_app_config(req_json)
        repo = MemoryRepository(str(saved["memory_path"]))
        type(self).repo = repo
        self.repo = repo
        extractor = LLMExtractor()
        type(self).extractor = extractor
        self.extractor = extractor
        self._send_json({"ok": True, "settings": mac_dashboard_ui.read_app_config(), "memory_path": str(repo.root)})

    def _handle_text(self, req_json: dict[str, Any]) -> None:
        extracted = self.extractor.extract_from_text_or_image(
            text=str(req_json.get("text") or ""),
            date_str=req_json.get("date"),
        )
        stored = _public_session(extracted)
        merged = self.repo.merge_and_save_session(stored, source_type="self_report")
        evaluation = score_library(self.repo)
        self.repo.write_analysis(str(merged.get("date")), evaluation)
        self._send_json(
            {
                "merged_session": merged,
                "pet_reply": extracted.get("pet_reply"),
                "evaluation": evaluation,
                "vpet_state": map_score_to_vpet_state(evaluation),
            }
        )

    def _handle_file(self, req_json: dict[str, Any]) -> None:
        filename = Path(str(req_json.get("filename") or "upload.csv")).name
        file_b64 = str(req_json.get("file_base64") or "")
        try:
            file_bytes = base64.b64decode(file_b64, validate=True) if file_b64 else b""
        except ValueError:
            self._send_json({"error": "file_base64 无法解码。"}, 400)
            return
        if len(file_bytes) > 8 * 1024 * 1024:
            self._send_json({"error": "文件超过 8MB。"}, 413)
            return
        suffix = Path(filename).suffix.lower()
        if suffix in {".csv", ".xlsx"}:
            parsed = parse_health_table_bytes(file_bytes, filename, default_date=req_json.get("date"))
            merged_list = [self.repo.merge_and_save_session(item, source_type="wearable_table") for item in parsed]
            evaluation = score_library(self.repo)
            if merged_list:
                self.repo.write_analysis(str(merged_list[-1].get("date")), evaluation)
            self._send_json(
                {
                    "file_type": "table",
                    "imported_days": len(merged_list),
                    "sessions": merged_list,
                    "evaluation": evaluation,
                    "vpet_state": map_score_to_vpet_state(evaluation),
                }
            )
            return
        extracted = self.extractor.extract_from_text_or_image(
            text=str(req_json.get("caption") or "请识别图片中的饮食或训练记录"),
            date_str=req_json.get("date"),
            image_base64=file_b64 or None,
            image_mime=str(req_json.get("mime") or "image/jpeg"),
        )
        merged = self.repo.merge_and_save_session(_public_session(extracted), source_type="image_ocr")
        evaluation = score_library(self.repo)
        self.repo.write_analysis(str(merged.get("date")), evaluation)
        self._send_json(
            {
                "file_type": "image",
                "image_note": extracted.get("image_note"),
                "merged_session": merged,
                "evaluation": evaluation,
                "vpet_state": map_score_to_vpet_state(evaluation),
            }
        )


def validate_profile_payload(raw: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    profile = dict(raw)
    missing = [key for key in score_checkin.REQUIRED_PROFILE if key not in profile or profile[key] is None or profile[key] == ""]
    invalid: list[str] = []
    if "sex" not in missing:
        sex = str(profile.get("sex", "")).strip().lower()
        if sex not in VALID_SEX:
            invalid.append("sex")
        else:
            profile["sex"] = sex
    for key in ("height_cm", "weight_kg", "age", "training_years"):
        if key in missing:
            continue
        value = profile.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            invalid.append(key)
    if "injury" not in missing and not isinstance(profile.get("injury"), bool):
        invalid.append("injury")
    if missing or invalid:
        return None, missing, invalid
    return profile, [], []


def _public_session(extracted: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": extracted.get("date"),
        "raw_text": extracted.get("raw_text") or "",
        "red_flags": extracted.get("red_flags") or [],
        "body_required": extracted.get("body_required") or {},
        "psych_required": extracted.get("psych_required") or {},
        "optional": extracted.get("optional") or {},
    }


def make_server(host: str, port: int, repo: MemoryRepository | None = None) -> ThreadingHTTPServer:
    if host not in LOOPBACK_HOSTS:
        raise SystemExit("只允许监听本机回环地址。")
    handler = type("BoundHealthHandler", (HealthAssistantHTTPHandler,), {})
    handler.repo = repo or MemoryRepository()
    handler.extractor = LLMExtractor()
    return ThreadingHTTPServer((host, port), handler)


def api_port() -> int:
    raw = os.environ.get("HEALTH_API_PORT", "").strip()
    if not raw:
        return DEFAULT_PORT
    try:
        port = int(raw)
    except ValueError:
        return DEFAULT_PORT
    if 0 < port < 65536:
        return port
    return DEFAULT_PORT


def run_server(host: str = DEFAULT_HOST, port: int | None = None) -> None:
    mac_dashboard_ui.prepare_process_environment()
    chosen = DEFAULT_PORT if port is None else port
    server = make_server(host, chosen)
    print(f"[Health-Assessment API] http://{host}:{chosen}")
    server.serve_forever()


if __name__ == "__main__":
    run_server(host=os.environ.get("HEALTH_API_HOST", DEFAULT_HOST), port=api_port())
