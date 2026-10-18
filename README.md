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

## 命令行计分

```bash
python scripts/score_checkin.py evals/fixtures/full-7.json
```

也可以把 JSON 从标准输入送进去。回复时使用脚本印出的 `mode`、`scores`、`conclusion`、`next_steps`，不要另算一遍。

## 本地服务与快速上手（3 步跑通）

### 第 1 步：启动本地服务

本地服务默认监听 `http://127.0.0.1:8765`（可通过 `HEALTH_API_PORT` 修改）。未配置 `LLM_API_KEY` 时，文字打卡自动使用本地规则提取；配置后支持 OpenAI 兼容接口识别文本与图片：

```bash
# 可选：配置大模型 API（macOS / Linux）
export LLM_API_KEY="your-api-key"
export LLM_API_URL="https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
export LLM_MODEL="gemini-2.5-flash"

# Windows PowerShell 可使用：$env:LLM_API_KEY="your-api-key"

# 启动本地回环服务
python scripts/health_api_server.py
```

### 第 2 步：绑定记忆库并初始化个人档案（首次必填）

服务按 **调用时传入目录 → `HEALTH_MEMORY_PATH` → 仓库根目录 `.memory-path` → `./memory_store`** 的顺序定位存储库，并自动创建 `sessions/` 与 `analyses/`。

打开第二个终端窗口，绑定记忆库并写入 6 项必填身体档案（`height_cm`、`weight_kg`、`age`、`sex`、`training_years`、`injury` 缺一不可，否则处于 `blocked_profile` 模式不予打分）：

```bash
# 1. 绑定本地记忆库目录
curl -s -X POST http://127.0.0.1:8765/api/bind-library \
  -H 'Content-Type: application/json' \
  -d '{"memory_path":"./my_health_memory"}'

# 2. 保存个人基础档案（保存后即返回当前评估状态与 vpet_state）
curl -s -X POST http://127.0.0.1:8765/api/profile \
  -H 'Content-Type: application/json' \
  -d '{"height_cm":172,"weight_kg":75,"age":36,"sex":"male","training_years":0,"injury":false}'
```

### 第 3 步：提交日常打卡与查询进度

```bash
# 自然语言打卡
curl -s -X POST http://127.0.0.1:8765/api/checkin/text \
  -H 'Content-Type: application/json' \
  -d '{"date":"2026-10-18","text":"今天抗阻训练45分钟并增加了卧推重量，蛋白质吃了140g，心理自评5分，排除恶意评价不内耗"}'

# 查看今日缺项与桌宠打招呼气泡
curl -s http://127.0.0.1:8765/api/greeting

# 查看当前 7 天窗口评估结果
curl -s http://127.0.0.1:8765/api/score
```

| 方法 | 路径 | 请求体关键字段 | 作用 |
| --- | --- | --- | --- |
| `POST` | `/api/bind-library` | `{"memory_path": "./my_health_memory"}` | 写入 `.memory-path` 并切换当前库 |
| `GET` | `/api/profile` | 无 | 读取当前档案和缺失字段 |
| `POST` | `/api/profile` | `height_cm`, `weight_kg`, `age`, `sex`, `training_years`, `injury` | 校验并保存档案，返回最新评估 |
| `GET` | `/api/greeting` | 无（可选 `?date=YYYY-MM-DD`） | 获取今日缺项和桌宠追问气泡 |
| `POST` | `/api/checkin/text` | `{"text": "...", "date": "YYYY-MM-DD"}` | 自然语言文本打卡 |
| `POST` | `/api/checkin/file` | `{"filename": "a.csv", "file_base64": "...", "date": "..."}` | 上传 Base64 编码的 CSV、Excel 或图片 |
| `GET` | `/api/score` | 无 | 获取当前窗口的评估和 `vpet_state` |

## macOS 顶部状态栏轻桌宠

Mac 上用菜单栏宠物，不启动 Windows 版 VPet。它连接同一个 `127.0.0.1:8765`；如果服务没开，会在后台拉起 `scripts/health_api_server.py`，退出时只关掉自己拉起的那个进程。

```bash
python3 -m pip install --user rumps
python3 scripts/mac_menubar_pet.py
```

要直接读 `.xlsx` 再加 `python3 -m pip install --user openpyxl`。端口仍由 `HEALTH_API_PORT` 控制，默认 8765。

状态栏会显示 `🐾 0/7天(0%)`、`😄 6/7天(100%)`、`💪 168/200分` 或 `🚨 红旗预警`。菜单可以文字打卡、用 Finder 选择 CSV / Excel / 图片、查看 7 天报告。每 2 小时用系统通知追问一次缺项。

## 桌宠插件（Windows VPet 端）

`vpet_bridge/` 为插件源码，首次使用前请先按上方“第 2 步”初始化个人档案（`profile.json`），随后按以下步骤编译并放入 [LorisYounger/VPet](https://github.com/LorisYounger/VPet) 的 `mod/` 目录：

```powershell
# 1. 在 Windows 下编译生成插件 DLL
dotnet build -c Release vpet_bridge/VPet.Plugin.HealthAssessment.csproj
```

2. 在 VPet 的 `mod/` 目录下新建 `HealthAssessment` 文件夹，按以下固定层级放置文件（`PluginName` 为 `HealthAssessment`，必须与 `info.lps` 一致）：

```text
VPet安装目录/mod/HealthAssessment/
├── info.lps                                    # 复制自 vpet_bridge/info.lps
└── plugin/
    └── VPet.Plugin.HealthAssessment.dll        # 复制自 vpet_bridge/bin/Release/net8.0-windows/
```

3. 启动 VPet 并在设置中启用该模组：
   - 插件启动时会先请求 `/api/greeting`；若本地服务未运行，插件会自动从 `HEALTH_ASSESSMENT_ROOT` 环境变量或上级目录找到 `scripts/health_api_server.py` 并在后台拉起 `python` 进程（退出桌宠时自动结束）。
   - 右键桌宠点击「互动」菜单可使用三项功能：**今日文字打卡**、**查看 7 天评估报告**、**导入手表或手机健康文件**；也可直接将 CSV、Excel 或图片拖到桌宠身上完成打卡。

## 测试

```bash
python scripts/test_score.py
python scripts/test_health_api.py
python scripts/validate_skill.py
```

## 协议与边界

项目使用 MIT License。分数只用于个人记录习惯。它不诊断、不开药、不解读化验或影像，也不提供财务、加密或婚恋建议。出现红旗或身体不适时，停止加练并联系医疗或当地紧急帮助。
