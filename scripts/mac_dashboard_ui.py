#!/usr/bin/env python3
"""macOS dashboard, Application Support config, and login LaunchAgent."""

from __future__ import annotations

import json
import os
import plistlib
import subprocess
import sys
from pathlib import Path
from typing import Any

LABEL = "com.songhangze.healthassessment"
_LOCK_HANDLE: Any = None


def app_support_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / "HealthAssessment"


def config_file() -> Path:
    return app_support_dir() / "config.json"


def default_memory_dir() -> Path:
    return app_support_dir() / "memory_store"


def launch_agent_plist() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def pet_lock_path() -> Path:
    return app_support_dir() / "pet.lock"


def default_config() -> dict[str, Any]:
    return {
        "memory_path": str(default_memory_dir()),
        "llm_api_key": os.environ.get("LLM_API_KEY", ""),
        "llm_api_url": os.environ.get(
            "LLM_API_URL",
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        ),
        "llm_model": os.environ.get("LLM_MODEL", "gemini-2.5-flash"),
        "auto_start_on_login": False,
        "profile": {},
    }


def read_app_config() -> dict[str, Any]:
    app_support_dir().mkdir(parents=True, exist_ok=True)
    cfg = default_config()
    path = config_file()
    if path.is_file():
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            saved = None
        if isinstance(saved, dict):
            for key in ("memory_path", "llm_api_key", "llm_api_url", "llm_model", "auto_start_on_login"):
                if key in saved:
                    cfg[key] = saved[key]
            if isinstance(saved.get("profile"), dict):
                cfg["profile"] = dict(saved["profile"])
    cfg["auto_start_on_login"] = bool(cfg.get("auto_start_on_login"))
    return cfg


def apply_config_to_env(cfg: dict[str, Any]) -> None:
    memory = str(cfg.get("memory_path") or "").strip()
    if memory:
        Path(memory).expanduser().mkdir(parents=True, exist_ok=True)
        os.environ["HEALTH_MEMORY_PATH"] = str(Path(memory).expanduser())
    if "llm_api_key" in cfg:
        os.environ["LLM_API_KEY"] = str(cfg.get("llm_api_key") or "").strip()
    if cfg.get("llm_api_url"):
        os.environ["LLM_API_URL"] = str(cfg["llm_api_url"]).strip()
    if cfg.get("llm_model"):
        os.environ["LLM_MODEL"] = str(cfg["llm_model"]).strip()


def load_app_config() -> dict[str, Any]:
    cfg = read_app_config()
    apply_config_to_env(cfg)
    return cfg


def prepare_process_environment() -> None:
    """Installed apps and saved configs must not write inside the read-only bundle."""
    if getattr(sys, "frozen", False) or config_file().is_file():
        load_app_config()


def normalize_memory_path(raw: str) -> Path:
    if not str(raw).strip() or "\x00" in str(raw):
        raise ValueError("memory_path 不能为空。")
    target = Path(str(raw)).expanduser()
    if not target.is_absolute():
        target = app_support_dir() / target
    target = target.resolve()
    if target == Path(target.anchor):
        raise ValueError("不能把记忆库绑到磁盘根目录。")
    target.mkdir(parents=True, exist_ok=True)
    return target


def save_app_config(new_cfg: dict[str, Any]) -> dict[str, Any]:
    cfg = read_app_config()
    if str(new_cfg.get("memory_path") or "").strip():
        cfg["memory_path"] = str(normalize_memory_path(str(new_cfg["memory_path"])))
    if "llm_api_key" in new_cfg:
        cfg["llm_api_key"] = str(new_cfg.get("llm_api_key") or "").strip()
    if str(new_cfg.get("llm_api_url") or "").strip():
        cfg["llm_api_url"] = str(new_cfg["llm_api_url"]).strip()
    if str(new_cfg.get("llm_model") or "").strip():
        cfg["llm_model"] = str(new_cfg["llm_model"]).strip()
    if "auto_start_on_login" in new_cfg:
        cfg["auto_start_on_login"] = bool(new_cfg.get("auto_start_on_login"))
    if isinstance(new_cfg.get("profile"), dict):
        kept: dict[str, Any] = {}
        for key in ("height_cm", "weight_kg", "age", "sex", "training_years", "injury"):
            if key in new_cfg["profile"]:
                kept[key] = new_cfg["profile"][key]
        cfg["profile"] = kept
    app_support_dir().mkdir(parents=True, exist_ok=True)
    config_file().write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    apply_config_to_env(cfg)
    configure_launch_agent(bool(cfg.get("auto_start_on_login")))
    return cfg


