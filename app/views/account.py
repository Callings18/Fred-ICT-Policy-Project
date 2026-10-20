from flask import Blueprint, flash, redirect, render_template, request, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app.auth import current_user, login_required
from app.db import get_db, write_tx
from app.services import write_audit
from app.validate import acceptable_password, clean

bp = Blueprint("account", __name__, url_prefix="/account")


@bp.route("/", methods=["GET", "POST"], strict_slashes=False)
@login_required
def index():
    user = current_user()
    form = {"full_name": user["full_name"]}
    errors = []
    if request.method == "POST":
        form["full_name"] = clean(request.form.get("full_name"), 120)
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        if len(form["full_name"]) < 3:
            errors.append("Enter your name.")
        changing_password = bool(new_password or confirm)
        if changing_password:
            if not check_password_hash(user["password_hash"], current_password):
                errors.append("The current password is not correct.")
            elif not acceptable_password(new_password):
                errors.append("The new password must be at least 8 characters and include a letter and a number.")
            elif new_password != confirm:
                errors.append("The new password and confirmation do not match.")
        if not errors:
            with write_tx() as connection:
                if changing_password:
                    connection.execute(
                        "UPDATE users SET full_name = ?, password_hash = ? WHERE id = ?",
                        (form["full_name"], generate_password_hash(new_password), user["id"]),
                    )
                    write_audit(connection, user["id"], "Updated profile", "user", user["id"], "Name and password updated.")
                else:
                    connection.execute(
                        "UPDATE users SET full_name = ? WHERE id = ?",
                        (form["full_name"], user["id"]),
                    )
                    write_audit(connection, user["id"], "Updated profile", "user", user["id"], "Name updated.")
            flash("Profile saved." if not changing_password else "Profile saved. Use the new password the next time you sign in.")
            return redirect(url_for("account.index"))
    connection = get_db()
    recent = connection.execute(
        """
        SELECT action, entity, created_at
        FROM audit_logs
        WHERE user_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 8
        """,
        (user["id"],),
    ).fetchall()
    return render_template("account/index.html", form=form, errors=errors, recent=recent)
