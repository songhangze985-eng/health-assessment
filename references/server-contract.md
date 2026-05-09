# Server Contract

Use this contract when implementing the production service behind the skill.

## Event Model

Common fields:

```json
{
  "event_id": "uuid",
  "user_id": "server-user-id",
  "type": "sleep_start | sleep_session | food_intake | exercise | condition_guidance | seasonal_fruit",
  "timestamp": "2026-05-09T23:10:00+08:00",
  "timezone": "Asia/Shanghai",
  "raw_text": "我睡觉了",
  "source": "implicit_now | explicit_user_time | imported",
  "standard_version": "health-standards:2026-05",
  "evidence_version": "evidence-papers:2026-05",
  "created_at": "2026-05-09T23:10:01+08:00",
  "schema_version": 1
}
```

Sleep session fields:

```json
{
  "type": "sleep_session",
  "start_at": "2026-05-09T23:10:00+08:00",
  "end_at": "2026-05-10T07:05:00+08:00",
  "duration_hours": 7.92,
  "duration_status": "target",
  "schedule_status": "normal | late | early | irregular | unknown",
  "assessment": ["睡眠时长在成人常见建议范围内"]
}
```

Food intake fields:

```json
{
  "type": "food_intake",
  "meal": "breakfast | lunch | dinner | snack | unknown",
  "items": [
    {
      "food_id": "apple_raw",
      "display_name": "苹果",
      "amount_g": 182,
      "amount_source": "default_portion | explicit",
      "estimated": true,
      "category": "fruit",
      "nutrients": {
        "energy_kcal": 94.6,
        "protein_g": 0.47,
        "fat_g": 0.31,
        "carbohydrate_g": 25.13,
        "fiber_g": 4.37
      }
    }
  ]
}
```

Exercise fields:

```json
{
  "type": "exercise",
  "activity": "running",
  "duration_minutes": 30,
  "intensity": "vigorous",
  "moderate_equivalent_minutes": 60,
  "strength_training": false
}
```

Condition guidance fields:

```json
{
  "type": "condition_guidance",
  "condition_id": "common_cold",
  "display_name": "感冒样症状",
  "red_flags": [],
  "questions": ["什么时候开始的？", "有没有发热、气短、胸痛或症状突然加重？"],
  "self_care": ["休息，补充水分"],
  "seek_medical_care": ["发热超过4天", "症状超过10天没有改善"],
  "emergency": ["呼吸困难", "胸痛或胸腹部持续压迫感"],
  "source_ids": ["CDC Common Cold", "MedlinePlus Common Cold"]
}
```

Seasonal fruit/weather fields:

```json
{
  "type": "seasonal_fruit",
  "month": 10,
  "season": "autumn",
  "fruits": ["苹果", "梨", "柿子", "石榴"],
  "weather": {
    "location": "北京 / Beijing / China",
    "temperature_c": 18.2,
    "relative_humidity_percent": 41,
    "source": "Open-Meteo"
  },
  "advice": ["天气无明显特殊提醒，按每日200-350g鲜果目标安排即可。"]
}
```

## APIs

Minimum endpoints:

- `POST /v1/health/messages`: accept raw user text, normalize, record, assess, and return immediate reply.
- `POST /v1/health/events`: accept structured events from trusted clients.
- `POST /v1/health/seasonal-fruits`: return month/season-aware fruit suggestions, optionally with weather context.
- `GET /v1/health/seasonal-fruits?city=北京&month=10`
- `POST /v1/health/conditions`: return non-diagnostic common symptom guidance, red-flag checks, cause questions, and self-care notes.
- `GET /v1/health/conditions`: list supported condition profiles.
- `GET /v1/health/reports/weekly?week_start=YYYY-MM-DD`
- `GET /v1/health/reports/monthly?month=YYYY-MM`
- `GET /v1/health/profile`
- `PATCH /v1/health/profile`
- `DELETE /v1/health/users/{user_id}`: delete user health records and raw text.

## Storage

Recommended tables:

- `health_users`: user profile, time zone, locale, age band, consent flags.
- `health_raw_messages`: raw text, normalized language, parser version.
- `health_events`: immutable event log.
- `health_daily_metrics`: materialized daily aggregates.
- `health_food_items`: server-side food database cache.
- `health_condition_events`: symptom messages, non-diagnostic condition profile id, red flags, and follow-up questions.
- `health_weather_cache`: city/coordinate weather snapshots with TTL and provider attribution.
- `health_jobs`: scheduled reminders and delivery status.
- `health_evidence_sources`: versioned citations used by assessment rules and reports.

Keep the event log immutable. Correct mistakes with correction events instead of overwriting historical rows.

## Evidence Traceability

Persist evidence metadata separately from user events:

```json
{
  "evidence_version": "evidence-papers:2026-05",
  "rule_id": "adult_sleep_duration",
  "threshold": "7-9 h/night",
  "source_type": "guideline",
  "primary_citations": [
    "CDC About Sleep",
    "AASM/SRS consensus statement, doi:10.5664/jcsm.4758"
  ],
  "supporting_citations": [
    "Scientific Reports, doi:10.1038/srep21480",
    "Nature Reviews Neuroscience, doi:10.1038/nrn.2017.55"
  ]
}
```

Reports may include source labels, but do not expose internal API keys, raw database credentials, or private user notes.

## Secrets

Keep these server-only:

- `FDC_API_KEY`
- database credentials
- notification provider tokens
- scheduler credentials
- encryption keys

Do not expose these values to clients, prompts, logs, analytics, screenshots, or generated reports. Open-Meteo weather lookup does not require a key by default; if a paid weather provider is added later, keep that key server-only.

## Weather

Default provider:

- Open-Meteo Forecast API: no key required for non-commercial use.
- Geocoding endpoint: `https://geocoding-api.open-meteo.com/v1/search`
- Forecast endpoint: `https://api.open-meteo.com/v1/forecast`

Implementation rules:

- Weather lookup is optional and must degrade gracefully.
- Cache weather snapshots to avoid repeated calls for the same user/city.
- Do not use weather as a diagnostic input. Use it only for lifestyle context such as hydration, storage, cold/dry/rain reminders.

## OpenClaw

Provide both:

- HTTP API service: `server/app.py`
- Stdio MCP adapter: `server/openclaw_mcp_server.py`

OpenClaw registry command shape:

```bash
openclaw mcp set health-assessment '{"command":"/path/to/health-assessment/.venv/bin/python","args":["server/openclaw_mcp_server.py"],"cwd":"/path/to/health-assessment","env":{"HEALTH_ASSESSMENT_URL":"http://127.0.0.1:8787"}}'
```

OpenClaw stores this definition only; the FastAPI service must already be running.

## Scheduler

Jobs use the user's time zone:

- Weekly reminder: Monday morning, default 09:00.
- Monthly report: first calendar day, default 09:00, covering the previous month.

Use idempotency keys:

- `weekly:{user_id}:{iso_week}`
- `monthly:{user_id}:{yyyy_mm}`

## Validation And Safety

- Validate units and reject negative or impossible durations.
- Cap sleep duration at a configured maximum before assessment; flag outliers for review.
- Require structured parsing before database writes.
- Use parameterized queries only.
- Encrypt records at rest when supported by the hosting environment.
- Support user export and deletion.
- Add "not medical advice" language to every report.
