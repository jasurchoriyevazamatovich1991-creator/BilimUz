import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Header } from "./Header";
import { useAuthStore } from "@/store/authStore";
import { notificationsApi } from "@/api/notifications";
import { useThemeStore } from "@/store/themeStore";

vi.mock("@/api/notifications");

function renderHeader() {
  // Header -> useLogout() -> useQueryClient() needs a real
  // QueryClientProvider in the tree, same pattern as every other
  // page-level test in the project (e.g. TopicsListPage.test.tsx) — a
  // fresh QueryClient per render call keeps each test's cache isolated.
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Header />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Header", () => {
  beforeEach(() => {
    useAuthStore.getState().logout();
    useAuthStore.getState().setUser({
      id: "1",
      first_name: "Aziz",
      last_name: "Karimov",
      phone: null,
      email: null,
      role: "Teacher",
    });
  });

  it("renders nothing if there is no user", () => {
    useAuthStore.getState().logout();
    const { container } = renderHeader();
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the user's name and role badge, menu closed by default", () => {
    renderHeader();
    expect(screen.getByText("Aziz Karimov")).toBeInTheDocument();
    expect(screen.getByText("Teacher")).toBeInTheDocument();
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("opens the dropdown on click, showing Profil, Sozlamalar, and Chiqish", () => {
    renderHeader();
    fireEvent.click(screen.getByRole("button", { expanded: false }));
    expect(screen.getByRole("menu")).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Profil" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Sozlamalar" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Chiqish" })).toBeInTheDocument();
  });

  it("links Profil and Sozlamalar to the role-correct panel paths", () => {
    renderHeader();
    fireEvent.click(screen.getByRole("button", { name: /Aziz Karimov/ }));
    expect(screen.getByRole("menuitem", { name: "Profil" })).toHaveAttribute("href", "/teacher/profile");
    expect(screen.getByRole("menuitem", { name: "Sozlamalar" })).toHaveAttribute("href", "/teacher/settings");
  });

  it("closes the dropdown on Escape", () => {
    renderHeader();
    fireEvent.click(screen.getByRole("button", { name: /Aziz Karimov/ }));
    expect(screen.getByRole("menu")).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("closes the dropdown on outside click", () => {
    renderHeader();
    fireEvent.click(screen.getByRole("button", { name: /Aziz Karimov/ }));
    expect(screen.getByRole("menu")).toBeInTheDocument();
    fireEvent.mouseDown(document.body);
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });
});

describe("Header — Sprint 24 theme toggle", () => {
  beforeEach(() => {
    useAuthStore.getState().logout();
    useAuthStore.getState().setUser({ id: "1", first_name: "Aziz", last_name: "Karimov", phone: null, email: null, role: "Teacher" });
    document.documentElement.classList.remove("dark");
    useThemeStore.setState({ theme: "light" }); // reset store state too — persist keeps it across tests otherwise
  });

  it("renders a theme toggle button for every role (not gated like the notification bell)", () => {
    renderHeader();
    expect(screen.getByLabelText(/rejimga o'tish/)).toBeInTheDocument();
  });

  it("toggles the .dark class on <html> when clicked", () => {
    renderHeader();
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    fireEvent.click(screen.getByLabelText("Qorong'i rejimga o'tish"));
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("toggles back to light on a second click", () => {
    renderHeader();
    fireEvent.click(screen.getByLabelText("Qorong'i rejimga o'tish"));
    fireEvent.click(screen.getByLabelText("Yorug' rejimga o'tish"));
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });
});

describe("Header — Sprint 23 notification bell (Student only)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.getState().logout();
  });

  it("does NOT render a bell for Teacher (out of approved scope, no /teacher/notifications route)", () => {
    useAuthStore.getState().setUser({ id: "1", first_name: "A", last_name: "B", phone: null, email: null, role: "Teacher" });
    renderHeader();
    expect(screen.queryByLabelText("Bildirishnomalar")).not.toBeInTheDocument();
  });

  it("does NOT render a bell for Admin (out of approved scope this sprint)", () => {
    useAuthStore.getState().setUser({ id: "1", first_name: "A", last_name: "B", phone: null, email: null, role: "Admin" });
    renderHeader();
    expect(screen.queryByLabelText("Bildirishnomalar")).not.toBeInTheDocument();
  });

  it("renders a bell for Student, linking to /student/notifications", () => {
    vi.mocked(notificationsApi.unreadCount).mockResolvedValue(0);
    useAuthStore.getState().setUser({ id: "1", first_name: "A", last_name: "B", phone: null, email: null, role: "Student" });
    renderHeader();
    expect(screen.getByLabelText("Bildirishnomalar")).toHaveAttribute("href", "/student/notifications");
  });

  it("shows the real unread count as a badge when > 0", async () => {
    vi.mocked(notificationsApi.unreadCount).mockResolvedValue(3);
    useAuthStore.getState().setUser({ id: "1", first_name: "A", last_name: "B", phone: null, email: null, role: "Student" });
    renderHeader();
    await waitFor(() => expect(screen.getByText("3")).toBeInTheDocument());
  });

  it("shows no badge when unread count is 0", async () => {
    vi.mocked(notificationsApi.unreadCount).mockResolvedValue(0);
    useAuthStore.getState().setUser({ id: "1", first_name: "A", last_name: "B", phone: null, email: null, role: "Student" });
    renderHeader();
    await waitFor(() => expect(screen.getByLabelText("Bildirishnomalar")).toBeInTheDocument());
    expect(screen.queryByLabelText(/o'qilmagan bildirishnoma/)).not.toBeInTheDocument();
  });

  it("never calls the unread-count endpoint for a non-Student role (enabled gating)", () => {
    useAuthStore.getState().setUser({ id: "1", first_name: "A", last_name: "B", phone: null, email: null, role: "Teacher" });
    renderHeader();
    expect(notificationsApi.unreadCount).not.toHaveBeenCalled();
  });
});
