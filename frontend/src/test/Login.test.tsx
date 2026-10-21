import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Login } from "../pages/login/Login";

function renderLogin(initialEntry = "/login") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Login />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("Login page", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders login form with email, password, and sign in button", () => {
    renderLogin();

    expect(screen.getByRole("heading", { name: "Sign in" })).toBeDefined();
    expect(screen.getByLabelText("Email")).toBeDefined();
    expect(screen.getByLabelText("Password")).toBeDefined();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeDefined();
  });

  it("shows session expired message when reason is expired", () => {
    renderLogin("/login?reason=expired");

    expect(
      screen.getByText("You were signed out after being away. Sign in to continue.")
    ).toBeDefined();
  });

  it("displays exact error copy on failed login attempt", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: "That email and password do not match." }),
    });

    renderLogin();

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "wrong@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "wrong_password123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeDefined();
      expect(
        screen.getByText("That email and password do not match.")
      ).toBeDefined();
    });
  });

  it("switches to two-factor verification step when 2FA is required", async () => {
    globalThis.fetch = vi.fn().mockImplementation(async (url: string) => {
      if (url.endsWith("/api/login")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            message: "Two-factor authentication code required",
            requires_2fa: true,
            pending_token: "test_pending_token",
          }),
        };
      }
      return {
        ok: true,
        status: 200,
        json: async () => ({}),
      };
    });

    renderLogin();

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "totp@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "secure_pass1234" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "Two-factor verification" })
      ).toBeDefined();
      expect(
        screen.getByLabelText("Authentication code or recovery code")
      ).toBeDefined();
      expect(screen.getByRole("button", { name: "Verify" })).toBeDefined();
      expect(screen.getByRole("button", { name: "Cancel" })).toBeDefined();
    });
  });
});

