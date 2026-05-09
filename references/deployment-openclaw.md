# Deployment And OpenClaw

Use this when deploying the skill as a server-side service and registering it for OpenClaw.

## One-Command Local Install

From the parent directory that contains `health-assessment`:

```bash
bash health-assessment/deploy/install.sh
```

Start the API service:

```bash
HEALTH_STORE="$(pwd)/health-assessment/data/events.jsonl" \
health-assessment/.venv/bin/uvicorn server.app:app --app-dir health-assessment --host 0.0.0.0 --port 8787
```

Health check:

```bash
curl -sS http://127.0.0.1:8787/healthz
```

## Docker Install

From `health-assessment`:

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

Health check:

```bash
curl -sS http://127.0.0.1:8787/healthz
```

## API Examples

Record or assess a message:

```bash
curl -sS http://127.0.0.1:8787/v1/health/messages \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"demo","text":"我感冒了","city":"北京"}'
```

Seasonal fruit with weather context:

```bash
curl -sS http://127.0.0.1:8787/v1/health/seasonal-fruits \
  -H 'Content-Type: application/json' \
  -d '{"city":"上海","month":10}'
```

Monthly report:

```bash
curl -sS 'http://127.0.0.1:8787/v1/health/reports/monthly?user_id=demo&month=2026-05'
```

## OpenClaw Registration

If `openclaw` is installed, `deploy/install.sh` attempts to register the MCP adapter automatically.

Manual registration:

```bash
openclaw mcp set health-assessment '{"command":"/absolute/path/to/health-assessment/.venv/bin/python","args":["server/openclaw_mcp_server.py"],"cwd":"/absolute/path/to/health-assessment","env":{"HEALTH_ASSESSMENT_URL":"http://127.0.0.1:8787"}}'
```

Check registration:

```bash
openclaw mcp show health-assessment --json
```

Important:

- OpenClaw `mcp set` writes config only; it does not start or validate the API service.
- Keep the FastAPI service running with systemd, Docker, pm2, supervisor, or your server process manager.
- Do not put `PYTHONPATH`, `PYTHONSTARTUP`, or interpreter-startup env variables in the OpenClaw MCP server config. OpenClaw rejects unsafe stdio env keys.

## Exposed MCP Tools

- `health_record`: records sleep, diet, exercise, seasonal fruit requests, and symptom messages.
- `seasonal_fruit_advice`: returns month-aware fruit suggestions and optional weather context.
- `condition_advice`: returns non-diagnostic common symptom guidance and red-flag checks.
- `weekly_health_report`: returns weekly progress.
- `monthly_health_report`: returns monthly report.

## Operations Notes

- Default storage is JSONL: `health-assessment/data/events.jsonl`.
- Set `HEALTH_STORE=/var/lib/health-assessment/events.jsonl` for production-like persistence.
- Open-Meteo weather lookup is no-key and optional. If network is unavailable, the server still returns season-only fruit suggestions.
- Condition guidance is health education, not diagnosis. It should escalate red flags and ask context questions before giving routine self-care suggestions.
