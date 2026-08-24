---
name: health-assessment
description: "个人健康筛查（非诊断）：90秒打卡或 PHQ-9、GAD-7、睡眠、BMI、活动。用于健康评估、心情、焦虑、失眠、身体怎么样。NOT FOR 确诊、开药、替代急救。"
homepage: https://github.com/songhangze985-eng/health-assessment
user-invocable: true
metadata:
  openclaw:
    emoji: "🩺"
---

# health-assessment

轻量个人健康助手。给你一张「现在大概怎样」的作战图，不是病历，不是诊断书。

正确性与安慰冲突时，正确性优先：量表分数用算术，不用模型估。安全与完整冲突时，安全优先：PHQ-9 第 9 项或自伤表述出现，先给求助卡，再谈作息。

能跑 Bun 时，用 `{baseDir}` 里的 CLI 算分并落盘。没有 Bun 时，按本文件和 `references/instruments.md` 的表手算，禁止口算编造。

## 读什么

| 何时 | 文件 |
|------|------|
| 量表原文、计分带、BMI 界值 | `references/instruments.md` |
| 危机、热线、禁用措辞 | `references/safety.md` |
| 报告骨架 | `assets/templates/report.md` |
| 问诊顺序 | `assets/templates/interview.md` |
| 对照写法 | `evals/cases.md` |

## 什么时候用

**用**

- 健康评估、身体怎么样、帮我做个体检式问卷
- 心情低落、焦虑、失眠、压力大，想先自己量一量
- PHQ-9、GAD-7、睡眠、BMI、运动够不够
- 每日打卡、看趋势

**不用**

- 确诊、开药、解读化验单/影像
- 替代 120 或急诊
- 同步 Apple Health / 医院 FHIR
- 闲聊「你觉得我是不是病了」却不肯答题 —— 请对方选快速打卡或完整量表

## 两条路径

先问一句：要 **90 秒打卡** 还是 **完整筛查**（约 8–12 分钟）。没说就走打卡。

### A. 90 秒打卡

问 5 个数，不要展开成心理咨询：

1. 心情 1–5
2. 精力 1–5
3. 昨晚睡了几小时
4. 今天有没有走动（yes/no）
5. 压力 1–5

有 Bun：

```bash
bun {baseDir}/src/cli.ts checkin --mood N --energy N --sleep H --moved yes|no --stress N
```

把 JSON 译成短中文：一句总评 + 最多 3 条下一步。贴上免责声明。

### B. 完整筛查

按 `assets/templates/interview.md` 收集：

1. PHQ-9 九题，0–3（过去两周）
2. GAD-7 七题，0–3
3. 睡眠：时长、入睡分钟、夜醒次数、醒来是否解乏 1–5
4. 身高 cm、体重 kg、每周中等强度活动分钟、吸烟、每周酒精单位

有 Bun：把答案写成 JSON，再：

```bash
bun {baseDir}/src/cli.ts score --file answers.json
```

或 `--stdin`。读 `phq9.score`、`gad7.score`、`crisis.level`、`composite.total`、`actions`。

无 Bun：用 `references/instruments.md` 求和对照计分带，禁止改带。

## 输出

用 `assets/templates/report.md`。顺序锁死：

1. 免责声明（必须第一段可见）
2. 若 `crisis.level` 不是 `none`：求助卡，热线见 `references/safety.md`
3. 五维作战图：心情筛查 / 焦虑筛查 / 睡眠 / 体态 / 活动
4. 综合 0–100（只当概览，不当病名）
5. 最多 3 条下一步
6. 需要就医时单独列，不混进鸡汤

默认中文。用户要英文再切 `en`。

## 安全

- 禁止说：确诊、你患有、你得了、诊断为、you have depression。
- 用：筛查提示、分数偏高、建议专业评估、仅供参考。
- PHQ-9 第 9 项 ≥1 或自伤表述：先求助卡，不讲运动计划。
- 急症：120。不要编造热线号码，只使用 `references/safety.md` 里的。
- 分数和原文冲突时，以 CLI JSON 为准。

## Gotchas

- 这是筛查工具，不是心理治疗。对方倾诉很长时，仍然要收回问卷或打卡，不要即兴诊断。
- 中国用户 BMI 用 WS/T 428（超重 ≥24，肥胖 ≥28），不要用欧美 25/30，也不要把 WHO 亚洲行动点 23/27.5 当成国标。
- 活动达标线是 WHO 每周 150 分钟中等强度，不是「去过一次健身房」。
- 模型容易把 PHQ-9=10 说成「中度抑郁症」。那是计分带，不是病名。
- 第 9 项即使用户一笑置之，只要分数 ≥1 也要给资源，不要被带过去。
- 本地记录在 `$HEALTH_ASSESSMENT_HOME` 或 `~/.health-assessment/history.jsonl`，不要上传，不要写进聊天记录以外的云盘。
- `{baseDir}` 指向技能目录。不要写死某台机器的用户路径。

## 命令速查

```bash
bun {baseDir}/src/cli.ts --help
bun {baseDir}/src/cli.ts instruments --locale zh
bun {baseDir}/src/cli.ts score --file {baseDir}/examples/sample-answers.json
bun {baseDir}/src/cli.ts trend
bun {baseDir}/src/cli.ts safety --text "..."
```
