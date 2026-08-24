import { describe, expect, test } from "bun:test";
import { mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const bun = process.execPath;
const cli = join(import.meta.dir, "../src/cli.ts");
const sample = join(import.meta.dir, "../examples/sample-answers.json");

async function run(args: string[], env: Record<string, string> = {}) {
  const proc = Bun.spawn([bun, cli, ...args], {
    stdout: "pipe",
    stderr: "pipe",
    env: { ...process.env, ...env },
  });
  const [stdout, stderr, code] = await Promise.all([
    new Response(proc.stdout).text(),
    new Response(proc.stderr).text(),
    proc.exited,
  ]);
  return { stdout, stderr, code };
}

describe("CLI", () => {
  test("--help lists core commands", async () => {
    const r = await run(["--help"]);
    expect(r.code).toBe(0);
    expect(r.stdout).toContain("score");
    expect(r.stdout).toContain("checkin");
    expect(r.stdout).toContain("trend");
  });

  test("score sample file", async () => {
    const home = await mkdtemp(join(tmpdir(), "ha-"));
    const r = await run(["score", "--file", sample], { HEALTH_ASSESSMENT_HOME: home });
    expect(r.code).toBe(0);
    const json = JSON.parse(r.stdout);
    expect(json.kind).toBe("full");
    expect(typeof json.phq9.score).toBe("number");
    expect(json.disclaimer).toContain("仅供参考");
    expect(json.phq9.score).toBe(7);
  });

  test("checkin then trend", async () => {
    const home = await mkdtemp(join(tmpdir(), "ha-"));
    const env = { HEALTH_ASSESSMENT_HOME: home };
    const c = await run(
      ["checkin", "--mood", "3", "--energy", "4", "--sleep", "7.5", "--moved", "yes", "--stress", "2"],
      env,
    );
    expect(c.code).toBe(0);
    const t = await run(["trend"], env);
    expect(t.code).toBe(0);
    const json = JSON.parse(t.stdout);
    expect(json.count).toBe(1);
  });
});
