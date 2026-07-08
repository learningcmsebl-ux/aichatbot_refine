"""
Session ownership tests (P0/P1 security).

Run from repo root:
  python bank_chatbot/test_session_ownership.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.dependencies import get_orchestrator
from app.core.security import get_current_user
from app.models.auth import EmployeeUser
from app.services.chat_session_service import (
    SessionOwnershipError,
    assert_reference_access,
    ensure_session,
    mint_user_scoped_reference,
)
from main import app


def _user(username: str = "alice") -> EmployeeUser:
    return EmployeeUser(username=username, employee_id="1001", full_name="Alice")


def _set_user(user: EmployeeUser) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


def _clear_overrides() -> None:
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_orchestrator, None)


def test_assert_reference_access_blocks_other_chat_session() -> None:
    mock_db = MagicMock()
    other_session = MagicMock()
    other_session.user_id = "bob"
    mock_db.query.return_value.filter.return_value.first.return_value = other_session

    try:
        assert_reference_access(mock_db, "shared-session", "alice")
        raise AssertionError("expected SessionOwnershipError")
    except SessionOwnershipError as exc:
        assert exc.owner_id == "bob"
        assert exc.requested_by == "alice"


def test_assert_reference_access_blocks_orphan_messages() -> None:
    mock_db = MagicMock()
    query = mock_db.query.return_value
    query.filter.return_value.first.side_effect = [None, MagicMock(user_id="bob")]

    try:
        assert_reference_access(mock_db, "legacy-session", "alice")
        raise AssertionError("expected SessionOwnershipError")
    except SessionOwnershipError:
        pass


def test_ensure_session_checks_access_before_create() -> None:
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with patch(
        "app.services.chat_session_service.assert_reference_access",
        side_effect=SessionOwnershipError("legacy-session", "bob", "alice"),
    ) as mock_assert:
        try:
            ensure_session(mock_db, "legacy-session", "alice")
            raise AssertionError("expected SessionOwnershipError")
        except SessionOwnershipError:
            pass
        mock_assert.assert_called_once_with(
            mock_db, "legacy-session", "alice", legacy_user_ids=[]
        )


def test_mint_user_scoped_reference_includes_user() -> None:
    ref = mint_user_scoped_reference("alice", "contested-id")
    assert ref.startswith("alice::")
    assert "contested-id" in ref


def test_chat_post_blocked_for_foreign_session() -> None:
    _set_user(_user("alice"))
    mock_orch = MagicMock()
    mock_orch.process_chat_sync = AsyncMock(
        return_value={"response": "ok", "session_id": "foreign", "sources": []}
    )
    app.dependency_overrides[get_orchestrator] = lambda: mock_orch
    try:
        with patch(
            "app.api.routes._require_session_reference_access",
            side_effect=HTTPException(status_code=403, detail="Not authorized to access this session"),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/api/chat",
                json={"query": "hello", "session_id": "foreign", "stream": False},
            )
            assert response.status_code == 403
            mock_orch.process_chat_sync.assert_not_called()
    finally:
        _clear_overrides()


def test_chat_post_allowed_for_own_session() -> None:
    _set_user(_user("alice"))
    mock_orch = MagicMock()
    mock_orch.process_chat_sync = AsyncMock(
        return_value={"response": "hello back", "session_id": "mine", "sources": []}
    )
    app.dependency_overrides[get_orchestrator] = lambda: mock_orch
    try:
        with patch("app.api.routes._require_session_reference_access") as mock_require:
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/api/chat",
                json={"query": "hello", "session_id": "mine", "stream": False},
            )
            assert response.status_code == 200
            assert response.json()["response"] == "hello back"
            # user_id is the stable AD id (falls back to username here); employee_id
            # "1001" is passed as a legacy key so prior history stays reachable.
            mock_require.assert_called_once_with("mine", "alice", ["1001"])
            mock_orch.process_chat_sync.assert_called_once()
    finally:
        _clear_overrides()


def test_history_403_not_wrapped_as_500() -> None:
    _set_user(_user("alice"))
    try:
        with patch("app.database.postgres.get_db", return_value=MagicMock()):
            with patch(
                "app.services.chat_session_service.assert_reference_access",
                side_effect=SessionOwnershipError("foreign", "bob", "alice"),
            ):
                client = TestClient(app, raise_server_exceptions=False)
                response = client.get("/api/chat/history/foreign")
                assert response.status_code == 403
    finally:
        _clear_overrides()


def test_claim_orphan_messages_stamps_user() -> None:
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.update.return_value = 3

    from app.services.chat_session_service import claim_orphan_messages

    count = claim_orphan_messages(mock_db, "orphan-ref", "alice")
    assert count == 3
    mock_db.commit.assert_called_once()


def test_ensure_session_resurrects_soft_deleted_for_owner() -> None:
    mock_db = MagicMock()
    deleted = MagicMock()
    deleted.user_id = "alice"
    deleted.deleted_at = object()
    mock_db.query.return_value.filter.return_value.first.return_value = deleted

    from app.services.chat_session_service import ensure_session

    with patch("app.services.chat_session_service.claim_orphan_messages") as mock_claim:
        sess = ensure_session(mock_db, "sess-1", "alice")
    assert sess is deleted
    assert deleted.deleted_at is None
    mock_claim.assert_called_once()


def main() -> int:
    tests = [
        test_assert_reference_access_blocks_other_chat_session,
        test_assert_reference_access_blocks_orphan_messages,
        test_ensure_session_checks_access_before_create,
        test_mint_user_scoped_reference_includes_user,
        test_claim_orphan_messages_stamps_user,
        test_ensure_session_resurrects_soft_deleted_for_owner,
        test_chat_post_blocked_for_foreign_session,
        test_chat_post_allowed_for_own_session,
        test_history_403_not_wrapped_as_500,
    ]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"[PASS] {test.__name__}")
        except Exception as exc:
            failures += 1
            print(f"[FAIL] {test.__name__}: {exc}")
    if failures:
        return 1
    print(f"\nAll {len(tests)} session ownership tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
