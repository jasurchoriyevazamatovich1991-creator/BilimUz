import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { GroupMediaManager } from "./GroupMediaManager";
import { questionGroupsApi, type QuestionGroupOut } from "@/api/examConfig";

vi.mock("@/api/examConfig");
// The real FileUploader runs the R2 presigned flow; here it only needs to
// report a finished upload id, which is all GroupMediaManager consumes.
vi.mock("@/components/uploads/FileUploader", () => ({
  FileUploader: ({ onSuccess }: { onSuccess?: (id: string, type: string) => void }) => (
    <button type="button" onClick={() => onSuccess?.("upload-9", "audio")}>fake-upload</button>
  ),
}));

const GROUP: QuestionGroupOut = {
  id: "g1", test_id: "t1", module_id: null, title: "Section 1", stimulus_text: null, order_number: 0,
  created_at: "", updated_at: "",
  media: [{ id: "gm1", group_id: "g1", upload_id: "u1", media_type: "audio", created_at: "" }],
};

function renderManager(group: QuestionGroupOut = GROUP) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <GroupMediaManager testId="t1" group={group} />
    </QueryClientProvider>,
  );
}

describe("GroupMediaManager (Task 3)", () => {
  beforeEach(() => vi.clearAllMocks());

  it("lists the group's media", () => {
    renderManager();
    expect(screen.getByText(/Audio 1/)).toBeInTheDocument();
  });

  it("shows an empty state when the group has no media (including older payloads)", () => {
    renderManager({ ...GROUP, media: undefined });
    expect(screen.getByText("Media biriktirilmagan.")).toBeInTheDocument();
  });

  it("attaches a finished upload to the group by id only", async () => {
    vi.mocked(questionGroupsApi.addMedia).mockResolvedValue({ id: "gm2", group_id: "g1", upload_id: "upload-9", media_type: "audio", created_at: "" });
    renderManager();
    fireEvent.click(screen.getByText("fake-upload"));
    await waitFor(() => expect(questionGroupsApi.addMedia).toHaveBeenCalledWith("g1", "upload-9"));
  });

  it("removes a media item", async () => {
    vi.mocked(questionGroupsApi.removeMedia).mockResolvedValue({} as never);
    renderManager();
    fireEvent.click(screen.getByRole("button", { name: "Audio 1 ni guruhdan olib tashlash" }));
    await waitFor(() => expect(questionGroupsApi.removeMedia).toHaveBeenCalledWith("g1", "gm1"));
  });
});
