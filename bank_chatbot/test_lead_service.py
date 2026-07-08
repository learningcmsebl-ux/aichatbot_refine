"""
Unit tests for Lead Generation service helpers and RBAC.

Run from repo root:
  python bank_chatbot/test_lead_service.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.models.auth import EmployeeUser
from app.models.lead import LeadLifecycleStatus, LeadUserRole, format_lead_reference_no
from app.models.leads import LeadCreateRequest, LeadProductType
from app.models.lead import LeadMaster
from app.services import lead_service as svc
from fastapi import HTTPException


def test_format_lead_reference():
    assert format_lead_reference_no(1) == "LD-000001"
    assert format_lead_reference_no(123) == "LD-000123"


def test_mask_pii():
    assert svc.mask_mobile("01712345678").endswith("5678")
    assert "@" in (svc.mask_email("john.doe@example.com") or "")
    assert svc.mask_email("john.doe@example.com") != "john.doe@example.com"


def test_valid_bd_mobile():
    assert svc._valid_bd_mobile("01712345678")
    assert svc._valid_bd_mobile("+8801712345678")
    assert not svc._valid_bd_mobile("12345")


def test_default_employee_role():
    roles = {LeadUserRole.EMPLOYEE}
    perms = svc.get_user_permissions(roles)
    assert perms["view_all"] is False
    assert perms["export"] is False
    assert perms["assign"] is False


def test_admin_permissions():
    roles = {LeadUserRole.ADMIN}
    perms = svc.get_user_permissions(roles)
    assert perms["view_all"] is True
    assert perms["export"] is True
    assert perms["manage_roles"] is True


def test_lead_owner_view():
    user = EmployeeUser(username="jdoe", employee_id="1001")
    lead = LeadMaster(
        id=1,
        lead_reference_no="LD-000001",
        customer_name="Test Customer",
        product_type="credit_card",
        status=LeadLifecycleStatus.SUBMITTED.value,
        created_by_employee_id="1001",
    )
    roles = {LeadUserRole.EMPLOYEE}
    assert svc.can_view_lead(user, lead, roles)
    assert not svc.can_update_lead_status(user, lead, roles)


def test_sales_user_assigned_update():
    user = EmployeeUser(username="sales1", employee_id="2002")
    lead = LeadMaster(
        id=2,
        lead_reference_no="LD-000002",
        customer_name="Test Customer",
        product_type="personal_loan",
        status=LeadLifecycleStatus.ASSIGNED.value,
        created_by_employee_id="1001",
        assigned_to_user_id="2002",
    )
    roles = {LeadUserRole.SALES_USER}
    assert svc.can_view_lead(user, lead, roles)
    assert svc.can_update_lead_status(user, lead, roles)
    assert not svc.can_assign_leads(roles)


def test_create_intent_not_fee_query():
    from app.services.handlers.lead_capture_handler import LeadCaptureHandler

    h = LeadCaptureHandler()
    assert h.detect_create_intent("create a lead for credit card") == LeadProductType.CREDIT_CARD
    assert h.detect_create_intent("what is the credit card annual fee") is None
    assert h.detect_create_intent("apply for personal loan") is None
    assert h.detect_create_intent("customer interested in home loan rates") is None
    assert h.detect_create_intent("customer interested in home loan lead") == LeadProductType.HOME_LOAN


def test_banking_escape_during_capture():
    from app.services.handlers.lead_capture_handler import LeadCaptureHandler

    h = LeadCaptureHandler()
    assert h._looks_like_banking_question("what is the credit card annual fee?")
    assert not h._looks_like_banking_question("John Smith")
    assert not h._looks_like_banking_question("cancel")


def test_status_intent():
    from app.services.handlers.lead_capture_handler import LeadCaptureHandler, LeadStatusIntent

    h = LeadCaptureHandler()
    assert h.detect_status_intent("show my submitted leads") == LeadStatusIntent.MY_LEADS
    assert h.extract_lead_reference("status of lead LD-000042") == "LD-000042"


def test_status_query_http_exception():
    from unittest.mock import MagicMock, patch

    from app.services.handlers.lead_capture_handler import LeadCaptureHandler, LeadStatusIntent

    h = LeadCaptureHandler()
    user = EmployeeUser(username="jdoe", employee_id="1001")
    mock_db = MagicMock()
    mock_lead = MagicMock()

    with (
        patch("app.database.postgres.get_db", return_value=mock_db),
        patch("app.services.lead_service.get_lead_by_reference", return_value=mock_lead),
        patch("app.services.lead_service.get_user_roles", return_value=set()),
        patch(
            "app.services.lead_service.require_lead_access",
            side_effect=HTTPException(status_code=403, detail="Access denied"),
        ),
    ):
        result = h._handle_status_query(
            "status of lead LD-000001", user, LeadStatusIntent.LEAD_DETAIL
        )
        assert result == "Access denied"


def main():
    tests = [
        test_format_lead_reference,
        test_mask_pii,
        test_valid_bd_mobile,
        test_default_employee_role,
        test_admin_permissions,
        test_lead_owner_view,
        test_sales_user_assigned_update,
        test_create_intent_not_fee_query,
        test_banking_escape_during_capture,
        test_status_intent,
        test_status_query_http_exception,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except Exception as exc:
            failed += 1
            print(f"FAIL  {t.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
