import type { CrisisLevel, CrisisResource, CrisisResult, Locale } from "./types.ts";

const DISCLAIMER_ZH =
  "仅供参考，不是诊断，也不能替代执业医师或心理专业人员。出现急症请立即拨打 120。";
const DISCLAIMER_EN =
  "For self-reflection only. Not a diagnosis and not a substitute for a licensed clinician. For emergencies call your local emergency number.";

const CRISIS_PATTERNS: RegExp[] = [
  /自杀/,
  /不想活(?!动)/,
  /活不下去/,
  /结束生命/,
  /伤害自己/,
  /自残/,
  /割腕/,
  /跳楼(?!价)/,
  /\bsuicide\b/i,
  /\bkill myself\b/i,
  /\bwant to die\b/i,
  /\bself[- ]harm\b/i,
  /\bend my life\b/i,
];

export const RESOURCES_ZH: CrisisResource[] = [
  { name: "急救", contact: "120" },
  { name: "全国心理援助热线", contact: "12356" },
  { name: "北京心理危机研究与干预中心（手机）", contact: "010-82951332" },
  { name: "北京心理危机研究与干预中心（座机）", contact: "800-810-1117" },
  { name: "IASP 全球资源", contact: "https://www.iasp.info/suicidalthoughts/" },
];

export const RESOURCES_EN: CrisisResource[] = [
  { name: "Local emergency", contact: "your local emergency number" },
  { name: "IASP resources", contact: "https://www.iasp.info/suicidalthoughts/" },
];

const FORBIDDEN = [/确诊/, /你患有/, /你得了/, /诊断为/, /you have depression/i, /you have gad/i];

export function disclaimer(locale: Locale): string {
  return locale === "en" ? DISCLAIMER_EN : DISCLAIMER_ZH;
}

export function detectCrisisText(text: string): boolean {
  return CRISIS_PATTERNS.some((re) => re.test(text));
}

export function crisisFromPhq9Item9(item9: number, textHits: boolean, locale: Locale): CrisisResult {
  let level: CrisisLevel = "none";
  const reasons: string[] = [];
  if (item9 >= 2) {
    level = "urgent";
    reasons.push(locale === "en" ? "PHQ-9 item 9 scored 2+" : "PHQ-9 第9项得分 ≥2");
  } else if (item9 === 1) {
    level = "watch";
    reasons.push(locale === "en" ? "PHQ-9 item 9 scored 1" : "PHQ-9 第9项得分 1");
  }
  if (textHits) {
    level = "urgent";
    reasons.push(locale === "en" ? "Self-harm language detected" : "检测到自我伤害相关表述");
  }
  return {
    level,
    reasons,
    resources: locale === "en" ? RESOURCES_EN : RESOURCES_ZH,
  };
}

export function assertNoDiagnosisLanguage(text: string): void {
  for (const re of FORBIDDEN) {
    if (re.test(text)) {
      throw new Error(`Diagnosis language is forbidden: matched ${re}`);
    }
  }
}

export function crisisCard(locale: Locale, crisis: CrisisResult): string {
  if (crisis.level === "none") return "";
  const title =
    crisis.level === "urgent"
      ? locale === "en"
        ? "Please get help now"
        : "请马上寻求帮助"
      : locale === "en"
        ? "Please talk to someone you trust"
        : "请尽快和信任的人谈谈，并考虑专业支持";
  const lines = [
    title,
    ...crisis.reasons,
    ...crisis.resources.map((r) => `${r.name}: ${r.contact}`),
  ];
  return lines.join("\n");
}
