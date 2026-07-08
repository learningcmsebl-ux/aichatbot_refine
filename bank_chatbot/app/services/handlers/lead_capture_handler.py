"""Lead capture and status-query handler for the chatbot."""

from __future__ import annotations

import json
import logging
import re
import time
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException

from app.models.auth import EmployeeUser
from app.models.lead import LeadProductType
from app.models.leads import LeadCreateRequest

logger = logging.getLogger(__name__)

LEAD_CAPTURE_TTL = 3600

CANCEL_WORDS = {"cancel", "stop", "nevermind", "never mind", "abort", "quit"}
RESTART_WORDS = {"start again", "start over", "restart", "reset"}
CONFIRM_YES = {"yes", "y", "confirm", "submit", "ok", "okay", "proceed", "correct"}
CONFIRM_NO = {"no", "n", "change", "edit", "fix"}

CREATE_INTENT_PHRASES = [
    "create a lead",
    "create lead",
    "generate customer lead",
    "generate a lead",
    "generate lead",
    "submit a lead",
    "submit lead",
    "submit a loan lead",
    "submit loan lead",
    "submit customer lead",
    "register customer lead",
    "new customer lead",
    "customer interested in",
    "refer a customer",
    "refer customer",
]

# Product/fee/rate questions that mention "interested in" but are not lead capture.
NON_LEAD_KEYWORDS = [
    "rate",
    "rates",
    "fee",
    "fees",
    "annual fee",
    "interest rate",
    "interest rates",
    "eligibility",
    "how much",
    "charges",
    "charge",
    "limit",
    "policy",
    "document",
    "documents",
    "required documents",
    "what is the",
    "what are the",
    "tell me about",
    "where is",
    "nearest atm",
    "branch location",
    "phone number",
]

BANKING_ESCAPE_PATTERNS = [
    "what is the",
    "what are the",
    "how much",
    "annual fee",
    "interest rate",
    "where is",
    "nearest atm",
    "branch location",
    "phone number of",
    "fee for",
    "charges for",
    "eligibility for",
    "tell me about",
    "credit card fee",
    "loan rate",
    "loan rates",
]

STATUS_MY_LEADS = [
    "show my submitted leads",
    "show my leads",
    "my submitted leads",
    "list my leads",
    "my leads",
]

STATUS_LEAD_DETAIL = [
    "what happened to lead",
    "status of lead",
    "show lead status",
    "lead status for",
    "track lead",
]

STATUS_MY_FEEDBACK = [
    "show feedback for my leads",
    "my lead feedback",
    "feedback on my leads",
]

PRODUCT_HINTS: List[tuple[str, LeadProductType]] = [
    ("credit card", LeadProductType.CREDIT_CARD),
    ("personal loan", LeadProductType.PERSONAL_LOAN),
    ("home loan", LeadProductType.HOME_LOAN),
    ("auto loan", LeadProductType.AUTO_LOAN),
    ("car loan", LeadProductType.AUTO_LOAN),
    ("sme loan", LeadProductType.SME_LOAN),
    ("business loan", LeadProductType.SME_LOAN),
    ("deposit account", LeadProductType.DEPOSIT_ACCOUNT),
    ("dps", LeadProductType.DPS),
    ("fdr", LeadProductType.FDR),
    ("debit card", LeadProductType.DEBIT_CARD),
    ("payroll banking", LeadProductType.PAYROLL_BANKING),
    ("payroll", LeadProductType.PAYROLL_BANKING),
]

COLLECTION_FIELDS = [
    ("customer_name", "What is the customer's full name?"),
    ("customer_mobile", "What is the customer's mobile number? (Bangladesh format, e.g. 017XXXXXXXX)"),
    (
        "customer_email",
        "What is the customer's email address? (type 'skip' if not available)",
    ),
    (
        "preferred_branch",
        "Which branch is preferred for follow-up? (type 'skip' if unknown)",
    ),
    (
        "preferred_contact_time",
        "Preferred contact time? (e.g. morning, 2-4 PM — or 'skip')",
    ),
    (
        "customer_location",
        "Customer location / area? (or 'skip')",
    ),
    (
        "remarks",
        "Any additional remarks about this lead? (or 'skip')",
    ),
]

