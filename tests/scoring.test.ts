import { describe, expect, test } from "bun:test";
import { assess, scoreCheckin, scoreGad7, scoreMovement, scorePhq9 } from "../src/scoring.ts";
import type { FullAnswers } from "../src/types.ts";

const base = (): FullAnswers => ({
  locale: "zh",
  phq9: { items: [0, 0, 0, 0, 0, 0, 0, 0, 0] },
  gad7: { items: [0, 0, 0, 0, 0, 0, 0] },
  sleep: { hours: 8, latencyMin: 10, awakenings: 0, restedness: 5 },
  lifestyle: {
    heightCm: 170,
    weightKg: 62,
    exerciseMinWeek: 150,
    smoking: "never",
    alcoholUnitsWeek: 0,
  },
});

describe("PHQ-9", () => {
  test("all zeros is minimal 0", () => {
    const r = scorePhq9([0, 0, 0, 0, 0, 0, 0, 0, 0], "zh");
    expect(r.score).toBe(0);
    expect(r.band.id).toBe("minimal");
  });

  test("all ones is mild 9", () => {
    const r = scorePhq9([1, 1, 1, 1, 1, 1, 1, 1, 1], "zh");
    expect(r.score).toBe(9);
    expect(r.band.id).toBe("mild");
  });

  test("bands match Kroenke cutoffs", () => {
    expect(scorePhq9([1, 1, 1, 1, 1, 0, 0, 0, 0], "zh").band.id).toBe("mild"); // 5
    expect(scorePhq9([2, 2, 2, 2, 2, 0, 0, 0, 0], "zh").score).toBe(10);
    expect(scorePhq9([2, 2, 2, 2, 2, 0, 0, 0, 0], "zh").band.id).toBe("moderate");
    expect(scorePhq9([3, 3, 3, 3, 3, 0, 0, 0, 0], "zh").score).toBe(15);
    expect(scorePhq9([3, 3, 3, 3, 3, 0, 0, 0, 0], "zh").band.id).toBe("mod-severe");
    expect(scorePhq9([3, 3, 3, 3, 3, 3, 2, 0, 0], "zh").score).toBe(20);
    expect(scorePhq9([3, 3, 3, 3, 3, 3, 2, 0, 0], "zh").band.id).toBe("severe");
  });

  test("item 9 = 1 is watch; 2 is urgent", () => {
    const watch = assess({ ...base(), phq9: { items: [0, 0, 0, 0, 0, 0, 0, 0, 1] } });
    expect(watch.crisis.level).toBe("watch");
    const urgent = assess({ ...base(), phq9: { items: [0, 0, 0, 0, 0, 0, 0, 0, 2] } });
    expect(urgent.crisis.level).toBe("urgent");
    expect(urgent.crisis.resources.some((r) => r.contact === "120")).toBe(true);
    expect(urgent.crisis.resources.some((r) => r.contact === "12356")).toBe(true);
  });

  test("rejects Likert 4", () => {
    expect(() => scorePhq9([0, 0, 0, 0, 0, 0, 0, 0, 4], "zh")).toThrow();
  });

  test("rejects wrong length", () => {
    expect(() => scorePhq9([0, 0, 0], "zh")).toThrow();
  });
});

describe("GAD-7", () => {
  test("all ones is mild 7", () => {
    const r = scoreGad7([1, 1, 1, 1, 1, 1, 1], "zh");
    expect(r.score).toBe(7);
    expect(r.band.id).toBe("mild");
  });

  test("15 is severe screening signal", () => {
    const r = scoreGad7([3, 3, 3, 3, 3, 0, 0], "zh");
    expect(r.score).toBe(15);
    expect(r.band.id).toBe("severe");
  });
});

describe("BMI and movement", () => {
  test("zh uses China WS/T 428 overweight at 24", () => {
    const normal = assess({
      ...base(),
      lifestyle: { ...base().lifestyle, heightCm: 170, weightKg: 68 },
    });
    expect(normal.bmi.cutoffSet).toBe("cn-wst428");
    expect(normal.bmi.value).toBe(23.5);
    expect(normal.bmi.band.id).toBe("normal");

    const over = assess({
      ...base(),
      lifestyle: { ...base().lifestyle, heightCm: 170, weightKg: 70 },
    });
    expect(over.bmi.value).toBe(24.2);
    expect(over.bmi.band.id).toBe("overweight");
  });

  test("en uses global overweight at 25", () => {
    const r = assess({
      ...base(),
      locale: "en",
      lifestyle: { ...base().lifestyle, heightCm: 170, weightKg: 68 },
    });
    expect(r.bmi.cutoffSet).toBe("who-global");
    expect(r.bmi.band.id).toBe("normal");
  });

  test("150 minutes meets WHO", () => {
    expect(scoreMovement(150).band.id).toBe("met");
    expect(scoreMovement(80).flags).toContain("below-who-150");
  });
});

describe("full assessment", () => {
  test("disclaimer is present and composite is 0-100", () => {
    const r = assess(base());
    expect(r.disclaimer.includes("仅供参考")).toBe(true);
    expect(r.composite.total).toBeGreaterThanOrEqual(0);
    expect(r.composite.total).toBeLessThanOrEqual(100);
    expect(r.actions.length).toBeLessThanOrEqual(3);
    expect(r.composite.dimensions).toHaveLength(4);
  });

  test("never diagnoses", () => {
    const r = assess(base());
    const blob = JSON.stringify(r);
    expect(blob.includes("确诊")).toBe(false);
    expect(blob.includes("你患有")).toBe(false);
  });

  test("crisis text overrides to urgent", () => {
    const r = assess(base(), "我不想活了");
    expect(r.crisis.level).toBe("urgent");
  });

  test("smoking and alcohol flags", () => {
    const r = assess({
      ...base(),
      lifestyle: { ...base().lifestyle, smoking: "current", alcoholUnitsWeek: 18 },
    });
    expect(r.lifestyleFlags).toContain("smoking-current");
    expect(r.lifestyleFlags).toContain("alcohol-high");
  });
});

describe("checkin", () => {
  test("happy checkin scores high", () => {
    const r = scoreCheckin({ mood: 5, energy: 5, sleepHours: 8, moved: true, stress: 1 });
    expect(r.kind).toBe("checkin");
    expect(r.score100).toBeGreaterThan(80);
    expect(r.disclaimer.includes("仅供参考")).toBe(true);
  });
});
