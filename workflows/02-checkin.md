# 打卡

没有文件时走这里。先确认库和档案。

按 [../prompts/bomi-required.md](../prompts/bomi-required.md) 收齐蛋白质、抗阻、超负荷。按 [../prompts/huangmao-classification.md](../prompts/huangmao-classification.md) 收 1–5 和一条评价分类。选填用 [../prompts/optional-items.md](../prompts/optional-items.md)，不追问全部小项。

用户没说的选填不要编。必填缺了就照实留空，让脚本记无法评分。

写入 `sessions/` 的一条 JSON：`date`、`date_defaulted`、`red_flags`、`body_required`、`psych_required`、`optional`。然后把窗内会话交给 [04-score.md](04-score.md)。
