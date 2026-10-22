/**
 * Task 4 — exam-specific scaled scoring: labels and admin helpers.
 * The backend (results/scaled_scoring.py) is the authority for every
 * rule; this only names things and parses the admin's table text.
 */
export type ScoringProfile = "ielts" | "sat" | "gre";

export const SCORING_PROFILE_LABELS: Record<ScoringProfile, string> = {
  ielts: "IELTS (band 0–9)",
  sat: "SAT (200–800, jami 400–1600)",
  gre: "GRE (130–170)",
};

export interface ScoreComponentInfo {
  label: string;
  profile: ScoringProfile;
  /** false = rated by an examiner (Writing/Speaking/AWA), no table. */
  tableConvertible: boolean;
  range: string;
}

export const SCORE_COMPONENTS: Record<string, ScoreComponentInfo> = {
  ielts_listening: { label: "IELTS Listening", profile: "ielts", tableConvertible: true, range: "0–9, 0.5 qadam" },
  ielts_reading: { label: "IELTS Reading", profile: "ielts", tableConvertible: true, range: "0–9, 0.5 qadam" },
  ielts_writing: { label: "IELTS Writing", profile: "ielts", tableConvertible: false, range: "0–9" },
  ielts_speaking: { label: "IELTS Speaking", profile: "ielts", tableConvertible: false, range: "0–9" },
  sat_reading_writing: { label: "SAT Reading and Writing", profile: "sat", tableConvertible: true, range: "200–800, 10 qadam" },
  sat_math: { label: "SAT Math", profile: "sat", tableConvertible: true, range: "200–800, 10 qadam" },
  gre_verbal: { label: "GRE Verbal Reasoning", profile: "gre", tableConvertible: true, range: "130–170, 1 qadam" },
  gre_quantitative: { label: "GRE Quantitative Reasoning", profile: "gre", tableConvertible: true, range: "130–170, 1 qadam" },
  gre_analytical_writing: { label: "GRE Analytical Writing", profile: "gre", tableConvertible: false, range: "0–6" },
};

export function componentsForProfile(profile: ScoringProfile | null | undefined): string[] {
  if (!profile) return [];
  return Object.entries(SCORE_COMPONENTS).filter(([, c]) => c.profile === profile).map(([code]) => code);
}

/** Student-facing explanation of why a scaled score is (not) shown. */
export const SCALED_STATUS_LABELS: Record<string, string> = {
  scaled: "",
  pending_manual_grading: "Baholovchi tekshiruvi kutilmoqda",
  partially_graded: "Qisman baholangan — qolgan javoblar tekshirilmoqda",
  no_conversion_table: "Shkala ballari hali sozlanmagan",
  raw_out_of_range: "Shkala balli hisoblab bo'lmadi",
  ambiguous_variant: "Shkala balli hisoblab bo'lmadi",
  no_score_component: "Shkala balli qo'llanilmaydi",
  // Task 7
  below_documented_range: "Rasmiy manbada bu xom ball uchun ko'rsatkich yo'q — band hisoblanmadi",
  // Task 8 — also used when an official SAT practice-test table was made
  // for a different number of one-mark items than this section has.
  raw_scale_mismatch: "Savollar soni yoki ballari manba shkalasiga mos emas — ball hisoblanmadi (IELTS: 40 ta bir ballik savol; SAT: jadvaldagi eng katta xom ball)",
  ielts_module_unknown: "IELTS moduli (Academic/General Training) belgilanmagan — Reading bandi hisoblanmadi",
};

export const OVERALL_STATUS_LABELS: Record<string, string> = {
  scaled: "",
  pending: "Umumiy ball barcha bo'limlar baholangandan keyin chiqadi",
  not_reported: "Bu imtihonda umumiy ball berilmaydi — bo'limlar alohida baholanadi",
};

export function overallLabel(profile: string | null | undefined): string {
  if (profile === "ielts") return "Umumiy band (Overall)";
  if (profile === "sat") return "Umumiy ball (Total)";
  return "Umumiy ball";
}

export interface TableEntryInput {
  raw: string;
  scaled: string;
}

/** Parses "raw,scaled" (or tab/space/semicolon separated) lines. Blank
 * lines are ignored. Returns entries or an error naming the bad line;
 * range/step/monotonic checks are left to the backend (422). */
