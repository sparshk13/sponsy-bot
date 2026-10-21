import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { Memory } from "../pages/memory/Memory";

function renderMemory(data?: object) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  queryClient.setQueryData(
    ["memory"],
    data || {
      total_sponsors: 2,
      total_cash_inr: 250000,
      entries: [
        {
          id: 1,
          company_name: "Past Sponsor Inc",
          company_domain: "past-sponsor.io",
          campaign_name: "Hack 2025",
          kind: "cash",
          tier: "cash",
          amount_inr: 250000,
          description: "Main sponsor tier",
          confirmed_at: "2025-10-15T10:00:00Z",
          ask_worked: "Offered workshop slot and career booth",
        },
        {
          id: 2,
          company_name: "Cloud Hosting Ltd",
          company_domain: "cloudhost.com",
          campaign_name: "Hack 2025",
          kind: "credits",
          tier: "credits",
          amount_inr: null,
          description: "$3000 server credits",
          confirmed_at: "2025-10-16T12:00:00Z",
          ask_worked: "Student credits for infra",
        },
      ],
    }
  );

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/memory"]}>
        <Memory />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("Memory page", () => {
  it("renders past sponsors, totals, and the ask that worked", () => {
    renderMemory();

    expect(screen.getByRole("heading", { name: "Memory" })).toBeDefined();
    expect(screen.getByText("Past Sponsors")).toBeDefined();
    expect(screen.getAllByText("2").length).toBeGreaterThan(0);
    expect(screen.getAllByText("₹2,50,000").length).toBeGreaterThan(0);



    expect(screen.getByText("Past Sponsor Inc")).toBeDefined();
    expect(screen.getByText("past-sponsor.io")).toBeDefined();
    expect(screen.getAllByText("Hack 2025").length).toBeGreaterThan(0);

    expect(screen.getByText("Offered workshop slot and career booth")).toBeDefined();

    expect(screen.getByText("Cloud Hosting Ltd")).toBeDefined();
    expect(screen.getByText("$3000 server credits")).toBeDefined();
    expect(screen.getByText("Student credits for infra")).toBeDefined();
  });

  it("renders empty state when no outcomes exist", () => {
    renderMemory({
      total_sponsors: 0,
      total_cash_inr: 0,
      entries: [],
    });

    expect(
      screen.getByText("No confirmed sponsorship outcomes recorded across campaigns yet.")
    ).toBeDefined();
  });
});
