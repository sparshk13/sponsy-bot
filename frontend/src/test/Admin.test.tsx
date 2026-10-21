import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { Admin } from "../pages/admin/Admin";

function renderAdmin(currentUserRole = "admin") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  queryClient.setQueryData(["session"], {
    user: {
      id: 1,
      name: "Admin User",
      email: "admin@example.com",
      role: currentUserRole,
      is_active: true,
    },
    csrf_token: "csrf_token_admin",
  });

  queryClient.setQueryData(["admin", "users"], [
    {
      id: 1,
      name: "Admin User",
      email: "admin@example.com",
      role: "admin",
      is_active: true,
      created_at: "2026-10-18T10:00:00Z",
    },
    {
      id: 2,
      name: "Organizer User",
      email: "organizer@example.com",
      role: "organizer",
      is_active: true,
      created_at: "2026-10-18T11:00:00Z",
    },
  ]);

  queryClient.setQueryData(["admin", "templates"], [
    {
      id: 1,
      name: "Standard Initial Outreach",
      tier: "cash",
      body: "Hi {contact_name}, would you sponsor our hackathon?",
      is_active: true,
      created_at: "2026-10-18T10:00:00Z",
      updated_at: "2026-10-18T10:00:00Z",
    },
  ]);

  queryClient.setQueryData(["admin", "brochures"], [
    {
      id: 1,
      tier: "cash",
      filename: "cash_brochure_2026.pdf",
      file_size: 1048576,
      created_at: "2026-10-18T10:00:00Z",
    },
  ]);

  queryClient.setQueryData(["admin", "system"], {
    last_mail_check: "2026-10-18T10:00:00Z",
    last_send: "2026-10-18T12:00:00Z",
    last_backup: "sponsy_backup_20261018.sql.gz.age",
    db_size_bytes: 15728640,
    disk_free_bytes: 42949672960,
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/admin"]}>
        <Admin />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("Admin page", () => {
  it("denies access to non-admin users", () => {
    renderAdmin("organizer");

    expect(
      screen.getByText("You do not have permission to view this page.")
    ).toBeDefined();
  });

  it("renders users list and protects admin from deactivating self", () => {
    renderAdmin("admin");

    expect(screen.getByRole("heading", { name: "Admin" })).toBeDefined();
    expect(screen.getByText("Admin User")).toBeDefined();
    expect(screen.getByText("Organizer User")).toBeDefined();
    expect(screen.getByText("Current account")).toBeDefined();
    expect(screen.getByRole("button", { name: "Deactivate" })).toBeDefined();
  });

  it("renders add user form with minimum 12 characters password helper", () => {
    renderAdmin("admin");

    expect(screen.getByLabelText("Full name")).toBeDefined();
    expect(screen.getByLabelText("Email address")).toBeDefined();
    expect(screen.getByLabelText("Password")).toBeDefined();
    expect(screen.getByText("Minimum 12 characters")).toBeDefined();
  });

  it("switches to Templates tab and shows template list and form", () => {
    renderAdmin("admin");

    const templatesTabBtn = screen.getByRole("button", { name: "Templates" });
    fireEvent.click(templatesTabBtn);

    expect(screen.getByText("Standard Initial Outreach")).toBeDefined();
    expect(screen.getByText("Hi {contact_name}, would you sponsor our hackathon?")).toBeDefined();
    expect(screen.getByLabelText("Template name")).toBeDefined();
    expect(screen.getByLabelText("Template body")).toBeDefined();
    expect(screen.getByRole("button", { name: "Add template" })).toBeDefined();
  });

  it("switches to Brochures tab and shows brochure list and upload form", () => {
    renderAdmin("admin");

    const brochuresTabBtn = screen.getByRole("button", { name: "Brochures" });
    fireEvent.click(brochuresTabBtn);

    expect(screen.getByText("cash_brochure_2026.pdf")).toBeDefined();
    expect(screen.getByRole("link", { name: "Download" })).toBeDefined();
    expect(screen.getByLabelText("PDF Document (maximum 5 MB)")).toBeDefined();
    expect(screen.getByRole("button", { name: "Upload brochure" })).toBeDefined();
  });

  it("renders 2FA status and switches to System tab", () => {
    renderAdmin("admin");

    // Check 2FA header in users table
    expect(screen.getByRole("columnheader", { name: "2FA" })).toBeDefined();

    // Click System tab
    const systemTabBtn = screen.getByRole("button", { name: "System" });
    fireEvent.click(systemTabBtn);

    expect(screen.getByText("System status and maintenance")).toBeDefined();
    expect(screen.getByText("Last mail check")).toBeDefined();
    expect(screen.getByText("Last email sent")).toBeDefined();
    expect(screen.getByText("Last backup file")).toBeDefined();
    expect(screen.getByText("Database size")).toBeDefined();
    expect(screen.getByText("Free disk space")).toBeDefined();
    expect(screen.getByRole("button", { name: "Revoke all sessions" })).toBeDefined();
  });
});


