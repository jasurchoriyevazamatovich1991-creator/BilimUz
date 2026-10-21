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
