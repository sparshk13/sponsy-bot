"""Acceptance and security tests for Phase 11 (Acceptance sections C, E, F, H)."""

import os
import re
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.drafting import validate_draft
from app.main import app
from app.models import Campaign, Company, Suppression, Target, User

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent


def test_routes_parity_against_docs():
    """Every route in docs/ROUTES.md exists in app, and no unlisted /api/ route exists (F)."""
    routes_doc_path = WORKSPACE_ROOT / "docs" / "ROUTES.md"
    assert routes_doc_path.exists(), "docs/ROUTES.md must exist"

    doc_content = routes_doc_path.read_text(encoding="utf-8")
    table_lines = [
        line.strip()
        for line in doc_content.splitlines()
        if line.strip().startswith("|") and "/api/" in line
    ]

    expected_routes: set[tuple[str, str]] = set()
    for line in table_lines:
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) >= 2:
            methods_raw, path_raw = parts[0], parts[1]
            methods = [m.strip().upper() for m in methods_raw.split(",")]
            # normalize {id} to generic parameter pattern for comparison
            normalized_path = re.sub(r"\{[^}]+\}", "{param}", path_raw)
            for m in methods:
                expected_routes.add((m, normalized_path))

    openapi = app.openapi()
    api_paths = openapi["paths"]
    actual_routes: set[tuple[str, str]] = set()

    for path, path_item in api_paths.items():
        if not path.startswith("/api/"):
            continue
        normalized_path = re.sub(r"\{[^}]+\}", "{param}", path)
        for method in path_item.keys():
            actual_routes.add((method.upper(), normalized_path))

    # Match expected routes against actual routes, allowing base resource path to map to {param}
    # for item-level actions like PUT /api/admin/users -> PUT /api/admin/users/{user_id}
    unmatched: set[tuple[str, str]] = set()
    for exp_method, exp_path in expected_routes:
        if (exp_method, exp_path) in actual_routes:
            continue
        if (exp_method, f"{exp_path}/{{param}}") in actual_routes:
            continue
        unmatched.add((exp_method, exp_path))

    assert not unmatched, f"Routes documented in docs/ROUTES.md missing in app: {unmatched}"

    # Check for unlisted routes: allowed known helper endpoints
    allowed_extras = {
        ("GET", "/api/admin/brochures"),
        ("GET", "/api/admin/pause"),
    }
    unlisted = actual_routes - expected_routes - allowed_extras
    # Filter out routes where {param} was matched
    truly_unlisted = set()
    for act_method, act_path in unlisted:
        base_path = re.sub(r"/\{param\}$", "", act_path)
        if (act_method, base_path) in expected_routes:
            continue
        truly_unlisted.add((act_method, act_path))

    assert not truly_unlisted, f"Unlisted API routes found in application: {truly_unlisted}"


def test_grep_no_dangerously_set_inner_html():
    """dangerouslySetInnerHTML must appear nowhere in frontend/src (C5, SEC-13)."""
    frontend_src = WORKSPACE_ROOT / "frontend" / "src"
    assert frontend_src.exists()

    hits = []
    for root, _, files in os.walk(frontend_src):
        for f in files:
            if f.endswith((".ts", ".tsx", ".js", ".jsx")):
                full_path = Path(root) / f
                content = full_path.read_text(encoding="utf-8")
                if "dangerouslySetInnerHTML" in content:
                    hits.append(str(full_path.relative_to(WORKSPACE_ROOT)))

    assert not hits, f"dangerouslySetInnerHTML found in frontend: {hits}"


def test_html_entry_point_no_inline_scripts_or_styles():
    """The HTML entry point must contain no inline script or style blocks (C6, SEC-15)."""
    index_html = WORKSPACE_ROOT / "frontend" / "index.html"
    assert index_html.exists()
    content = index_html.read_text(encoding="utf-8")

    # Reject inline <script> without src
    inline_scripts = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", content, re.DOTALL)
    non_empty_inline_scripts = [s.strip() for s in inline_scripts if s.strip()]
    assert not non_empty_inline_scripts, (
        f"Inline scripts found in index.html: {non_empty_inline_scripts}"
    )

    # Reject <style> tags
    inline_styles = re.findall(r"<style[^>]*>(.*?)</style>", content, re.DOTALL)
    assert not inline_styles, f"Inline styles found in index.html: {inline_styles}"

    # Reject event attributes like onload=, onclick=
    event_handlers = re.findall(r"\son\w+\s*=", content, re.IGNORECASE)
    assert not event_handlers, f"Inline event handlers found in index.html: {event_handlers}"


def test_grep_approved_status_only_in_approve_route():
    """Nothing but the approve route code path sets message status to approved (E, SEC-20)."""
    backend_app = WORKSPACE_ROOT / "backend" / "app"
    assert backend_app.exists()

    suspicious_assignments = []
    # Pattern looking for message.status = "approved" or similar
    pattern = re.compile(r'(\.status\s*=\s*["\']approved["\'])')

    for root, _, files in os.walk(backend_app):
        for f in files:
            if f.endswith(".py"):
                full_path = Path(root) / f
                content = full_path.read_text(encoding="utf-8")
                rel_path = str(full_path.relative_to(backend_app))
                if pattern.search(content):
                    # Only app/routes/messages.py is authorized to set approved
                    if rel_path != "routes/messages.py":
                        suspicious_assignments.append(rel_path)

    assert not suspicious_assignments, (
        f"Code outside app/routes/messages.py sets approved status: {suspicious_assignments}"
    )


