import { describe, expect, test } from "bun:test";
import { assertNoDiagnosisLanguage, detectCrisisText } from "../src/safety.ts";

describe("safety", () => {
  test("detects Chinese and English crisis phrases", () => {
    expect(detectCrisisText("有时候不想活")).toBe(true);
    expect(detectCrisisText("我不想活了")).toBe(true);
    expect(detectCrisisText("I want to kill myself")).toBe(true);
    expect(detectCrisisText("今天走了两公里")).toBe(false);
    expect(detectCrisisText("最近不想活动")).toBe(false);
    expect(detectCrisisText("这鞋跳楼价")).toBe(false);
  });

  test("forbids diagnosis wording", () => {
    expect(() => assertNoDiagnosisLanguage("你患有中度抑郁")).toThrow();
    expect(() => assertNoDiagnosisLanguage("仅供参考，筛查提示偏高")).not.toThrow();
  });
});
