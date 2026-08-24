import {
  BMI_CN_BANDS,
  BMI_GLOBAL_BANDS,
  GAD7_BANDS,
  PHQ9_BANDS,
  assertLength,
  assertLikert4,
  bandFor,
  cutoffSetFor,
} from "./instruments.ts";
import { assertNoDiagnosisLanguage, crisisFromPhq9Item9, detectCrisisText, disclaimer } from "./safety.ts";
import type {
  AssessmentResult,
  Band,
  BmiResult,
  Checkin,
  CheckinResult,
  FullAnswers,
  Likert4,
  Locale,
  ScaleResult,
  SleepAnswers,
} from "./types.ts";

function clamp100(n: number): number {
  return Math.max(0, Math.min(100, Math.round(n)));
}

function likertList(values: number[], label: string): Likert4[] {
  return values.map((v, i) => assertLikert4(v, `${label}[${i}]`));
}

export function scorePhq9(items: number[], locale: Locale): ScaleResult {
  const nine = likertList(assertLength(items, 9, "PHQ-9"), "PHQ-9") as Likert4[];
  const score = nine.reduce((a, b) => a + b, 0);
  const flags: string[] = [];
  if (nine[8] >= 1) flags.push("phq9-item9");
  return {
    id: "phq9",
    score,
    max: 27,
    band: bandFor(score, PHQ9_BANDS),
    flags,
  };
}

export function scoreGad7(items: number[], locale: Locale): ScaleResult {
  const seven = likertList(assertLength(items, 7, "GAD-7"), "GAD-7");
  const score = seven.reduce((a, b) => a + b, 0);
  return {
    id: "gad7",
    score,
    max: 21,
    band: bandFor(score, GAD7_BANDS),
    flags: [],
  };
}

export function scoreSleep(sleep: SleepAnswers): ScaleResult {
  if (!Number.isFinite(sleep.hours) || sleep.hours < 0 || sleep.hours > 24) {
    throw new Error(`sleep.hours out of range: ${sleep.hours}`);
  }
  if (!Number.isFinite(sleep.latencyMin) || sleep.latencyMin < 0) {
    throw new Error(`sleep.latencyMin out of range: ${sleep.latencyMin}`);
  }
  if (!Number.isFinite(sleep.awakenings) || sleep.awakenings < 0) {
    throw new Error(`sleep.awakenings out of range: ${sleep.awakenings}`);
  }
  if (![1, 2, 3, 4, 5].includes(sleep.restedness)) {
    throw new Error(`sleep.restedness must be 1–5, got ${sleep.restedness}`);
  }

  let hours = 10;
  if (sleep.hours >= 7 && sleep.hours <= 9) hours = 100;
  else if (sleep.hours >= 6 && sleep.hours < 7) hours = 70;
  else if (sleep.hours > 9 && sleep.hours <= 10) hours = 70;
  else if (sleep.hours >= 5 && sleep.hours < 6) hours = 40;
  else if (sleep.hours > 10 && sleep.hours <= 11) hours = 40;

  let latency = 10;
  if (sleep.latencyMin <= 15) latency = 100;
  else if (sleep.latencyMin <= 30) latency = 70;
  else if (sleep.latencyMin <= 60) latency = 40;

  let wakes = 20;
  if (sleep.awakenings <= 1) wakes = 100;
  else if (sleep.awakenings === 2) wakes = 60;

  const rest = (sleep.restedness - 1) * 25;
  const score = clamp100((hours + latency + wakes + rest) / 4);
  const bands: Band[] = [
    { id: "poor", min: 0, max: 39, labelZh: "睡眠负担偏重", labelEn: "Sleep load high" },
    { id: "fair", min: 40, max: 69, labelZh: "睡眠一般", labelEn: "Sleep fair" },
    { id: "good", min: 70, max: 100, labelZh: "睡眠尚可", labelEn: "Sleep adequate" },
  ];
  return { id: "sleep", score, max: 100, band: bandFor(score, bands), flags: [] };
}

