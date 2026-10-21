import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { Usage } from "../pages/usage/Usage";

function renderUsage(usageData: object[]) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  queryClient.setQueryData(["usage"], usageData);

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Usage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("Usage page", () => {
  it("renders usage items, percentages, and normal statuses", () => {
    const mockUsage = [
      {
        provider: "gemini",
        period: "daily",
        used: 100,
        cap: 800,
        percent: 12,
        is_warning: false,
        is_exhausted: false,
      },
      {
        provider: "tavily",
        period: "monthly",
        used: 50,
        cap: 800,
        percent: 6,
        is_warning: false,
        is_exhausted: false,
      },
    ];

    renderUsage(mockUsage);

    expect(
      screen.getByRole("heading", { name: "Usage and free-tier budgets" })
    ).toBeDefined();
    expect(screen.getByText("gemini")).toBeDefined();
    expect(screen.getByText("tavily")).toBeDefined();
    expect(screen.getByText("12%")).toBeDefined();
    expect(screen.getAllByText("Active").length).toBe(2);
  });

  it("renders warning banner and exhausted banner when thresholds are reached", () => {
    const mockWarningUsage = [
      {
        provider: "gemini",
        period: "daily",
        used: 800,
        cap: 800,
        percent: 100,
        is_warning: true,
        is_exhausted: true,
      },
    ];

    renderUsage(mockWarningUsage);

    expect(
      screen.getByText(
        "Gemini's free quota for today is used up. Drafting resumes tomorrow. Nothing is lost."
      )
    ).toBeDefined();
    expect(screen.getByText("Exhausted")).toBeDefined();
  });
});
