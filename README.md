# Health Assessment Skill

[中文说明](#中文说明) | [English](#english)

## 中文说明

### 项目简介

Health Assessment Skill 是一个中文优先的通用健康记录与评估系统，用于记录睡眠、饮食、运动、当季水果摄入、天气相关生活建议、常见症状分诊提示，并生成每周提醒和每月健康评估表。

系统的核心定位是“生活方式记录 + 健康教育”，不是医疗诊断工具。所有持久化数据、营养查询、天气查询、定时任务、OpenClaw/MCP 适配都在服务器侧运行，避免把密钥、数据库凭证或用户健康数据暴露给客户端提示词。

### 主要能力

- 睡眠记录：用户输入“我睡觉了”“我起床了”时，按用户时区记录时间；如果用户明确给出时间，则优先使用用户时间。
- 睡眠评估：自动计算睡眠时长，参考成人常见建议范围评估时长与作息时段合理性。
- 饮食记录：支持“我今天吃了苹果”“午饭吃了米饭150克、鸡胸肉100克”等自然语言记录。
- 营养评估：内置基础食物营养种子库，生产环境可接入权威食物数据库；未知食物不会编造营养数据。
- 当季水果建议：按月份和季节给出水果参考，并可结合 Open-Meteo 实时天气做生活提醒。
- 运动记录：记录运动类型、时长、强度，按每周运动建议做进度评估。
- 常见症状提示：覆盖感冒、发热、咽痛、腹泻、头痛、胸痛、尿路症状、过敏等常见场景，提供非诊断分诊提示、危险信号和自我照护建议。
- 周提醒：每周一提醒本周水果摄入目标和运动目标。
- 月报：每月第一天生成上个月健康评估表，未记录的模块不会展示。
- OpenClaw 协同：提供 FastAPI 服务和 stdio MCP 适配器，可注册到 OpenClaw 使用。
- 低幻觉提示词：内置提示词护栏，要求 AI 只使用服务器返回结果和本地引用资料，不编造营养、天气、诊断或引用。

### 目录结构

```text
health-assessment/
├── SKILL.md                         # Codex/Agent skill 入口
├── README.md                        # GitHub 项目说明
├── agents/
│   └── openai.yaml                  # Skill 展示与默认提示
├── deploy/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── install.sh                   # 一键安装脚本
│   └── openclaw-mcp.json
├── references/
│   ├── health-standards.md          # 健康评估阈值
│   ├── evidence-papers.md           # Nature/Lancet/BMJ 等研究依据
│   ├── food-seed.json               # 内置食物营养种子库
│   ├── seasonal-fruits.json         # 季节水果和天气规则
│   ├── condition-guidance.json      # 常见症状提示
│   ├── prompting-guardrails.md      # 低幻觉/低 token 提示词规范
│   ├── report-templates.md          # 周报、月报模板
│   └── server-contract.md           # API、存储、隐私、安全契约
├── scripts/
│   └── health_assessment.py         # 本地 CLI 参考实现
└── server/
    ├── app.py                       # FastAPI 服务
    ├── openclaw_mcp_server.py       # OpenClaw MCP 适配器
    └── requirements.txt
```

### 快速开始

#### 作为 Codex Skill 使用

如果你只想把它作为本地 Codex Skill 使用，可以把整个目录放到 Codex skills 目录：

```bash
mkdir -p ~/.codex/skills
cp -R health-assessment ~/.codex/skills/
```

Windows PowerShell：

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.codex\skills"
Copy-Item -Recurse .\health-assessment "$env:USERPROFILE\.codex\skills\"
```

之后可以在支持 skills 的 Codex 环境中用自然语言触发，例如：

```text
我睡觉了
我起床了
我今天吃了一个苹果
跑步30分钟
这个季节吃什么水果
我感冒了
生成 2026-05 的健康月报
```

#### 1. 解压项目

```bash
tar -xzf health-assessment-skill.tar.gz
cd health-assessment
```

如果使用 zip：

```bash
unzip health-assessment-skill.zip
cd health-assessment
```

#### 2. 一键安装

```bash
bash deploy/install.sh
```

安装脚本会创建 Python 虚拟环境、安装依赖、生成 `.env.example`，并在检测到 `openclaw` 命令时尝试自动注册 MCP 适配器。

#### 3. 启动 API 服务

```bash
HEALTH_STORE="$(pwd)/data/events.jsonl" \
.venv/bin/uvicorn server.app:app --host 0.0.0.0 --port 8787
```

健康检查：

```bash
curl -sS http://127.0.0.1:8787/healthz
```

返回示例：

```json
{"status":"ok","service":"health-assessment"}
```

### Docker 部署

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

检查服务：

```bash
curl -sS http://127.0.0.1:8787/healthz
```

### OpenClaw 接入

如果安装脚本没有自动注册，可以手动执行：

```bash
openclaw mcp set health-assessment '{"command":"/absolute/path/to/health-assessment/.venv/bin/python","args":["server/openclaw_mcp_server.py"],"cwd":"/absolute/path/to/health-assessment","env":{"HEALTH_ASSESSMENT_URL":"http://127.0.0.1:8787"}}'
```

查看注册结果：

```bash
openclaw mcp show health-assessment --json
```

注意：OpenClaw 注册只保存 MCP 配置，不会自动启动 FastAPI 服务。生产环境应使用 systemd、Docker、supervisor、pm2 或其他进程管理工具保持服务运行。

### HTTP API 使用示例

#### 记录睡眠

```bash
curl -sS http://127.0.0.1:8787/v1/health/messages \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"demo","text":"我睡觉了","timezone":"Asia/Shanghai"}'
```

```bash
curl -sS http://127.0.0.1:8787/v1/health/messages \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"demo","text":"我起床了","timezone":"Asia/Shanghai"}'
```

#### 记录饮食

```bash
curl -sS http://127.0.0.1:8787/v1/health/messages \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"demo","text":"我今天吃了一个苹果"}'
```

#### 记录运动

```bash
curl -sS http://127.0.0.1:8787/v1/health/messages \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"demo","text":"跑步30分钟"}'
```

#### 获取当季水果和天气建议

```bash
curl -sS http://127.0.0.1:8787/v1/health/seasonal-fruits \
  -H 'Content-Type: application/json' \
  -d '{"city":"北京","month":10,"timezone":"Asia/Shanghai"}'
```

#### 常见症状提示

```bash
curl -sS http://127.0.0.1:8787/v1/health/conditions \
  -H 'Content-Type: application/json' \
  -d '{"text":"我感冒了，有点嗓子疼","city":"上海"}'
```

#### 月度报告

```bash
curl -sS 'http://127.0.0.1:8787/v1/health/reports/monthly?user_id=demo&month=2026-05'
```

### MCP 工具

OpenClaw 可调用以下 MCP 工具：

- `health_record`：记录睡眠、饮食、运动或症状文本，并返回即时评估。
- `seasonal_fruit_advice`：返回当季水果建议和可选天气上下文。
- `condition_advice`：返回常见症状的非诊断分诊提示。
- `weekly_health_report`：生成周进度提醒。
- `monthly_health_report`：生成月度健康评估表。

### 数据与隐私

- 默认数据文件：`data/events.jsonl`
- 可通过环境变量指定存储位置：

```bash
export HEALTH_STORE=/var/lib/health-assessment/events.jsonl
```

生产环境建议：

- 使用数据库替代 JSONL。
- 加密健康记录。
- 支持用户导出和删除数据。
- 将营养 API key、数据库密码、通知服务 token、加密密钥保存在服务器侧。
- 不把密钥写入客户端、提示词、日志、截图或报告。

### 反幻觉策略

本项目在 `references/prompting-guardrails.md` 中内置了提示词护栏：

- 只使用服务器工具返回和本地引用资料。
- 缺失数据时说“未记录”“暂无法判断”或“需要补充”。
- 不编造营养、天气、疾病原因、药物剂量或论文引用。
- 常见症状只做健康教育和分诊提示，不做诊断。
- 紧急危险信号优先展示。
- 常规回复限制长度，避免消耗过多 token。
- 通过回归用例测试提示词变化。

### 医疗免责声明

本项目仅用于生活方式记录、健康教育和非诊断性建议，不构成医疗诊断、治疗方案或用药建议。若出现胸痛、呼吸困难、意识改变、严重脱水、高热不退、症状快速加重等危险信号，应立即联系急救或尽快就医。

---

## English

### Overview

Health Assessment Skill is a Chinese-first health logging and assessment system for sleep, diet, exercise, seasonal fruit intake, weather-aware lifestyle context, common symptom triage guidance, weekly reminders, and monthly health reports.

The project is designed as a lifestyle logging and health education tool, not a medical diagnosis system. Persistent records, nutrition lookup, weather lookup, scheduled jobs, and OpenClaw/MCP integration are handled server-side to keep secrets and health data out of client prompts.

### Features

- Sleep logging: records "I am going to sleep" and "I woke up" style messages using the user's time zone.
- Sleep assessment: calculates duration and evaluates timing against general adult lifestyle guidance.
- Diet logging: records natural-language food intake such as fruit, meals, grams, and default portions.
- Nutrition assessment: includes a seed food database and can be extended with authoritative server-side nutrition sources.
- Seasonal fruit advice: recommends month-aware fruit options and optional weather-aware lifestyle notes.
- Exercise tracking: records activity type, duration, intensity, and weekly progress.
- Common symptom guidance: covers cold-like symptoms, fever, sore throat, diarrhea, headache, chest pain, urinary symptoms, allergies, and related red flags.
- Weekly reminders: summarizes weekly fruit and exercise targets.
- Monthly reports: generates a previous-month health assessment table and omits empty modules.
- OpenClaw integration: provides both a FastAPI service and a stdio MCP adapter.
- Low-hallucination prompts: built-in guardrails require the AI to rely on server results and local references instead of inventing facts.

### Project Structure

```text
health-assessment/
├── SKILL.md                         # Codex/agent skill entry
├── README.md                        # GitHub documentation
├── agents/
│   └── openai.yaml                  # Skill display metadata
├── deploy/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── install.sh                   # One-command installer
│   └── openclaw-mcp.json
├── references/
│   ├── health-standards.md          # Assessment thresholds
│   ├── evidence-papers.md           # Nature/Lancet/BMJ and related evidence
│   ├── food-seed.json               # Seed nutrition database
│   ├── seasonal-fruits.json         # Seasonal fruit calendar and weather rules
│   ├── condition-guidance.json      # Common symptom guidance
│   ├── prompting-guardrails.md      # Low-hallucination prompt rules
│   ├── report-templates.md          # Weekly and monthly report templates
│   └── server-contract.md           # API, storage, privacy, and safety contract
├── scripts/
│   └── health_assessment.py         # CLI reference implementation
└── server/
    ├── app.py                       # FastAPI service
    ├── openclaw_mcp_server.py       # OpenClaw MCP adapter
    └── requirements.txt
```

### Quick Start

#### Use as a Codex Skill

If you only want to use this as a local Codex Skill, place the whole directory under the Codex skills folder:

```bash
mkdir -p ~/.codex/skills
cp -R health-assessment ~/.codex/skills/
```

Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.codex\skills"
Copy-Item -Recurse .\health-assessment "$env:USERPROFILE\.codex\skills\"
```

Then trigger it with natural-language messages in a Codex environment that supports skills:

```text
我睡觉了
我起床了
我今天吃了一个苹果
跑步30分钟
这个季节吃什么水果
我感冒了
生成 2026-05 的健康月报
```

#### 1. Extract the package

```bash
tar -xzf health-assessment-skill.tar.gz
cd health-assessment
```

Or with zip:

```bash
unzip health-assessment-skill.zip
cd health-assessment
```

#### 2. Install

```bash
bash deploy/install.sh
```

The installer creates a Python virtual environment, installs dependencies, writes `.env.example`, and attempts to register the MCP adapter if the `openclaw` command is available.

#### 3. Start the API server

```bash
HEALTH_STORE="$(pwd)/data/events.jsonl" \
.venv/bin/uvicorn server.app:app --host 0.0.0.0 --port 8787
```

Health check:

```bash
curl -sS http://127.0.0.1:8787/healthz
```

Expected response:

```json
{"status":"ok","service":"health-assessment"}
```

### Docker Deployment

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

Check the service:

```bash
curl -sS http://127.0.0.1:8787/healthz
```

### OpenClaw Integration

If the installer did not register the MCP adapter automatically, run:

```bash
openclaw mcp set health-assessment '{"command":"/absolute/path/to/health-assessment/.venv/bin/python","args":["server/openclaw_mcp_server.py"],"cwd":"/absolute/path/to/health-assessment","env":{"HEALTH_ASSESSMENT_URL":"http://127.0.0.1:8787"}}'
```

Check registration:

```bash
openclaw mcp show health-assessment --json
```

OpenClaw registration only stores the MCP configuration. It does not start the FastAPI service. Use systemd, Docker, supervisor, pm2, or another process manager for production.

### HTTP API Examples

#### Sleep

```bash
curl -sS http://127.0.0.1:8787/v1/health/messages \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"demo","text":"我睡觉了","timezone":"Asia/Shanghai"}'
```

```bash
curl -sS http://127.0.0.1:8787/v1/health/messages \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"demo","text":"我起床了","timezone":"Asia/Shanghai"}'
```

#### Diet

```bash
curl -sS http://127.0.0.1:8787/v1/health/messages \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"demo","text":"我今天吃了一个苹果"}'
```

#### Exercise

```bash
curl -sS http://127.0.0.1:8787/v1/health/messages \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"demo","text":"跑步30分钟"}'
```

#### Seasonal Fruit Advice

```bash
curl -sS http://127.0.0.1:8787/v1/health/seasonal-fruits \
  -H 'Content-Type: application/json' \
  -d '{"city":"Beijing","month":10,"timezone":"Asia/Shanghai"}'
```

#### Common Symptom Guidance

```bash
curl -sS http://127.0.0.1:8787/v1/health/conditions \
  -H 'Content-Type: application/json' \
  -d '{"text":"我感冒了，有点嗓子疼","city":"Shanghai"}'
```

#### Monthly Report

```bash
curl -sS 'http://127.0.0.1:8787/v1/health/reports/monthly?user_id=demo&month=2026-05'
```

### MCP Tools

OpenClaw can call these MCP tools:

- `health_record`: records sleep, diet, exercise, or symptom text and returns an immediate assessment.
- `seasonal_fruit_advice`: returns month-aware fruit suggestions and optional weather context.
- `condition_advice`: returns non-diagnostic triage guidance for common symptoms.
- `weekly_health_report`: generates weekly progress.
- `monthly_health_report`: generates a monthly health assessment.

### Data and Privacy

Default storage:

```text
data/events.jsonl
```

Override it with:

```bash
export HEALTH_STORE=/var/lib/health-assessment/events.jsonl
```

Production recommendations:

- Replace JSONL with a database.
- Encrypt health records at rest.
- Support user export and deletion.
- Keep nutrition API keys, database credentials, notification tokens, and encryption keys server-side.
- Never include secrets in prompts, logs, screenshots, analytics, or generated reports.

### Hallucination Reduction

The project includes prompt guardrails in `references/prompting-guardrails.md`:

- Use only server tool results and local reference files.
- Say "not recorded", "cannot determine yet", or "needs more information" when data is missing.
- Do not invent nutrition values, weather, disease causes, medication doses, or citations.
- Treat symptoms as health education and triage, not diagnosis.
- Show urgent red flags first.
- Keep routine replies short to reduce token cost.
- Test prompt changes with regression cases.

### Medical Disclaimer

This project is for lifestyle logging, health education, and non-diagnostic guidance only. It is not a medical diagnosis, treatment plan, or medication recommendation. Seek urgent care if you experience chest pain, difficulty breathing, altered consciousness, severe dehydration, persistent high fever, or rapidly worsening symptoms.