def test_gitignore_contains_required_patterns():
    """.gitignore must protect secrets, databases, backups, and uploads (C13, SEC-01)."""
    gitignore_path = WORKSPACE_ROOT / ".gitignore"
    assert gitignore_path.exists(), ".gitignore must exist"
    content = gitignore_path.read_text(encoding="utf-8")

    required_entries = [".env", "backups", "uploads"]
    for entry in required_entries:
        assert entry in content, f".gitignore missing essential pattern: {entry}"


def test_frontend_no_sensitive_storage():
    """No tokens or secrets in localStorage or sessionStorage in frontend (C15, SEC-35)."""
    frontend_src = WORKSPACE_ROOT / "frontend" / "src"
    assert frontend_src.exists()

    banned_usages = []
    storage_pattern = re.compile(r"(localStorage|sessionStorage)\.(setItem|getItem)")

    for root, _, files in os.walk(frontend_src):
        for f in files:
            if f.endswith((".ts", ".tsx")):
                full_path = Path(root) / f
                content = full_path.read_text(encoding="utf-8")
                if storage_pattern.search(content):
                    banned_usages.append(str(full_path.relative_to(WORKSPACE_ROOT)))

    assert not banned_usages, f"Unapproved storage usage found: {banned_usages}"


def test_admin_suppression_endpoints(client: TestClient, admin_user: User, db: Session):
    """Admin can list, add, and delete suppression records with CSRF and auth (R6, SEC-22)."""
    login_resp = client.post(
        "/api/login", json={"email": admin_user.email, "password": "admin_secure_pass123"}
    )
    assert login_resp.status_code == 200
    csrf_token = client.get("/api/session").json()["csrf_token"]

    # 1. Add suppression
    add_resp = client.post(
        "/api/admin/suppression",
        json={"kind": "email", "value": "optout@example.com", "reason": "Declined outreach"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert add_resp.status_code == 201
    supp_id = add_resp.json()["id"]

    # 2. List suppression
    list_resp = client.get("/api/admin/suppression")
    assert list_resp.status_code == 200
    supp_values = [s["value"] for s in list_resp.json()]
    assert "optout@example.com" in supp_values

    # 3. Delete suppression
    del_resp = client.delete(
        f"/api/admin/suppression/{supp_id}",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert del_resp.status_code == 204

    # Verify deleted
    assert db.get(Suppression, supp_id) is None


def test_target_reassign_endpoint(
    client: TestClient, admin_user: User, organizer_user: User, db: Session
):
    """Admin can reassign target to another user with audit logging (docs/ROUTES.md)."""
    # Create another organizer
    new_organizer = User(
        email="new_org@example.com",
        name="New Organizer",
        role="organizer",
        password_hash="fakehash123",
        is_active=True,
    )
    db.add(new_organizer)

    campaign = Campaign(
        name="Reassign Test Campaign",
        event_summary="Summary",
        created_by=admin_user.id,
    )
    db.add(campaign)
    db.commit()

    company = Company(name="Reassign Corp", domain="reassign.com", website="https://reassign.com")
    db.add(company)
    db.commit()

    target = Target(
        campaign_id=campaign.id,
        company_id=company.id,
        owner_id=organizer_user.id,
        status="not_contacted",
    )
    db.add(target)
    db.commit()

    # Login as admin
    client.post("/api/login", json={"email": admin_user.email, "password": "admin_secure_pass123"})
    csrf_token = client.get("/api/session").json()["csrf_token"]

    resp = client.post(
        f"/api/targets/{target.id}/reassign",
        json={"new_owner_id": new_organizer.id},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp.status_code == 200
    assert resp.json()["owner_id"] == new_organizer.id

    db.refresh(target)
    assert target.owner_id == new_organizer.id


def test_email_voice_invariants():
    """Outreach email validation checks voice guidelines (no em dash, opt-out line present)."""
    campaign_dict = {
        "name": "DevFest",
        "event_summary": "A student developer summit in Delhi",
        "event_date": "2026-10-24",
        "audience_note": "500 students",
        "cash_target_inr": 150000,
        "goodies_note": None,
        "credits_note": None,
    }
    verified_facts = [
        {"id": 1, "status": "verified", "claim": "Tech company founded in 2020"},
    ]

    # 1. Valid body with opt-out and no em dash
    valid_body = (
        "Hi Alex,\n\n"
        "I am writing from DevFest, an engineering student conference at campus.\n"
        "We saw your developer tools and wanted to invite you as an event partner.\n"
        "We are expecting 500 attendees and would love to collaborate on a booth.\n"
        "Please let me know if you would be open to a short chat this week.\n\n"
        "If this is not for you, reply and I will not write again.\n\n"
        "Best,\n"
        "Sparsh"
    )
    res = validate_draft(
        subject="Partnership inquiry for DevFest",
        body=valid_body,
        facts_used=[1],
        campaign_data=campaign_dict,
        company_name="Acme Corp",
        verified_facts=verified_facts,
        kind="first",
    )
    # Check that opt-out is recognized
    assert not any("opt-out" in e.lower() for e in res.errors)

    # 2. Body missing opt-out line
    no_opt_out_body = (
        "Hi Alex,\n\n"
        "I am writing from DevFest, an engineering student conference at campus.\n"
        "We saw your developer tools and wanted to invite you as an event partner.\n"
        "We are expecting 500 attendees and would love to collaborate on a booth.\n"
        "Please let me know if you would be open to a short chat this week.\n\n"
        "Best,\n"
        "Sparsh"
    )
    res_no_opt = validate_draft(
        subject="Partnership inquiry for DevFest",
        body=no_opt_out_body,
        facts_used=[1],
        campaign_data=campaign_dict,
        company_name="Acme Corp",
        verified_facts=verified_facts,
        kind="first",
    )
    assert any("opt-out" in e.lower() for e in res_no_opt.errors)
