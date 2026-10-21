import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { Inbox } from "../pages/inbox/Inbox";

const MOCK_INBOX_ITEMS = [
  {
    id: 101,
    target_id: 1,
    company_id: 10,
    company_name: "Kavach Systems",
    company_domain: "kavach.in",
    campaign_id: 2,
    campaign_name: "HackFest 2026",
    contact_id: 5,
    contact_name: "Priya Sharma",
    contact_email: "priya@kavach.in",
    subject: "Re: HackFest 2026 Sponsorship",
    body: "Hi Sparsh,\n\nWe would be happy to support the event with cash sponsorship. Could you share details?",
    summary: "Interested in cash sponsorship. Requested details.",
    classification: "interested",
    classified_by_human: false,
    suggested_reply: "Hi Priya, thank you! I've attached our tier packages and would love to connect.",
    created_at: "2026-10-19T02:00:00Z",
    is_owner: true,
  },
  {
    id: 102,
    target_id: 2,
    company_id: 20,
    company_name: "Decline Corp",
    company_domain: "declinecorp.com",
    campaign_id: 2,
    campaign_name: "HackFest 2026",
    contact_id: 6,
    contact_name: "Alex",
    contact_email: "alex@declinecorp.com",
    subject: "Re: HackFest 2026",
    body: "We have allocated all sponsorship funds for the year. Please remove us.",
    summary: "Declined: budget exhausted.",
    classification: "declined",
    classified_by_human: false,
    suggested_reply: null,
    created_at: "2026-10-19T02:10:00Z",
    is_owner: true,
  },
];

function renderInbox(items: object[] | null = MOCK_INBOX_ITEMS) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  queryClient.setQueryData(["inbox", undefined, undefined], items);

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Inbox />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("Inbox page", () => {
  it("renders inbox table with company rows, summary, and status marks with shapes", () => {
    renderInbox();

    expect(screen.getByText("Inbox")).toBeDefined();
    expect(screen.getByText("Kavach Systems")).toBeDefined();
    expect(screen.getByText("Decline Corp")).toBeDefined();
    expect(screen.getByText("Interested in cash sponsorship. Requested details.")).toBeDefined();

    // Verify word + shape status marks (HUM-22)
    const interestedBadge = screen.getByText(/Interested/i, { selector: "span" });
    expect(interestedBadge.textContent).toContain("●");
    expect(interestedBadge.textContent).toContain("Interested");

    const declinedBadge = screen.getByText(/Declined/i, { selector: "span" });
    expect(declinedBadge.textContent).toContain("■");
    expect(declinedBadge.textContent).toContain("Declined");
  });

  it("shows empty state when no replies exist", () => {
    renderInbox([]);

    expect(
      screen.getByText("No replies yet. We check the mailbox every 5 minutes.")
    ).toBeDefined();
  });

  it("opens review panel to display raw message body and suggestion", () => {
    renderInbox();

    const reviewButtons = screen.getAllByText("Review");
    fireEvent.click(reviewButtons[0]);

    expect(screen.getByTestId("inbox-detail-101")).toBeDefined();
    expect(
      screen.getByText(/We would be happy to support the event with cash sponsorship/i)
    ).toBeDefined();
    expect(screen.getByText("Create queue draft")).toBeDefined();
  });

  it("allows selecting a new classification in the dropdown", () => {
    renderInbox();

    const select = screen.getByLabelText("Change classification for Kavach Systems") as HTMLSelectElement;
    expect(select.value).toBe("interested");

    fireEvent.change(select, { target: { value: "question" } });
    expect(select.value).toBe("question");
  });
});
