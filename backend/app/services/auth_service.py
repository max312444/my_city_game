import hashlib
import secrets

from sqlalchemy import select

from app.db import async_session_maker
from app.models.user import User

PBKDF2_ITERATIONS = 100_000


class AuthError(Exception):
    pass


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS
    ).hex()


async def username_available(username: str) -> bool:
    async with async_session_maker() as db:
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none() is None


async def signup(username: str, password: str, display_name: str) -> dict:
    username = username.strip()
    display_name = display_name.strip()
    if not username or not password or not display_name:
        raise AuthError("아이디, 비밀번호, 이름을 모두 입력해주세요")
    if len(password) < 4:
        raise AuthError("비밀번호는 4자 이상이어야 합니다")

    async with async_session_maker() as db:
        result = await db.execute(select(User).where(User.username == username))
        if result.scalar_one_or_none() is not None:
            raise AuthError("이미 사용 중인 아이디입니다")

        salt = secrets.token_hex(16)
        user = User(
            username=username,
            password_hash=_hash_password(password, salt),
            salt=salt,
            display_name=display_name,
        )
        db.add(user)
        await db.commit()
        return {"username": user.username, "display_name": user.display_name}


async def login(username: str, password: str) -> dict:
    username = username.strip()
    async with async_session_maker() as db:
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if user is None or _hash_password(password, user.salt) != user.password_hash:
            raise AuthError("아이디 또는 비밀번호가 올바르지 않습니다")
        return {"username": user.username, "display_name": user.display_name}
