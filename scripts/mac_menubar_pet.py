#!/usr/bin/env python3
"""macOS menu bar companion for the local health API.

Requires rumps on macOS:

    python3 -m pip install --user rumps

Then:

    python3 scripts/mac_menubar_pet.py
"""

from __future__ import annotations

import atexit
import base64
import datetime
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import health_api_server
import mac_dashboard_ui

API_PORT = int(os.environ.get("HEALTH_API_PORT", "8765") or "8765")
API_BASE = f"http://127.0.0.1:{API_PORT}"
SCRIPT_DIR = Path(__file__).resolve().parent
SERVER_SCRIPT = SCRIPT_DIR / "health_api_server.py"
REPO_ROOT = SCRIPT_DIR.parent


def asset_path(name: str) -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
        return base / "assets" / name
    return REPO_ROOT / "assets" / name

try:
    import rumps  # type: ignore

    HAS_RUMPS = True
except ImportError:
    rumps = None
    HAS_RUMPS = False


class BackendProcessManager:
    """Start scripts/health_api_server.py when the loopback API is down."""

    def __init__(self) -> None:
        self.proc: subprocess.Popen[bytes] | None = None
        self._httpd: Any = None
        self._thread: threading.Thread | None = None
        atexit.register(self.stop)

    def is_alive(self) -> bool:
        request = urllib.request.Request(f"{API_BASE}/api/greeting", method="GET")
        try:
            with urllib.request.urlopen(request, timeout=1.5) as response:
                return response.status == 200
        except (urllib.error.URLError, TimeoutError, OSError):
            return False

    def ensure_running(self) -> bool:
        if self.is_alive():
            return True
        mac_dashboard_ui.prepare_process_environment()
        if getattr(sys, "frozen", False):
            return self._start_embedded()
        if not SERVER_SCRIPT.is_file():
            return False
        env = os.environ.copy()
        env["HEALTH_API_PORT"] = str(API_PORT)
        env["HEALTH_API_HOST"] = "127.0.0.1"
        self.proc = subprocess.Popen(
            [sys.executable, str(SERVER_SCRIPT)],
            cwd=str(REPO_ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(20):
            time.sleep(0.25)
            if self.is_alive():
                return True
            if self.proc.poll() is not None:
                return False
        return False

    def _start_embedded(self) -> bool:
        """PyInstaller replaces sys.executable with the app binary, so the API stays in-process."""
        if self._thread is not None and self._thread.is_alive():
            return self.is_alive()

        def serve() -> None:
            try:
                self._httpd = health_api_server.make_server("127.0.0.1", API_PORT)
                self._httpd.serve_forever()
            except OSError:
                self._httpd = None

        self._thread = threading.Thread(target=serve, name="health-api", daemon=True)
        self._thread.start()
        for _ in range(40):
            time.sleep(0.1)
            if self.is_alive():
                return True
        return False

    def stop(self) -> None:
        httpd = self._httpd
        if httpd is not None:
            self._httpd = None
            httpd.shutdown()
            httpd.server_close()
        if self.proc is None or self.proc.poll() is not None:
            return
        self.proc.terminate()
        try:
            self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def api_get(path: str) -> dict[str, Any]:
    request = urllib.request.Request(f"{API_BASE}{path}", method="GET")
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("接口没有返回 JSON 对象")
    return payload


def api_post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{API_BASE}{path}",
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        parsed = json.loads(response.read().decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("接口没有返回 JSON 对象")
    return parsed


def applescript_text(value: str) -> str:
    parts = value.replace("\\", "\\\\").replace('"', '\\"').splitlines() or [""]
    return " & return & ".join(f'"{part}"' for part in parts)


def macos_notify(title: str, subtitle: str, message: str) -> None:
    script = (
        f"display notification {applescript_text(message)} "
        f"with title {applescript_text(title)} subtitle {applescript_text(subtitle)} sound name \"Glass\""
    )
    subprocess.run(["osascript", "-e", script], check=False)


def macos_prompt_input(prompt_text: str, default_text: str = "") -> str | None:
    script = (
        "set userResponse to display dialog "
        f"{applescript_text(prompt_text)} "
        f"default answer {applescript_text(default_text)} "
        'with title "薄肌与黄毛健康助手 - 今日打卡" '
        'buttons {"取消", "提交打卡"} default button "提交打卡"\n'
        "return text returned of userResponse"
    )
    completed = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def macos_choose_file() -> Path | None:
    script = (
        'set theFile to choose file with prompt "请选择手表或手机导出的 CSV、Excel，或饮食与训练截图：" '
        'of type {"csv", "xlsx", "png", "jpg", "jpeg", "webp"}\n'
        "return POSIX path of theFile"
    )
    completed = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    return Path(completed.stdout.strip())


def macos_alert(title: str, message: str) -> None:
    script = (
        f"display dialog {applescript_text(message)} with title {applescript_text(title)} "
        'buttons {"知道了"} default button "知道了"'
    )
    subprocess.run(["osascript", "-e", script], check=False)


def _nested_score(data: dict[str, Any], key: str) -> float | None:
    section = (data.get("scores") or {}).get(key) or {}
    value = section.get("score")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def format_menubar_title(eval_data: dict[str, Any]) -> str:
    mode = eval_data.get("mode")
    if mode == "redflag":
        return "🚨 红旗预警"
    if mode == "blocked_profile":
        return "📋 待建档"
    if mode == "scored":
        total = _nested_score(eval_data, "total")
        if total is None:
            return "🐾 缺必填项"
        icon = "💪" if total >= 150 else "🐾"
        return f"{icon} {total:.0f}/200分"
    days = int(eval_data.get("distinct_dates") or 0)
    ratio = float((eval_data.get("daily_progress") or {}).get("required_completion_ratio") or 0)
    percent = int(ratio * 100)
    icon = "😄" if percent >= 80 else "🐾"
    return f"{icon} {days}/7天({percent}%)"


def format_score_report(data: dict[str, Any]) -> str:
    mode = data.get("mode")
    distinct_dates = int(data.get("distinct_dates") or 0)
    span_days = int(data.get("calendar_span_days") or distinct_dates)
    gaps = data.get("daily_progress") or {}
    missing = gaps.get("missing_required_fields") or []
    missing_text = "\n  - ".join(str(item) for item in missing) if missing else "无（今日必填已经齐了）"
    if mode == "scored":
        return (
            "【满 7 天周期评估】\n"
            f"• 累计打卡：{distinct_dates} 天（自然日跨度 {span_days} 天）\n"
            f"• 周期总分：{_nested_score(data, 'total')} / 200 分\n"
            f"• 身体（薄肌）：{_nested_score(data, 'body')} / 100 分\n"
            f"• 心理（黄毛）：{_nested_score(data, 'psych')} / 100 分\n\n"
            f"【今日（{gaps.get('target_date', '')}）未补齐项】\n  - {missing_text}"
        )
    if mode == "redflag":
        details = data.get("red_flag_details") or []
        if details and isinstance(details[0], dict):
            flags = ", ".join(f"{item.get('date')}:{item.get('flag')}" for item in details)
        else:
            flags = ", ".join(str(item) for item in (data.get("red_flags") or []))
        return f"触发红旗：{flags}\n先联系医疗或当地紧急帮助。这轮不打分。"
    remaining = max(7 - distinct_dates, 0)
    percent = int(float(gaps.get("required_completion_ratio") or 0) * 100)
    return (
        "【未满 7 天，不出总分】\n"
        f"• 当前累计：{distinct_dates} / 7 天（还差 {remaining} 天）\n"
        f"• 今日完成度：{percent}%\n\n"
        f"【今日还缺】\n  - {missing_text}"
    )


def status_line(data: dict[str, Any]) -> str:
    vpet = data.get("vpet_state") or {}
    return str(vpet.get("health_buff") or data.get("label") or data.get("mode") or "运行中")


if HAS_RUMPS:

    class HealthMenuBarPet(rumps.App):
        def __init__(self) -> None:
            icon = asset_path("menubar_icon.png")
            icon_file = str(icon) if icon.is_file() else None
            super().__init__(
                "HealthAssessment",
                title="🐾 健康助手",
                icon=icon_file,
                template=True if icon_file else None,
                quit_button=None,
            )
            self.backend = BackendProcessManager()
            self._opened_setup = False
            self.status_item = rumps.MenuItem("状态: 正在连接本地健康服务...")
            self.menu = [
                rumps.MenuItem("打开健康助手主界面与设置...", callback=self.on_open_dashboard),
                self.status_item,
                None,
                rumps.MenuItem("今日文字自述打卡", callback=self.on_text_checkin),
                rumps.MenuItem("导入手表或手机数据", callback=self.on_file_checkin),
                rumps.MenuItem("查看 7 天评估报告", callback=self.on_view_score),
                rumps.MenuItem("现在打招呼", callback=self.on_trigger_greeting),
                None,
                rumps.MenuItem("退出健康桌宠", callback=self.on_quit),
            ]
            self.backend.ensure_running()
            self.refresh_status()
            rumps.Timer(self._startup_greeting, 2).start()

        def on_open_dashboard(self, _: Any) -> None:
            if not self.backend.ensure_running():
                macos_notify("健康桌宠", "主界面没有打开", "本地服务还没起来。")
                return
            mac_dashboard_ui.open_dashboard_window(f"{API_BASE}/ui")

        @rumps.timer(20)
        def poll_status(self, _: Any) -> None:
            self.refresh_status()

        def refresh_status(self) -> dict[str, Any] | None:
            if not self.backend.ensure_running():
                self.title = "⚠️ 服务未启动"
                self.status_item.title = "状态: 无法启动 scripts/health_api_server.py"
                return None
            try:
                data = api_get("/api/score")
            except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
                self.title = "⚠️ 连接异常"
                self.status_item.title = f"状态异常: {exc.__class__.__name__}"
                return None
            self.title = format_menubar_title(data)
            self.status_item.title = "状态: " + status_line(data)
            if data.get("mode") == "blocked_profile" and not self._opened_setup:
                self._opened_setup = True
                mac_dashboard_ui.open_dashboard_window(f"{API_BASE}/ui")
            return data

        @rumps.timer(7200)
        def scheduled_greeting(self, _: Any) -> None:
            self._notify_greeting()

        def _startup_greeting(self, timer: Any) -> None:
            timer.stop()
            self._notify_greeting()

        def _notify_greeting(self) -> None:
            if not self.backend.ensure_running():
                return
            try:
                greeting = api_get("/api/greeting")
            except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
                return
            bubble = str(greeting.get("vpet_bubble_text") or "")
            days = greeting.get("distinct_dates_collected", 0)
            if bubble:
                macos_notify("薄肌与黄毛健康桌宠", f"当前累计 {days}/7 天", bubble)
            self.refresh_status()

        def on_trigger_greeting(self, _: Any) -> None:
            if not self.backend.ensure_running():
                return
            try:
                greeting = api_get("/api/greeting")
            except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
                macos_notify("健康桌宠", "没有连上本地服务", "请看状态栏里的提示。")
                return
            answer = macos_prompt_input(str(greeting.get("vpet_bubble_text") or "今天状态怎么样？"))
            if answer:
                self._submit_text(answer)

        def on_text_checkin(self, _: Any) -> None:
            if not self.backend.ensure_running():
                return
            try:
                greeting = api_get("/api/greeting")
                lead = str(greeting.get("vpet_bubble_text") or "")
            except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
                lead = ""
            prompt = (
                f"{lead}\n\n可以直接说：今天练背加了重量，蛋白145g，睡了7.5小时，心情5分，无视喷子。"
            ).strip()
            answer = macos_prompt_input(prompt)
            if answer:
                self._submit_text(answer)

        def _submit_text(self, text: str) -> None:
            try:
                response = api_post(
                    "/api/checkin/text",
                    {"text": text, "date": datetime.date.today().isoformat()},
                )
            except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
                macos_notify("健康桌宠", "打卡没有送出", "本地服务没有收下这段记录。")
                return
            self.refresh_status()
            vpet = response.get("vpet_state") or {}
            reply = str(response.get("pet_reply") or vpet.get("bubble_message") or "打卡已归档。")
            macos_notify("打卡已记下", str(vpet.get("health_buff") or ""), reply)

        def on_file_checkin(self, _: Any) -> None:
            if not self.backend.ensure_running():
                return
            chosen = macos_choose_file()
            if chosen is None or not chosen.is_file():
                return
            macos_notify("正在解析文件", chosen.name, "正在提取指标并合并到今天的记录。")
            try:
                response = api_post(
                    "/api/checkin/file",
                    {
                        "filename": chosen.name,
                        "file_base64": base64.b64encode(chosen.read_bytes()).decode("ascii"),
                        "date": datetime.date.today().isoformat(),
                    },
                )
            except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
                macos_alert("文件没有导入", f"{chosen.name} 没有被本地服务收下。")
                return
            self.refresh_status()
            vpet = response.get("vpet_state") or {}
            macos_alert(
                "健康文件已导入",
                f"文件：{chosen.name}\n状态：{vpet.get('health_buff', '')}\n反馈：{vpet.get('bubble_message', '已合并入库')}",
            )

        def on_view_score(self, _: Any) -> None:
            data = self.refresh_status()
            if not data:
                return
            macos_alert("薄肌与黄毛健康评估", format_score_report(data))

        def on_quit(self, _: Any) -> None:
            self.backend.stop()
            rumps.quit_application()


def main() -> None:
    if sys.platform != "darwin":
        print("scripts/mac_menubar_pet.py 只在 macOS 菜单栏运行。")
        sys.exit(1)
    if not HAS_RUMPS:
        print("请先安装菜单栏库 rumps：\n  python3 -m pip install --user rumps\n然后运行：\n  python3 scripts/mac_menubar_pet.py")
        sys.exit(1)
    if not mac_dashboard_ui.acquire_pet_lock():
        print("健康桌宠已经在运行。")
        sys.exit(0)
    HealthMenuBarPet().run()


if __name__ == "__main__":
    main()
