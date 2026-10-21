import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { Targets } from "../pages/targets/Targets";

function renderTargets(targetsData: object[] = []) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  queryClient.setQueryData(["session"], {
    user: {
      id: 1,
      name: "Current User",
      email: "current@example.com",
      role: "organizer",
      is_active: true,
    },
    csrf_token: "csrf_token_targets",
  });

  queryClient.setQueryData(["campaigns"], [
    {
      id: 1,
      name: "Hackathon 2026",
      event_summary: "Annual hackathon",
      cash_target_inr: 500000,
    },
  ]);

  queryClient.setQueryData(["targets", { campaign_id: 1 }], targetsData);

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/targets"]}>
        <Targets />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("Targets page", () => {
  it("renders empty state when no targets exist", () => {
    renderTargets([]);

    expect(screen.getByRole("heading", { name: "Targets" })).toBeDefined();
    expect(
      screen.getByText("No companies yet. Import a CSV or add one by hand.")
    ).toBeDefined();
    expect(screen.getByRole("button", { name: "Add company" })).toBeDefined();
    expect(screen.getByRole("button", { name: "Import CSV" })).toBeDefined();
  });

  it("renders target table rows, priorities, and ownership indicators", () => {
    const mockTargets = [
      {
        id: 1,
        campaign_id: 1,
        company_id: 10,
        company_name: "Stripe",
        domain: "stripe.com",
        category: "Fintech",
        website: "https://stripe.com",
        owner_id: 1,
        owner_name: "Current User",
        status: "contacted",
        tier: "cash",
        priority: "A",
        priority_score: 5,
        contact: {
          id: 101,
          name: "Patrick",
          email: "patrick@stripe.com",
          role: "Sponsorship Lead",
          source: "manual",
          is_valid: true,
        },
        followup_count: 0,
        last_contacted_at: null,
        next_followup_at: null,
        cooldown_active: false,
        cooldown_unlocked: false,
        created_at: "2026-10-18T12:00:00Z",
      },
      {
        id: 2,
        campaign_id: 1,
        company_id: 20,
        company_name: "Google Cloud",
        domain: "cloud.google.com",
        category: "Cloud",
        website: "https://cloud.google.com",
        owner_id: 2,
        owner_name: "Priya",
        status: "not_contacted",
        tier: "credits",
        priority: "B",
        priority_score: 3,
        contact: null,
        followup_count: 0,
        last_contacted_at: null,
        next_followup_at: null,
        cooldown_active: false,
        cooldown_unlocked: false,
        created_at: "2026-10-18T12:00:00Z",
      },
      {
        id: 3,
        campaign_id: 1,
        company_id: 30,
        company_name: "Unclaimed Corp",
        domain: "unclaimed.com",
        category: "Tools",
        website: "https://unclaimed.com",
        owner_id: null,
        owner_name: null,
        status: "not_contacted",
        tier: null,
        priority: "C",
        priority_score: 1,
        contact: null,
        followup_count: 0,
        last_contacted_at: null,
        next_followup_at: null,
        cooldown_active: true,
        cooldown_unlocked: false,
        created_at: "2026-10-18T12:00:00Z",
      },
    ];

    renderTargets(mockTargets);

    // Verify company names and domains
    expect(screen.getByText("Stripe")).toBeDefined();
    expect(screen.getByText("stripe.com")).toBeDefined();
    expect(screen.getByText("Google Cloud")).toBeDefined();
    expect(screen.getByText("cloud.google.com")).toBeDefined();

    // Verify ownership: "You" for own target, "Priya" for other organizer, "Claim" for unclaimed
    expect(screen.getByText("You")).toBeDefined();
    expect(screen.getAllByText("Priya").length).toBe(2);
    expect(screen.getByRole("button", { name: "Claim" })).toBeDefined();

    // Verify cooldown indicator
    expect(screen.getByText("Cooldown")).toBeDefined();
  });
});
