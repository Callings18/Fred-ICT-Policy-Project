import functools
import hmac
import secrets

from flask import abort, redirect, request, session, url_for
from werkzeug.security import check_password_hash

from app.db import get_db


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    cached = getattr(request, "_ipmcs_user", None)
    if cached and cached["id"] == user_id:
        return cached
    connection = get_db()
    row = connection.execute(
        """
        SELECT u.*, r.name AS role_name, r.description AS role_description, e.email
        FROM users u
        JOIN roles r ON r.id = u.role_id
        LEFT JOIN employees e ON e.id = u.employee_id
        WHERE u.id = ?
        """,
        (user_id,),
    ).fetchone()
    if row is None or row["status"] != "ACTIVE":
        session.clear()
        return None
    user = dict(row)
    permissions = connection.execute(
        """
        SELECT p.code
        FROM permissions p
        JOIN role_permissions rp ON rp.permission_id = p.id
        WHERE rp.role_id = ?
        """,
        (user["role_id"],),
    ).fetchall()
    user["permissions"] = {item["code"] for item in permissions}
    request._ipmcs_user = user
    return user


def can(code):
    user = current_user()
    return bool(user) and code in user["permissions"]


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def permission_required(code):
    def decorator(view):
        @functools.wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if not can(code):
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def authenticate(username, password):
    connection = get_db()
    row = connection.execute(
        "SELECT * FROM users WHERE username = ?",
        (username.strip().lower(),),
    ).fetchone()
    if row is None or not check_password_hash(row["password_hash"], password):
        return None, "invalid"
    if row["status"] != "ACTIVE":
        return row, "inactive"
    return row, "ok"


def start_session(user_id):
    session.clear()
    session["user_id"] = user_id
    session["_csrf"] = secrets.token_urlsafe(32)
    session.permanent = True
    request._ipmcs_user = None


def csrf_token():
    token = session.get("_csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf"] = token
    return token


def csrf_ok():
    expected = session.get("_csrf") or ""
    sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token") or ""
    if not expected or not sent or len(expected) != len(sent):
        return False
    return hmac.compare_digest(expected, sent)


def safe_next(value):
    if value and value.startswith("/") and not value.startswith("//"):
        return value
    return url_for("dashboard.index")