export function scoreBmi(heightCm: number, weightKg: number, locale: Locale): BmiResult {
  if (!(heightCm >= 80 && heightCm <= 250)) throw new Error(`heightCm out of range: ${heightCm}`);
  if (!(weightKg >= 20 && weightKg <= 400)) throw new Error(`weightKg out of range: ${weightKg}`);
  const m = heightCm / 100;
  const value = Math.round((weightKg / (m * m)) * 10) / 10;
  const cutoffSet = cutoffSetFor(locale);
  const table = cutoffSet === "cn-wst428" ? BMI_CN_BANDS : BMI_GLOBAL_BANDS;
  const band = table.find((b) => value >= b.min && value <= b.max) ?? table[table.length - 1];
  const scoreMap: Record<string, number> = {
    underweight: 60,
    normal: 100,
    overweight: 70,
    "obese-1": 35,
    "obese-2": 20,
  };
  return { value, cutoffSet, band, score100: scoreMap[band.id] ?? 50 };
}

export function scoreMovement(exerciseMinWeek: number): ScaleResult {
  if (!Number.isFinite(exerciseMinWeek) || exerciseMinWeek < 0) {
    throw new Error(`exerciseMinWeek out of range: ${exerciseMinWeek}`);
  }
  let score = 10;
  if (exerciseMinWeek >= 150) score = 100;
  else if (exerciseMinWeek >= 75) score = 60;
  else if (exerciseMinWeek >= 30) score = 30;
  const bands: Band[] = [
    { id: "low", min: 0, max: 29, labelZh: "活动很少", labelEn: "Low activity" },
    { id: "some", min: 30, max: 59, labelZh: "有一些活动", labelEn: "Some activity" },
    { id: "near", min: 60, max: 99, labelZh: "接近建议量", labelEn: "Approaching guideline" },
    { id: "met", min: 100, max: 100, labelZh: "达到 WHO 建议", labelEn: "Meets WHO 150 min" },
  ];
  return {
    id: "movement",
    score,
    max: 100,
    band: bandFor(score, bands),
    flags: exerciseMinWeek >= 150 ? [] : ["below-who-150"],
  };
}

function invertInstrument(score: number, max: number): number {
  return clamp100(100 * (1 - score / max));
}

function pickActions(locale: Locale, result: Omit<AssessmentResult, "actions" | "seekCare">): string[] {
  if (result.crisis.level !== "none") {
    return locale === "en"
      ? ["Contact emergency services or a crisis line now", "Stay with someone you trust", "Do not use this tool as a plan"]
      : ["立刻拨打 120 或心理热线", "请和身边可信任的人待在一起", "不要把本工具当成应对计划"];
  }
  const actions: string[] = [];
  if (result.sleep.score < 70) {
    actions.push(locale === "en" ? "Pick a fixed wake time for the next 3 days" : "接下来 3 天固定同一起床时间");
  }
  if (result.movement.score < 100) {
    actions.push(locale === "en" ? "Add two 20-minute walks this week" : "本周加两次 20 分钟走路");
  }
  if (result.phq9.score >= 5 || result.gad7.score >= 5) {
    actions.push(
      locale === "en"
        ? "Write one sentence each evening: what felt heavy, what helped"
        : "每晚写一句：今天哪里沉、什么帮上了忙",
    );
  }
  if (result.bmi.band.id !== "normal") {
    actions.push(locale === "en" ? "Keep meals regular; skip crash dieting" : "规律吃饭，不要节食惩罚自己");
  }
  return actions.slice(0, 3);
}

function pickSeekCare(locale: Locale, result: Omit<AssessmentResult, "actions" | "seekCare">): string[] {
  const out: string[] = [];
  if (result.crisis.level !== "none") {
    out.push(locale === "en" ? "Seek urgent professional support" : "尽快寻求专业人员当面支持");
  }
  if (result.phq9.score >= 10 || result.gad7.score >= 10) {
    out.push(
      locale === "en"
        ? "Consider a primary-care or mental-health appointment this week"
        : "建议本周预约社区医院/心理门诊做专业评估",
    );
  }
  if (result.phq9.score >= 15 || result.gad7.score >= 15) {
    out.push(
      locale === "en"
        ? "Scores in this range are a reason to talk to a clinician soon, not to self-diagnose"
        : "这个分数区间适合尽快和医生谈，而不是自己下结论",
    );
  }
  return out;
}