export function parseTableText(text: string): { entries: TableEntryInput[] } | { error: string } {
  const entries: TableEntryInput[] = [];
  const lines = text.split(/\r?\n/);
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i].trim();
    if (!line) continue;
    const parts = line.split(/[\s,;]+/).filter(Boolean);
    const num = /^-?(\d+(\.\d+)?|\.\d+)$/;
    if (parts.length !== 2 || !num.test(parts[0]) || !num.test(parts[1])) {
      return { error: `${i + 1}-qator: "raw, scaled" ko'rinishida ikki son bo'lishi kerak` };
    }
    entries.push({ raw: parts[0], scaled: parts[1] });
  }
  if (entries.length === 0) return { error: "Kamida bitta qator kiriting" };
  return { entries };
}

// --- Task 7 — score provenance ---------------------------------------------------

export type ScoreBasis = "official_rule" | "official_practice_test" | "estimate" | "unverified_table" | "rubric";

/** Short badge text: never calls a practice-test conversion an official result. */
export const SCORE_BASIS_LABELS: Record<ScoreBasis, string> = {
  official_rule: "Rasmiy hisoblash qoidasi",
  official_practice_test: "Rasmiy amaliy test jadvali",
  estimate: "Taxminiy",
  unverified_table: "Tasdiqlanmagan jadval",
  rubric: "Baholovchi (rubrika)",
};

/** One-line explanation shown under the score. */
export function scoreBasisExplanation(basis: ScoreBasis, profile?: string | null): string {
  switch (basis) {
    case "official_practice_test":
      return "Rasmiy amaliy test (paper, nonadaptive) jadvali bo'yicha taxminiy oraliq — rasmiy SAT natijasi emas va adaptiv SAT ballini aniq bashorat qilmaydi.";
    case "estimate":
      return profile === "ielts"
        ? "IELTS.org e'lon qilgan o'rtacha ko'rsatkichlar asosida indikativ oraliq — aniq chegaralar test versiyasiga qarab farq qiladi. Rasmiy IELTS natijasi emas."
        : profile === "gre"
          ? "Taxminiy ball. ETS ballni equating orqali hisoblaydi va ochiq jadval chop etmaydi — bu rasmiy GRE natijasi emas."
          : "Taxminiy ball — rasmiy natija emas.";
    case "unverified_table":
      return "Administrator kiritgan jadval; manbasi tasdiqlanmagan — rasmiy natija emas.";
    case "rubric":
      return "Platforma baholovchisi rubrika asosida qo'ygan ball — rasmiy imtihon natijasi emas.";
    case "official_rule":
      return "Rasmiy IELTS umumiy band qoidasi (o'rtacha, yarim bandga yaxlitlash) platforma ballariga qo'llangan — rasmiy IELTS natijasi emas.";
  }
}

/** "6.5" or "6–6.5"; null when there is nothing to show. */
export function formatScoreRange(single: number | null | undefined, lower: number | null | undefined, upper: number | null | undefined): string | null {
  if (lower != null && upper != null && lower !== upper) return `${lower}–${upper}`;
  if (single != null) return String(single);
  if (lower != null) return String(lower);
  return null;
}

export const IELTS_MODULE_LABELS: Record<"academic" | "general_training", string> = {
  academic: "Academic",
  general_training: "General Training",
};

/** Mirrors backend official_scoring.PRACTICE_FORMS (SAT Practice Test 4–11, paper/nonadaptive). */
export const SAT_PRACTICE_FORMS: { id: string; label: string }[] = Array.from({ length: 8 }, (_, i) => ({
  id: `sat_practice_test_${i + 4}`,
  label: `SAT Practice Test ${i + 4} (paper, nonadaptive)`,
}));

export interface RangeEntryInput {
  raw: string;
  lower: string;
  upper: string;
}

/** Parses "raw, lower, upper" lines (College Board scoring-guide layout). */
export function parseRangeTableText(text: string): { entries: RangeEntryInput[] } | { error: string } {
  const entries: RangeEntryInput[] = [];
  const num = /^-?(\d+(\.\d+)?|\.\d+)$/;
  const lines = text.split(/\r?\n/);
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i].trim();
    if (!line) continue;
    const parts = line.split(/[\s,;]+/).filter(Boolean);
    if (parts.length !== 3 || !parts.every((p) => num.test(p))) {
      return { error: `${i + 1}-qator: "raw, lower, upper" ko'rinishida uchta son bo'lishi kerak` };
    }
    entries.push({ raw: parts[0], lower: parts[1], upper: parts[2] });
  }
  if (entries.length === 0) return { error: "Kamida bitta qator kiriting" };
  return { entries };
}
