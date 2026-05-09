#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from typing import Any


BASE_URL = os.environ.get("HEALTH_ASSESSMENT_URL", "http://127.0.0.1:8787").rstrip("/")
TIMEOUT_SECONDS = 20


def request_json(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{BASE_URL}{path}"
    data = None
    headers = {"User-Agent": "health-assessment-openclaw-mcp/0.2"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


TOOLS: list[dict[str, Any]] = [
    {
        "name": "health_record",
        "description": "Record raw Chinese sleep, diet, exercise, or symptom text. Return the server reply as the factual boundary; do not add nutrition, weather, diagnosis, or dosing facts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "default": "default"},
                "text": {"type": "string"},
                "timezone": {"type": "string", "default": "Asia/Shanghai"},
                "city": {"type": "string"},
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "seasonal_fruit_advice",
        "description": "Return seasonal fruit suggestions and optional server weather context. Do not claim fruit prevents or treats disease; if weather is absent, say it is unavailable.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
                "timezone": {"type": "string", "default": "Asia/Shanghai"},
                "month": {"type": "integer", "minimum": 1, "maximum": 12},
            },
        },
    },
    {
        "name": "condition_advice",
        "description": "Return non-diagnostic symptom triage for common complaints. Preserve urgent red-flag guidance first; do not add diagnosis, medication dose, or unsupported causes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "city": {"type": "string"},
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
                "timezone": {"type": "string", "default": "Asia/Shanghai"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "weekly_health_report",
        "description": "Generate weekly progress from stored records only. Do not infer missing fruit, exercise, sleep, or symptom data.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "default": "default"},
                "week_start": {"type": "string", "description": "YYYY-MM-DD"},
                "timezone": {"type": "string", "default": "Asia/Shanghai"},
            },
        },
    },
    {
        "name": "monthly_health_report",
        "description": "Generate a monthly assessment from stored records only. Omit empty modules and do not add facts absent from the server response.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "default": "default"},
                "month": {"type": "string", "description": "YYYY-MM"},
                "timezone": {"type": "string", "default": "Asia/Shanghai"},
            },
            "required": ["month"],
        },
    },
]


def text_result(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}]}


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "health_record":
        data = request_json("POST", "/v1/health/messages", arguments)
    elif name == "seasonal_fruit_advice":
        data = request_json("POST", "/v1/health/seasonal-fruits", arguments)
    elif name == "condition_advice":
        data = request_json("POST", "/v1/health/conditions", arguments)
    elif name == "weekly_health_report":
        query = urllib.parse.urlencode(arguments)
        data = request_json("GET", f"/v1/health/reports/weekly?{query}")
    elif name == "monthly_health_report":
        query = urllib.parse.urlencode(arguments)
        data = request_json("GET", f"/v1/health/reports/monthly?{query}")
    else:
        raise ValueError(f"Unknown tool: {name}")
    return text_result(data.get("reply", json.dumps(data, ensure_ascii=False, indent=2)))


def handle(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    msg_id = message.get("id")
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "health-assessment-openclaw", "version": "0.2.0"},
            },
        }
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = message.get("params") or {}
        try:
            result = call_tool(params["name"], params.get("arguments") or {})
            return {"jsonrpc": "2.0", "id": msg_id, "result": result}
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32000, "message": str(exc)},
            }
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
            response = handle(message)
        except Exception as exc:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}}
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
