# Report Templates

Use concise Chinese output. Omit sections with no data.

## Immediate Reply

```markdown
已记录：{record_summary}

评估：{assessment_summary}
{missing_data_hint}
```

Examples:

```markdown
已记录：睡眠 23:10-07:05，共 7.9 小时。

评估：时长在成人常见建议范围内，入睡和起床时段也比较规律。
```

```markdown
已记录：苹果 1 个，按默认可食部 182g 估算。

评估：本次约 95 kcal，水果摄入约 182g，接近每日 200-350g 的参考范围。未提供实际重量，营养值为估算。
```

## Condition Guidance Reply

```markdown
已识别：{condition_name}。这不是诊断，我会先按健康教育和分诊提示处理。

警示：{red_flag_summary}

可能原因：
- {possible_cause}

建议补充的信息：
- {question}

可先注意：
- {self_care}

{weather_context}

提示：本内容仅用于健康教育和分诊提示，不构成诊断或处方。症状严重、持续或让你担心时，应联系医疗专业人员。
```

## Seasonal Fruit Reply

```markdown
{month}月当季水果参考：{fruit_list}。

{season_focus}

每日鲜果参考量：200-350g，优先完整鲜果，果汁不能替代鲜果。

{weather_advice}
```

## Weekly Monday Reminder

```markdown
本周健康目标：

| 模块 | 建议目标 | 当前进度 |
| --- | ---: | ---: |
| 水果 | 1400-2450g | {fruit_progress} |
| 中等强度运动 | >=150分钟 | {moderate_progress} |
| 抗阻/力量训练 | >=2天 | {strength_progress} |

{coverage_note}
```

If there are no current-week records, omit `当前进度` values or show `暂无记录`.

## Monthly Report

```markdown
# {month} 健康评估表

数据覆盖：{coverage_summary}

## 睡眠

| 指标 | 结果 |
| --- | ---: |
| 记录天数 | {sleep_days} |
| 平均时长 | {avg_sleep_hours} 小时 |
| 达标天数 | {target_sleep_days} |
| 偏晚入睡次数 | {late_bedtime_count} |

结论：{sleep_summary}

## 饮食

| 指标 | 结果 |
| --- | ---: |
| 水果总量 | {fruit_g} g |
| 蔬菜总量 | {vegetable_g} g |
| 平均每日能量 | {avg_energy_kcal} kcal |
| 估算记录比例 | {estimated_ratio} |

结论：{diet_summary}

## 运动

| 指标 | 结果 |
| --- | ---: |
| 中等强度等效总量 | {moderate_equivalent_minutes} 分钟 |
| 运动天数 | {exercise_days} |
| 力量训练天数 | {strength_days} |

结论：{exercise_summary}

提示：本报告仅用于生活方式记录和健康教育，不构成医疗建议。
```

Remove any module section with no records in the month.
