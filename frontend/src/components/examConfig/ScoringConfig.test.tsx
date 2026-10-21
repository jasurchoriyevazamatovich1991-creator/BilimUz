/** Task 4 — ScoringProfileCard and ConversionTablesPanel (admin). */
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

const TABLE = (version: number, current: boolean, variant: string | null = null): ConversionTableOut => ({
  id: `tbl-${version}-${variant ?? "x"}`, section_id: "s1", routing_variant: variant, version, method: "exact",
  entries: [{ raw: "0", scaled: "200" }, { raw: "1", scaled: "210" }], is_current: current, created_by: "u1", created_at: "",
});

describe("ScoringProfileCard", () => {
  beforeEach(() => vi.clearAllMocks());

  it("saves a chosen profile and can clear it back to percentage scoring", async () => {
    vi.mocked(scoringApi.setProfile).mockResolvedValue({} as never);
    const { rerender } = wrap(<ScoringProfileCard testId="t1" current={null} />);
    const save = screen.getByRole("button", { name: "Profilni saqlash" });
    expect(save).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Profil"), { target: { value: "sat" } });
    fireEvent.click(save);
    await waitFor(() => expect(scoringApi.setProfile).toHaveBeenCalledWith("t1", "sat"));

    rerender(
      <QueryClientProvider client={new QueryClient()}>
        <ScoringProfileCard testId="t1" current="sat" />
      </QueryClientProvider>,
    );
    fireEvent.change(screen.getByLabelText("Profil"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Profilni saqlash" }));
    await waitFor(() => expect(scoringApi.setProfile).toHaveBeenLastCalledWith("t1", null));
  });
});

describe("ConversionTablesPanel", () => {
  beforeEach(() => vi.clearAllMocks());

  it("lists versions and marks the current one", async () => {
    vi.mocked(scoringApi.listTables).mockResolvedValue([TABLE(2, true), TABLE(1, false)]);
    wrap(<ConversionTablesPanel sectionId="s1" component="sat_math" variants={[]} />);
    await screen.findByText("v2");
    expect(screen.getByText("v1")).toBeInTheDocument();
    expect(screen.getAllByText("joriy")).toHaveLength(1);
    expect(screen.queryByLabelText("Routing variant")).not.toBeInTheDocument();
  });

  it("shows an empty state when there is no table", async () => {
    vi.mocked(scoringApi.listTables).mockResolvedValue([]);
    wrap(<ConversionTablesPanel sectionId="s1" component="gre_verbal" variants={[]} />);
    expect(await screen.findByText(/Hali jadval yo'q/)).toBeInTheDocument();
  });

  it("publishes parsed rows with method and routing variant", async () => {
    vi.mocked(scoringApi.listTables).mockResolvedValue([]);
    vi.mocked(scoringApi.publishTable).mockResolvedValue(TABLE(1, true, "hard"));
    wrap(<ConversionTablesPanel sectionId="s1" component="sat_math" variants={["hard", "easy"]} />);
    await screen.findByText(/Hali jadval yo'q/);

    fireEvent.change(screen.getByLabelText("Usul"), { target: { value: "linear" } });
    fireEvent.change(screen.getByLabelText("Routing variant"), { target: { value: "hard" } });
    fireEvent.change(screen.getByLabelText(/Qatorlar/), { target: { value: "0, 200\n22, 800" } });
    fireEvent.click(screen.getByRole("button", { name: "Yangi versiyani e'lon qilish" }));

    await waitFor(() => expect(scoringApi.publishTable).toHaveBeenCalledWith("s1", {
      method: "linear", routing_variant: "hard", entries: [{ raw: "0", scaled: "200" }, { raw: "22", scaled: "800" }],
    }));
  });

  it("blocks malformed rows client-side without calling the API", async () => {
    vi.mocked(scoringApi.listTables).mockResolvedValue([]);
    wrap(<ConversionTablesPanel sectionId="s1" component="sat_math" variants={[]} />);
    await screen.findByText(/Hali jadval yo'q/);
    fireEvent.change(screen.getByLabelText(/Qatorlar/), { target: { value: "0, 200\nbad row" } });
    fireEvent.click(screen.getByRole("button", { name: "Yangi versiyani e'lon qilish" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("2-qator");
    expect(scoringApi.publishTable).not.toHaveBeenCalled();
  });
});
