"""LangGraph Graph A for preparation, drafting, validation, and interrupt (R4, R5)."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Literal, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from sqlalchemy import select

from app.audit import log_audit
from app.config import settings
from app.db import get_db
from app.drafting import validate_draft
from app.followup import compute_next_followup_at, get_followup_delay_days
from app.llm import llm_client
from app.models import Brochure, CompanyFact, Contact, Message, Target, Template
from app.research import run_research


@contextmanager
def _get_db_session():
    from app.main import app

    override = app.dependency_overrides.get(get_db)
    gen = override() if override else get_db()
    session = next(gen)
    try:
        yield session
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


class GraphAState(TypedDict, total=False):
    target_id: int
    user_id: int
    needs_contact: bool
    validation_errors: list[str]
    message_id: int | None
    completed: bool


def _load_node(state: GraphAState) -> GraphAState:
    with _get_db_session() as db:
        target = db.get(Target, state["target_id"])
        if not target:
            raise ValueError(f"Target {state['target_id']} not found.")
    return state


def _research_node(state: GraphAState) -> GraphAState:
    with _get_db_session() as db:
        target = db.get(Target, state["target_id"])
        if target:
            run_research(db, target, force_refresh=False)
    return state


def _recommend_node(state: GraphAState) -> GraphAState:
    with _get_db_session() as db:
        target = db.get(Target, state["target_id"])
        if not target:
            return state
        # If recommendation is not yet set, run research recommendation
        if not target.tier or not target.ask_summary:
            run_research(db, target, force_refresh=False)
    return state


def _find_contact_node(state: GraphAState) -> GraphAState:
    with _get_db_session() as db:
        target = db.get(Target, state["target_id"])
        if not target:
            return state
        contact = db.scalar(
            select(Contact).where(
                Contact.company_id == target.company_id,
                Contact.email.isnot(None),
                Contact.is_valid.is_(True),
            )
        )
        if not contact or not contact.email:
            state["needs_contact"] = True
        else:
            state["needs_contact"] = False
    return state


def _draft_node(state: GraphAState) -> GraphAState:
    if state.get("needs_contact"):
        return state

    with _get_db_session() as db:
        target = db.get(Target, state["target_id"])
        if not target:
            return state
        campaign = target.campaign
        company = target.company
        contact = db.scalar(
            select(Contact).where(
                Contact.company_id == target.company_id,
                Contact.email.isnot(None),
                Contact.is_valid.is_(True),
            )
        )

        facts = db.scalars(
            select(CompanyFact).where(
                CompanyFact.company_id == target.company_id,
                CompanyFact.status == "verified",
            )
        ).all()
        facts_data = [
            {
                "id": f.id,
                "kind": f.kind,
                "claim": f.claim,
                "evidence_quote": f.evidence_quote,
                "status": f.status,
            }
            for f in facts
        ]

        campaign_info = {
            "name": campaign.name,
            "event_summary": campaign.event_summary,
            "event_date": str(campaign.event_date) if campaign.event_date else "",
            "audience_note": campaign.audience_note or "",
            "cash_target": str(campaign.cash_target_inr or ""),
            "goodies_note": campaign.goodies_note or "",
            "credits_note": campaign.credits_note or "",
            "calendar_link": campaign.calendar_link or "",
        }

        # Retrieve existing draft bodies in campaign for similarity comparison
        other_drafts = db.scalars(
            select(Message.body)
            .join(Target, Message.target_id == Target.id)
            .where(
                Target.campaign_id == campaign.id,
                Message.target_id != target.id,
                Message.status.in_(["draft", "approved", "sent"]),
            )
        ).all()
        other_bodies = [b for b in other_drafts if b]

        # Template lookup (Phase 8, G6)
        template = db.scalar(
            select(Template).where(Template.kind == "first").order_by(Template.id.desc())
        )
        template_body = template.body if template else None

        # Generate draft (Call 2)
        plan_and_draft = llm_client.generate_plan_and_draft(
            company_name=company.name,
            category=company.category,
            campaign_info=campaign_info,
            verified_facts=facts_data,
            contact_name=contact.name if contact else None,
            sender_name="Outreach Organizer",
            sender_club="Student Tech Club",
            template_body=template_body,
        )

        # Validate draft
        val = validate_draft(
            subject=plan_and_draft.subject,
            body=plan_and_draft.body,
            facts_used=plan_and_draft.facts_used,
            campaign_data=campaign_info,
            company_name=company.name,
            verified_facts=facts_data,
            other_draft_bodies=other_bodies,
        )

        # Retry once if validation failed (SEC-25)
        if not val.is_valid:
            plan_and_draft = llm_client.generate_plan_and_draft(
                company_name=company.name,
                category=company.category,
                campaign_info=campaign_info,
                verified_facts=facts_data,
                contact_name=contact.name if contact else None,
                sender_name="Outreach Organizer",
                sender_club="Student Tech Club",
            )
            val = validate_draft(
                subject=plan_and_draft.subject,
                body=plan_and_draft.body,
                facts_used=plan_and_draft.facts_used,
                campaign_data=campaign_info,
                company_name=company.name,
                verified_facts=facts_data,
                other_draft_bodies=other_bodies,
            )

        # Check for existing inflight message for this target
        existing_msg = db.scalar(
            select(Message).where(
                Message.target_id == target.id,
                Message.direction == "out",
                Message.status.in_(["draft", "approved"]),
            )
        )

        # Match tier brochure (Phase 8, G5)
        brochure = None
        if target.tier:
            brochure = db.scalar(
                select(Brochure).where(Brochure.tier == target.tier).order_by(Brochure.id.desc())
            )
        attachment_id = brochure.id if brochure else None

        if existing_msg:
            # Overwrite draft content; reset status to draft
            existing_msg.subject = plan_and_draft.subject
            existing_msg.body = plan_and_draft.body
            existing_msg.facts_used = plan_and_draft.facts_used
            existing_msg.contact_id = contact.id if contact else None
            existing_msg.attachment_id = attachment_id
            existing_msg.status = "draft"
            existing_msg.approved_by = None
            existing_msg.approved_at = None
            existing_msg.approved_hash = None
            msg = existing_msg
        else:
            msg = Message(
                target_id=target.id,
                contact_id=contact.id if contact else None,
                attachment_id=attachment_id,
                direction="out",
                kind="first",
                subject=plan_and_draft.subject,
                body=plan_and_draft.body,
                status="draft",
                facts_used=plan_and_draft.facts_used,
                created_by=state.get("user_id"),
            )
            db.add(msg)

        db.commit()
        db.refresh(msg)

        state["message_id"] = msg.id
        state["validation_errors"] = val.errors
    return state


def _await_approval_node(state: GraphAState) -> GraphAState:
    # SEC-20: Graph never approves. It halts here via interrupt and requires human approval.
    interrupt(
        {
            "action": "await_approval",
            "target_id": state["target_id"],
            "message_id": state.get("message_id"),
        }
    )
    return state


def _end_node(state: GraphAState) -> GraphAState:
    state["completed"] = True
    return state


def _route_after_contact(state: GraphAState) -> str:
    if state.get("needs_contact"):
        return "end"
    return "draft"


_checkpointer_instance: SqliteSaver | None = None


def get_checkpointer(db_path: str = "checkpoints.db") -> SqliteSaver:
    global _checkpointer_instance
    if _checkpointer_instance is None:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        saver = SqliteSaver(conn)
        saver.setup()
        _checkpointer_instance = saver
    return _checkpointer_instance


def build_graph_a(checkpointer: Any = None):
    """Build and compile Graph A with human-in-the-loop interrupt."""
    if checkpointer is None:
        checkpointer = get_checkpointer()

    builder = StateGraph(GraphAState)
    builder.add_node("load", _load_node)
    builder.add_node("research", _research_node)
    builder.add_node("recommend", _recommend_node)
    builder.add_node("find_contact", _find_contact_node)
    builder.add_node("draft", _draft_node)
    builder.add_node("await_approval", _await_approval_node)
    builder.add_node("end_step", _end_node)

    builder.add_edge(START, "load")
    builder.add_edge("load", "research")
    builder.add_edge("research", "recommend")
    builder.add_edge("recommend", "find_contact")
    builder.add_conditional_edges(
        "find_contact",
        _route_after_contact,
        {"draft": "draft", "end": "end_step"},
    )
    builder.add_edge("draft", "await_approval")
    builder.add_edge("await_approval", "end_step")
    builder.add_edge("end_step", END)

    return builder.compile(checkpointer=checkpointer)


class GraphBState(TypedDict, total=False):
    event: Literal["sent", "reply_received", "followup_due"]
    target_id: int
    message_id: int | None
    classification: str | None
    now_iso: str | None


def _handle_sent_node(state: GraphBState) -> GraphBState:
    with _get_db_session() as db:
        target = db.get(Target, state["target_id"])
        if not target:
            return state

        current_time = (
            datetime.fromisoformat(state["now_iso"])
            if state.get("now_iso")
            else datetime.now(timezone.utc)
        )
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        msg = db.get(Message, state["message_id"]) if state.get("message_id") else None

        target.last_contacted_at = current_time

        if msg and msg.kind in ("followup", "follow_up"):
            target.followup_count += 1
            target.status = "follow_up"
        elif target.status == "not_contacted":
            target.status = "contacted"

        delay_days = get_followup_delay_days(target.followup_count)
        next_dt = compute_next_followup_at(current_time, delay_days)
        target.next_followup_at = next_dt

        log_audit(
            db,
            msg.approved_by if msg else None,
            "scheduled_followup",
            "targets",
            str(target.id),
            f"Scheduled next follow-up for target {target.id} at {next_dt.isoformat()}",
        )
        db.commit()
    return state


def _handle_reply_node(state: GraphBState) -> GraphBState:
    with _get_db_session() as db:
        target = db.get(Target, state["target_id"])
        if not target:
            return state

        classification = state.get("classification")

        # Non-replies (auto_reply or bounce) do not cancel schedule (ARCHITECTURE.md 112)
        if classification not in ("auto_reply", "bounce"):
            target.next_followup_at = None

        if classification == "interested":
            target.status = "interested"
            contact = db.scalar(
                select(Contact).where(
                    Contact.company_id == target.company_id,
                    Contact.is_valid.is_(True),
                    Contact.email.isnot(None),
                )
            )

            existing_draft = db.scalar(
                select(Message).where(
                    Message.target_id == target.id,
                    Message.direction == "out",
                    Message.status.in_(["draft", "approved"]),
                )
            )

            incoming_msg = db.get(Message, state["message_id"]) if state.get("message_id") else None
            orig_subj = incoming_msg.subject if incoming_msg else "Sponsorship discussion"

            subj, body = llm_client.generate_meeting_draft(
                company_name=target.company.name,
                contact_name=contact.name if contact else None,
                calendar_link=target.campaign.calendar_link,
                original_subject=orig_subj or "Sponsorship discussion",
            )

            if existing_draft:
                existing_draft.subject = subj
                existing_draft.body = body
                existing_draft.status = "draft"
                existing_draft.kind = "meeting"
            else:
                draft_msg = Message(
                    target_id=target.id,
                    contact_id=contact.id if contact else None,
                    direction="out",
                    kind="meeting",
                    subject=subj,
                    body=body,
                    status="draft",
                    in_reply_to=incoming_msg.message_id_header if incoming_msg else None,
                )
                db.add(draft_msg)

            log_audit(
                db,
                None,
                "queued_meeting_draft",
                "targets",
                str(target.id),
                f"Generated meeting response draft for target {target.id}",
            )
        db.commit()
    return state


def _handle_followup_due_node(state: GraphBState) -> GraphBState:
    with _get_db_session() as db:
        target = db.get(Target, state["target_id"])
        if not target or target.status not in ("contacted", "follow_up"):
            return state

        if target.followup_count >= settings.max_followups:
            target.status = "closed_no_reply"
            target.next_followup_at = None
            log_audit(
                db,
                None,
                "close_target_no_reply",
                "targets",
                str(target.id),
                f"Target {target.id} reached follow-up limit ({settings.max_followups}); "
                "closed_no_reply.",
            )
            db.commit()
            return state

        existing_draft = db.scalar(
            select(Message).where(
                Message.target_id == target.id,
                Message.direction == "out",
                Message.status.in_(["draft", "approved"]),
            )
        )
        if existing_draft:
            return state

        contact = db.scalar(
            select(Contact).where(
                Contact.company_id == target.company_id,
                Contact.is_valid.is_(True),
                Contact.email.isnot(None),
            )
        )

        facts = db.scalars(
            select(CompanyFact).where(
                CompanyFact.company_id == target.company_id,
                CompanyFact.status == "verified",
            )
        ).all()
        facts_data = [
            {
                "id": f.id,
                "kind": f.kind,
                "claim": f.claim,
                "evidence_quote": f.evidence_quote,
                "status": f.status,
            }
            for f in facts
        ]

        campaign = target.campaign
        campaign_info = {
            "name": campaign.name,
            "event_summary": campaign.event_summary,
            "event_date": str(campaign.event_date) if campaign.event_date else "",
            "audience_note": campaign.audience_note or "",
            "cash_target": str(campaign.cash_target_inr or ""),
            "goodies_note": campaign.goodies_note or "",
            "credits_note": campaign.credits_note or "",
            "calendar_link": campaign.calendar_link or "",
        }

        sent_messages = db.scalars(
            select(Message)
            .where(
                Message.target_id == target.id,
                Message.direction == "out",
                Message.status == "sent",
            )
            .order_by(Message.sent_at.asc())
        ).all()
        prev_list = [{"subject": m.subject or "", "body": m.body or ""} for m in sent_messages]

        followup_num = target.followup_count + 1
        followup_draft = llm_client.generate_followup_draft(
            company_name=target.company.name,
            campaign_info=campaign_info,
            verified_facts=facts_data,
            contact_name=contact.name if contact else None,
            sender_name="Outreach Organizer",
            sender_club="Student Tech Club",
            followup_number=followup_num,
            previous_messages=prev_list,
        )

        val = validate_draft(
            subject=followup_draft.subject,
            body=followup_draft.body,
            facts_used=followup_draft.facts_used,
            campaign_data=campaign_info,
            company_name=target.company.name,
            verified_facts=facts_data,
            kind="followup",
        )

        if not val.is_valid:
            followup_draft = llm_client.generate_followup_draft(
                company_name=target.company.name,
                campaign_info=campaign_info,
                verified_facts=facts_data,
                contact_name=contact.name if contact else None,
                sender_name="Outreach Organizer",
                sender_club="Student Tech Club",
                followup_number=followup_num,
                previous_messages=prev_list,
            )

        new_msg = Message(
            target_id=target.id,
            contact_id=contact.id if contact else None,
            direction="out",
            kind="followup",
            subject=followup_draft.subject,
            body=followup_draft.body,
            status="draft",
            facts_used=followup_draft.facts_used,
            created_by=target.owner_id,
        )
        db.add(new_msg)

        target.next_followup_at = None

        log_audit(
            db,
            None,
            "created_followup_draft",
            "messages",
            None,
            f"Created follow-up #{followup_num} draft for target {target.id}",
        )
        db.commit()
    return state


def _route_graph_b(state: GraphBState) -> str:
    return state.get("event", "sent")


def build_graph_b(checkpointer: Any = None):
    """Build and compile Graph B event router (ARCHITECTURE.md)."""
    if checkpointer is None:
        checkpointer = get_checkpointer()

    builder = StateGraph(GraphBState)
    builder.add_node("sent", _handle_sent_node)
    builder.add_node("reply_received", _handle_reply_node)
    builder.add_node("followup_due", _handle_followup_due_node)

    builder.add_conditional_edges(
        START,
        _route_graph_b,
        {
            "sent": "sent",
            "reply_received": "reply_received",
            "followup_due": "followup_due",
        },
    )
    builder.add_edge("sent", END)
    builder.add_edge("reply_received", END)
    builder.add_edge("followup_due", END)

    return builder.compile(checkpointer=checkpointer)


def handle_graph_b_event(
    event: Literal["sent", "reply_received", "followup_due"],
    target_id: int,
    message_id: int | None = None,
    classification: str | None = None,
    now: datetime | None = None,
    checkpointer: Any = None,
) -> None:
    """Convenience helper to invoke Graph B for an event."""
    graph = build_graph_b(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": f"event_{event}_{target_id}"}}
    state_input: GraphBState = {
        "event": event,
        "target_id": target_id,
        "message_id": message_id,
        "classification": classification,
        "now_iso": now.isoformat() if now else None,
    }
    graph.invoke(state_input, config=config)
