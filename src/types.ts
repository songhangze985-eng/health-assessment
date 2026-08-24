export type Likert4 = 0 | 1 | 2 | 3;
export type Locale = "zh" | "en";
export type CrisisLevel = "none" | "watch" | "urgent";
export type SmokingStatus = "never" | "former" | "current";

export interface Band {
  id: string;
  min: number;
  max: number;
  labelZh: string;
  labelEn: string;
}

export interface Phq9Answers {
  items: [Likert4, Likert4, Likert4, Likert4, Likert4, Likert4, Likert4, Likert4, Likert4];
}

export interface Gad7Answers {
  items: [Likert4, Likert4, Likert4, Likert4, Likert4, Likert4, Likert4];
}

export interface SleepAnswers {
  hours: number;
  latencyMin: number;
  awakenings: number;
  restedness: 1 | 2 | 3 | 4 | 5;
}

export interface LifestyleAnswers {
  heightCm: number;
  weightKg: number;
  exerciseMinWeek: number;
  smoking: SmokingStatus;
  alcoholUnitsWeek: number;
}

export interface FullAnswers {
  locale?: Locale;
  phq9: Phq9Answers;
  gad7: Gad7Answers;
  sleep: SleepAnswers;
  lifestyle: LifestyleAnswers;
}

export interface Checkin {
  at?: string;
  mood: 1 | 2 | 3 | 4 | 5;
  energy: 1 | 2 | 3 | 4 | 5;
  sleepHours: number;
  moved: boolean;
  stress: 1 | 2 | 3 | 4 | 5;
}

export interface ScaleResult {
  id: string;
  score: number;
  max: number;
  band: Band;
  flags: string[];
}

export interface BmiResult {
  value: number;
  cutoffSet: "cn-wst428" | "who-global";
  band: Band;
  score100: number;
}

export interface Dimension {
  id: string;
  score: number;
  weight: number;
}

export interface CompositeResult {
  total: number;
  dimensions: Dimension[];
}

export interface CrisisResource {
  name: string;
  contact: string;
}

export interface CrisisResult {
  level: CrisisLevel;
  reasons: string[];
  resources: CrisisResource[];
}

export interface AssessmentResult {
  kind: "full";
  locale: Locale;
  disclaimer: string;
  crisis: CrisisResult;
  phq9: ScaleResult;
  gad7: ScaleResult;
  sleep: ScaleResult;
  bmi: BmiResult;
  movement: ScaleResult;
  lifestyleFlags: string[];
  composite: CompositeResult;
  actions: string[];
  seekCare: string[];
}

export interface CheckinResult {
  kind: "checkin";
  locale: Locale;
  disclaimer: string;
  snapshot: Checkin;
  score100: number;
}
