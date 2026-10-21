"""Email reply classifier checking headers and LLM structured output (SEC-24, SEC-25, R6)."""

from app.llm import ReplyAnalysis, llm_client


def is_bounce(headers: dict[str, str], sender: str, subject: str) -> bool:
    """Check headers, sender, and subject for email bounce indicators."""
    sender_lower = sender.lower()
    subject_lower = subject.lower()

    if "mailer-daemon@" in sender_lower or "postmaster@" in sender_lower:
        return True

    bounce_subjects = (
        "delivery status notification",
        "mail delivery failed",
        "failure notice",
        "undeliverable:",
        "undelivered mail returned to sender",
    )
    if any(bs in subject_lower for bs in bounce_subjects):
        return True

    content_type = headers.get("content-type", "").lower()
    if "report-type=delivery-status" in content_type or "multipart/report" in content_type:
        return True

    if "x-failed-recipients" in headers:
        return True

    return False


def is_auto_reply(headers: dict[str, str], subject: str) -> bool:
    """Check headers and subject for automatic responder indicators."""
    auto_submitted = headers.get("auto-submitted", "").lower().strip()
    if auto_submitted and auto_submitted != "no":
        return True

    if headers.get("x-autoreply", "").lower().strip() == "yes":
        return True

    precedence = headers.get("precedence", "").lower().strip()
    if precedence in ("auto_reply", "bulk", "junk"):
        return True

    subject_lower = subject.lower().strip()
    auto_prefixes = (
        "auto:",
        "automatic reply:",
        "out of office:",
        "out of office auto-reply:",
        "autoreply:",
    )
    if any(subject_lower.startswith(prefix) for prefix in auto_prefixes):
        return True

    return False


def strip_quoted_text(body: str) -> str:
    """Remove email reply quotes and signature blocks."""
    lines = body.splitlines()
    cleaned_lines: list[str] = []
    quote_markers = (
        "-----original message-----",
        "-----original message follow-----",
        "________________________________",
    )
    for line in lines:
        stripped = line.strip().lower()
        if any(marker in stripped for marker in quote_markers):
            break
        if stripped.startswith("on ") and "wrote:" in stripped:
            break
        if stripped.startswith(">"):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def classify_reply(
    headers: dict[str, str],
    sender: str,
    subject: str,
    body: str,
    company_name: str,
    campaign_info: dict[str, str],
) -> ReplyAnalysis:
    """Classify incoming email via header checks first, falling back to LLM."""
    headers_lower = {k.lower(): v for k, v in headers.items()}

    # 1. Header bounce check (no LLM call)
    if is_bounce(headers_lower, sender, subject):
        return ReplyAnalysis(
            classification="bounce",
            summary="Delivery failure notice (bounce).",
            suggested_reply="",
        )

    # 2. Header auto-reply check (no LLM call)
    if is_auto_reply(headers_lower, subject):
        return ReplyAnalysis(
            classification="auto_reply",
            summary="Automated out-of-office or auto-reply.",
            suggested_reply="",
        )

    # 3. Clean body and classify with LLM
    cleaned_body = strip_quoted_text(body)
    return llm_client.classify_and_suggest_reply(
        reply_text=cleaned_body or body,
        subject=subject,
        company_name=company_name,
        campaign_info=campaign_info,
    )