LEAD_REF_RE = re.compile(r"\b(LD-?\d{6})\b", re.IGNORECASE)
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
MOBILE_DIGITS_RE = re.compile(r"^01[3-9]\d{8}$")


class LeadStatusIntent(str, Enum):
    MY_LEADS = "my_leads"
    LEAD_DETAIL = "lead_detail"
    MY_FEEDBACK = "my_feedback"


class LeadCaptureHandler:
    """Guided lead capture + employee lead status queries."""

    def __init__(self, redis_cache=None):
        self.redis_cache = redis_cache
        self._local_state: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------ intents

    def _is_product_info_query(self, q: str) -> bool:
        """True when the message looks like a fee/rate/eligibility question, not lead capture."""
        if "lead" in q:
            return False
        return any(kw in q for kw in NON_LEAD_KEYWORDS)

    def _looks_like_banking_question(self, query: str) -> bool:
        q = query.lower().strip()
        if q in CANCEL_WORDS or any(w in q for w in RESTART_WORDS):
            return False
        if "?" in query:
            return True
        return any(p in q for p in BANKING_ESCAPE_PATTERNS)

    def detect_create_intent(self, query: str) -> Optional[LeadProductType]:
        q = query.lower().strip()
        if not any(p in q for p in CREATE_INTENT_PHRASES):
            return None
        if self._is_product_info_query(q):
            return None
        if "customer interested in" in q and "lead" not in q:
            return None
        for hint, product in PRODUCT_HINTS:
            if hint in q:
                return product
        return LeadProductType.OTHER

    def detect_status_intent(self, query: str) -> Optional[LeadStatusIntent]:
        q = query.lower().strip()
        if any(p in q for p in STATUS_MY_FEEDBACK):
            return LeadStatusIntent.MY_FEEDBACK
        if LEAD_REF_RE.search(q) and any(p in q for p in STATUS_LEAD_DETAIL):
            return LeadStatusIntent.LEAD_DETAIL
        if LEAD_REF_RE.search(q) and "status" in q:
            return LeadStatusIntent.LEAD_DETAIL
        if any(p in q for p in STATUS_MY_LEADS):
            return LeadStatusIntent.MY_LEADS
        if any(p in q for p in STATUS_LEAD_DETAIL):
            return LeadStatusIntent.LEAD_DETAIL
        return None

    def extract_lead_reference(self, query: str) -> Optional[str]:
        m = LEAD_REF_RE.search(query)
        if not m:
            return None
        raw = m.group(1).upper().replace("LD", "").strip("-")
        digits = re.sub(r"\D", "", raw)
        if digits:
            return f"LD-{int(digits):06d}"
        return m.group(1).upper()

    # ------------------------------------------------------------------ state

    def _state_key(self, conversation_key: str) -> str:
        return f"lead_capture:{conversation_key}"

    async def get_state(self, conversation_key: str) -> Optional[Dict[str, Any]]:
        key = self._state_key(conversation_key)
        if self.redis_cache and self.redis_cache.client:
            try:
                raw = await self.redis_cache.client.get(key)
                if raw:
                    return json.loads(raw)
            except Exception as exc:
                logger.warning("[LEAD] Redis get failed: %s", exc)
        local = self._local_state.get(conversation_key)
        if local and local.get("expires_at", 0) > time.time():
            return local.get("state")
        return None

    async def set_state(self, conversation_key: str, state: Dict[str, Any]) -> None:
        key = self._state_key(conversation_key)
        payload = json.dumps(state)
        if self.redis_cache and self.redis_cache.client:
            try:
                await self.redis_cache.client.setex(key, LEAD_CAPTURE_TTL, payload)
            except Exception as exc:
                logger.warning("[LEAD] Redis set failed: %s", exc)
        self._local_state[conversation_key] = {
            "state": state,
            "expires_at": time.time() + LEAD_CAPTURE_TTL,
        }

    async def clear_state(self, conversation_key: str) -> None:
        key = self._state_key(conversation_key)
        if self.redis_cache and self.redis_cache.client:
            try:
                await self.redis_cache.client.delete(key)
            except Exception as exc:
                logger.warning("[LEAD] Redis clear failed: %s", exc)
        self._local_state.pop(conversation_key, None)

    # ------------------------------------------------------------------ main

    async def handle_turn(
        self,
        query: str,
        conversation_key: str,
        session_id: str,
        employee: Optional[EmployeeUser],
    ) -> Optional[str]:
        if employee is None or employee.username == "anonymous":
            if self.detect_create_intent(query) or self.detect_status_intent(query):
                return "Please sign in to create or view customer leads."
            return None

        state = await self.get_state(conversation_key)
        if state:
            result = await self._continue_capture(
                query, conversation_key, session_id, employee, state
            )
            if result is None:
                return None
            return result

        status_intent = self.detect_status_intent(query)
        if status_intent:
            return self._handle_status_query(query, employee, status_intent)

        product = self.detect_create_intent(query)
        if product:
            return await self._start_capture(conversation_key, session_id, employee, product)

        return None

    async def _start_capture(
        self,
        conversation_key: str,
        session_id: str,
        employee: EmployeeUser,
        product: LeadProductType,
    ) -> str:
        state = {
            "phase": "collect",
            "field_index": 0,
            "data": {"product_type": product.value},
            "session_id": session_id,
        }
        await self.set_state(conversation_key, state)
        product_label = LeadProductType.label_for(product.value)
        emp_line = self._employee_summary(employee)
        intro = (
            f"I'll help you submit a {product_label} lead.\n\n"
            f"Your details (auto-filled): {emp_line}\n\n"
            "You can type 'cancel' at any time to stop, or 'start again' to restart.\n\n"
        )
        return intro + COLLECTION_FIELDS[0][1]

    async def _continue_capture(
        self,
        query: str,
        conversation_key: str,
        session_id: str,
        employee: EmployeeUser,
        state: Dict[str, Any],
    ) -> Optional[str]:
        q = query.strip()
        q_lower = q.lower()

        if any(w in q_lower for w in CANCEL_WORDS):
            await self.clear_state(conversation_key)
            return "Lead submission cancelled. How else can I help you?"

        if any(w in q_lower for w in RESTART_WORDS):
            product = LeadProductType(state["data"].get("product_type", LeadProductType.OTHER.value))
            return await self._start_capture(conversation_key, session_id, employee, product)

        if state.get("phase") == "collect" and self._looks_like_banking_question(q):
            await self.clear_state(conversation_key)
            return None

        if state.get("phase") == "confirm":
            return await self._handle_confirmation(q_lower, conversation_key, session_id, employee, state)

        return await self._collect_field(q, conversation_key, session_id, employee, state)

    async def _collect_field(
        self,
        query: str,
        conversation_key: str,
        session_id: str,
        employee: EmployeeUser,
        state: Dict[str, Any],
    ) -> str:
        idx = state.get("field_index", 0)
        if idx >= len(COLLECTION_FIELDS):
            state["phase"] = "confirm"
            await self.set_state(conversation_key, state)
            return self._build_confirmation(employee, state["data"])

        field_name, _ = COLLECTION_FIELDS[idx]
        value, error = self._parse_field(field_name, query)
        if error:
            return f"{error}\n\n{COLLECTION_FIELDS[idx][1]}"

        if value is not None:
            state["data"][field_name] = value

        state["field_index"] = idx + 1
        if state["field_index"] >= len(COLLECTION_FIELDS):
            state["phase"] = "confirm"
            await self.set_state(conversation_key, state)
            return self._build_confirmation(employee, state["data"])

        await self.set_state(conversation_key, state)
        _, next_q = COLLECTION_FIELDS[state["field_index"]]
        return next_q

    def _parse_field(self, field_name: str, query: str) -> tuple[Optional[str], Optional[str]]:
        q = query.strip()
        if q.lower() in {"skip", "none", "n/a", "na", "-"}:
            if field_name in {"customer_name", "customer_mobile"}:
                return None, "This field is required and cannot be skipped."
            return None, None

        if field_name == "customer_name":
            if len(q) < 2:
                return None, "Please enter the customer's full name (at least 2 characters)."
            return q, None

        if field_name == "customer_mobile":
            digits = re.sub(r"\D", "", q)
            if digits.startswith("880"):
                digits = "0" + digits[3:]
            elif len(digits) == 10 and digits[0] == "1":
                digits = "0" + digits
            if not MOBILE_DIGITS_RE.match(digits):
                return None, "Please enter a valid Bangladesh mobile number (e.g. 01712345678)."
            return digits, None

        if field_name == "customer_email":
            if not EMAIL_RE.match(q):
                return None, "Please enter a valid email address, or type 'skip'."
            return q, None

        return q, None

    def _build_confirmation(self, employee: EmployeeUser, data: Dict[str, Any]) -> str:
        product = LeadProductType.label_for(data.get("product_type", "other"))
        lines = [
            "Please review the lead details before submission:",
            "",
            f"Product: {product}",
            f"Customer name: {data.get('customer_name', '—')}",
            f"Mobile: {data.get('customer_mobile') or '—'}",
            f"Email: {data.get('customer_email') or '—'}",
            f"Preferred branch: {data.get('preferred_branch') or '—'}",
            f"Contact time: {data.get('preferred_contact_time') or '—'}",
            f"Location: {data.get('customer_location') or '—'}",
            f"Remarks: {data.get('remarks') or '—'}",
            "",
            f"Referrer: {self._employee_summary(employee)}",
            "",
            "Reply 'yes' to submit, 'no' to cancel, or 'start again' to re-enter details.",
        ]
        return "\n".join(lines)

    async def _handle_confirmation(
        self,
        q_lower: str,
        conversation_key: str,
        session_id: str,
        employee: EmployeeUser,
        state: Dict[str, Any],
    ) -> str:
        if q_lower in CONFIRM_NO or q_lower.startswith("no "):
            await self.clear_state(conversation_key)
            return "Lead submission cancelled. How else can I help you?"

        if q_lower not in CONFIRM_YES and not any(q_lower.startswith(y + " ") for y in CONFIRM_YES):
            return (
                self._build_confirmation(employee, state["data"])
                + "\n\nPlease reply 'yes' to submit or 'cancel' to stop."
            )

        data = state["data"]
        mobile = data.get("customer_mobile")
        email = data.get("customer_email")
        if not mobile and not email:
            state["phase"] = "collect"
            state["field_index"] = 1
            await self.set_state(conversation_key, state)
            return "At least a mobile number or email is required. What is the customer's mobile number?"

        from app.database.postgres import get_db
        from app.services import lead_service as svc

        db = get_db()
        if not db:
            await self.clear_state(conversation_key)
            return "Sorry, the database is unavailable. Please try again later."

        try:
            chat_uuid = self._resolve_session_uuid(db, session_id, employee.username)
            req = LeadCreateRequest(
                customer_name=data["customer_name"],
                customer_mobile=mobile,
                customer_email=email,
                preferred_contact_time=data.get("preferred_contact_time"),
                customer_location=data.get("customer_location"),
                preferred_branch=data.get("preferred_branch"),
                product_type=LeadProductType(data["product_type"]),
                remarks=data.get("remarks"),
                chat_session_id=chat_uuid,
            )
            lead = svc.create_lead(db, employee, req)
            await self.clear_state(conversation_key)
            product_label = LeadProductType.label_for(lead.product_type)
            return (
                f"Lead submitted successfully. Your Lead ID is {lead.lead_reference_no}.\n\n"
                f"Product: {product_label}\n"
                f"Customer: {data['customer_name']}\n"
                f"Status: Submitted\n\n"
                "Our sales team will follow up. You can ask \"show my submitted leads\" anytime to check status."
            )
        except Exception as exc:
            if isinstance(exc, HTTPException):
                await self.clear_state(conversation_key)
                return f"Could not submit lead: {exc.detail}"
            logger.error("[LEAD] Submit failed: %s", exc, exc_info=True)
            await self.clear_state(conversation_key)
            return "Sorry, there was an error saving the lead. Please try again or contact support."
        finally:
            db.close()

    def _handle_status_query(
        self,
        query: str,
        employee: EmployeeUser,
        intent: LeadStatusIntent,
    ) -> str:
        from app.database.postgres import get_db
        from app.services import lead_service as svc

        db = get_db()
        if not db:
            return "Sorry, the database is unavailable. Please try again later."

        try:
            roles = svc.get_user_roles(db, employee)
            if intent == LeadStatusIntent.MY_LEADS:
                rows, total = svc.list_my_submitted(db, employee, limit=10)
                if not rows:
                    return "You have not submitted any leads yet."
                lines = [f"You have {total} submitted lead(s). Recent:\n"]
                for lead in rows:
                    summary = svc.to_summary(lead, mask_pii=True)
                    lines.append(
                        f"- {summary.lead_reference_no} | {summary.product_type_label} | "
                        f"{summary.customer_name} | Status: {summary.status_label}"
                    )
                lines.append("\nAsk \"status of lead LD-000123\" for details on a specific lead.")
                return "\n".join(lines)

            if intent == LeadStatusIntent.LEAD_DETAIL:
                ref = self.extract_lead_reference(query)
                if not ref:
                    return "Please include a Lead ID, e.g. \"status of lead LD-000001\"."
                lead = svc.get_lead_by_reference(db, ref)
                if not lead:
                    return f"I could not find lead {ref}."
                svc.require_lead_access(employee, lead, roles)
                detail = svc.to_detail(lead, mask_pii=True)
                history = svc.get_status_history(db, employee, lead, roles)
                lines = [
                    f"Lead {detail.lead_reference_no}",
                    f"- Product: {detail.product_type_label}",
                    f"- Customer: {detail.customer_name}",
                    f"- Mobile: {detail.customer_mobile or '—'}",
                    f"- Email: {detail.customer_email or '—'}",
                    f"- Status: {detail.status_label}",
                    f"- Branch: {detail.preferred_branch or '—'}",
                    f"- Submitted: {detail.created_at.strftime('%d %b %Y')}",
                ]
                if history:
                    lines.append("\nStatus history:")
                    for h in history[:5]:
                        old = h.old_status or "—"
                        lines.append(
                            f"- {h.changed_at.strftime('%d %b %Y')}: {old} → {h.new_status}"
                        )
                return "\n".join(lines)

            if intent == LeadStatusIntent.MY_FEEDBACK:
                rows, _ = svc.list_my_submitted(db, employee, limit=20)
                if not rows:
                    return "You have no submitted leads yet."
                lines = ["Feedback on your leads:\n"]
                found = False
                for lead in rows:
                    feedback = svc.get_feedback_for_lead(db, employee, lead, roles)
                    if not feedback:
                        continue
                    found = True
                    lines.append(f"\n{lead.lead_reference_no} ({lead.customer_name}):")
                    for fb in feedback[:3]:
                        lines.append(f"- {fb.created_at.strftime('%d %b %Y')}: {fb.feedback_text[:200]}")
                if not found:
                    return "No feedback has been recorded on your submitted leads yet."
                return "\n".join(lines)

            return "I couldn't process that lead status request."
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            return detail or "Lead status request could not be completed."
        except Exception as exc:
            logger.error("[LEAD] Status query failed: %s", exc, exc_info=True)
            return "Sorry, there was an error loading lead status. Please try again."
        finally:
            db.close()

    def _employee_summary(self, employee: EmployeeUser) -> str:
        parts = [employee.full_name or employee.username]
        if employee.employee_id:
            parts.append(f"ID {employee.employee_id}")
        if employee.department:
            parts.append(employee.department)
        return " | ".join(parts)

    def _resolve_session_uuid(
        self, db, session_reference: str, user_id: str
    ) -> Optional[UUID]:
        try:
            from app.models.chat_session import ChatSession

            sess = (
                db.query(ChatSession)
                .filter(
                    ChatSession.session_reference_no == session_reference,
                    ChatSession.user_id == user_id,
                )
                .first()
            )
            return sess.id if sess else None
        except Exception:
            return None
