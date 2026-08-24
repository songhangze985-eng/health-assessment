# health-assessment

> An [Agent Skill](https://agentskills.io) that turns a short conversation into a personal health **screening** picture — not a diagnosis.

90 秒打卡，或 PHQ-9 / GAD-7 / 睡眠 / BMI / 活动的完整筛查。给你一张五维作战图和最多三件下一步。急症仍然是 **120**。

兼容任何实现 [Agent Skills](https://agentskills.io) 的宿主：OpenClaw、Claude Code、Grok、Cursor、Codex、Copilot 等。技能本体是 `SKILL.md`。Bun 脚本只负责算术，避免模型口算量表。

[![Agent Skills](https://img.shields.io/badge/SKILL.md-open_standard-blue)](https://agentskills.io)
[![License: MIT](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)
[![Bun](https://img.shields.io/badge/scorer-Bun_TypeScript-f9f1e1)](https://bun.sh)

**仅供参考，不是诊断，也不能替代执业医师。**

## 它做什么

| 输入 | 输出 |
|------|------|
| 「帮我做个健康评估」 | 先选 90 秒打卡或完整量表 |
| PHQ-9 九题 0–3 | 0–27 + Kroenke 计分带（筛查信号，不是病名） |
| GAD-7 七题 0–3 | 0–21 + 计分带 |
| 身高体重 / 活动分钟 | 中国 WS/T 428 BMI（超重 24 / 肥胖 28）+ 每周 150 分钟线 |
| 第 9 项或「不想活」 | 求助卡置顶，热线见 `references/safety.md` |

和医院健康 OS 的差别：不接 FHIR，不拉病历，不上云，不要求 API key。本地 `history.jsonl` 可选。

## 从高 star 项目学什么、不学什么

检索了同赛道里真正有星的仓库，再压成轻量技能：

| 项目 | 星级量级 | 采纳 | 拒绝 |
|------|----------|------|------|
| [FreedomIntelligence/OpenClaw-Medical-Skills](https://github.com/FreedomIntelligence/OpenClaw-Medical-Skills) | ~3k | 技能形态、PHQ/GAD、危机分流、中文、本地数据 | 869 个临床/组学/PubMed 技能，体积与「轻量」相反 |
| [Health CLAW / healthy-habits](https://github.com/FHIR-IQ/FHIRBuilders) | FHIR 健康助手套件 | 「健康作战图」、免责声明、写操作需人确认 | SMART-on-FHIR、MCP 后端、HEDIS |
| [PHQ / GAD screeners](https://www.phqscreeners.com/) | 临床标准工具 | 官方题干与计分带；Pfizer 声明公众可免费使用 | 把筛查带写成确诊；自制自杀风险总分 |
| 用户自己的 [conversion-skill](https://github.com/songhangze985-eng/conversion-skill) | 同作者技能包装 | `SKILL.md` 为产品、references / evals / 中文默认、零账号 | 把健康评估做成需要故事皮肤的转换器 |

**明确不在范围：** EHR、CT 解读、开药、Framingham 十年风险、可穿戴同步。

## 快速开始

技能会在自然语言里自动触发。也可以显式调用 `/health-assessment`。

**适合**

```
帮我做个健康评估
最近失眠又心情差，想先自己测测
做一下 PHQ-9 和 GAD-7
每日健康打卡
我活动量够不够
```

**不适合**

- 确诊、开药、替代急诊
- 把医院信息系统接进来
- 纯闲聊却不肯答题

### 安装到 Agent

把本仓库拷到宿主的 skills 路径，文件夹名必须是 `health-assessment`：

| 宿主 | 路径 |
|------|------|
| OpenClaw | `~/.openclaw/workspace/skills/health-assessment/` |
| Claude Code | `~/.claude/skills/health-assessment/` |
| Grok | `~/.grok/skills/health-assessment/` |
| Cursor | `.cursor/skills/health-assessment/` 或 `~/.cursor/skills/health-assessment/` |

Windows（OpenClaw）：

```powershell
git clone https://github.com/songhangze985-eng/health-assessment.git
Copy-Item -Recurse health-assessment "$env:USERPROFILE\.openclaw\workspace\skills\health-assessment"
```

要求：目录内有 `SKILL.md`，YAML `name` 为 `health-assessment`。

### 可选：本地计分 CLI

需要 [Bun](https://bun.sh)。**不算分也可以用技能** —— 宿主按 `references/instruments.md` 手算。

```bash
bun src/cli.ts --help
bun src/cli.ts score --file examples/sample-answers.json
bun src/cli.ts checkin --mood 3 --energy 4 --sleep 7.5 --moved yes --stress 2
bun src/cli.ts trend
bun test
```

Windows 若 `bun` 不在 PATH：`%USERPROFILE%\.bun\bin\bun.exe`。

历史默认写到 `~/.health-assessment/history.jsonl`。可用环境变量 `HEALTH_ASSESSMENT_HOME` 改目录（测试用临时目录，不要写死用户路径）。

## 默认行为

| 项 | 默认 | 用户可改 |
|----|------|----------|
| 语言 | 中文 | `--locale en` |
| BMI 界值 | 中国 WS/T 428（超重 24 / 肥胖 28） | 英文走 WHO 国际 25/30 |
| 活动 | WHO 150 分钟/周 | — |
| 记录 | 本地 JSONL | `--no-store` |
| 危机 | 第 9 项或自伤词 → 求助卡 | — |

## 仓库结构

```
health-assessment/
├── SKILL.md                    # 技能入口
├── LICENSE
├── README.md
├── src/                        # Bun 计分器（可选）
│   ├── cli.ts
│   ├── scoring.ts
│   ├── instruments.ts
│   ├── safety.ts
│   └── store.ts
├── tests/
├── examples/
├── references/                 # 量表、安全
├── assets/templates/           # 问诊与报告骨架
└── evals/                      # 触发样本与评测
```

## FAQ

**会不会把我诊断成抑郁症？**  
不会当作合法结果。输出只允许「筛查提示」。计分带来自 PHQ-9 文献，不是病名。

**数据去哪？**  
默认本机。计分路径没有 `fetch`。不要把 `history.jsonl` 提交进 git。

**为什么不用 869 个医疗技能？**  
那是研究/临床工具箱。本仓库要的是能装进 OpenClaw 的轻量助手。

## License

[MIT](LICENSE)

PHQ-9 / GAD-7 题干版权属于原作者；Pfizer 允许免费复制分发。本仓库的代码与文档按 MIT 授权。
