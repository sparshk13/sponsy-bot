import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it } from "vitest";
import { TargetDetail } from "../pages/targets/TargetDetail";

function renderTargetDetail(targetData: object) {
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
    csrf_token: "csrf_test_token",
  });

  queryClient.setQueryData(["targets", 1], targetData);

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/targets/1"]}>
        <Routes>
          <Route path="/targets/:id" element={<TargetDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("TargetDetail page", () => {
  it("renders target details, verified facts, and recommendation block", () => {
    const mockTarget = {
      id: 1,
      campaign_id: 1,
      company_id: 10,
      company_name: "Stripe",
      domain: "stripe.com",
      status: "not_contacted",
      owner_id: 1,
      owner_name: "Current User",
      campaign_name: "Hackathon 2026",
      tier: "cash",
      priority: "A",
      priority_score: 5,
      ask_summary: "Ask ₹1,00,000 cash tier",
      ask_reasoning: "Stripe has previously supported student hackathons.",
      ask_basis: "evidence",
      ask_fact_ids: [101],
      researched_at: "2026-10-19T00:00:00Z",
      facts: [
        {
          id: 101,
          company_id: 10,
          kind: "past_sponsorship",
          claim: "Stripe sponsored HackMIT with $10,000",
          source_url: "https://stripe.com/newsroom",
          evidence_quote: "Stripe sponsored HackMIT with $10,000",
          status: "verified",
          retrieved_at: "2026-10-19T00:00:00Z",
        },
        {
          id: 102,
          company_id: 10,
          kind: "other",
          claim: "Unverified rumour",
          source_url: "https://rumour.com",
          evidence_quote: "Unverified quote",
          status: "unverified",
          retrieved_at: "2026-10-19T00:00:00Z",
        },
      ],
    };

    renderTargetDetail(mockTarget);

    expect(screen.getByRole("heading", { name: "Stripe" })).toBeDefined();
    expect(screen.getByText("stripe.com")).toBeDefined();
    expect(screen.getByText("Ask ₹1,00,000 cash tier")).toBeDefined();
    expect(screen.getByText("Verified")).toBeDefined();
    expect(screen.getByText("Unverified")).toBeDefined();
    expect(screen.getByText("Score 5")).toBeDefined();
  });

  it("renders assumption badge and empty evidence state when no facts exist", () => {
    const mockTargetNoEvidence = {
      id: 1,
      campaign_id: 1,
      company_id: 20,
      company_name: "Unknown Startup",
      domain: "unknown.com",
      status: "not_contacted",
      owner_id: 1,
      owner_name: "Current User",
      campaign_name: "Hackathon 2026",
      tier: "credits",
      priority: "C",
      priority_score: 1,
      ask_summary: "Infrastructure tier",
      ask_reasoning:
        "No sponsorship history found in the sources searched. This ask is an assumption.",
      ask_basis: "assumption",
      ask_fact_ids: [],
      researched_at: "2026-10-19T00:00:00Z",
      facts: [],
    };

    renderTargetDetail(mockTargetNoEvidence);

    expect(screen.getByText("Assumption, not evidence")).toBeDefined();
    expect(
      screen.getByText("No sponsorship history found in the sources searched.")
    ).toBeDefined();
  });

  it("renders status progression button and outcome form when interested or meeting booked", () => {
    const mockTargetInterested = {
      id: 1,
      campaign_id: 1,
      company_id: 30,
      company_name: "Interested Partner",
      domain: "partner.com",
      status: "interested",
      owner_id: 1,
      owner_name: "Current User",
      campaign_name: "Hackathon 2026",
      tier: "cash",
      facts: [],
      thread: [
        {
          id: 50,
          target_id: 1,
          direction: "in",
          kind: "reply",
          subject: "Re: Sponsorship",
          body: "We are interested in speaking with your team.",
          status: "received",
          created_at: "2026-10-19T06:00:00Z",
        },
      ],
      outcomes: [],
    };

    renderTargetDetail(mockTargetInterested);

    expect(screen.getByRole("button", { name: "Mark meeting booked" })).toBeDefined();
    expect(screen.getByText("Record Outcome")).toBeDefined();
    expect(screen.getByText("Message thread history")).toBeDefined();
    expect(screen.getByText("We are interested in speaking with your team.")).toBeDefined();
  });

  it("renders contact info and toggles manual contact form", () => {
    const mockTargetWithContact = {
      id: 1,
      campaign_id: 1,
      company_id: 40,
      company_name: "GitHub",
      domain: "github.com",
      status: "not_contacted",
      owner_id: 1,
      owner_name: "Current User",
      contact: {
        id: 1,
        target_id: 1,
        name: "Jane Doe",
        email: "jane@github.com",
        role: "Developer Relations",
        source: "manual",
      },
      facts: [],
    };

    renderTargetDetail(mockTargetWithContact);

    expect(screen.getByText("Jane Doe")).toBeDefined();
    expect(screen.getByText("(Developer Relations),")).toBeDefined();
    expect(screen.getByText("jane@github.com")).toBeDefined();
    expect(screen.getByRole("button", { name: "Find contact (Hunter)" })).toBeDefined();

    const editBtn = screen.getByRole("button", { name: "Edit contact" });
    expect(editBtn).toBeDefined();
  });

  it("renders brochure attachment link on outreach draft", () => {
    const mockTargetWithBrochure = {
      id: 1,
      campaign_id: 1,
      company_id: 50,
      company_name: "Postman",
      domain: "postman.com",
      status: "not_contacted",
      owner_id: 1,
      owner_name: "Current User",
      facts: [],
      contact: {
        id: 2,
        target_id: 1,
        name: "Dev Lead",
        email: "dev@postman.com",
        source: "hunter",
      },
      draft: {
        id: 99,
        target_id: 1,
        subject: "Postman sponsorship query",
        body: "Hello Dev Lead, would Postman consider partnering with us for our upcoming student hackathon? We are looking for tool credits and API support.",
        status: "draft",
        kind: "initial",
        attachment_id: 7,
      },
    };

    renderTargetDetail(mockTargetWithBrochure);

    expect(screen.getByText("Brochure attached:")).toBeDefined();
    const downloadLink = screen.getByRole("link", { name: "Download PDF" });
    expect(downloadLink.getAttribute("href")).toBe("/api/brochures/7");
  });
});


