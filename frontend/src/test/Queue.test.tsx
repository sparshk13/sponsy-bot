import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { Queue } from "../pages/queue/Queue";

const MOCK_QUEUE = [
  {
    id: 10,
    target_id: 1,
    company_id: 100,
    company_name: "Kavach Systems",
    company_domain: "kavach.in",
    campaign_id: 2,
    campaign_name: "HackFest 2026",
    tier: "cash",
    contact_id: 5,
    contact_name: "Priya Sharma",
    contact_role: "Sponsorship Manager",
    contact_email: "priya@kavach.in",
    subject: "HackFest 2026 Sponsorship",
    body: (
      "Hello Priya,\n\n" +
      "I organize HackFest 2026 at our college, a 24-hour hackathon for 150 engineering students. " +
      "We are bringing together motivated students to build technical projects over a single weekend.\n\n" +
      "We noticed that Kavach Systems sponsored student hackathons in 2024. Your developer tools are popular " +
      "among our participants, and support from your team would make a genuine difference for our event.\n\n" +
      "Could Kavach Systems consider sponsoring our event? In return, we would feature your developer tools " +
      "directly to participants. If a short call is easier, please let me know.\n\n" +
      "Sparsh, Organizer, Student Tech Club\n" +
      "If this is not for you, tell me and I will not write again."
    ),
    status: "draft",
    facts_used: [1],
    approved_by: null,
    approved_at: null,
    created_at: "2026-10-19T01:00:00Z",
    is_owner: true,
  },
  {
    id: 20,
    target_id: 2,
    company_id: 200,
    company_name: "Trishul Cloud",
    company_domain: "trishulcloud.io",
    campaign_id: 2,
    campaign_name: "HackFest 2026",
    tier: "credits",
    contact_id: 6,
    contact_name: "Rahul Verma",
    contact_role: "Tech Evangelist",
    contact_email: "rahul@trishulcloud.io",
    subject: "Trishul Cloud Credits Sponsorship",
    body: (
      "Hello Rahul,\n\n" +
      "I organize HackFest 2026 at our college, a 24-hour hackathon for 150 engineering students. " +
      "We are bringing together motivated students to build technical projects over a single weekend.\n\n" +
      "We would love to collaborate with Trishul Cloud to provide valuable compute credits for participants. " +
      "Could Trishul Cloud support our student initiative this term? In return we will showcase your brand to attendees.\n\n" +
      "If you are available for a brief conversation, please let me know.\n\n" +
      "Sparsh, Organizer, Student Tech Club\n" +
      "If this is not for you, tell me and I will not write again."
    ),
    status: "draft",
    facts_used: [],
    approved_by: null,
    approved_at: null,
    created_at: "2026-10-19T01:05:00Z",
    is_owner: false, // Not owned by current user
  },
];

function renderQueue(queueData: object[]) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  queryClient.setQueryData(["queue"], queueData);

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Queue />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("Queue page", () => {
  it("renders queue table with company rows and inspection button", () => {
    renderQueue(MOCK_QUEUE);

    expect(screen.getByText("Approval queue")).toBeDefined();
    expect(screen.getByText("Kavach Systems")).toBeDefined();
    expect(screen.getByText("Trishul Cloud")).toBeDefined();
    expect(screen.getAllByText("Inspect / Edit").length).toBe(2);
  });

  it("inspects row and shows Approve button for owner", () => {
    renderQueue(MOCK_QUEUE);

    const inspectButtons = screen.getAllByText("Inspect / Edit");
    fireEvent.click(inspectButtons[0]); // Inspect Kavach Systems (is_owner: true)

    expect(screen.getByTestId("draft-editor-10")).toBeDefined();
    expect(screen.getByTestId("approve-btn-10")).toBeDefined();
    expect(screen.getByText("Approve Draft")).toBeDefined();
  });

  it("does not show Approve button for draft not owned by user", () => {
    renderQueue(MOCK_QUEUE);

    const inspectButtons = screen.getAllByText("Inspect / Edit");
    fireEvent.click(inspectButtons[1]); // Inspect Trishul Cloud (is_owner: false)

    expect(screen.getByTestId("draft-editor-20")).toBeDefined();
    expect(screen.queryByTestId("approve-btn-20")).toBeNull();
  });

  it("validates follow-up draft using 40-100 word count range", () => {
    const followupQueue = [
      {
        id: 30,
        target_id: 3,
        company_id: 300,
        company_name: "FollowUp Corp",
        company_domain: "followup.com",
        campaign_id: 2,
        campaign_name: "HackFest 2026",
        tier: "cash",
        contact_id: 7,
        contact_name: "Anita",
        contact_role: "Lead",
        contact_email: "anita@followup.com",
        subject: "Follow-up on HackFest",
        body: (
          "Hello Anita, I wanted to share a quick update regarding HackFest 2026. " +
          "We have finalised our attendee registration and event schedule for next month. " +
          "Could FollowUp Corp partner with our students this term? Let me know if a call works. " +
          "Sparsh, Student Tech Club. If this is not for you, tell me and I will not write again."
        ),
        status: "draft",
        kind: "followup",
        facts_used: [],
        approved_by: null,
        approved_at: null,
        created_at: "2026-10-19T02:00:00Z",
        is_owner: true,
      },
    ];

    renderQueue(followupQueue);

    const inspectButton = screen.getByText("Inspect / Edit");
    fireEvent.click(inspectButton);

    expect(screen.getByText(/Valid 40-100/)).toBeDefined();
  });
});

