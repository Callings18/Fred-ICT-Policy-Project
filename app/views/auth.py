from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.auth import authenticate, current_user, permission_required, safe_next, start_session
from app.clock import now
from app.db import get_db, write_tx
from app.services import write_audit

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user() is not None:
        return redirect(url_for("dashboard.index"))
    error = None
    username = ""
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        row, status = authenticate(username, password)
        if status == "ok":
            with write_tx() as connection:
                connection.execute("UPDATE users SET last_login = ? WHERE id = ?", (now(), row["id"]))
                write_audit(connection, row["id"], "Signed in", "user", row["id"], "Successful sign-in.")
            start_session(row["id"])
            return redirect(safe_next(request.args.get("next")))
        with write_tx() as connection:
            write_audit(
                connection,
                None,
                "Sign-in failed",
                "user",
                None,
                f"Rejected username {username.strip().lower()[:32]}.",
            )
        error = (
            "This account is inactive. Contact an administrator."
            if status == "inactive"
            else "Invalid username or password."
        )
    return render_template("login.html", error=error, username=username)


@bp.post("/logout")
def logout():
    user = current_user()
    if user is not None:
        with write_tx() as connection:
            write_audit(connection, user["id"], "Signed out", "user", user["id"], "User signed out.")
    from flask import session

    session.clear()
    flash("You have signed out.", "info")
    return redirect(url_for("auth.login"))
