# 出分

收集窗内会话。用户指定了起止日期就用那段；没指定就用库里已有会话。

```bash
py -3 scripts/score_checkin.py path\to\payload.json
```

`payload.json` 形如 `evals/fixtures/full-7.json`。

回复顺序：

1. 脚本的 `mode` 和 `label`（若有）。
2. `scores` 里的身体必填、身体选填、心理必填、心理选填、合计。无法评分写无法评分，不写成 0。
3. `conclusion` 里的薄肌和黄毛两句。
4. `next_steps`，最多三条。不满 7 天时不要添加训练动作。

把同一份 JSON 写入 `analyses/`。不要改已经存在的 `sessions/` 文件。
