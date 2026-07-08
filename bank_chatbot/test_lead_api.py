"""
API-level RBAC tests for Lead Generation routes.

Run from repo root:
  python bank_chatbot/test_lead_api.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.models.auth import EmployeeUser
from app.models.lead import LeadUserRole
from app.services import lead_service as svc
from main import app


def _employee(username: str = "emp1", employee_id: str = "1001") -> EmployeeUser:
    return EmployeeUser(username=username, employee_id=employee_id, full_name="Test User")


def _admin() -> EmployeeUser:
    return EmployeeUser(username="admin", employee_id="2872", full_name="Admin User")


def _set_user(user: EmployeeUser) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


def _clear_user() -> None:
    app.dependency_overrides.pop(get_current_user, None)


def test_export_forbidden_for_employee():
    _set_user(_employee())
    mock_db = MagicMock()
    try:
        with patch("app.api.lead_routes.get_db", return_value=mock_db):
            with patch(
                "app.api.lead_routes.svc.get_user_roles",
                return_value={LeadUserRole.EMPLOYEE},
            ):
                client = TestClient(app, raise_server_exceptions=False)
                response = client.get("/api/leads/export.csv")
                assert response.status_code == 403
    finally:
        _clear_user()


def test_export_allowed_for_sales_manager():
    _set_user(_admin())
    mock_db = MagicMock()
    try:
        with patch("app.api.lead_routes.get_db", return_value=mock_db):
            with patch(
                "app.api.lead_routes.svc.get_user_roles",
                return_value={LeadUserRole.SALES_MANAGER},
            ):
                with patch(
                    "app.api.lead_routes.svc.export_leads_csv",
                    return_value="lead_reference_no\nLD-000001\n",
                ):
                    client = TestClient(app, raise_server_exceptions=False)
                    response = client.get("/api/leads/export.csv")
                    assert response.status_code == 200
                    assert "LD-000001" in response.text
    finally:
        _clear_user()


def test_list_roles_forbidden_for_employee():
    _set_user(_employee())
    mock_db = MagicMock()
    try:
        with patch("app.api.lead_routes.get_db", return_value=mock_db):
            with patch(
                "app.api.lead_routes.svc.get_user_roles",
                return_value={LeadUserRole.EMPLOYEE},
            ):
                client = TestClient(app, raise_server_exceptions=False)
                response = client.get("/api/leads/roles")
                assert response.status_code == 403
    finally:
        _clear_user()


def test_revoke_role_admin_success():
    _set_user(_admin())
    mock_db = MagicMock()
    try:
        with patch("app.api.lead_routes.get_db", return_value=mock_db):
            with patch(
                "app.api.lead_routes.svc.get_user_roles",
                return_value={LeadUserRole.ADMIN},
            ):
                with patch("app.api.lead_routes.svc.revoke_role") as mock_revoke:
                    client = TestClient(app, raise_server_exceptions=False)
                    response = client.delete(
                        "/api/leads/roles",
                        params={"employee_id": "3002", "role": "sales_user"},
                    )
                    assert response.status_code == 204
                    mock_revoke.assert_called_once()
    finally:
        _clear_user()


def test_revoke_role_forbidden_for_employee():
    _set_user(_employee())
    mock_db = MagicMock()
    try:
        with patch("app.api.lead_routes.get_db", return_value=mock_db):
            with patch(
                "app.api.lead_routes.svc.get_user_roles",
                return_value={LeadUserRole.EMPLOYEE},
            ):
                client = TestClient(app, raise_server_exceptions=False)
                response = client.delete(
                    "/api/leads/roles",
                    params={"employee_id": "3002", "role": "sales_user"},
                )
                assert response.status_code == 403
    finally:
        _clear_user()


def test_revoke_role_not_found():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.delete.return_value = 0
    try:
        svc.revoke_role(mock_db, _admin(), "9999", LeadUserRole.SALES_USER)
        raise AssertionError("expected HTTPException")
    except HTTPException as exc:
        assert exc.status_code == 404


def test_export_service_rbac():
    mock_db = MagicMock()
    user = _employee()
    try:
        svc.export_leads_csv(mock_db, user, {LeadUserRole.EMPLOYEE})
        raise AssertionError("expected HTTPException")
    except HTTPException as exc:
        assert exc.status_code == 403


def main():
    tests = [
        test_export_forbidden_for_employee,
        test_export_allowed_for_sales_manager,
        test_list_roles_forbidden_for_employee,
        test_revoke_role_admin_success,
        test_revoke_role_forbidden_for_employee,
        test_revoke_role_not_found,
        test_export_service_rbac,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except Exception as exc:
            failed += 1
            print(f"FAIL  {test.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
