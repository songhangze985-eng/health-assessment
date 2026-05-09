# Health Standards

Use these defaults for general adult lifestyle assessment. Do not use them as diagnosis, treatment, or individualized medical advice.

Thresholds in this file should come from public-health guidelines or formal consensus statements. Use `evidence-papers.md` for peer-reviewed supporting literature, including Nature, Lancet, BMJ, and other research sources. Do not change a user-facing target from a single observational paper alone.

## Source Map

Guidelines and public data:

- CDC About Sleep: https://www.cdc.gov/sleep/about/index.html
- CDC Sleep indicator definition: https://www.cdc.gov/cdi/indicator-definitions/sleep.html
- Chinese Dietary Guidelines 2022, rule 1: https://dg.cnsoc.org/article/04/K7tlcs-UQh67DBC5XY1Jqw.html
- Chinese Dietary Guidelines 2022, rule 2: https://dg.cnsoc.org/article/04/k9W2iu8FT6K5oWaQKArU9g.html
- Chinese Dietary Guidelines 2022, rule 3: https://dg.cnsoc.org/article/04/70JvPbFmTlyZbjoO67LeRg.html
- Chinese Dietary Guidelines 2022, rule 4: https://dg.cnsoc.org/article/04/3tyM8WoTTUmc_oFHMymk3Q.html
- Chinese Dietary Guidelines 2022, rule 5: https://dg.cnsoc.org/article/04/ApX3_ozGTmSoqQaFFh5z_Q.html
- WHO physical activity guidance: https://www.who.int/initiatives/behealthy/physical-activity
- CDC adult physical activity guidance: https://www.cdc.gov/physical-activity-basics/guidelines/adults.html
- USDA FoodData Central API: https://fdc.nal.usda.gov/api-guide
- Peer-reviewed evidence map: `evidence-papers.md`

Evidence hierarchy:

1. Public-health guidelines and formal consensus statements set default thresholds.
2. Systematic reviews and meta-analyses justify risk direction and confidence.
3. Nature-series mechanistic and cohort papers inform explanation, wearable features, and future model tuning.
4. Single cohort studies should not override guideline targets without corroborating evidence.

## Sleep

Default adult thresholds:

- `short`: less than 7 hours.
- `target`: 7 to 9 hours.
- `long`: more than 9 hours.

Age-specific defaults:

| Age group | Recommended daily sleep |
| --- | --- |
| 18-60 | 7+ hours |
| 61-64 | 7-9 hours |
| 65+ | 7-8 hours |

Sleep-window heuristic:

- Bedtime normal window: 21:00-00:30.
- Wake normal window: 05:30-09:00.
- Flag outside this window as schedule feedback only.

## Diet

Chinese Dietary Guidelines 2022 defaults for general adults:

| Item | Default target |
| --- | --- |
| Fresh fruit | 200-350 g/day |
| Fresh vegetables | >=300 g/day |
| Dairy equivalent | >=300 ml liquid milk/day |
| Grain foods | 200-300 g/day |
| Whole grains and legumes | 50-150 g/day |
| Tubers | 50-100 g/day |
| Fish, poultry, eggs, lean meat | 120-200 g/day average |
| Fish | 300-500 g/week is preferred |
| Eggs | 300-350 g/week |
| Livestock and poultry meat | 300-500 g/week |
| Salt | <=5 g/day |
| Cooking oil | 25-30 g/day |
| Added sugar | <=50 g/day, preferably <=25 g/day |
| Trans fat | <=2 g/day |
| Food variety | 12+ food types/day, 25+ food types/week |

Assessment rules:

- Use targets only when the corresponding data is recorded.
- Do not infer salt, oil, added sugar, alcohol, or trans fat from vague dish names.
- For weight-loss, chronic disease, pregnancy, children, older adults, or sports nutrition, require a profile-specific standard set.

## Exercise

Default adult targets:

| Metric | Target |
| --- | --- |
| Moderate aerobic activity | 150-300 min/week |
| Vigorous aerobic activity | 75-150 min/week |
| Equivalent conversion | 1 vigorous minute = 2 moderate-equivalent minutes |
| Muscle strengthening | 2+ days/week |
| China guideline cadence | 5+ days/week moderate activity, 150+ min total |
| Active movement | Preferably 6000 active steps/day |

Intensity inference:

- Moderate: brisk walking, cycling at easy/moderate pace, dancing, household activity.
- Vigorous: running, fast cycling, fast swimming, high-intensity interval training.
- Strength: resistance training, weight training, bodyweight strength work.

If intensity is unclear, store it as `unknown` and ask for optional intensity details in the reply.
