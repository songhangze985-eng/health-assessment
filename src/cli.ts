#!/usr/bin/env bun
import { readFile } from "node:fs/promises";
import { assess, scoreCheckin } from "./scoring.ts";
import { crisisFromPhq9Item9, detectCrisisText, disclaimer } from "./safety.ts";
import { appendRecord, historyPath, readHistory } from "./store.ts";
import { GAD7_ITEMS, LIKERT4_LABELS, PHQ9_ITEMS } from "./instruments.ts";
import type { Checkin, FullAnswers, Locale } from "./types.ts";

function usage(): string {
  return `health-assessment — lightweight screening CLI (not a diagnosis)

Usage:
  bun src/cli.ts score --file <answers.json>
  bun src/cli.ts score --stdin
  bun src/cli.ts checkin --mood N --energy N --sleep H --moved yes|no --stress N [--locale zh|en]
  bun src/cli.ts trend
  bun src/cli.ts safety --text "..."
  bun src/cli.ts instruments [--locale zh|en]
  bun src/cli.ts --help
`;
}

function arg(flag: string, argv: string[]): string | undefined {
  const i = argv.indexOf(flag);
  if (i >= 0 && i + 1 < argv.length) return argv[i + 1];
  return undefined;
}

function has(flag: string, argv: string[]): boolean {
  return argv.includes(flag);
}

function parseLocale(argv: string[]): Locale {
  const v = arg("--locale", argv) ?? "zh";
  if (v === "zh" || v === "en") return v;
  throw new Error(`--locale must be zh or en, got ${v}`);
}

function intFlag(flag: string, argv: string[], min: number, max: number): number {
  const raw = arg(flag, argv);
  if (raw === undefined) throw new Error(`missing ${flag}`);
  const n = Number(raw);
  if (!Number.isInteger(n) || n < min || n > max) {
    throw new Error(`${flag} must be integer ${min}–${max}, got ${raw}`);
  }
  return n;
}

function floatFlag(flag: string, argv: string[]): number {
  const raw = arg(flag, argv);
  if (raw === undefined) throw new Error(`missing ${flag}`);
  const n = Number(raw);
  if (!Number.isFinite(n)) throw new Error(`${flag} must be a number, got ${raw}`);
  return n;
}

async function readAnswers(argv: string[]): Promise<FullAnswers> {
  if (has("--stdin", argv)) {
    const text = await new Response(Bun.stdin).text();
    return JSON.parse(text) as FullAnswers;
  }
  const file = arg("--file", argv);
  if (!file) throw new Error("score needs --file or --stdin");
  return JSON.parse(await readFile(file, "utf8")) as FullAnswers;
}

async function main(argv: string[]): Promise<number> {
  const cmd = argv[0] ?? "--help";
  if (cmd === "--help" || cmd === "-h" || cmd === "help") {
    console.log(usage());
    return 0;
  }

  if (cmd === "score") {
    const extra = arg("--text", argv) ?? "";
    const answers = await readAnswers(argv.slice(1));
    const result = assess(answers, extra);
    if (!has("--no-store", argv)) await appendRecord(result);
    console.log(JSON.stringify(result, null, 2));
    return 0;
  }

  if (cmd === "checkin") {
    const locale = parseLocale(argv);
    const movedRaw = arg("--moved", argv);
    if (movedRaw !== "yes" && movedRaw !== "no") throw new Error("--moved must be yes or no");
    const checkin: Checkin = {
      mood: intFlag("--mood", argv, 1, 5) as Checkin["mood"],
      energy: intFlag("--energy", argv, 1, 5) as Checkin["energy"],
      sleepHours: floatFlag("--sleep", argv),
      moved: movedRaw === "yes",
      stress: intFlag("--stress", argv, 1, 5) as Checkin["stress"],
    };
    const result = scoreCheckin(checkin, locale);
    if (!has("--no-store", argv)) await appendRecord(result);
    console.log(JSON.stringify(result, null, 2));
    return 0;
  }

  if (cmd === "trend") {
    const rows = await readHistory();
    const summary = {
      disclaimer: disclaimer("zh"),
      path: historyPath(),
      count: rows.length,
      last: rows.at(-1) ?? null,
    };
    console.log(JSON.stringify(summary, null, 2));
    return 0;
  }

  if (cmd === "safety") {
    const text = arg("--text", argv) ?? "";
    const locale = parseLocale(argv);
    const result = {
      disclaimer: disclaimer(locale),
      hit: detectCrisisText(text),
      crisis: crisisFromPhq9Item9(0, detectCrisisText(text), locale),
    };
    console.log(JSON.stringify(result, null, 2));
    return 0;
  }

  if (cmd === "instruments") {
    const locale = parseLocale(argv);
    console.log(
      JSON.stringify(
        {
          likert: LIKERT4_LABELS[locale],
          phq9: PHQ9_ITEMS[locale],
          gad7: GAD7_ITEMS[locale],
        },
        null,
        2,
      ),
    );
    return 0;
  }

  console.error(usage());
  return 2;
}

const code = await main(process.argv.slice(2));
process.exit(code);
