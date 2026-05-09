# Evidence Papers

Use this file as the peer-reviewed evidence layer behind `health-standards.md`.

Do not convert one paper directly into medical advice. Public-health guidelines and formal consensus statements set thresholds; papers below support the rationale, explain mechanisms, and guide future model improvements.

## Evidence Use Rules

- Prefer systematic reviews, meta-analyses, consensus statements, and large prospective cohorts.
- Prefer Nature, Lancet, BMJ, JAMA, NEJM, WHO-backed papers, PubMed-indexed literature, and official guideline publications.
- Treat most nutrition, sleep, and exercise cohort findings as association unless the study design supports causality.
- Keep default recommendations conservative for general adults. Use age, pregnancy, chronic disease, medication, and clinician advice as profile-specific overrides.
- Record citation identifiers in server-side `health_evidence_sources` so reports can cite rule versions.

## Sleep

| Use | Citation | Evidence note |
| --- | --- | --- |
| Adult sleep duration threshold | Watson NF et al. Recommended Amount of Sleep for a Healthy Adult: AASM/SRS Joint Consensus Statement. J Clin Sleep Med. 2015. DOI: https://doi.org/10.5664/jcsm.4758 | Formal consensus supporting 7+ hours for healthy adults. |
| Sleep-duration risk curve | Shen X, Wu Y, Zhang D. Nighttime sleep duration, 24-hour sleep duration and risk of all-cause mortality among adults: meta-analysis. Scientific Reports. 2016. DOI: https://doi.org/10.1038/srep21480 | Nature portfolio meta-analysis; supports U-shaped risk interpretation around usual adult sleep duration. |
| Sleep and cardiovascular outcomes | Cappuccio FP et al. Sleep duration predicts cardiovascular outcomes: systematic review and meta-analysis. European Heart Journal. 2011. DOI: https://doi.org/10.1093/eurheartj/ehr007 | Supports flagging both short and long sleep as risk markers, not diagnoses. |
| Sleep deprivation mechanism | Krause AJ et al. The sleep-deprived human brain. Nature Reviews Neuroscience. 2017. DOI: https://doi.org/10.1038/nrn.2017.55 | Mechanistic review for attention, memory, emotion, and brain-network effects. |
| Acute sleep deprivation | Nir Y et al. Selective neuronal lapses precede human cognitive lapses following sleep deprivation. Nature Medicine. 2017. DOI: https://doi.org/10.1038/nm.4433 | Mechanistic evidence for cognitive lapses after sleep deprivation. |

Implementation notes:

- Keep `short <7 h`, `target 7-9 h`, and `long >9 h` for general adults unless profile-specific rules exist.
- Explain schedule regularity as a habit heuristic, not as disease risk scoring.
- If users report insomnia, sleep apnea symptoms, severe daytime sleepiness, or safety-critical fatigue, recommend clinical consultation rather than algorithmic scoring.

## Diet And Nutrition

| Use | Citation | Evidence note |
| --- | --- | --- |
| Fruit and vegetable rationale | Aune D et al. Fruit and vegetable intake and risk of cardiovascular disease, total cancer and all-cause mortality: systematic review and dose-response meta-analysis. International Journal of Epidemiology. 2017. DOI: https://doi.org/10.1093/ije/dyw319 | Supports fruit/vegetable tracking as a meaningful diet-quality signal. |
| Global dietary risk priorities | GBD 2017 Diet Collaborators. Health effects of dietary risks in 195 countries, 1990-2017. The Lancet. 2019. DOI: https://doi.org/10.1016/S0140-6736(19)30041-8 | Supports attention to sodium, whole grains, fruit, nuts/seeds, vegetables, and other population-level diet risks. |
| Fiber and whole grains | Reynolds A et al. Carbohydrate quality and human health: systematic reviews and meta-analyses. The Lancet. 2019. DOI: https://doi.org/10.1016/S0140-6736(18)31809-9 | Supports fiber and whole-grain fields in the nutrition model. |
| Food healthfulness scoring | Mozaffarian D et al. Food Compass is a nutrient profiling system. Nature Food. 2021. DOI: https://doi.org/10.1038/s43016-021-00381-y | Useful design reference for multi-domain food scoring; do not copy scores blindly. |
| Updated food scoring | Barrett EM et al. Food Compass 2.0. Nature Food. 2024. DOI: https://doi.org/10.1038/s43016-024-01053-3 | Useful if adding a server-side food quality score. Keep separate from guideline targets. |
| Healthy aging diet patterns | Tessier AJ et al. Optimal dietary patterns for healthy aging. Nature Medicine. 2025. DOI: https://doi.org/10.1038/s41591-025-03570-5 | Supports plant-forward dietary pattern summaries in long-term reports; observational cohort evidence. |
| Ultra-processed foods | Lane MM et al. Ultra-processed food exposure and adverse health outcomes: umbrella review. BMJ. 2024. DOI: https://doi.org/10.1136/bmj-2023-077310 | Supports optional tracking of ultra-processed foods when user-entered data or labels make it feasible. |

Implementation notes:

- Keep Chinese Dietary Guidelines 2022 as the primary Chinese-default target source.
- Use USDA FoodData Central and package labels for nutrient facts; use peer-reviewed papers for rationale and scoring design.
- Do not estimate sodium, added sugar, cooking oil, or ultra-processed status from vague home-cooked dish names unless recipe or label data is present.

## Exercise And Sedentary Behavior

| Use | Citation | Evidence note |
| --- | --- | --- |
| Physical activity threshold | Bull FC et al. WHO 2020 guidelines on physical activity and sedentary behaviour. British Journal of Sports Medicine. 2020. DOI: https://doi.org/10.1136/bjsports-2020-102955 | Formal guideline paper supporting 150-300 min moderate or 75-150 min vigorous weekly activity. |
| Dose-response and sedentary time | Ekelund U et al. Accelerometry measured physical activity, sedentary time, and all-cause mortality: systematic review and harmonised meta-analysis. BMJ. 2019. DOI: https://doi.org/10.1136/bmj.l4570 | Supports "move more, sit less" messaging and non-linear dose-response framing. |
| Wearable activity data | Strain T et al. Wearable-device-measured physical activity and future health risk. Nature Medicine. 2020. DOI: https://doi.org/10.1038/s41591-020-1012-3 | Supports future wearable integration and intensity-aware activity scoring. |
| Short vigorous bursts | Stamatakis E et al. Wearable device-measured vigorous intermittent lifestyle physical activity with mortality. Nature Medicine. 2022. DOI: https://doi.org/10.1038/s41591-022-02100-x | Supports recording brief vigorous activity if captured by wearable or user input. |
| Step counts | Paluch AE et al. Daily steps and all-cause mortality: meta-analysis of 15 international cohorts. The Lancet Public Health. 2022. DOI: https://doi.org/10.1016/S2468-2667(21)00302-9 | Supports optional step-count reports while avoiding an unsupported universal 10,000-step rule. |

Implementation notes:

- Keep weekly activity targets from WHO/CDC/Chinese Dietary Guidelines.
- Convert vigorous minutes to moderate-equivalent minutes only for progress tracking.
- Store wearable-derived metrics separately from self-reported exercise because measurement error and interpretation differ.

## Future Evidence Updates

When updating evidence:

1. Add the citation here with DOI or official URL.
2. Note whether it is guideline, consensus, meta-analysis, cohort, randomized trial, mechanistic, or narrative review.
3. Update `health_evidence_sources` seed data or migrations in the server implementation.
4. Change thresholds in `health-standards.md` only when guideline or consensus evidence changes.
5. Re-run skill validation and representative record/report examples.