def _program_arguments() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable]
    pet_script = Path(__file__).resolve().parent / "mac_menubar_pet.py"
    return [sys.executable, str(pet_script)]


def _launchctl(args: list[str]) -> None:
    subprocess.run(
        ["launchctl", *args],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def pet_is_running() -> bool:
    path = pet_lock_path()
    if not path.exists():
        return False
    import fcntl

    handle = path.open("a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return True
    else:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return False
    finally:
        handle.close()


def acquire_pet_lock() -> bool:
    """Keep a second login-item instance from opening another status icon."""
    global _LOCK_HANDLE
    import fcntl

    app_support_dir().mkdir(parents=True, exist_ok=True)
    handle = pet_lock_path().open("a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return False
    _LOCK_HANDLE = handle
    return True


def configure_launch_agent(enable: bool) -> None:
    """Write ~/Library/LaunchAgents and ask launchctl to pick it up."""
    if sys.platform != "darwin":
        return
    plist_path = launch_agent_plist()
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    domain = f"gui/{os.getuid()}"
    if not enable:
        if os.environ.get("HEALTH_SKIP_LAUNCH_AGENT") != "1":
            _launchctl(["bootout", domain, str(plist_path)])
            _launchctl(["unload", str(plist_path)])
        if plist_path.exists():
            plist_path.unlink()
        return

    payload = {
        "Label": LABEL,
        "ProgramArguments": _program_arguments(),
        "RunAtLoad": True,
        "KeepAlive": False,
        "WorkingDirectory": str(app_support_dir()),
    }
    plist_path.write_bytes(plistlib.dumps(payload))
    if os.environ.get("HEALTH_SKIP_LAUNCH_AGENT") == "1":
        return
    # Booting out a job that is this process would quit the pet mid-save.
    # The plist is enough for the next login; start a copy only when none is running.
    if pet_is_running():
        _launchctl(["enable", f"{domain}/{LABEL}"])
        return
    _launchctl(["bootout", domain, str(plist_path)])
    _launchctl(["unload", str(plist_path)])
    _launchctl(["bootstrap", domain, str(plist_path)])
    _launchctl(["enable", f"{domain}/{LABEL}"])


def open_dashboard_window(url: str = "http://127.0.0.1:8765/ui") -> None:
    """Open the loopback page in a chromeless window, then fall back to the default browser."""
    browsers = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]
    for browser in browsers:
        if Path(browser).is_file():
            subprocess.Popen(
                [browser, f"--app={url}", "--window-size=920,760"],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
    subprocess.run(["open", url], check=False)


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>Health Assessment - 薄肌与黄毛健康助手</title>
<style>
  :root { --bg: #e7eef0; --card: rgba(255,255,255,0.78); --primary: #0f9d76; --text: #1d2939; --muted: #667085; --border: rgba(228,231,236,0.9); }
  * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif; }
  body { margin: 0; padding: 24px; color: var(--text); background: linear-gradient(160deg, #d7ebe4, #e7eef5 45%, #f4f7f6); }
  .container { max-width: 860px; margin: 0 auto; display: grid; gap: 18px; }
  .header, .card { backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px); }
  .header { display: flex; justify-content: space-between; align-items: center; background: linear-gradient(135deg, rgba(15,157,118,0.92), rgba(20,122,133,0.92)); color: #fff; padding: 18px 24px; border-radius: 14px; }
  .header h1 { margin: 0; font-size: 20px; }
  .badge { background: rgba(255,255,255,0.2); padding: 6px 12px; border-radius: 99px; font-size: 13px; font-weight: 600; }
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 18px; box-shadow: 0 8px 24px rgba(16,24,40,0.06); }
  .card h2 { margin: 0 0 14px 0; font-size: 16px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }
  .form-row { display: grid; grid-template-columns: 110px 1fr; align-items: center; gap: 8px; margin-bottom: 10px; font-size: 13px; }
  input, select, textarea { width: 100%; padding: 8px 10px; border: 1px solid var(--border); border-radius: 8px; font-size: 13px; background: rgba(255,255,255,0.9); }
  button { background: var(--primary); color: #fff; border: none; padding: 9px 16px; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; }
  button:hover { opacity: 0.92; }
  .score-box { display: flex; gap: 12px; margin-bottom: 12px; }
  .metric { flex: 1; background: rgba(248,250,252,0.9); border: 1px solid var(--border); border-radius: 10px; padding: 12px; text-align: center; }
  .metric .val { font-size: 22px; font-weight: 700; color: var(--primary); }
  .metric .lbl { font-size: 12px; color: var(--muted); margin-top: 4px; }
  .bar { height: 6px; border-radius: 99px; background: #e4e7ec; margin-top: 8px; overflow: hidden; }
  .bar > span { display: block; height: 100%; width: 0; background: var(--primary); }
  .status-banner { padding: 10px 12px; border-radius: 8px; background: #ecfdf3; color: #027a48; font-size: 13px; margin-bottom: 12px; }
  #dropZone.drag { outline: 2px dashed var(--primary); }
  @media (max-width: 760px) { .grid-2, .score-box { grid-template-columns: 1fr; display: grid; } }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div>
      <h1>薄肌与黄毛健康助手</h1>
      <div style="font-size:12px;opacity:0.9;margin-top:4px;">保存参数后，本地评估和顶部状态栏会按这份配置运行</div>
    </div>
    <div class="badge" id="modeBadge">正在加载状态...</div>
  </div>

  <div class="card">
    <h2>7 天周期评估看板与今日缺项</h2>
    <div class="status-banner" id="greetingBanner">正在获取今日打卡追问...</div>
    <div class="score-box">
      <div class="metric"><div class="val" id="daysVal">0/7</div><div class="bar"><span id="daysBar"></span></div><div class="lbl">已积累不同日期</div></div>
      <div class="metric"><div class="val" id="totalVal">--</div><div class="bar"><span id="totalBar"></span></div><div class="lbl">周期总分 (200分)</div></div>
      <div class="metric"><div class="val" id="bodyVal">--</div><div class="bar"><span id="bodyBar"></span></div><div class="lbl">身体·薄肌 (100分)</div></div>
      <div class="metric"><div class="val" id="psychVal">--</div><div class="bar"><span id="psychBar"></span></div><div class="lbl">心理·黄毛 (100分)</div></div>
    </div>
    <div style="font-size:13px;color:var(--muted);" id="missingFields"></div>
  </div>

  <div class="grid-2">
    <div class="card" id="dropZone">
      <h2>今日快速打卡</h2>
      <textarea id="checkinText" rows="4" placeholder="例如：今天抗阻训练45分钟并增加了卧推重量，蛋白质吃了145g，睡了7.5小时，心情自评5分，排除恶意评价不内耗"></textarea>
      <div style="margin-top:10px;display:flex;justify-content:space-between;align-items:center;gap:8px;">
        <button type="button" id="textButton">提交文字打卡</button>
        <label style="font-size:12px;color:var(--primary);cursor:pointer;">
          上传或拖入 CSV / Excel / 图片
          <input type="file" id="fileInput" accept=".csv,.xlsx,.png,.jpg,.jpeg,.webp" style="display:none">
        </label>
      </div>
    </div>

    <div class="card">
      <h2>个人身体档案与运行参数</h2>
      <div class="form-row"><label>身高 / 体重</label><div style="display:flex;gap:6px;"><input id="height_cm" type="number" placeholder="身高(cm)"><input id="weight_kg" type="number" step="0.1" placeholder="体重(kg)"></div></div>
      <div class="form-row"><label>年龄 / 性别</label><div style="display:flex;gap:6px;"><input id="age" type="number" placeholder="年龄"><select id="sex"><option value="male">男 (male)</option><option value="female">女 (female)</option><option value="other">其他 (other)</option></select></div></div>
      <div class="form-row"><label>训练年限 / 伤病</label><div style="display:flex;gap:6px;"><input id="training_years" type="number" step="0.5" placeholder="训练年限"><select id="injury"><option value="false">无伤病</option><option value="true">有伤病记录</option></select></div></div>
      <div class="form-row"><label>LLM API Key</label><input id="llm_api_key" type="password" placeholder="可选：留空则使用本地规则提取" autocomplete="off"></div>
      <div class="form-row"><label>记忆库目录</label><input id="memory_path" type="text" placeholder="~/Library/Application Support/HealthAssessment/memory_store"></div>
      <div class="form-row"><label>开机自动运行</label><label style="display:flex;align-items:center;gap:6px;"><input id="auto_start" type="checkbox" style="width:auto;"> 登录 Mac 时自动启动顶部栏桌宠与服务</label></div>
      <button type="button" id="saveButton" style="width:100%;margin-top:6px;">保存配置并立即激活</button>
    </div>
  </div>
</div>
<script>
function scoreOf(data, key) {
  const section = data && data.scores && data.scores[key];
  if (!section || typeof section.score !== "number") return null;
  return section.score;
}
function setBar(id, value, max) {
  const width = value == null || !max ? 0 : Math.max(0, Math.min(100, (value / max) * 100));
  document.getElementById(id).style.width = width + "%";
}
function numberOrNull(id) {
  const raw = document.getElementById(id).value.trim();
  if (!raw) return null;
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}
async function readJson(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = data.error || ("请求失败 " + response.status);
    throw new Error(message);
  }
  return data;
}
async function refreshAll() {
  const [scoreRes, greetRes, profRes, cfgRes] = await Promise.all([
    fetch("/api/score").then(r => r.json()).catch(() => ({})),
    fetch("/api/greeting").then(r => r.json()).catch(() => ({})),
    fetch("/api/profile").then(r => r.json()).catch(() => ({})),
    fetch("/api/settings").then(r => r.json()).catch(() => ({}))
  ]);
  const modeNames = { blocked_profile: "待建档", under7: "未满 7 天", scored: "已评分", redflag: "红旗预警" };
  document.getElementById("modeBadge").textContent = "模式: " + (modeNames[scoreRes.mode] || scoreRes.mode || "unknown");
  document.getElementById("greetingBanner").textContent = greetRes.vpet_bubble_text || "准备就绪";
  const days = Number(scoreRes.distinct_dates || 0);
  const total = scoreOf(scoreRes, "total");
  const body = scoreOf(scoreRes, "body");
  const psych = scoreOf(scoreRes, "psych");
  document.getElementById("daysVal").textContent = days + "/7";
  document.getElementById("totalVal").textContent = total == null ? "--" : String(Math.round(total));
  document.getElementById("bodyVal").textContent = body == null ? "--" : String(Math.round(body));
  document.getElementById("psychVal").textContent = psych == null ? "--" : String(Math.round(psych));
  setBar("daysBar", days, 7);
  setBar("totalBar", total, 200);
  setBar("bodyBar", body, 100);
  setBar("psychBar", psych, 100);
  const missing = (scoreRes.daily_progress && scoreRes.daily_progress.missing_required_fields) || [];
  const missingNode = document.getElementById("missingFields");
  if (scoreRes.mode === "blocked_profile") {
    missingNode.textContent = "请先保存右侧六项身体档案。缺一项就不会开始打分。";
  } else if (missing.length) {
    missingNode.textContent = "今日待补齐必填项：" + missing.join("、");
  } else {
    missingNode.textContent = "今日 5 项核心必填指标已全部集齐。";
  }
  const profile = profRes.profile || {};
  if (profile.height_cm != null) document.getElementById("height_cm").value = profile.height_cm;
  if (profile.weight_kg != null) document.getElementById("weight_kg").value = profile.weight_kg;
  if (profile.age != null) document.getElementById("age").value = profile.age;
  if (profile.sex) document.getElementById("sex").value = profile.sex;
  if (profile.training_years != null) document.getElementById("training_years").value = profile.training_years;
  if (profile.injury != null) document.getElementById("injury").value = String(Boolean(profile.injury));
  if (cfgRes.memory_path) document.getElementById("memory_path").value = cfgRes.memory_path;
  if (cfgRes.llm_api_key != null) document.getElementById("llm_api_key").value = cfgRes.llm_api_key;
  document.getElementById("auto_start").checked = Boolean(cfgRes.auto_start_on_login);
}
async function saveAllSettings() {
  const profile = {
    height_cm: numberOrNull("height_cm"),
    weight_kg: numberOrNull("weight_kg"),
    age: numberOrNull("age"),
    sex: document.getElementById("sex").value,
    training_years: numberOrNull("training_years"),
    injury: document.getElementById("injury").value === "true"
  };
  const settings = {
    memory_path: document.getElementById("memory_path").value.trim(),
    llm_api_key: document.getElementById("llm_api_key").value.trim(),
    auto_start_on_login: document.getElementById("auto_start").checked,
    profile: profile
  };
  try {
    await readJson(await fetch("/api/settings", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(settings)
    }));
    await readJson(await fetch("/api/profile", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(profile)
    }));
  } catch (err) {
    alert(err.message || "没有保存。");
    await refreshAll();
    return;
  }
  await refreshAll();
  alert("配置和个人档案已保存，后台评估已按这份输入运行。");
}
async function submitTextCheckin() {
  const text = document.getElementById("checkinText").value.trim();
  if (!text) return;
  try {
    await readJson(await fetch("/api/checkin/text", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ text: text })
    }));
  } catch (err) {
    alert(err.message || "打卡没有送出。");
    return;
  }
  document.getElementById("checkinText").value = "";
  await refreshAll();
}
async function uploadFile(file) {
  if (!file) return;
  const reader = new FileReader();
  reader.onload = async () => {
    const raw = String(reader.result || "");
    const b64 = raw.includes(",") ? raw.split(",")[1] : raw;
    try {
      await readJson(await fetch("/api/checkin/file", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ filename: file.name, file_base64: b64 })
      }));
    } catch (err) {
      alert(err.message || "文件没有导入。");
      return;
    }
    await refreshAll();
  };
  reader.readAsDataURL(file);
}
document.getElementById("saveButton").addEventListener("click", saveAllSettings);
document.getElementById("textButton").addEventListener("click", submitTextCheckin);
document.getElementById("fileInput").addEventListener("change", () => {
  const file = document.getElementById("fileInput").files[0];
  uploadFile(file);
});
const dropZone = document.getElementById("dropZone");
["dragenter", "dragover"].forEach((name) => dropZone.addEventListener(name, (event) => {
  event.preventDefault();
  dropZone.classList.add("drag");
}));
["dragleave", "drop"].forEach((name) => dropZone.addEventListener(name, (event) => {
  event.preventDefault();
  dropZone.classList.remove("drag");
}));
dropZone.addEventListener("drop", (event) => {
  const file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
  uploadFile(file);
});
refreshAll();
</script>
</body>
</html>
"""
