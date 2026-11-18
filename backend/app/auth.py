"""Вход, роли и журнал аудита.

Роли: specialist — проверки, сопоставления, решения; admin — дополнительно загрузка справочников
и просмотр журнала аудита. Учётные записи прототипа задаются переменной окружения APP_USERS
в формате «логин:пароль:Имя:роль,…»; пароли хранятся только в виде хеша PBKDF2."""
import hashlib
import hmac
import os
import secrets

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_session
from .models import AuditEvent, SessionToken, User

COOKIE = "kp_session"
DEFAULT_USERS = ("specialist:specialist:Специалист по профилактике коррупционных правонарушений:specialist,"
                 "admin:admin:Администратор справочников:admin")
ROLE_TITLES = {"specialist": "Специалист", "admin": "Администратор"}


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    salt, _ = stored.split("$", 1)
    return hmac.compare_digest(hash_password(password, salt), stored)


def seed_users(s: Session) -> None:
    if s.scalar(select(User).limit(1)):
        return
    for entry in os.getenv("APP_USERS", DEFAULT_USERS).split(","):
        login, password, name, role = [x.strip() for x in entry.split(":", 3)]
        if role not in ROLE_TITLES:
            raise ValueError(f"Неизвестная роль {role} в APP_USERS")
        s.add(User(login=login, name=name, role=role, password_hash=hash_password(password)))
    s.flush()


def login(s: Session, login_: str, password: str) -> SessionToken | None:
    user = s.scalar(select(User).where(User.login == login_))
    if not user or not verify_password(password, user.password_hash):
        return None
    tok = SessionToken(token=secrets.token_hex(32), user_id=user.id)
    s.add(tok)
    s.flush()
    return tok


def current_user(request: Request, s: Session = Depends(get_session)) -> User:
    token = request.cookies.get(COOKIE)
    tok = s.get(SessionToken, token) if token else None
    if not tok:
        raise HTTPException(401, "Требуется вход")
    return tok.user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Действие доступно только администратору справочников")
    return user


def audit(s: Session, user: User, action: str, object_ref: str = "", **details) -> None:
    s.add(AuditEvent(user_login=user.login, action=action, object_ref=object_ref, details=details))
