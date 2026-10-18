# Health Assessment（薄肌与黄毛个人健康评估）

**Seven days. Deterministic scores. No medical diagnosis.**

`health-assessment` 把日常自述、饮食或训练图片，以及手表、手机导出的 CSV / Excel，收成同一个人的打卡记录。身体「薄肌」和心理抗压「黄毛」各 100 分。满 7 个不同日期后，由本地脚本合成 200 分。不满 7 天只给出当天还缺什么。

它同时是一份 OpenClaw Skill，并带有 [LorisYounger/VPet](https://github.com/LorisYounger/VPet) 桌宠插件工程。

## 核心特性

- **只认脚本算的分。** `scripts/score_checkin.py` 是唯一算分入口。模型不要心算，也不要补没写的数字。
- **两条主线分开记。** 身体必填是蛋白质、抗阻、渐进超负荷，三项平分 80 分。心理必填是 1–5 自评和评价分类，两项各 40 分。每一侧再加 20 分选填。
- **选填只在写过的项目之间平分 20 分。** 没写的项目不计 0。一项都没写则是无法评分，该侧 100 分不合成。
- **抗阻按自然日跨度算期望次数。** 有窗口就用窗口起止日；没有窗口就用最早和最晚打卡日。不满 7 个不同日期仍然不出总分。
- **同日多源合并。** 训练时长和蛋白质优先保留穿戴记录。超负荷和心理自评优先保留本人自述。
- **本地服务只听回环地址。** 默认 `http://127.0.0.1:8765`，可用 `HEALTH_API_PORT` 修改。
- **红旗立即停分。** 胸痛、昏厥、晕厥、自伤、轻生、自行停药、急性剧痛、呼吸困难、异常心悸、骨裂、关节急性肿胀。写在标签里，或出现在原文里，都停。紧挨着「没有」「无」「否认」「未出现」「未诉」的不算。停分后只提示联系医疗或当地紧急帮助，不开药，不给训练计划。

## 运行模式

| `mode` | 条件 | 结果 |
| :--- | :--- | :--- |
| `blocked_profile` | 缺身高、体重、年龄、性别、训练年限或是否有伤病 | 不打分，返回缺的字段 |
| `redflag` | 标签或原文命中红旗词 | 不打分。桌宠状态为 `Ill` |
| `under7` | 档案完整、无红旗，不同日期少于 7 天 | 不出 200 分。返回 `daily_progress` |
| `scored` | 档案完整、无红旗，不同日期不少于 7 天 | 给出 200 分明细。桌宠按分数使用 `Happy` 或 `Nomal` |

`Nomal` 是 VPet 状态枚举里的拼写。

身体或心理的必填缺任何一块，那一侧不合成，总分也不合成。有伤病只记在档案里，本身不停分。

## 目录

```text
health-assessment/
├── LICENSE
├── README.md
├── SKILL.md
├── evals/
│   ├── accept.md
│   └── fixtures/
├── prompts/
│   ├── bomi-required.md
│   ├── custom-standard.md
│   ├── huangmao-classification.md
│   └── optional-items.md
├── scripts/
│   ├── score_checkin.py
│   ├── health_api_server.py
│   ├── test_score.py
│   ├── test_health_api.py
│   └── validate_skill.py
├── standards/
│   ├── domains.md
│   ├── item-sources.md
│   ├── literature.md
│   ├── safety.md
│   └── scoring.md
├── vpet_bridge/
│   ├── VPetHealthPlugin.cs
│   ├── VPet.Plugin.HealthAssessment.csproj
│   └── info.lps
└── workflows/
    ├── 00-bind-library.md
    ├── 01-create-profile.md
    ├── 02-checkin.md
    ├── 03-analyze-file.md
    ├── 04-score.md
    ├── 05-read-memory.md
    └── 06-red-flag.md
```

## 环境

- Python 3.10 或更高版本。计分和 CSV 解析只用标准库。
- 读取 `.xlsx` 时需要 `openpyxl`：`pip install openpyxl`。没有它时请先导出 CSV。
- VPet 插件在 Windows 上编译，目标框架是 `net8.0-windows`，NuGet 包为 `VPet-Simulator.Core` 与 `VPet-Simulator.Windows.Interface` 1.1。

## 记忆库与档案

服务按这个顺序找库：调用时传入的目录、`HEALTH_MEMORY_PATH`、仓库根目录的 `.memory-path`。三者都没有时，使用 `./memory_store`，并创建 `sessions/` 与 `analyses/`。`.memory-path` 和 `memory_store/` 不提交。

对话流程里仍然先问这个人的库在哪，不要把下一个人的记录写进上一个库。

```bash
mkdir -p ./my_health_memory
printf '%s\n' "./my_health_memory" > .memory-path
```

也可以等服务起来后提交：

```bash
curl -s -X POST http://127.0.0.1:8765/api/bind-library \
  -H 'Content-Type: application/json' \
  -d '{"memory_path":"./my_health_memory"}'
```

档案六个字段缺一不可：`height_cm`、`weight_kg`、`age`、`sex`（`female`、`male` 或 `other`）、`training_years`、`injury`（布尔值）。缺了就拒绝保存，不估算。

```bash
curl -s -X POST http://127.0.0.1:8765/api/profile \
  -H 'Content-Type: application/json' \
  -d '{"height_cm":172,"weight_kg":75,"age":36,"sex":"male","training_years":0,"injury":false}'
```

`GET /api/profile` 读取当前档案。保存成功后的响应就是当前 `evaluate_payload`，并带上 `vpet_state`。

## 命令行计分

```bash
python scripts/score_checkin.py evals/fixtures/full-7.json
```

也可以把 JSON 从标准输入送进去。回复时使用脚本印出的 `mode`、`scores`、`conclusion`、`next_steps`，不要另算一遍。

## 本地服务

```bash
python scripts/health_api_server.py
```

没设置 `LLM_API_KEY` 时，文字打卡用本地规则。图片不会被识别，只保留说明文字。设置了 Key 后，`LLM_API_URL` 与 `LLM_MODEL` 可用 OpenAI 兼容接口。

| 方法 | 路径 | 作用 |
| :--- | :--- | :--- |
| `POST` | `/api/bind-library` | 写入 `.memory-path` 并切换当前库 |
| `GET` | `/api/profile` | 读取档案和缺字段 |
| `POST` | `/api/profile` | 校验并保存档案，返回最新评估 |
| `GET` | `/api/greeting` | 今日缺项和桌宠气泡 |
| `POST` | `/api/checkin/text` | 自然语言打卡 |
| `POST` | `/api/checkin/file` | Base64 的 CSV、Excel 或图片 |
| `GET` | `/api/score` | 当前窗口的评估和 `vpet_state` |

## 桌宠插件

`vpet_bridge/` 是插件源码，不是已经编译好的模组。在 Windows 上用该目录的 csproj 生成 DLL 后，与 `info.lps` 一起放进 VPet 模组目录。`PluginName` 是 `HealthAssessment`，必须和 `info.lps` 里的模组名一致。

插件启动时先访问 `/api/greeting`。连不上就从 `HEALTH_ASSESSMENT_ROOT`，或插件目录往上找到的 `scripts/health_api_server.py`，后台拉起 `python`。这个子进程只在插件自己启动它时，于 `EndGame()` 里结束。

右键「互动」菜单有三项：今日文字打卡、查看 7 天评估报告、导入手表或手机健康文件。CSV、Excel 和图片也可以直接拖到桌宠上。

## 测试

```bash
python scripts/test_score.py
python scripts/test_health_api.py
python scripts/validate_skill.py
```

## 协议与边界

项目使用 MIT License。分数只用于个人记录习惯。它不诊断、不开药、不解读化验或影像，也不提供财务、加密或婚恋建议。出现红旗或身体不适时，停止加练并联系医疗或当地紧急帮助。
