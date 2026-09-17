import pytest

from app.services import auth_service


async def test_signup_then_login_roundtrip(session_id):
    username = session_id
    result = await auth_service.signup(username, "password123", "테스터")
    assert result["username"] == username
    assert result["display_name"] == "테스터"

    logged_in = await auth_service.login(username, "password123")
    assert logged_in["username"] == username


async def test_signup_rejects_duplicate_username(session_id):
    await auth_service.signup(session_id, "password123", "첫번째")
    with pytest.raises(auth_service.AuthError):
        await auth_service.signup(session_id, "different-password", "두번째")


async def test_username_available_reflects_signups(session_id):
    assert await auth_service.username_available(session_id) is True
    await auth_service.signup(session_id, "password123", "테스터")
    assert await auth_service.username_available(session_id) is False


async def test_login_wrong_password_and_missing_user_give_same_generic_error(session_id):
    await auth_service.signup(session_id, "correct-password", "테스터")

    # Both failure modes must be indistinguishable to callers — a different message
    # for "no such user" vs "wrong password" would let an attacker enumerate accounts.
    with pytest.raises(auth_service.AuthError) as wrong_password_exc:
        await auth_service.login(session_id, "wrong-password")
    with pytest.raises(auth_service.AuthError) as no_such_user_exc:
        await auth_service.login(session_id + "_nonexistent", "anything")

    assert str(wrong_password_exc.value) == str(no_such_user_exc.value)


async def test_signup_rejects_short_password(session_id):
    with pytest.raises(auth_service.AuthError):
        await auth_service.signup(session_id, "abc", "테스터")
