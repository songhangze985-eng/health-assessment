import { describe, expect, test } from "bun:test";
import { mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { appendRecord, historyPath, readHistory, storeDir } from "../src/store.ts";

describe("store", () => {
  test("uses HEALTH_ASSESSMENT_HOME and append-only jsonl", async () => {
    const home = await mkdtemp(join(tmpdir(), "ha-"));
    process.env.HEALTH_ASSESSMENT_HOME = home;
    expect(storeDir()).toBe(home);
    expect(historyPath()).toBe(join(home, "history.jsonl"));
    await appendRecord({ kind: "checkin", n: 1 });
    await appendRecord({ kind: "checkin", n: 2 });
    const rows = await readHistory();
    expect(rows).toHaveLength(2);
    expect((rows[1] as { n: number }).n).toBe(2);
  });

  test("never uses a hardcoded user folder", () => {
    const src = storeDir.toString();
    expect(src.includes("C:\\\\Users\\\\33446")).toBe(false);
  });
});
