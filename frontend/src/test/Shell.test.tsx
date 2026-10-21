import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { Shell } from "../components/Shell";
import { Today } from "../pages/today/Today";

function createTestQueryClient(userData?: object) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  if (userData) {
    queryClient.setQueryData(["session"], userData);
  }
  return queryClient;
}

describe("Shell", () => {
  it("renders navigation rail links and brand when authenticated", () => {
    const queryClient = createTestQueryClient({
      user: {
        id: 1,
        name: "Test Admin",
        email: "admin@example.com",
        role: "admin",
        is_active: true,
      },
      csrf_token: "csrf_test_123",
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/"]}>
          <Shell>
            <div>Content</div>
          </Shell>
        </MemoryRouter>
      </QueryClientProvider>
    );

    expect(screen.getByText("Sponsy")).toBeDefined();
    expect(screen.getByText("Today")).toBeDefined();
    expect(screen.getByText("Targets")).toBeDefined();
    expect(screen.getByText("Approvals")).toBeDefined();
    expect(screen.getByText("Inbox")).toBeDefined();
    expect(screen.getByText("Admin")).toBeDefined();
    expect(screen.getByText("Test Admin")).toBeDefined();
    expect(screen.getByText("Content")).toBeDefined();
  });
});

describe("Today page", () => {
  it("renders headline and empty states", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <Today />
      </MemoryRouter>
    );

    expect(screen.getByRole("heading", { name: "Today" })).toBeDefined();
    expect(screen.getByText("Nothing is waiting for your approval.")).toBeDefined();
    expect(screen.getByText("Sent today: 0 of 30")).toBeDefined();
  });
});
