---
name: health-assessment
description: Build, deploy, or operate a Chinese-first health assessment assistant that records sleep, diet, seasonal fruit intake, weather-aware context, exercise, common symptom guidance, weekly reminders, and monthly reports. Use when users ask to create, implement, evaluate, deploy, prompt-engineer, reduce hallucinations, optimize token use, or run a health logging skill/system for messages such as "我睡觉了", "我起床了", "我今天吃了苹果", "跑步30分钟", "我感冒了", "我发烧了", or when designing server-side storage, nutrition databases, scheduled reminders, OpenClaw/MCP integration, privacy-safe health assessment workflows, and non-diagnostic lifestyle summaries.
---

# Health Assessment

## Contract

Use this skill as a lifestyle logging and health education system, not a medical diagnosis system.

Critical defaults:

- Locale: Chinese-first input and output.
- Time zone: `Asia/Shanghai` unless the user profile provides another IANA time zone.
- Population: general adults unless profile data says otherwise.
- Persistence: store records, API keys, nutrition lookup credentials, scheduler jobs, and weather calls server-side.
- Medical boundary: never diagnose; surface emergency red flags before routine advice.
- Factual boundary: do not invent nutrient values, weather, medication dosing, disease causes, or citations.

## Load Only What You Need

- Prompt quality, hallucination control, output schemas, token budget, and OpenClaw agent instructions: `references/prompting-guardrails.md`.
- Sleep, diet, exercise, fruit/vegetable, and guideline thresholds: `references/health-standards.md`.
- Nature/Lancet/BMJ/BJSM and other research rationale: `references/evidence-papers.md`.
- Seed nutrition data: `references/food-seed.json`.
- Seasonal fruit calendar and weather-sensitive advice rules: `references/seasonal-fruits.json`.
- Common symptom triage, red flags, questions, and self-care boundaries: `references/condition-guidance.json`.
- API, storage, scheduler, weather, privacy, and OpenClaw/MCP contracts: `references/server-contract.md`.
- Server deployment and one-command install: `references/deployment-openclaw.md`.
- Weekly and monthly report templates: `references/report-templates.md`.
- Deterministic CLI reference implementation: `scripts/health_assessment.py`.

## Runtime Flow

1. Normalize user id, locale, and time zone.
2. Classify each message into modules: sleep, diet, seasonal fruit, weather context, exercise, condition guidance, profile, report, or unknown.
3. Extract timestamps, amounts, units, foods, exercise type, duration, intensity, symptoms, and city/coordinates.
4. Use current server time only for event messages where the user omitted time.
5. Record raw text and normalized structured events before assessment.
6. Assess only fields backed by user data, bundled references, or server tool results.
7. Reply with what was recorded, one key assessment, and at most three missing fields that would materially improve accuracy.
8. Use scheduled jobs for Monday weekly reminders and first-day monthly reports.

## Module Rules

| Module | Core behavior | Reference |
| --- | --- | --- |
| Sleep | Record `sleep_start`/`sleep_end`; compute duration and schedule reasonableness; close latest open session. | `health-standards.md` |
| Diet | Match foods to seed/server nutrition data; estimate only marked default portions; unknown foods keep raw text only. | `food-seed.json` |
| Seasonal fruit | Suggest 1-3 current-season fruits with 200-350 g/day target; weather failure must degrade gracefully. | `seasonal-fruits.json` |
| Condition | Triage common symptoms; urgent-care red flags first; no diagnosis or dosing. | `condition-guidance.json` |
| Exercise | Track duration/intensity; convert vigorous minutes to moderate equivalents; assess weekly targets. | `health-standards.md` |
| Reports | Omit empty sections; include data coverage and estimation ratio. | `report-templates.md` |

## Server And OpenClaw

- Use `server/app.py` as the FastAPI service.
- Use `server/openclaw_mcp_server.py` as the OpenClaw stdio MCP adapter.
- Keep client prompts thin: prefer MCP tool calls and returned structured data over embedding large reference text.
- Keep secrets off clients and out of prompts.
- Use parameterized database access and structured validation for incoming events.
- Add a user-facing disclaimer to reports: lifestyle assessment only, not medical advice.

## Validation

Run these after edits:

```bash
python C:/Users/fantasy/.codex/skills/.system/skill-creator/scripts/quick_validate.py C:/Users/fantasy/Desktop/健康评估系统/health-assessment
python -m py_compile health-assessment/server/app.py health-assessment/server/openclaw_mcp_server.py health-assessment/scripts/health_assessment.py
```

For MCP compatibility, send `initialize` and `tools/list` JSON-RPC messages to `server/openclaw_mcp_server.py` while the FastAPI service is available.