export function assess(input: FullAnswers, extraText = ""): AssessmentResult {
  const locale: Locale = input.locale ?? "zh";
  const phq9 = scorePhq9(input.phq9.items, locale);
  const gad7 = scoreGad7(input.gad7.items, locale);
  const sleep = scoreSleep(input.sleep);
  const bmi = scoreBmi(input.lifestyle.heightCm, input.lifestyle.weightKg, locale);
  const movement = scoreMovement(input.lifestyle.exerciseMinWeek);

  const lifestyleFlags: string[] = [];
  if (input.lifestyle.smoking === "current") lifestyleFlags.push("smoking-current");
  if (input.lifestyle.smoking === "former") lifestyleFlags.push("smoking-former");
  if (input.lifestyle.alcoholUnitsWeek >= 15) lifestyleFlags.push("alcohol-high");
  else if (input.lifestyle.alcoholUnitsWeek >= 8) lifestyleFlags.push("alcohol-caution");

  let bodyScore = bmi.score100;
  if (input.lifestyle.smoking === "current") bodyScore = clamp100(bodyScore - 15);

  const mental = clamp100((invertInstrument(phq9.score, 27) + invertInstrument(gad7.score, 21)) / 2);
  const dimensions = [
    { id: "mental", score: mental, weight: 0.3 },
    { id: "sleep", score: sleep.score, weight: 0.25 },
    { id: "body", score: bodyScore, weight: 0.2 },
    { id: "movement", score: movement.score, weight: 0.25 },
  ];
  const total = clamp100(dimensions.reduce((s, d) => s + d.score * d.weight, 0));

  const crisis = crisisFromPhq9Item9(input.phq9.items[8], detectCrisisText(extraText), locale);
  const draft: Omit<AssessmentResult, "actions" | "seekCare"> = {
    kind: "full",
    locale,
    disclaimer: disclaimer(locale),
    crisis,
    phq9,
    gad7,
    sleep,
    bmi,
    movement,
    lifestyleFlags,
    composite: { total, dimensions },
  };
  const result: AssessmentResult = {
    ...draft,
    actions: pickActions(locale, draft),
    seekCare: pickSeekCare(locale, draft),
  };
  assertNoDiagnosisLanguage(JSON.stringify(result));
  return result;
}

export function scoreCheckin(checkin: Checkin, locale: Locale = "zh"): CheckinResult {
  for (const key of ["mood", "energy", "stress"] as const) {
    const v = checkin[key];
    if (![1, 2, 3, 4, 5].includes(v)) throw new Error(`${key} must be 1–5, got ${v}`);
  }
  if (!Number.isFinite(checkin.sleepHours) || checkin.sleepHours < 0 || checkin.sleepHours > 24) {
    throw new Error(`sleepHours out of range: ${checkin.sleepHours}`);
  }
  const sleepPart = checkin.sleepHours >= 7 && checkin.sleepHours <= 9 ? 100 : checkin.sleepHours >= 6 ? 60 : 30;
  const parts = [
    checkin.mood * 20,
    checkin.energy * 20,
    (6 - checkin.stress) * 20,
    sleepPart,
    checkin.moved ? 100 : 20,
  ];
  const score100 = clamp100(parts.reduce((a, b) => a + b, 0) / parts.length);
  const result: CheckinResult = {
    kind: "checkin",
    locale,
    disclaimer: disclaimer(locale),
    snapshot: { ...checkin, at: checkin.at ?? new Date().toISOString() },
    score100,
  };
  assertNoDiagnosisLanguage(JSON.stringify(result));
  return result;
}
