---
name: health-assessment
description: >-
  个人发展与健康评估。多人各用一个记忆库：没文件就显化打卡，有文件就先分析再入库。
  满 7 个不同日期后给出身体 100、心理抗压 100、合计 200 和最多三条下一步。
  用于打卡、训练饮食睡眠记录、薄肌、黄毛、心理抗压、健康复盘。
  不用于诊断、开药、影像或财务建议。
---

# 个人发展与健康评估

非诊断。分数只来自 `scripts/score_checkin.py`，不要心算。薄肌和黄毛只出现在结论文字里，不另开分数栏。

## 先做哪一步

1. 读 [workflows/00-bind-library.md](workflows/00-bind-library.md)，确定这个人的记忆库。
2. 档案缺字段时读 [workflows/01-create-profile.md](workflows/01-create-profile.md)，停在补字段，不估算。
3. 输入里出现红旗时只读 [workflows/06-red-flag.md](workflows/06-red-flag.md)。红旗：胸痛、昏厥、晕厥、自伤、轻生、自行停药、急性剧痛、呼吸困难、异常心悸、骨裂、关节急性肿胀。
4. 有文档或表格时读 [workflows/03-analyze-file.md](workflows/03-analyze-file.md)。没有文件时读 [workflows/02-checkin.md](workflows/02-checkin.md)。
5. 要出分时读 [workflows/04-score.md](workflows/04-score.md)。只回顾旧记录时读 [workflows/05-read-memory.md](workflows/05-read-memory.md)。

## 分数

身体 100 = 必填 80 + 选填 20。心理抗压同样。合计 200。必填三项和黄毛两项在内部均分。选填只在写过的小项之间平分 20。没写的选填记无法评分，不记 0。必填缺任何一块，该 80 不合成，总分不合成。不满 7 个不同日期不出 200 分。

公式、文献范围和选填名单在 [standards/scoring.md](standards/scoring.md)、[standards/literature.md](standards/literature.md)、[standards/domains.md](standards/domains.md)。红旗和禁止项在 [standards/safety.md](standards/safety.md)。

## 记忆库

路径第一次要问，写入仓库外的库，并在本仓库 `.memory-path` 只记指针。`.memory-path` 不提交。授予写入后只追加 `sessions/` 和 `analyses/`，不改旧文件。回顾时只读。布局见 [workflows/00-bind-library.md](workflows/00-bind-library.md)。

## 本地接口

表格导入或桌宠状态用 `py -3 scripts/health_api_server.py`。它只听 `127.0.0.1:8765`。记忆库仍由 `.memory-path` 或 `HEALTH_MEMORY_PATH` 指出，不在仓库里猜路径，也不补档案数字。

## 验收

`py -3 scripts/test_score.py` 必须通过。样例在 `evals/fixtures/`。人工核对表在 [evals/accept.md](evals/accept.md)。
