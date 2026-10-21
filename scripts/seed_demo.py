"""Seed rich, realistic production data showcasing Sponsy Bot in full operation."""

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
for p in [str(backend_dir), str(root_dir), "/app"]:
    if p not in sys.path:
        sys.path.insert(0, p)

from sqlalchemy import delete, select

from app.audit import log_audit
from app.auth import hash_password
from app.config import settings
from app.db import SessionLocal
from app.models import (
    ApiUsage,
    AuditLog,
    Brochure,
    Campaign,
    Company,
    CompanyFact,
    Contact,
    Message,
    Outcome,
    Suppression,
    Target,
    Template,
    User,
    utc_now,
    utc_today,
)


def seed_demo_data() -> None:
    db = SessionLocal()
    try:
        now = utc_now()
        today = utc_today()

        # -------------------------------------------------------------
        # 1. Clean old demo records for an idempotent fresh seed
        # -------------------------------------------------------------
        db.execute(delete(AuditLog))
        db.execute(delete(Outcome))
        db.execute(delete(Message))
        db.execute(delete(Target))
        db.execute(delete(CompanyFact))
        db.execute(delete(Contact))
        db.execute(delete(Company))
        db.execute(delete(Campaign))
        db.execute(delete(Suppression))
        db.execute(delete(Brochure))
        db.execute(delete(Template))
        db.execute(delete(ApiUsage))
        db.commit()

        # -------------------------------------------------------------
        # 2. Users: Admin Sparsh and 2 Club Organizers (Priya & Rohan)
        # -------------------------------------------------------------
        admin = db.scalar(select(User).where(User.email == "admin@example.com"))
        if not admin:
            admin = User(
                email="admin@example.com",
                name="Admin Sparsh",
                role="admin",
                password_hash=hash_password("Password12345!"),
                is_active=True,
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
        else:
            admin.name = "Admin Sparsh"
            admin.password_hash = hash_password("Password12345!")
            admin.is_active = True
            db.commit()

        priya = db.scalar(select(User).where(User.email == "priya@sponsy.club"))
        if not priya:
            priya = User(
                email="priya@sponsy.club",
                name="Priya Sharma",
                role="organizer",
                password_hash=hash_password("Password12345!"),
                is_active=True,
            )
            db.add(priya)
            db.commit()
            db.refresh(priya)
        else:
            priya.name = "Priya Sharma"
            priya.password_hash = hash_password("Password12345!")
            priya.is_active = True
            db.commit()

        rohan = db.scalar(select(User).where(User.email == "rohan@sponsy.club"))
        if not rohan:
            rohan = User(
                email="rohan@sponsy.club",
                name="Rohan Verma",
                role="organizer",
                password_hash=hash_password("Password12345!"),
                is_active=True,
            )
            db.add(rohan)
            db.commit()
            db.refresh(rohan)
        else:
            rohan.name = "Rohan Verma"
            rohan.password_hash = hash_password("Password12345!")
            rohan.is_active = True
            db.commit()

        # -------------------------------------------------------------
        # 3. API Usage: Active Counters Demonstrating Real Operations
        # -------------------------------------------------------------
        db.add(ApiUsage(day=today, provider="gemini", units=184))
        db.add(ApiUsage(day=today, provider="tavily", units=112))
        db.add(ApiUsage(day=today, provider="hunter", units=22))
        db.commit()

        # -------------------------------------------------------------
        # 4. Campaigns: HackFest 2026 (Active), 2025 & 2024 (Memory)
        # -------------------------------------------------------------
        camp_2024 = Campaign(
            name="HackFest 2024",
            event_summary="First in-person collegiate hackathon edition with 900 developers.",
            event_date=(now - timedelta(days=730)).date(),
            cash_target_inr=250000,
            audience_note="900 engineering undergraduates.",
            created_by=admin.id,
            created_at=now - timedelta(days=740),
        )
        db.add(camp_2024)

        camp_2025 = Campaign(
            name="HackFest 2025",
            event_summary="Second annual 24-hour student hackathon with 1,200 attendees.",
            event_date=(now - timedelta(days=365)).date(),
            cash_target_inr=350000,
            audience_note="1,200 undergraduates across top 20 universities.",
            created_by=admin.id,
            created_at=now - timedelta(days=375),
        )
        db.add(camp_2025)

        camp_2026 = Campaign(
            name="HackFest 2026",
            event_summary=(
                "24-hour national student hackathon with 1,500+ student developers, "
                "focusing on AI agents, cloud infrastructure, Web3, and developer tooling."
            ),
            event_date=(now + timedelta(days=22)).date(),
            audience_note="1,500+ active computer science and engineering undergraduates across top Indian colleges.",
            cash_target_inr=500000,
            goodies_note="T-shirts, stickers, hardware kits, snacks, and midnight energy drink packs.",
            credits_note="Cloud compute credits, database vouchers, and AI API inference keys.",
            calendar_link="https://cal.com/hackfest2026/sponsor-chat",
            created_by=admin.id,
            created_at=now - timedelta(days=16),
        )
        db.add(camp_2026)
        db.commit()
        db.refresh(camp_2024)
        db.refresh(camp_2025)
        db.refresh(camp_2026)

        # -------------------------------------------------------------
        # 5. Templates (Admin Outreach Templates)
        # -------------------------------------------------------------
        t_cash = Template(
            kind="first",
            name="Initial Outreach: Title & Cash Prize Track",
            body=(
                "Hi {{contact_name}},\n\n"
                "I am organizing {{event_name}} on {{event_date}}, bringing together 1,500 student developers for a 24-hour hackathon. "
                "Our participants build web and mobile applications from scratch, and we are setting up dedicated technical tracks for teams.\n\n"
                "Given {{company_name}}'s work in developer tools and engineering, we would value having your team involved as our {{ask_summary}}. "
                "Your support directly funds the prize pool and hardware resources for the student builders.\n\n"
                "Would you be open to a 15-minute call this week to explore this? Our scheduling link is {{calendar_link}}.\n\n"
                "Best regards,\n{{user_name}}\nSponsorship Team\n"
                "If this is not relevant for you, reply and I will not follow up."
            ),
        )
        t_swag = Template(
            kind="first",
            name="Goodies & Swag Partnership Ask",
            body=(
                "Hi {{contact_name}},\n\n"
                "We are hosting {{event_name}} on {{event_date}}, gathering 1,500 active student developers. "
                "Every attendee receives a welcome kit at check-in, and developer merchandise from engineering brands is always well received.\n\n"
                "We would like to partner with {{company_name}} for {{ask_summary}} to place inside these kits. "
                "In return, we distribute your items to builders, place your logo on our event site, and credit your support.\n\n"
                "Let us know if {{company_name}} would be open to this. I can share our logistics details and attendee numbers.\n\n"
                "Best regards,\n{{user_name}}\nSponsorship Team\n"
                "If this is not for you, reply and I will not write again."
            ),
        )
        t_credits = Template(
            kind="first",
            name="Cloud Infrastructure & Developer Tooling Vouchers",
            body=(
                "Hi {{contact_name}},\n\n"
                "Students at {{event_name}} on {{event_date}} will spend 24 hours building web and machine learning applications. "
                "Most projects require cloud compute, hosted databases, and API credits during the event.\n\n"
                "We would love to offer {{company_name}} developer access ({{ask_summary}}) so participants can build directly on your platform. "
                "In return, we feature {{company_name}} in our hacker kit, highlight your tooling at kickoff, and direct teams to your documentation.\n\n"
                "Would you be open to providing credits for our builders? I can share our attendee demographics and timeline.\n\n"
                "Cheers,\n{{user_name}}\nSponsorship Team\n"
                "If this is not for you, reply and I will not write again."
            ),
        )
        t_follow = Template(
            kind="followup",
            name="Day 4 Follow-up: Polite Check-in",
            body=(
                "Hi {{contact_name}},\n\n"
                "I am following up on my previous note regarding {{event_name}} on {{event_date}}. "
                "We are now finalizing technical track partners and participant welcome materials ahead of our deadline this Friday.\n\n"
                "We would value having {{company_name}} join us as our {{ask_summary}}. "
                "Over 1,500 student builders will be working on projects throughout the weekend, and having your platform support makes a direct difference to their build experience.\n\n"
                "If you are interested, I would be glad to send over our brief sponsorship deck or hop on a short call.\n\n"
                "Best regards,\n{{user_name}}\nSponsorship Team\n"
                "If you are not interested, reply and I will not follow up again."
            ),
        )
        db.add_all([t_cash, t_swag, t_credits, t_follow])
        db.commit()

        # -------------------------------------------------------------
        # 6. Brochures (PDF files with SEC-17 magic bytes b"%PDF")
        # -------------------------------------------------------------
        storage_dir = Path(settings.brochures_upload_dir)
        storage_dir.mkdir(parents=True, exist_ok=True)

        minimal_pdf = (
            b"%PDF-1.4\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
            b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000114 00000 n\n"
            b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF\n"
        )

        b_cash_file = f"{uuid.uuid4().hex}.pdf"
        b_goodies_file = f"{uuid.uuid4().hex}.pdf"
        b_credits_file = f"{uuid.uuid4().hex}.pdf"

        (storage_dir / b_cash_file).write_bytes(minimal_pdf)
        (storage_dir / b_goodies_file).write_bytes(minimal_pdf)
        (storage_dir / b_credits_file).write_bytes(minimal_pdf)

        b_cash = Brochure(
            tier="cash",
            filename="HackFest_2026_Corporate_Sponsorship_Deck.pdf",
            stored_name=b_cash_file,
            uploaded_by=admin.id,
            created_at=now - timedelta(days=14),
        )
        b_goodies = Brochure(
            tier="goodies",
            filename="HackFest_2026_Swag_Partner_Deliverables.pdf",
            stored_name=b_goodies_file,
            uploaded_by=admin.id,
            created_at=now - timedelta(days=14),
        )
        b_credits = Brochure(
            tier="credits",
            filename="HackFest_2026_Cloud_Partner_Kit.pdf",
            stored_name=b_credits_file,
            uploaded_by=admin.id,
            created_at=now - timedelta(days=14),
        )
        db.add_all([b_cash, b_goodies, b_credits])
        db.commit()

        # -------------------------------------------------------------
        # 7. Suppression List
        # -------------------------------------------------------------
        db.add_all([
            Suppression(
                kind="domain",
                value="coinswitch.co",
                reason="Declined participation: university sponsorships paused for current quarter",
                created_at=now - timedelta(days=4),
            ),
            Suppression(
                kind="email",
                value="partnerships@coinswitch.co",
                reason="Declined participation",
                created_at=now - timedelta(days=4),
            ),
            Suppression(
                kind="domain",
                value="stickermule.com",
                reason="Sponsorship capacity full for this year",
                created_at=now - timedelta(days=5),
            ),
            Suppression(
                kind="email",
                value="no-reply-sponsors@oracle.com",
                reason="Unsubscribed via email opt-out link",
                created_at=now - timedelta(days=2),
            ),
        ])
        db.commit()

        # -------------------------------------------------------------
        # Helper utilities for populating companies & facts
        # -------------------------------------------------------------
        def create_company(name: str, domain: str, category: str, website: str) -> Company:
            c = Company(
                name=name,
                domain=domain,
                category=category,
                website=website,
                first_added_at=now - timedelta(days=15),
            )
            db.add(c)
            db.commit()
            db.refresh(c)
            return c

        def create_contact(company: Company, name: str, role: str, email: str, source: str = "hunter") -> Contact:
            c = Contact(
                company_id=company.id,
                name=name,
                role=role,
                email=email,
                source=source,
                is_valid=True,
            )
            db.add(c)
            db.commit()
            db.refresh(c)
            return c

        def create_fact(company: Company, kind: str, claim: str, source_url: str, quote: str) -> CompanyFact:
            f = CompanyFact(
                company_id=company.id,
                kind=kind,
                claim=claim,
                source_url=source_url,
                evidence_quote=quote,
                status="verified",
                retrieved_at=now - timedelta(days=6),
            )
            db.add(f)
            db.commit()
            db.refresh(f)
            return f

        # -------------------------------------------------------------
        # 8. HackFest 2026 Targets (Total: 31 Targets across full lifecycle)
        # -------------------------------------------------------------

        # Target 1: Postman (Secured Cash ₹75,000 - Sparsh)
        co_postman = create_company("Postman", "postman.com", "API Tools", "https://postman.com")
        ct_postman = create_contact(co_postman, "Abhinav Asthana", "CEO & Co-founder", "abhinav@postman.com")
        create_fact(
            co_postman, "past_sponsorship",
            "Postman supports collegiate hackathons with API workshops and cash tracks.",
            "https://blog.postman.com/student-programs",
            "Postman actively partners with top student hackathons worldwide."
        )
        t_postman = Target(
            campaign_id=camp_2026.id,
            company_id=co_postman.id,
            owner_id=admin.id,
            status="secured",
            tier="cash",
            priority="A",
            priority_score=5,
            ask_summary="₹75,000 Title API Track Sponsor",
            ask_reasoning="Postman has sponsored student hackathons in India before with dedicated API prize tracks.",
            researched_at=now - timedelta(days=10),
            last_contacted_at=now - timedelta(days=4),
        )
        db.add(t_postman)
        db.commit()
        db.refresh(t_postman)

        db.add(Message(
            target_id=t_postman.id,
            contact_id=ct_postman.id,
            direction="out",
            kind="initial",
            subject="Partnering with HackFest 2026: API track for 1,500 student developers",
            body="Hi Abhinav,\n\nWe are organizing HackFest 2026 with 1,500+ builders...",
            status="sent",
            sent_at=now - timedelta(days=8),
        ))
        db.add(Message(
            target_id=t_postman.id,
            contact_id=ct_postman.id,
            direction="in",
            kind="reply",
            subject="Re: Partnering with HackFest 2026: API track for 1,500 student developers",
            body="We'd be glad to sponsor HackFest 2026 with a ₹75,000 API track! Please share your official college bank account details and GST invoice.",
            status="received",
            classification="interested",
            summary="Agreed to sponsor ₹75,000 API track. Requested bank details and invoice.",
            suggested_reply="Thanks Abhinav! We have sent over the college banking credentials and signed agreement.",
            classified_by_human=True,
            sent_at=now - timedelta(days=5),
        ))
        db.add(Outcome(
            target_id=t_postman.id,
            kind="cash",
            amount_inr=75000,
            description="Title API track sponsorship of ₹75,000 confirmed and invoiced.",
            confirmed_by=admin.id,
            confirmed_at=now - timedelta(days=3),
        ))

        # Target 2: Polygon (Secured Cash ₹1,20,000 - Priya)
        co_poly = create_company("Polygon", "polygon.technology", "Web3 / Blockchain", "https://polygon.technology")
        ct_poly = create_contact(co_poly, "Sandeep Nailwal", "Co-founder", "sandeep@polygon.technology")
        create_fact(
            co_poly, "past_sponsorship",
            "Polygon actively supports student Web3 developer tracks at Indian hackathons.",
            "https://polygon.technology/community",
            "Polygon developer community fosters next-gen decentralized apps."
        )
        t_poly = Target(
            campaign_id=camp_2026.id,
            company_id=co_poly.id,
            owner_id=priya.id,
            status="secured",
            tier="cash",
            priority="A",
            priority_score=5,
            ask_summary="₹1,20,000 Web3 Track & Bounty Sponsor",
            ask_reasoning="Polygon has high developer adoption and routinely funds university bounties.",
            researched_at=now - timedelta(days=9),
            last_contacted_at=now - timedelta(days=3),
        )
        db.add(t_poly)
        db.commit()
        db.refresh(t_poly)
        db.add(Outcome(
            target_id=t_poly.id,
            kind="cash",
            amount_inr=120000,
            description="Web3 Track Bounty & Workshop sponsorship of ₹1,20,000 confirmed.",
            confirmed_by=priya.id,
            confirmed_at=now - timedelta(days=2),
        ))

        # Target 3: Docker (Secured Cash ₹50,000 - Priya)
        co_docker = create_company("Docker", "docker.com", "DevOps & Containers", "https://docker.com")
        ct_docker = create_contact(co_docker, "Scott Johnston", "CEO & Community Lead", "scott@docker.com")
        t_docker = Target(
            campaign_id=camp_2026.id,
            company_id=co_docker.id,
            owner_id=priya.id,
            status="secured",
            tier="cash",
            priority="A",
            priority_score=5,
            ask_summary="₹50,000 Containerization & Microservices Track",
            ask_reasoning="Docker promotes developer containers and microservice architecture in university hackathons.",
            researched_at=now - timedelta(days=8),
            last_contacted_at=now - timedelta(days=2),
        )
        db.add(t_docker)
        db.commit()
        db.refresh(t_docker)
        db.add(Message(
            target_id=t_docker.id,
            contact_id=ct_docker.id,
            direction="in",
            kind="reply",
            subject="Re: Docker Track at HackFest 2026",
            body="Hi Priya,\n\nWe're thrilled to sponsor the Container Track for ₹50,000. Send us the speaker onboarding details for our DevRel lead.",
            status="received",
            classification="interested",
            summary="Confirmed ₹50,000 Container Track sponsorship. Requested DevRel speaker onboarding.",
            suggested_reply="Thank you Scott! We've onboarded your DevRel team into the HackFest Discord.",
            classified_by_human=True,
            sent_at=now - timedelta(days=2),
        ))
        db.add(Outcome(
            target_id=t_docker.id,
            kind="cash",
            amount_inr=50000,
            description="₹50,000 Containerization Track sponsorship confirmed.",
            confirmed_by=priya.id,
            confirmed_at=now - timedelta(days=1),
        ))

        # Target 4: NVIDIA Inception (Secured Cash ₹1,50,000 - Sparsh)
        co_nvidia = create_company("NVIDIA Inception", "nvidia.com", "AI & Deep Learning", "https://nvidia.com")
        ct_nvidia = create_contact(co_nvidia, "Inception Program Lead", "University Programs Manager", "inception@nvidia.com")
        create_fact(
            co_nvidia, "past_sponsorship",
            "NVIDIA Inception sponsors collegiate AI and robotics hackathons with cash tracks.",
            "https://nvidia.com/inception",
            "Empowering AI developers and student visionaries."
        )
        t_nvidia = Target(
            campaign_id=camp_2026.id,
            company_id=co_nvidia.id,
            owner_id=admin.id,
            status="secured",
            tier="cash",
            priority="A",
            priority_score=5,
            ask_summary="₹1,50,000 Generative AI & Edge Inference Track",
            ask_reasoning="NVIDIA supports collegiate hackathons focusing on LLMs and accelerated compute.",
            researched_at=now - timedelta(days=11),
            last_contacted_at=now - timedelta(days=3),
        )
        db.add(t_nvidia)
        db.commit()
        db.refresh(t_nvidia)
        db.add(Outcome(
            target_id=t_nvidia.id,
            kind="cash",
            amount_inr=150000,
            description="₹1,50,000 GenAI Track sponsorship confirmed.",
            confirmed_by=admin.id,
            confirmed_at=now - timedelta(days=2),
        ))

        # Target 5: Vercel (Secured Cash ₹1,00,000 - Rohan)
        co_vercel = create_company("Vercel", "vercel.com", "Cloud Frontend", "https://vercel.com")
        ct_vercel = create_contact(co_vercel, "Guillermo Rauch", "CEO & Community", "guillermo@vercel.com")
        t_vercel = Target(
            campaign_id=camp_2026.id,
            company_id=co_vercel.id,
            owner_id=rohan.id,
            status="secured",
            tier="cash",
            priority="A",
            priority_score=5,
            ask_summary="₹1,00,000 Frontend Speed & Next.js Track",
            ask_reasoning="Vercel routinely awards cash grants to student teams shipping production-grade apps.",
            researched_at=now - timedelta(days=9),
            last_contacted_at=now - timedelta(days=2),
        )
        db.add(t_vercel)
        db.commit()
        db.refresh(t_vercel)
        db.add(Outcome(
            target_id=t_vercel.id,
            kind="cash",
            amount_inr=100000,
            description="₹1,00,000 Next.js & Frontend Speed Track confirmed.",
            confirmed_by=rohan.id,
            confirmed_at=now - timedelta(days=1),
        ))

        # Target 6: DevZero (Secured Goodies - Rohan)
        co_devzero = create_company("DevZero", "devzero.io", "Cloud Dev Environments", "https://devzero.io")
        ct_devzero = create_contact(co_devzero, "Ayush Sharma", "Growth Lead", "ayush@devzero.io")
        t_devzero = Target(
            campaign_id=camp_2026.id,
            company_id=co_devzero.id,
            owner_id=rohan.id,
            status="secured",
            tier="goodies",
            priority="B",
            priority_score=4,
            ask_summary="200 Custom Hacker T-Shirts and Sticker Packs",
            ask_reasoning="DevZero frequently partners with developer events offering high quality swag.",
            researched_at=now - timedelta(days=7),
            last_contacted_at=now - timedelta(days=2),
        )
        db.add(t_devzero)
        db.commit()
        db.refresh(t_devzero)
        db.add(Outcome(
            target_id=t_devzero.id,
            kind="goodies",
            amount_inr=None,
            description="200 custom hacker t-shirts and premium sticker packs confirmed for participants.",
            confirmed_by=rohan.id,
            confirmed_at=now - timedelta(days=1),
        ))

        # Target 7: Red Bull (Secured Goodies - Rohan)
        co_redbull = create_company("Red Bull", "redbull.com", "Energy & Beverage", "https://redbull.com")
        ct_redbull = create_contact(co_redbull, "Campus Brand Manager", "Student Marketing Lead", "campus@redbull.com")
        t_redbull = Target(
            campaign_id=camp_2026.id,
            company_id=co_redbull.id,
            owner_id=rohan.id,
            status="secured",
            tier="goodies",
            priority="A",
            priority_score=5,
            ask_summary="500 Cans of Energy Drink for Midnight Coding Sprint",
            ask_reasoning="Red Bull partners with overnight hackathons to energize student developers.",
            researched_at=now - timedelta(days=6),
            last_contacted_at=now - timedelta(days=1),
        )
        db.add(t_redbull)
        db.commit()
        db.refresh(t_redbull)
        db.add(Outcome(
            target_id=t_redbull.id,
            kind="goodies",
            amount_inr=None,
            description="500 cold cans of Red Bull delivered directly to campus on event night.",
            confirmed_by=rohan.id,
            confirmed_at=now - timedelta(days=1),
        ))

        # Target 8: GitHub Campus (Secured Goodies - Sparsh)
        co_github = create_company("GitHub Campus", "github.com", "Developer Tools", "https://github.com")
        ct_github = create_contact(co_github, "Campus Program Lead", "Student Developer Relations", "education@github.com")
        t_github = Target(
            campaign_id=camp_2026.id,
            company_id=co_github.id,
            owner_id=admin.id,
            status="secured",
            tier="goodies",
            priority="A",
            priority_score=5,
            ask_summary="1,500 Octocat Sticker Sheets, Cheat Sheets & Pins",
            ask_reasoning="GitHub Education actively supports certified university hackathons with swag bundles.",
            researched_at=now - timedelta(days=10),
            last_contacted_at=now - timedelta(days=3),
        )
        db.add(t_github)
        db.commit()
        db.refresh(t_github)
        db.add(Outcome(
            target_id=t_github.id,
            kind="goodies",
            amount_inr=None,
            description="1,500 Octocat sticker sheets, Git cheat sheets, and collector pins confirmed.",
            confirmed_by=admin.id,
            confirmed_at=now - timedelta(days=2),
        ))

        # Target 9: DigitalOcean (Secured Credits $10k - Sparsh)
        co_do = create_company("DigitalOcean", "digitalocean.com", "Cloud Infrastructure", "https://digitalocean.com")
        ct_do = create_contact(co_do, "Hatch Program Manager", "Startup & University Lead", "hatch@digitalocean.com")
        t_do = Target(
            campaign_id=camp_2026.id,
            company_id=co_do.id,
            owner_id=admin.id,
            status="secured",
            tier="credits",
            priority="A",
            priority_score=5,
            ask_summary="$10,000 Hatch Cloud Infrastructure Credits",
            ask_reasoning="DigitalOcean Hatch program supports hackathons with generous droplet credits.",
            researched_at=now - timedelta(days=8),
            last_contacted_at=now - timedelta(days=3),
        )
        db.add(t_do)
        db.commit()
        db.refresh(t_do)
        db.add(Outcome(
            target_id=t_do.id,
            kind="credits",
            amount_inr=None,
            description="$10,000 in DigitalOcean cloud compute credits for top 50 teams.",
            confirmed_by=admin.id,
            confirmed_at=now - timedelta(days=2),
        ))

        # Target 10: Supabase (Secured Credits - Sparsh)
        co_sub = create_company("Supabase", "supabase.com", "Database Cloud", "https://supabase.com")
        ct_sub = create_contact(co_sub, "Paul Copplestone", "DevRel & Partnerships", "paul@supabase.com")
        t_sub = Target(
            campaign_id=camp_2026.id,
            company_id=co_sub.id,
            owner_id=admin.id,
            status="secured",
            tier="credits",
            priority="A",
            priority_score=5,
            ask_summary="Pro Plan Vouchers for 1,500 Hackathon Builders",
            ask_reasoning="Supabase open-source Postgres is beloved by hackathon hackers.",
            researched_at=now - timedelta(days=7),
            last_contacted_at=now - timedelta(days=2),
        )
        db.add(t_sub)
        db.commit()
        db.refresh(t_sub)
        db.add(Outcome(
            target_id=t_sub.id,
            kind="credits",
            amount_inr=None,
            description="1,500 Supabase Pro vouchers (worth $25/mo each) distributed to participants.",
            confirmed_by=admin.id,
            confirmed_at=now - timedelta(days=1),
        ))

        # Target 11: Together AI (Secured Credits - Rohan)
        co_together = create_company("Together AI", "together.ai", "AI Cloud Inference", "https://together.ai")
        ct_together = create_contact(co_together, "Vipul Ved Prakash", "CEO & Research", "developer@together.ai")
        t_together = Target(
            campaign_id=camp_2026.id,
            company_id=co_together.id,
            owner_id=rohan.id,
            status="secured",
            tier="credits",
            priority="A",
            priority_score=5,
            ask_summary="$5,000 Open Source LLM API Inference Tokens",
            ask_reasoning="Together AI powers high-speed open-source Llama-3 inference for hackathon teams.",
            researched_at=now - timedelta(days=6),
            last_contacted_at=now - timedelta(days=2),
        )
        db.add(t_together)
        db.commit()
        db.refresh(t_together)
        db.add(Outcome(
            target_id=t_together.id,
            kind="credits",
            amount_inr=None,
            description="$5,000 in fast LLM inference tokens for hackers building autonomous agents.",
            confirmed_by=rohan.id,
            confirmed_at=now - timedelta(days=1),
        ))

        # Target 12: Hasura (Meeting Booked - Priya)
        co_hasura = create_company("Hasura", "hasura.io", "GraphQL & Data APIs", "https://hasura.io")
        ct_hasura = create_contact(co_hasura, "Tanmai Gopal", "CEO", "tanmai@hasura.io")
        t_hasura = Target(
            campaign_id=camp_2026.id,
            company_id=co_hasura.id,
            owner_id=priya.id,
            status="meeting_booked",
            tier="cash",
            priority="B",
            priority_score=4,
            ask_summary="₹40,000 Fast API Development Track",
            ask_reasoning="Hasura supports high-velocity API building during student hackathons.",
            researched_at=now - timedelta(days=5),
            last_contacted_at=now - timedelta(days=1),
        )
        db.add(t_hasura)
        db.commit()
        db.refresh(t_hasura)
        db.add(Message(
            target_id=t_hasura.id,
            contact_id=ct_hasura.id,
            direction="in",
            kind="reply",
            subject="Re: Hasura Track at HackFest 2026",
            body="Hey Priya, our DevRel team would be glad to host a GraphQL prize track. Call booked for Thursday 4 PM on your link.",
            status="received",
            classification="interested",
            summary="DevRel team ready for GraphQL track. Call slot booked for Thursday 4 PM.",
            suggested_reply="Confirmed! Call booked for Thursday 4 PM. We'll share our technical track rubric.",
            classified_by_human=True,
            sent_at=now - timedelta(hours=20),
        ))

        # Target 13: Atlassian (Meeting Booked - Sparsh)
        co_atlassian = create_company("Atlassian", "atlassian.com", "Enterprise Collaboration", "https://atlassian.com")
        ct_atlassian = create_contact(co_atlassian, "University Talent Team", "Campus Recruiting Lead", "university@atlassian.com")
        t_atlassian = Target(
            campaign_id=camp_2026.id,
            company_id=co_atlassian.id,
            owner_id=admin.id,
            status="meeting_booked",
            tier="cash",
            priority="A",
            priority_score=5,
            ask_summary="₹80,000 Developer Productivity Partner",
            ask_reasoning="Atlassian actively hires engineers from Indian colleges through hackathon challenges.",
            researched_at=now - timedelta(days=5),
            last_contacted_at=now - timedelta(days=1),
        )
        db.add(t_atlassian)
        db.commit()
        db.refresh(t_atlassian)
        db.add(Message(
            target_id=t_atlassian.id,
            contact_id=ct_atlassian.id,
            direction="in",
            kind="reply",
            subject="Re: Atlassian Partnership with HackFest 2026",
            body="Hi Sparsh,\n\nWe would love to discuss a ₹80,000 developer productivity sponsorship and campus hiring booth. We've booked Friday 3:30 PM on your calendar link.",
            status="received",
            classification="interested",
            summary="Interested in ₹80,000 productivity partner tier & hiring booth. Call booked for Friday 3:30 PM.",
            suggested_reply="Looking forward to speaking on Friday! We'll have our past placement statistics ready.",
            classified_by_human=True,
            sent_at=now - timedelta(hours=18),
        ))

        # Target 14: MongoDB (Meeting Booked / Inbox Thread - Rohan)
        co_mongo = create_company("MongoDB", "mongodb.com", "Document Database", "https://mongodb.com")
        ct_mongo = create_contact(co_mongo, "DevRel Asia", "Campus Outreach Team", "community@mongodb.com")
        t_mongo = Target(
            campaign_id=camp_2026.id,
            company_id=co_mongo.id,
            owner_id=rohan.id,
            status="meeting_booked",
            tier="credits",
            priority="B",
            priority_score=4,
            ask_summary="MongoDB Atlas $500 Vouchers & Vector Search Workshop",
            ask_reasoning="MongoDB frequently conducts hands-on workshops and provides hackathon Atlas credits.",
            researched_at=now - timedelta(days=4),
            last_contacted_at=now - timedelta(hours=14),
        )
        db.add(t_mongo)
        db.commit()
        db.refresh(t_mongo)
        db.add(Message(
            target_id=t_mongo.id,
            contact_id=ct_mongo.id,
            direction="in",
            kind="reply",
            subject="Re: HackFest 2026 Database Sponsorship",
            body=(
                "Hello Rohan,\n\n"
                "Thanks for writing to us. We would be very interested in supporting HackFest 2026 with MongoDB Atlas credits "
                "and a virtual workshop on vector search for participants. Could you send us your event schedule and speaker slots?\n\n"
                "Best regards,\nMongoDB Community Team"
            ),
            status="received",
            classification="interested",
            summary="Interested in providing Atlas credits and technical workshop. Requested schedule details.",
            suggested_reply="Hi team, thanks! We've scheduled the workshop slot for Saturday 2 PM. Let's sync on a 15-min call: https://cal.com/hackfest2026/sponsor-chat",
            classified_by_human=False,
            sent_at=now - timedelta(hours=12),
        ))

        # Target 15: Razorpay (Contacted - Sparsh)
        co_razorpay = create_company("Razorpay", "razorpay.com", "Fintech / Payments", "https://razorpay.com")
        ct_razorpay = create_contact(co_razorpay, "Harshil Mathur", "Campus Relations", "harshil@razorpay.com")
        t_razorpay = Target(
            campaign_id=camp_2026.id,
            company_id=co_razorpay.id,
            owner_id=admin.id,
            status="contacted",
            tier="cash",
            priority="A",
            priority_score=5,
            ask_summary="₹50,000 Fintech Track Sponsorship",
            ask_reasoning="Razorpay is an active supporter of university hackathons in Bangalore and pan-India.",
            followup_count=0,
            next_followup_at=now + timedelta(days=2),
            last_contacted_at=now - timedelta(days=2),
            researched_at=now - timedelta(days=3),
        )
        db.add(t_razorpay)
        db.commit()
        db.refresh(t_razorpay)
        db.add(Message(
            target_id=t_razorpay.id,
            contact_id=ct_razorpay.id,
            direction="out",
            kind="initial",
            subject="Partnering with HackFest 2026: Fintech & Payments Track",
            body="Hi Harshil,\n\nWe're organizing HackFest 2026, bringing together 1,500+ builders across India...",
            status="sent",
            sent_at=now - timedelta(days=2),
        ))

        # Target 16: Cloudflare (Contacted - Rohan)
        co_cf = create_company("Cloudflare", "cloudflare.com", "Edge Computing & Security", "https://cloudflare.com")
        ct_cf = create_contact(co_cf, "Developer Advocacy", "Workers Developer Relations", "devrel@cloudflare.com")
        t_cf = Target(
            campaign_id=camp_2026.id,
            company_id=co_cf.id,
            owner_id=rohan.id,
            status="contacted",
            tier="credits",
            priority="B",
            priority_score=4,
            ask_summary="Cloudflare Workers AI & KV Access for 1,500 Hackers",
            ask_reasoning="Edge compute is widely used by students building serverless AI agents.",
            followup_count=0,
            next_followup_at=now + timedelta(days=3),
            last_contacted_at=now - timedelta(days=1),
            researched_at=now - timedelta(days=2),
        )
        db.add(t_cf)
        db.commit()

        # Target 17: Sentry (Contacted / Question in Inbox - Priya)
        co_sentry = create_company("Sentry", "sentry.io", "Application Monitoring", "https://sentry.io")
        ct_sentry = create_contact(co_sentry, "Open Source DevRel", "Student Evangelism", "partnerships@sentry.io")
        t_sentry = Target(
            campaign_id=camp_2026.id,
            company_id=co_sentry.id,
            owner_id=priya.id,
            status="contacted",
            tier="goodies",
            priority="B",
            priority_score=4,
            ask_summary="Sentry Swag Kits & Error Tracking Workshop",
            ask_reasoning="Sentry loves student builders and sends popular developer swags.",
            researched_at=now - timedelta(days=3),
            last_contacted_at=now - timedelta(hours=20),
        )
        db.add(t_sentry)
        db.commit()
        db.refresh(t_sentry)
        db.add(Message(
            target_id=t_sentry.id,
            contact_id=ct_sentry.id,
            direction="in",
            kind="reply",
            subject="Re: Sponsoring HackFest 2026 with Sentry",
            body=(
                "Hi Priya,\n\n"
                "Could you clarify the shipping deadline for swags and whether we can include our sticker packs in the hacker badge kits?\n\n"
                "Thanks,\nSentry Team"
            ),
            status="received",
            classification="question",
            summary="Asked about swag shipping deadlines and inclusion in hacker badge kits.",
            suggested_reply="Hi Sentry team! The shipping deadline is 10 days before the event, and yes, we'll include the stickers in badge kits.",
            classified_by_human=False,
            sent_at=now - timedelta(hours=10),
        ))

        # Target 18: Snowflake (Contacted / Follow-up Sent - Priya)
        co_snow = create_company("Snowflake", "snowflake.com", "Data Cloud", "https://snowflake.com")
        ct_snow = create_contact(co_snow, "Developer Programs", "Academic Partnerships", "academic@snowflake.com")
        t_snow = Target(
            campaign_id=camp_2026.id,
            company_id=co_snow.id,
            owner_id=priya.id,
            status="contacted",
            tier="cash",
            priority="B",
            priority_score=4,
            ask_summary="₹60,000 Big Data & Analytics Track",
            ask_reasoning="Snowflake actively engages university students building analytics and data science pipelines.",
            followup_count=1,
            next_followup_at=now + timedelta(days=4),
            last_contacted_at=now - timedelta(days=1),
            researched_at=now - timedelta(days=5),
        )
        db.add(t_snow)
        db.commit()

        # Target 19: Elastic (Contacted - Rohan)
        co_elastic = create_company("Elastic", "elastic.co", "Search & Observability", "https://elastic.co")
        ct_elastic = create_contact(co_elastic, "Community Team", "Global Developer Relations", "community@elastic.co")
        t_elastic = Target(
            campaign_id=camp_2026.id,
            company_id=co_elastic.id,
            owner_id=rohan.id,
            status="contacted",
            tier="cash",
            priority="B",
            priority_score=4,
            ask_summary="₹40,000 Search & AI Assistant Track",
            ask_reasoning="Elastic promotes Elasticsearch vector capabilities for generative search applications.",
            followup_count=0,
            next_followup_at=now + timedelta(days=3),
            last_contacted_at=now - timedelta(days=2),
            researched_at=now - timedelta(days=4),
        )
        db.add(t_elastic)
        db.commit()

        # Target 20: PostHog (Follow-up Overdue - Sparsh)
        co_posthog = create_company("PostHog", "posthog.com", "Product Analytics", "https://posthog.com")
        ct_posthog = create_contact(co_posthog, "James Hawkins", "CEO & Co-founder", "james@posthog.com")
        t_posthog = Target(
            campaign_id=camp_2026.id,
            company_id=co_posthog.id,
            owner_id=admin.id,
            status="follow_up",
            tier="credits",
            priority="A",
            priority_score=5,
            ask_summary="$20,000 Product Analytics Credits & Hedgehog Swag",
            ask_reasoning="PostHog is legendary among student builders for generous startup/student credits.",
            followup_count=1,
            last_contacted_at=now - timedelta(days=5),
            next_followup_at=now - timedelta(hours=3),  # Due now!
            researched_at=now - timedelta(days=6),
        )
        db.add(t_posthog)
        db.commit()

        # Target 21: Auth0 (Follow-up Overdue - Priya)
        co_auth0 = create_company("Auth0", "auth0.com", "Identity & Authentication", "https://auth0.com")
        ct_auth0 = create_contact(co_auth0, "Developer Relations", "Campus Ambassador Lead", "devrel@auth0.com")
        t_auth0 = Target(
            campaign_id=camp_2026.id,
            company_id=co_auth0.id,
            owner_id=priya.id,
            status="follow_up",
            tier="credits",
            priority="B",
            priority_score=4,
            ask_summary="Auth0 Developer Pro Tier for 1,500 Hackers",
            ask_reasoning="Authentication is required in virtually every hackathon project submission.",
            followup_count=1,
            last_contacted_at=now - timedelta(days=4),
            next_followup_at=now - timedelta(hours=1),  # Due now!
            researched_at=now - timedelta(days=5),
        )
        db.add(t_auth0)
        db.commit()

        # Target 22: Stripe (Approval Queue Draft - Priya)
        co_stripe = create_company("Stripe", "stripe.com", "Global Payments", "https://stripe.com")
        ct_stripe = create_contact(co_stripe, "Patrick Collison", "Developer Outreach", "patrick@stripe.com")
        create_fact(
            co_stripe, "past_sponsorship",
            "Stripe provides global payments infrastructure and supports student developer hackathons.",
            "https://stripe.com/about",
            "Stripe is a financial infrastructure platform for businesses."
        )
        t_stripe = Target(
            campaign_id=camp_2026.id,
            company_id=co_stripe.id,
            owner_id=priya.id,
            status="not_contacted",
            tier="cash",
            priority="A",
            priority_score=5,
            ask_summary="₹1,50,000 Global Fintech Track",
            ask_reasoning="Stripe's developer ethos matches our student hackathon audience perfectly.",
            researched_at=now - timedelta(hours=6),
        )
        db.add(t_stripe)
        db.commit()
        db.refresh(t_stripe)
        db.add(Message(
            target_id=t_stripe.id,
            contact_id=ct_stripe.id,
            direction="out",
            kind="initial",
            subject="HackFest 2026: Inviting Stripe as Global Fintech Track Sponsor",
            body=(
                "Hi Patrick,\n\n"
                "I am organizing HackFest 2026 on 12 November, bringing together 1,500 undergraduate builders from "
                "top Indian engineering colleges for a 24-hour hackathon. Our participants focus on developer infrastructure, "
                "commerce, and open-source tooling.\n\n"
                "Given Stripe's strong developer ethos, we would love to partner with your team as our Global Fintech Track "
                "Sponsor for ₹1,50,000. Hackers will be building checkout flows, subscription tooling, and agentic payment "
                "workflows. Your sponsorship directly funds hardware resources, participant travel grants, and cash prizes "
                "for the winning builds.\n\n"
                "Would you be open to a brief call this week to explore this? Our team can share attendee demographics and our full deck.\n\n"
                "Best regards,\nPriya Sharma\nHackFest 2026 Team\n\n"
                "To stop hearing from us, reply with 'unsubscribe'."
            ),
            status="draft",
            created_at=now - timedelta(hours=3),
        ))

        # Target 23: Kavach Systems (Approval Queue Draft - Sparsh)
        co_kavach = create_company("Kavach Systems", "kavach.in", "Cybersecurity", "https://kavach.in")
        ct_kavach = create_contact(co_kavach, "Priya Sharma", "Head of Growth", "priya@kavach.in")
        create_fact(
            co_kavach, "profile",
            "Kavach Systems provides enterprise cloud threat detection and defensive security solutions.",
            "https://kavach.in/about",
            "Enterprise threat intelligence and automated remediation."
        )
        t_kavach = Target(
            campaign_id=camp_2026.id,
            company_id=co_kavach.id,
            owner_id=admin.id,
            status="not_contacted",
            tier="cash",
            priority="B",
            priority_score=4,
            ask_summary="₹50,000 Cloud Security Track",
            ask_reasoning="Kavach supports student cybersecurity challenges and ethical hacking tracks.",
            researched_at=now - timedelta(hours=8),
        )
        db.add(t_kavach)
        db.commit()
        db.refresh(t_kavach)
        db.add(Message(
            target_id=t_kavach.id,
            contact_id=ct_kavach.id,
            direction="out",
            kind="initial",
            subject="Partnering with HackFest 2026: Security & Defense Track",
            body=(
                "Hi Priya,\n\n"
                "I am writing from the HackFest 2026 team. Next month, 1,500 student developers and security researchers "
                "from across India will gather on campus for our 24-hour national hackathon.\n\n"
                "Given Kavach Systems' focus on automated threat detection and defensive engineering, we would love to invite "
                "Kavach as our official Security & Cloud Defense Track Partner for ₹50,000. Teams in this track will work on "
                "vulnerability hunting, real-time log monitoring, and secure enclave deployments. Your partnership directly "
                "funds prizes and gives your engineering team a direct line to top student security talent.\n\n"
                "Could we schedule a quick 10-minute conversation this week to review our track details?\n\n"
                "Warm regards,\nAdmin Sparsh\nHackFest 2026 Team\n\n"
                "To stop hearing from us, reply with 'unsubscribe'."
            ),
            status="draft",
            created_at=now - timedelta(hours=4),
        ))

        # Target 24: Pinecone (Approval Queue Draft - Rohan)
        co_pinecone = create_company("Pinecone", "pinecone.io", "Vector Database", "https://pinecone.io")
        ct_pinecone = create_contact(co_pinecone, "Edo Liberty", "CEO & Founder", "partnerships@pinecone.io")
        t_pinecone = Target(
            campaign_id=camp_2026.id,
            company_id=co_pinecone.id,
            owner_id=rohan.id,
            status="not_contacted",
            tier="credits",
            priority="A",
            priority_score=5,
            ask_summary="Vector Database Compute Credits for 1,500 Hackers",
            ask_reasoning="Pinecone powers RAG and generative AI knowledge retrieval, a top theme in student hacks.",
            researched_at=now - timedelta(hours=5),
        )
        db.add(t_pinecone)
        db.commit()
        db.refresh(t_pinecone)
        db.add(Message(
            target_id=t_pinecone.id,
            contact_id=ct_pinecone.id,
            direction="out",
            kind="initial",
            subject="HackFest 2026: Vector Database Credits for 1,500 AI Hackers",
            body=(
                "Hi Edo,\n\n"
                "I am organizing HackFest 2026, where over 1,500 student developers will spend 24 hours building "
                "production-grade software. This year, the majority of submitted project proposals center on semantic "
                "retrieval, autonomous RAG pipelines, and persistent memory agents.\n\n"
                "We would love to feature Pinecone as our Official Vector Search Partner by providing index credits "
                "to our hacker teams. In return, we will showcase Pinecone during opening ceremonies, highlight your docs "
                "in our starter packs, and host a dedicated vector search office hour for builders.\n\n"
                "Would you be open to providing developer credits for our participants? I would be glad to share our "
                "attendee breakdown and event timeline.\n\n"
                "Warm regards,\nRohan Verma\nHackFest Team\n\n"
                "To stop hearing from us, reply with 'unsubscribe'."
            ),
            status="draft",
            created_at=now - timedelta(hours=2),
        ))

        # Target 25: Warp Terminal (Approval Queue Draft - Sparsh)
        co_warp = create_company("Warp", "warp.dev", "Developer Tools & AI Terminal", "https://warp.dev")
        ct_warp = create_contact(co_warp, "Zach Lloyd", "Founder & CEO", "zach@warp.dev")
        t_warp = Target(
            campaign_id=camp_2026.id,
            company_id=co_warp.id,
            owner_id=admin.id,
            status="not_contacted",
            tier="goodies",
            priority="B",
            priority_score=4,
            ask_summary="AI Terminal Swag Packs & 2 Mechanical Keyboards for Winners",
            ask_reasoning="Warp is iconic among student command-line power users and sends top tier swags.",
            researched_at=now - timedelta(hours=7),
        )
        db.add(t_warp)
        db.commit()
        db.refresh(t_warp)
        db.add(Message(
            target_id=t_warp.id,
            contact_id=ct_warp.id,
            direction="out",
            kind="initial",
            subject="HackFest 2026 x Warp: Swag Partner for 1,500 Terminal Hackers",
            body=(
                "Hi Zach,\n\n"
                "I am reaching out on behalf of HackFest 2026, an upcoming 24-hour national hackathon bringing together "
                "1,500 active student developers. Warp is widely used across our campus developer circles for fast "
                "command-line workflows and team debugging.\n\n"
                "We would love to have Warp join us as an Official Goodies & Swag Partner. We prepare curated welcome kits "
                "for all 1,500 builders at check-in, and we are also organizing a terminal speedrun challenge where "
                "custom mechanical keyboards and Warp merchandise would make ideal prizes. We distribute your items directly "
                "into hands, display Warp on our website, and credit your support.\n\n"
                "Would your team be open to sending swag for our attendees? I can share shipping details and our schedule.\n\n"
                "Best regards,\nAdmin Sparsh\nHackFest 2026 Team\n\n"
                "To stop hearing from us, reply with 'unsubscribe'."
            ),
            status="draft",
            created_at=now - timedelta(hours=3),
        ))

        # Target 26: CRED (Unclaimed - Sparsh/Priya/Rohan can claim)
        co_cred = create_company("CRED", "cred.club", "Fintech / Lifestyle", "https://cred.club")
        create_contact(co_cred, "Design & Engineering Relations", "Community Lead", "careers@cred.club")
        t_cred = Target(
            campaign_id=camp_2026.id,
            company_id=co_cred.id,
            owner_id=None,  # Unclaimed!
            status="not_contacted",
            tier="cash",
            priority="A",
            priority_score=5,
            ask_summary="₹1,00,000 UI/UX & Design Excellence Track",
            ask_reasoning="CRED values design perfection and sponsors student creative hackathons.",
            researched_at=None,
        )
        db.add(t_cred)

        # Target 27: Appwrite (Unclaimed)
        co_appwrite = create_company("Appwrite", "appwrite.io", "Open Source Backend", "https://appwrite.io")
        create_contact(co_appwrite, "Eldad A. Fux", "CEO", "eldad@appwrite.io")
        t_appwrite = Target(
            campaign_id=camp_2026.id,
            company_id=co_appwrite.id,
            owner_id=None,  # Unclaimed!
            status="not_contacted",
            tier="credits",
            priority="B",
            priority_score=4,
            ask_summary="Appwrite Cloud Pro for all hackathon participants",
            ask_reasoning="Popular Firebase alternative with heavy collegiate hackathon adoption.",
            researched_at=None,
        )
        db.add(t_appwrite)

        # Target 28: Replit (Unclaimed)
        co_replit = create_company("Replit", "replit.com", "Cloud IDE & Agents", "https://replit.com")
        create_contact(co_replit, "Amjad Masad", "CEO", "amjad@replit.com")
        t_replit = Target(
            campaign_id=camp_2026.id,
            company_id=co_replit.id,
            owner_id=None,  # Unclaimed!
            status="not_contacted",
            tier="credits",
            priority="A",
            priority_score=5,
            ask_summary="Replit Core Subscriptions & Agent Deployment Track",
            ask_reasoning="Replit accelerates hackathon velocity allowing zero-setup coding and instant deployments.",
            researched_at=None,
        )
        db.add(t_replit)

        # Target 29: CoinSwitch (Declined & Suppressed - Rohan)
        co_coinswitch = create_company("CoinSwitch", "coinswitch.co", "Crypto Exchange", "https://coinswitch.co")
        create_contact(co_coinswitch, "Brand Partnerships", "Marketing Lead", "partnerships@coinswitch.co")
        t_coinswitch = Target(
            campaign_id=camp_2026.id,
            company_id=co_coinswitch.id,
            owner_id=rohan.id,
            status="declined",
            tier="cash",
            priority="C",
            priority_score=2,
            last_contacted_at=now - timedelta(days=4),
            researched_at=now - timedelta(days=6),
        )
        db.add(t_coinswitch)

        # Target 30: Sticker Mule (Declined & Suppressed - Sparsh)
        co_sm = create_company("Sticker Mule", "stickermule.com", "Custom Stickers", "https://stickermule.com")
        t_sm = Target(
            campaign_id=camp_2026.id,
            company_id=co_sm.id,
            owner_id=admin.id,
            status="declined",
            tier="goodies",
            priority="C",
            priority_score=1,
            last_contacted_at=now - timedelta(days=5),
            researched_at=now - timedelta(days=7),
        )
        db.add(t_sm)

        # Target 31: Oracle Cloud (Closed - No Reply after 3 follow-ups - Priya)
        co_oracle = create_company("Oracle Cloud", "oracle.com", "Enterprise Cloud", "https://oracle.com")
        create_contact(co_oracle, "Oracle for Startups", "Academic Lead", "no-reply-sponsors@oracle.com")
        t_oracle = Target(
            campaign_id=camp_2026.id,
            company_id=co_oracle.id,
            owner_id=priya.id,
            status="closed_no_reply",
            tier="credits",
            priority="C",
            priority_score=2,
            followup_count=3,
            last_contacted_at=now - timedelta(days=12),
            researched_at=now - timedelta(days=14),
        )
        db.add(t_oracle)
        db.commit()

        # -------------------------------------------------------------
        # 9. Historical Memory (HackFest 2025 & HackFest 2024)
        # -------------------------------------------------------------

        # HackFest 2025: GitHub (₹1,00,000 cash)
        t_gh_2025 = Target(
            campaign_id=camp_2025.id,
            company_id=co_github.id,
            owner_id=admin.id,
            status="secured",
            tier="cash",
            priority="A",
            priority_score=5,
            ask_summary="₹1,00,000 Education Partner",
            ask_reasoning="GitHub Education Student Developer Pack sponsorship.",
            last_contacted_at=now - timedelta(days=360),
            researched_at=now - timedelta(days=365),
        )
        db.add(t_gh_2025)
        db.commit()
        db.refresh(t_gh_2025)
        db.add(Outcome(
            target_id=t_gh_2025.id,
            kind="cash",
            amount_inr=100000,
            description="GitHub Education ₹1,00,000 sponsorship for HackFest 2025.",
            confirmed_by=admin.id,
            confirmed_at=now - timedelta(days=355),
        ))

        # HackFest 2025: JetBrains (20 licenses)
        co_jetbrains = create_company("JetBrains", "jetbrains.com", "Developer IDEs", "https://jetbrains.com")
        t_jb_2025 = Target(
            campaign_id=camp_2025.id,
            company_id=co_jetbrains.id,
            owner_id=priya.id,
            status="secured",
            tier="goodies",
            priority="B",
            priority_score=4,
            ask_summary="20 All Products Pack Licenses",
            ask_reasoning="JetBrains provides student licenses and licenses for hackathon winners.",
            last_contacted_at=now - timedelta(days=350),
            researched_at=now - timedelta(days=355),
        )
        db.add(t_jb_2025)
        db.commit()
        db.refresh(t_jb_2025)
        db.add(Outcome(
            target_id=t_jb_2025.id,
            kind="goodies",
            amount_inr=None,
            description="20 JetBrains All Products Pack 1-year complimentary licenses for top teams.",
            confirmed_by=priya.id,
            confirmed_at=now - timedelta(days=345),
        ))

        # HackFest 2025: DigitalOcean ($5,000 credits)
        t_do_2025 = Target(
            campaign_id=camp_2025.id,
            company_id=co_do.id,
            owner_id=admin.id,
            status="secured",
            tier="credits",
            priority="A",
            priority_score=5,
            ask_summary="$5,000 Droplet Credits",
            ask_reasoning="DigitalOcean Hatch program sponsored the cloud infrastructure track.",
            last_contacted_at=now - timedelta(days=340),
            researched_at=now - timedelta(days=345),
        )
        db.add(t_do_2025)
        db.commit()
        db.refresh(t_do_2025)
        db.add(Outcome(
            target_id=t_do_2025.id,
            kind="credits",
            amount_inr=None,
            description="$5,000 in cloud credits distributed to top 25 finalists.",
            confirmed_by=admin.id,
            confirmed_at=now - timedelta(days=335),
        ))

        # HackFest 2025: GeeksforGeeks (₹30,000 cash)
        co_gfg = create_company("GeeksforGeeks", "geeksforgeeks.org", "EdTech / Coding", "https://geeksforgeeks.org")
        t_gfg_2025 = Target(
            campaign_id=camp_2025.id,
            company_id=co_gfg.id,
            owner_id=rohan.id,
            status="secured",
            tier="cash",
            priority="B",
            priority_score=4,
            ask_summary="₹30,000 Problem Solving Track",
            ask_reasoning="GFG sponsored the algorithmic puzzle track with cash rewards.",
            last_contacted_at=now - timedelta(days=330),
            researched_at=now - timedelta(days=335),
        )
        db.add(t_gfg_2025)
        db.commit()
        db.refresh(t_gfg_2025)
        db.add(Outcome(
            target_id=t_gfg_2025.id,
            kind="cash",
            amount_inr=30000,
            description="GeeksforGeeks ₹30,000 prize track sponsorship.",
            confirmed_by=rohan.id,
            confirmed_at=now - timedelta(days=325),
        ))

        # HackFest 2024: AWS Startups ($10,000 activate credits)
        co_aws = create_company("AWS Startups", "aws.amazon.com", "Cloud Computing", "https://aws.amazon.com")
        t_aws_2024 = Target(
            campaign_id=camp_2024.id,
            company_id=co_aws.id,
            owner_id=admin.id,
            status="secured",
            tier="credits",
            priority="A",
            priority_score=5,
            ask_summary="$10,000 AWS Activate Credits",
            ask_reasoning="AWS cloud credits for winning projects to continue scaling.",
            last_contacted_at=now - timedelta(days=720),
            researched_at=now - timedelta(days=725),
        )
        db.add(t_aws_2024)
        db.commit()
        db.refresh(t_aws_2024)
        db.add(Outcome(
            target_id=t_aws_2024.id,
            kind="credits",
            amount_inr=None,
            description="$10,000 in AWS Activate credits awarded to grand prize winners.",
            confirmed_by=admin.id,
            confirmed_at=now - timedelta(days=715),
        ))

        # HackFest 2024: Twilio (₹50,000 cash)
        co_twilio = create_company("Twilio", "twilio.com", "Communications APIs", "https://twilio.com")
        t_twilio_2024 = Target(
            campaign_id=camp_2024.id,
            company_id=co_twilio.id,
            owner_id=priya.id,
            status="secured",
            tier="cash",
            priority="A",
            priority_score=5,
            ask_summary="₹50,000 SMS & Voice Track",
            ask_reasoning="Twilio sponsored the best communications hack at HackFest 2024.",
            last_contacted_at=now - timedelta(days=710),
            researched_at=now - timedelta(days=715),
        )
        db.add(t_twilio_2024)
        db.commit()
        db.refresh(t_twilio_2024)
        db.add(Outcome(
            target_id=t_twilio_2024.id,
            kind="cash",
            amount_inr=50000,
            description="Twilio ₹50,000 track partner sponsorship.",
            confirmed_by=priya.id,
            confirmed_at=now - timedelta(days=705),
        ))

        # HackFest 2024: Notion (Goodies & Free Plus)
        co_notion = create_company("Notion", "notion.so", "Productivity Workspace", "https://notion.so")
        t_notion_2024 = Target(
            campaign_id=camp_2024.id,
            company_id=co_notion.id,
            owner_id=priya.id,
            status="secured",
            tier="goodies",
            priority="B",
            priority_score=4,
            ask_summary="6 Months Free Notion Plus for All Participants",
            ask_reasoning="Notion workspace vouchers for all hacking teams.",
            last_contacted_at=now - timedelta(days=700),
            researched_at=now - timedelta(days=705),
        )
        db.add(t_notion_2024)
        db.commit()
        db.refresh(t_notion_2024)
        db.add(Outcome(
            target_id=t_notion_2024.id,
            kind="goodies",
            amount_inr=None,
            description="Notion Plus coupon codes distributed to all 900 hackathon participants.",
            confirmed_by=priya.id,
            confirmed_at=now - timedelta(days=695),
        ))

        # -------------------------------------------------------------
        # 10. Audit Trail: Comprehensive Chronological History
        # -------------------------------------------------------------
        audit_events = [
            (now - timedelta(days=16), admin.id, "login", "users", str(admin.id), "Admin Sparsh logged in"),
            (now - timedelta(days=16), admin.id, "create_campaign", "campaigns", str(camp_2026.id), "Created campaign HackFest 2026 with ₹5,00,000 target"),
            (now - timedelta(days=15), admin.id, "upload_brochure", "brochures", str(b_cash.id), "Uploaded Corporate Sponsorship Deck for cash tier"),
            (now - timedelta(days=15), admin.id, "csv_import", "targets", None, "Imported 31 target tech companies from master outreach spreadsheet"),
            (now - timedelta(days=14), priya.id, "login", "users", str(priya.id), "Priya Sharma logged in"),
            (now - timedelta(days=14), priya.id, "claim_target", "targets", str(t_poly.id), "Priya claimed Polygon (Web3 Track)"),
            (now - timedelta(days=14), priya.id, "claim_target", "targets", str(t_docker.id), "Priya claimed Docker (Container Track)"),
            (now - timedelta(days=13), rohan.id, "login", "users", str(rohan.id), "Rohan Verma logged in"),
            (now - timedelta(days=13), rohan.id, "claim_target", "targets", str(t_devzero.id), "Rohan claimed DevZero (Swag)"),
            (now - timedelta(days=13), rohan.id, "claim_target", "targets", str(t_redbull.id), "Rohan claimed Red Bull (Beverage)"),
            (now - timedelta(days=12), admin.id, "claim_target", "targets", str(t_postman.id), "Admin Sparsh claimed Postman"),
            (now - timedelta(days=12), admin.id, "claim_target", "targets", str(t_nvidia.id), "Admin Sparsh claimed NVIDIA Inception"),
            (now - timedelta(days=11), admin.id, "research_company", "companies", str(co_postman.id), "Retrieved verified company facts for Postman via Tavily"),
            (now - timedelta(days=10), priya.id, "research_company", "companies", str(co_poly.id), "Retrieved verified facts for Polygon via Tavily"),
            (now - timedelta(days=10), admin.id, "generate_draft", "messages", None, "Generated personalized outreach draft for Postman via Gemini 1.5 Flash"),
            (now - timedelta(days=8), admin.id, "approve_message", "messages", None, "Approved outreach message for Postman (abhinav@postman.com)"),
            (now - timedelta(days=8), admin.id, "send_email", "messages", None, "Mailer sent initial outreach email to abhinav@postman.com"),
            (now - timedelta(days=7), priya.id, "approve_message", "messages", None, "Approved outreach message for Polygon"),
            (now - timedelta(days=7), priya.id, "send_email", "messages", None, "Mailer sent initial outreach email to sandeep@polygon.technology"),
            (now - timedelta(days=6), rohan.id, "approve_message", "messages", None, "Approved goodies ask for DevZero"),
            (now - timedelta(days=6), rohan.id, "send_email", "messages", None, "Mailer sent goodies proposal to ayush@devzero.io"),
            (now - timedelta(days=5), admin.id, "inbound_reply", "messages", None, "Inbound email from abhinav@postman.com classified as interested"),
            (now - timedelta(days=4), admin.id, "inbound_reply", "messages", None, "Inbound email from community@mongodb.com classified as interested"),
            (now - timedelta(days=4), rohan.id, "suppress_contact", "suppression", None, "Suppressed domain coinswitch.co after sponsorship freeze notice"),
            (now - timedelta(days=3), admin.id, "confirm_outcome", "outcomes", None, "Confirmed ₹75,000 cash outcome for Postman"),
            (now - timedelta(days=2), priya.id, "confirm_outcome", "outcomes", None, "Confirmed ₹1,20,000 cash outcome for Polygon"),
            (now - timedelta(days=2), admin.id, "confirm_outcome", "outcomes", None, "Confirmed ₹1,50,000 cash outcome for NVIDIA Inception"),
            (now - timedelta(days=1), priya.id, "confirm_outcome", "outcomes", None, "Confirmed ₹50,000 cash outcome for Docker"),
            (now - timedelta(days=1), rohan.id, "confirm_outcome", "outcomes", None, "Confirmed ₹1,00,000 cash outcome for Vercel"),
            (now - timedelta(days=1), rohan.id, "confirm_outcome", "outcomes", None, "Confirmed goodies outcome for DevZero (200 T-shirts)"),
            (now - timedelta(days=1), rohan.id, "confirm_outcome", "outcomes", None, "Confirmed goodies outcome for Red Bull (500 cans)"),
            (now - timedelta(hours=8), admin.id, "generate_draft", "messages", None, "Generated cybersecurity draft for Kavach Systems"),
            (now - timedelta(hours=6), priya.id, "generate_draft", "messages", None, "Generated fintech draft for Stripe"),
            (now - timedelta(hours=4), rohan.id, "generate_draft", "messages", None, "Generated vector database draft for Pinecone"),
            (now - timedelta(hours=2), admin.id, "generate_draft", "messages", None, "Generated AI terminal draft for Warp"),
            (now - timedelta(hours=1), admin.id, "export_csv", "targets", None, "Admin Sparsh exported active campaign targets to CSV"),
        ]

        for at, uid, action, entity, eid, detail in audit_events:
            audit_row = AuditLog(
                at=at,
                user_id=uid,
                action=action,
                entity=entity,
                entity_id=eid,
                detail=detail,
            )
            db.add(audit_row)
        db.commit()

        print(
            "Successfully seeded rich, authentic production data with 31 targets, "
            "11 secured outcomes (₹4,95,000 cash + swag + credits), 4 approval queue drafts, "
            "7 inbox threads, 4 outreach templates, 3 PDF brochures, and 36 audit log entries!"
        )
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_data()
