import type { Band, Likert4, Locale } from "./types.ts";

export const LIKERT4_LABELS = {
  zh: ["根本没有", "有几天", "超过一半天数", "几乎每天"] as const,
  en: ["Not at all", "Several days", "More than half the days", "Nearly every day"] as const,
};

export const PHQ9_ITEMS = {
  zh: [
    "做事时提不起劲或没有乐趣",
    "感到心情低落、沮丧或绝望",
    "入睡困难、睡不安稳或睡眠过多",
    "感觉疲倦或没有活力",
    "食欲不振或吃太多",
    "觉得自己很糟，或觉得自己很失败，或让自己或家人失望",
    "对事物专注有困难，例如阅读报纸或看电视时",
    "动作或说话速度缓慢到别人已经察觉；或正好相反——烦躁或坐立不安、动来动去的情况比平常更严重",
    "有不如死掉或用某种方式伤害自己的念头",
  ],
  en: [
    "Little interest or pleasure in doing things",
    "Feeling down, depressed, or hopeless",
    "Trouble falling or staying asleep, or sleeping too much",
    "Feeling tired or having little energy",
    "Poor appetite or overeating",
    "Feeling bad about yourself — or that you are a failure or have let yourself or your family down",
    "Trouble concentrating on things, such as reading the newspaper or watching television",
    "Moving or speaking so slowly that other people could have noticed. Or the opposite — being so fidgety or restless that you have been moving around a lot more than usual",
    "Thoughts that you would be better off dead, or of hurting yourself in some way",
  ],
} as const;

export const GAD7_ITEMS = {
  zh: [
    "感觉紧张、焦虑或不安",
    "无法停止或控制担忧",
    "对各种事情担心太多",
    "难以放松",
    "坐立不安，以至于很难安静地坐下来",
    "变得容易生气或急躁",
    "感觉害怕，好像有可怕的事情要发生一样",
  ],
  en: [
    "Feeling nervous, anxious, or on edge",
    "Not being able to stop or control worrying",
    "Worrying too much about different things",
    "Trouble relaxing",
    "Being so restless that it is hard to sit still",
    "Becoming easily annoyed or irritable",
    "Feeling afraid as if something awful might happen",
  ],
} as const;

export const PHQ9_BANDS: Band[] = [
  { id: "minimal", min: 0, max: 4, labelZh: "很少或没有", labelEn: "None–minimal" },
  { id: "mild", min: 5, max: 9, labelZh: "轻度", labelEn: "Mild" },
  { id: "moderate", min: 10, max: 14, labelZh: "中度", labelEn: "Moderate" },
  { id: "mod-severe", min: 15, max: 19, labelZh: "中重度", labelEn: "Moderately severe" },
  { id: "severe", min: 20, max: 27, labelZh: "重度筛查信号", labelEn: "Severe screening signal" },
];

export const GAD7_BANDS: Band[] = [
  { id: "minimal", min: 0, max: 4, labelZh: "很少或没有", labelEn: "Minimal" },
  { id: "mild", min: 5, max: 9, labelZh: "轻度", labelEn: "Mild" },
  { id: "moderate", min: 10, max: 14, labelZh: "中度", labelEn: "Moderate" },
  { id: "severe", min: 15, max: 21, labelZh: "重度筛查信号", labelEn: "Severe screening signal" },
];

/** China WS/T 428-2013 adult BMI. Default for locale zh. */
export const BMI_CN_BANDS: Band[] = [
  { id: "underweight", min: 0, max: 18.49, labelZh: "偏瘦", labelEn: "Underweight" },
  { id: "normal", min: 18.5, max: 23.99, labelZh: "正常范围", labelEn: "Normal (WS/T 428)" },
  { id: "overweight", min: 24, max: 27.99, labelZh: "超重", labelEn: "Overweight (WS/T 428)" },
  { id: "obese-1", min: 28, max: 200, labelZh: "肥胖", labelEn: "Obese (WS/T 428)" },
];

export const BMI_GLOBAL_BANDS: Band[] = [
  { id: "underweight", min: 0, max: 18.49, labelZh: "偏瘦", labelEn: "Underweight" },
  { id: "normal", min: 18.5, max: 24.99, labelZh: "正常范围", labelEn: "Normal" },
  { id: "overweight", min: 25, max: 29.99, labelZh: "超重", labelEn: "Overweight" },
  { id: "obese-1", min: 30, max: 34.99, labelZh: "肥胖 I 级", labelEn: "Obese class I" },
  { id: "obese-2", min: 35, max: 200, labelZh: "肥胖 II 级+", labelEn: "Obese class II+" },
];

export function bandFor(score: number, bands: Band[]): Band {
  const hit = bands.find((b) => score >= b.min && score <= b.max);
  if (!hit) {
    throw new Error(`No band for score ${score}`);
  }
  return hit;
}

export function assertLikert4(value: number, label: string): Likert4 {
  if (value === 0 || value === 1 || value === 2 || value === 3) return value;
  throw new Error(`${label} must be 0–3, got ${value}`);
}

export function assertLength<T>(arr: T[], n: number, label: string): T[] {
  if (arr.length !== n) throw new Error(`${label} needs ${n} items, got ${arr.length}`);
  return arr;
}

export function cutoffSetFor(locale: Locale): "cn-wst428" | "who-global" {
  return locale === "zh" ? "cn-wst428" : "who-global";
}
