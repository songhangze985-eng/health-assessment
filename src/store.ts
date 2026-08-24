import { homedir } from "node:os";
import { join } from "node:path";
import { mkdir, appendFile, readFile } from "node:fs/promises";
import { existsSync } from "node:fs";

export function storeDir(): string {
  const override = process.env.HEALTH_ASSESSMENT_HOME;
  if (override && override.trim().length > 0) return override;
  return join(homedir(), ".health-assessment");
}

export function historyPath(): string {
  return join(storeDir(), "history.jsonl");
}

export async function appendRecord(record: unknown): Promise<string> {
  const dir = storeDir();
  await mkdir(dir, { recursive: true });
  const line = JSON.stringify({ ...asObject(record), storedAt: new Date().toISOString() }) + "\n";
  await appendFile(historyPath(), line, "utf8");
  return historyPath();
}

export async function readHistory(): Promise<unknown[]> {
  const path = historyPath();
  if (!existsSync(path)) return [];
  const raw = await readFile(path, "utf8");
  return raw
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean)
    .map((l) => JSON.parse(l));
}

function asObject(record: unknown): Record<string, unknown> {
  if (record && typeof record === "object" && !Array.isArray(record)) {
    return record as Record<string, unknown>;
  }
  return { value: record };
}
