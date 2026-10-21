import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { Dashboard } from "../pages/dashboard/Dashboard";

function renderDashboard(userRole = "admin") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  queryClient.setQueryData(["session"], {
    user: {
      id: 1,
      name: "Test User",
      email: "test@example.com",
      role: userRole,
      is_active: true,
    },
    csrf_token: "csrf_token_test",
  });

  queryClient.setQueryData(["dashboard"], {
    total_targets: 10,
    contacted_count: 8,
    replied_count: 4,
    response_rate: 50.0,
    interested_count: 3,
    interest_rate: 37.5,
    declined_count: 1,
    secured_count: 2,
    total_cash_inr: 350000,
    pipeline: [
      { stage: "not_contacted", label: "Not Contacted", count: 2 },
      { stage: "contacted", label: "Contacted", count: 3 },
      { stage: "follow_up", label: "Follow-up", count: 1 },
      { stage: "interested", label: "Interested", count: 1 },
      { stage: "meeting_booked", label: "Meeting Booked", count: 0 },
      { stage: "secured", label: "Secured", count: 2 },
      { stage: "declined", label: "Declined", count: 1 },
      { stage: "closed_no_reply", label: "Closed (No Reply)", count: 0 },
    ],
    non_cash_outcomes: [
      {
        id: 1,
        company_name: "Swag Co",
        kind: "goodies",
        description: "100 Hoodies for participants",
        confirmed_at: "2026-10-18T10:00:00Z",
      },
    ],
    organizers: [
      {
        user_id: 1,
        name: "Test User",
        assigned_count: 6,
        contacted_count: 5,
        secured_count: 1,
        secured_cash_inr: 200000,
      },
      {
        user_id: 2,
        name: "Other Organizer",
        assigned_count: 4,
        contacted_count: 3,
        secured_count: 1,
        secured_cash_inr: 150000,
      },
    ],
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Dashboard />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("Dashboard page", () => {
  it("renders pipeline stages, summary metrics, and conversion rates", () => {
    renderDashboard("organizer");

    expect(screen.getByRole("heading", { name: "Dashboard" })).toBeDefined();
    expect(screen.getByText("Total Targets")).toBeDefined();
    expect(screen.getByText("10")).toBeDefined();
    expect(screen.getByText("50%")).toBeDefined();
    expect(screen.getByText("37.5%")).toBeDefined();
    expect(screen.getByText("₹3,50,000")).toBeDefined();

    expect(screen.getByText("Not Contacted")).toBeDefined();
    expect(screen.getAllByText("Contacted").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Secured").length).toBeGreaterThan(0);
    expect(screen.getByText("Swag Co")).toBeDefined();
    expect(screen.getByText("100 Hoodies for participants")).toBeDefined();
    expect(screen.getByText("Other Organizer")).toBeDefined();


    // Organizer should NOT see CSV export button
    expect(screen.queryByRole("link", { name: "Export tracker (CSV)" })).toBeNull();
  });

  it("renders export tracker CSV button for admin users", () => {
    renderDashboard("admin");

    const exportBtn = screen.getByRole("link", { name: "Export tracker (CSV)" });
    expect(exportBtn).toBeDefined();
    expect(exportBtn.getAttribute("href")).toBe("/api/export/tracker.csv");
  });
});
