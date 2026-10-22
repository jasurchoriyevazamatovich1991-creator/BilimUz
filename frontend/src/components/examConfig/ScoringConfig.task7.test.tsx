/** Task 7 — IELTS module choice and table provenance in the admin UI. */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { ScoringProfileCard } from "./ScoringProfileCard";
import { ConversionTablesPanel } from "./ConversionTablesPanel";
import { scoringApi, type ConversionTableOut } from "@/api/examConfig";

vi.mock("@/api/examConfig");

function wrap(ui: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

const OFFICIAL: ConversionTableOut = {
  id: "t1", section_id: "s1", routing_variant: null, version: 1, method: "range",
  entries: [{ raw: "0", lower: "200", upper: "200" }, { raw: "54", lower: "790", upper: "800" }],
  is_current: true, created_by: "u1", created_at: "", conversion_type: "official_practice_test", test_form: "sat_practice_test_4",
  source_url: "https://satsuite.collegeboard.org/media/pdf/scoring-sat-practice-test-4-digital.pdf",
  source_title: "Scoring guide — SAT Practice Test 4 (paper, nonadaptive)", source_version: null, source_verified_at: "2026-10-21",
};

describe("ScoringProfileCard — IELTS module", () => {
  beforeEach(() => vi.clearAllMocks());

  it("asks for Academic/General Training only for IELTS and sends it", async () => {
    vi.mocked(scoringApi.setProfile).mockResolvedValue({} as never);
    wrap(<ScoringProfileCard testId="t1" current={null} />);
    expect(screen.queryByLabelText("IELTS moduli")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Profil"), { target: { value: "ielts" } });
    expect(screen.getByText(/Modul tanlanmasa Reading/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("IELTS moduli"), { target: { value: "general_training" } });
    fireEvent.click(screen.getByRole("button", { name: "Profilni saqlash" }));
    await waitFor(() => expect(scoringApi.setProfile).toHaveBeenCalledWith("t1", "ielts", "general_training"));
  });

  it("enables saving when only the module changes", async () => {
    vi.mocked(scoringApi.setProfile).mockResolvedValue({} as never);
    wrap(<ScoringProfileCard testId="t1" current="ielts" currentIeltsModule="academic" />);
    const save = screen.getByRole("button", { name: "Profilni saqlash" });
    expect(save).toBeDisabled();
    fireEvent.change(screen.getByLabelText("IELTS moduli"), { target: { value: "" } });
    expect(save).toBeEnabled();
    fireEvent.click(save);
    await waitFor(() => expect(scoringApi.setProfile).toHaveBeenCalledWith("t1", "ielts", null));
  });
});

describe("ConversionTablesPanel — provenance", () => {
  beforeEach(() => vi.clearAllMocks());

  it("lists a range table with its type, form and source", async () => {
    vi.mocked(scoringApi.listTables).mockResolvedValue([OFFICIAL]);
    wrap(<ConversionTablesPanel sectionId="s1" component="sat_math" variants={[]} />);
    const prov = await screen.findByTestId("table-provenance");
    expect(prov).toHaveTextContent("Rasmiy amaliy test jadvali · SAT Practice Test 4 (paper, nonadaptive)");
    expect(prov).toHaveTextContent("tekshirilgan: 2026-10-21");
    expect(screen.getByRole("link", { name: OFFICIAL.source_title! })).toHaveAttribute("href", OFFICIAL.source_url);
    expect(screen.getByText(/0→200–200 … 54→790–800/)).toBeInTheDocument();
  });

  // Task 8 — official tables are imported from the verified dataset: no values are typed.
  it("imports an official SAT practice-test table for a chosen form without typed values", async () => {
    vi.mocked(scoringApi.listTables).mockResolvedValue([]);
    vi.mocked(scoringApi.publishTable).mockResolvedValue(OFFICIAL);
    wrap(<ConversionTablesPanel sectionId="s1" component="sat_math" variants={["hard"]} />);
    await screen.findByText(/Hali jadval yo'q/);
    fireEvent.change(screen.getByLabelText("Jadval turi"), { target: { value: "official_practice_test" } });
    expect(screen.queryByLabelText("Usul")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Routing variant")).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Manba havolasi/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Qatorlar/)).not.toBeInTheDocument();
    expect(screen.getByTestId("official-import-note")).toHaveTextContent("R&W 0–66, Math 0–54");
    const submit = screen.getByRole("button", { name: "Rasmiy jadvalni import qilish" });
    fireEvent.click(submit);
    expect(await screen.findByRole("alert")).toHaveTextContent("amaliy testni tanlang");
    expect(scoringApi.publishTable).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Amaliy test"), { target: { value: "sat_practice_test_4" } });
    fireEvent.click(submit);
    await waitFor(() => expect(scoringApi.publishTable).toHaveBeenCalledWith("s1", {
      method: "range", conversion_type: "official_practice_test", test_form: "sat_practice_test_4",
    }));
  });

  it("shows documented source anomalies as warnings", async () => {
    const note = "Scoring Your Paper SAT Practice Test #6 (2324-WKD-1054): raw 41 lower = 530, raw 40 da 540 — rasmiy jadvalda kamayish bor; manbadagidek saqlangan";
    vi.mocked(scoringApi.listTables).mockResolvedValue([{ ...OFFICIAL, test_form: "sat_practice_test_6", source_anomalies: [note],
      source_version: "2324-WKD-1054 (© 2024 College Board)" }]);
    wrap(<ConversionTablesPanel sectionId="s1" component="sat_reading_writing" variants={[]} />);
    expect(await screen.findByTestId("table-anomaly")).toHaveTextContent(`⚠ ${note}`);
    expect(screen.getByTestId("table-provenance")).toHaveTextContent("2324-WKD-1054 (© 2024 College Board)");
  });

  it("does not offer official tables for IELTS or GRE; estimates carry a source", async () => {
    vi.mocked(scoringApi.listTables).mockResolvedValue([]);
    vi.mocked(scoringApi.publishTable).mockResolvedValue({ ...OFFICIAL, conversion_type: "estimate" });
    wrap(<ConversionTablesPanel sectionId="s1" component="gre_verbal" variants={[]} />);
    await screen.findByText(/Hali jadval yo'q/);
    expect(screen.getByText(/ETS GRE ballarini equating orqali/)).toBeInTheDocument();
    const types = Array.from((screen.getByLabelText("Jadval turi") as HTMLSelectElement).options).map((o) => o.value);
    expect(types).toEqual(["unverified", "estimate"]);
    fireEvent.change(screen.getByLabelText("Jadval turi"), { target: { value: "estimate" } });
    fireEvent.change(screen.getByLabelText(/Manba nomi/), { target: { value: "Internal estimate" } });
    fireEvent.change(screen.getByLabelText(/Manba tekshirilgan sana/), { target: { value: "2026-10-21" } });
    fireEvent.change(screen.getByLabelText(/Qatorlar/), { target: { value: "0, 130\n1, 150" } });
    fireEvent.click(screen.getByRole("button", { name: "Yangi versiyani e'lon qilish" }));
    await waitFor(() => expect(scoringApi.publishTable).toHaveBeenCalledWith("s1", {
      method: "exact", conversion_type: "estimate", source_title: "Internal estimate", source_verified_at: "2026-10-21",
      entries: [{ raw: "0", scaled: "130" }, { raw: "1", scaled: "150" }],
    }));
  });

  it("IELTS panel explains the indicative fallback", async () => {
    vi.mocked(scoringApi.listTables).mockResolvedValue([]);
    wrap(<ConversionTablesPanel sectionId="s1" component="ielts_reading" variants={[]} />);
    expect(await screen.findByText(/IELTS rasmiy to'liq jadval chop etmaydi/)).toBeInTheDocument();
    const types = Array.from((screen.getByLabelText("Jadval turi") as HTMLSelectElement).options).map((o) => o.value);
    expect(types).not.toContain("official_practice_test");
  });
});
