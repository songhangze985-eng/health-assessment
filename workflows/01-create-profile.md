# 建档

缺任何一项就停，不估算，不打分：

- 身高厘米 `height_cm`
- 体重千克 `weight_kg`
- 年龄 `age`
- 生理性别 `sex`：female、male 或 other
- 训练年限 `training_years`
- 是否有伤病 `injury`：true 或 false

伤病只写入备注。不诊断，不因此停分。

默认目标，除非用户当次就要改：

- `protein_g_per_kg`：1.6，来源 `literature_default_1.6_within_1.4_2.0`
- `resistance_sessions_per_7d`：3，来源 `literature_default_within_2_to_3`

用户要改时，先读 [../prompts/custom-standard.md](../prompts/custom-standard.md)。把档案写入 `settings/config.json`。
