from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

from app.auth import current_user, permission_required
from app.clock import now
from app.constants import ACCOUNT_STATUSES, ROLE_ADMIN
from app.db import get_db, write_tx
from app.services import write_audit
from app.validate import USERNAME, acceptable_password, clean

bp = Blueprint("users", __name__, url_prefix="/users")


def _roles(connection):
    return connection.execute("SELECT id, name FROM roles ORDER BY name").fetchall()


def _employees(connection):
    return connection.execute(
        "SELECT id, full_name, employee_number FROM employees ORDER BY full_name"
    ).fetchall()


def _validate(connection, form, user_id=None):
    errors = []
    username = clean(form.get("username"), 32).lower()
    full_name = clean(form.get("full_name"), 120)
    password = form.get("password", "")
    status = form.get("status", "")
    role_raw = form.get("role_id", "")
    employee_raw = form.get("employee_id", "")
    if user_id is None and not USERNAME.match(username or ""):
        errors.append("Username must be 3–32 characters: lowercase letters, numbers, dots, hyphens, or underscores.")
    if len(full_name) < 3:
        errors.append("Enter the person's name.")
    if status not in ACCOUNT_STATUSES:
        errors.append("Choose an account status.")
    if not str(role_raw).isdigit():
        errors.append("Choose a role.")
        role_id = None
        role_name = ""
    else:
        role_id = int(role_raw)
        role = connection.execute("SELECT name FROM roles WHERE id = ?", (role_id,)).fetchone()
        if role is None:
            errors.append("Choose a role.")
            role_name = ""
        else:
            role_name = role["name"]
    employee_id = None
    if employee_raw:
        if not str(employee_raw).isdigit():
            errors.append("Choose an employee link or leave it blank.")
        else:
            employee_id = int(employee_raw)
            if connection.execute("SELECT id FROM employees WHERE id = ?", (employee_id,)).fetchone() is None:
                errors.append("Choose an employee link or leave it blank.")
    if user_id is None:
        if not acceptable_password(password):
            errors.append("Password must be at least 8 characters and include a letter and a number.")
        elif username:
            taken = connection.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            if taken:
                errors.append("That username is already in use.")
    elif password and not acceptable_password(password):
        errors.append("Password must be at least 8 characters and include a letter and a number.")
    actor = current_user()
    if user_id and actor and user_id == actor["id"] and status != "ACTIVE":
        errors.append("You cannot deactivate the account you are using.")
    if user_id and role_name and not errors:
        current = connection.execute(
            """
            SELECT r.name, u.status
            FROM users u JOIN roles r ON r.id = u.role_id
            WHERE u.id = ?
            """,
            (user_id,),
        ).fetchone()
        losing_admin = current and current["name"] == ROLE_ADMIN and current["status"] == "ACTIVE"
        still_admin = role_name == ROLE_ADMIN and status == "ACTIVE"
        if losing_admin and not still_admin:
            others = connection.execute(
                """
                SELECT COUNT(*) FROM users u
                JOIN roles r ON r.id = u.role_id
                WHERE r.name = ? AND u.status = 'ACTIVE' AND u.id != ?
                """,
                (ROLE_ADMIN, user_id),
            ).fetchone()[0]
            if others == 0:
                errors.append("Keep at least one active system administrator.")
    return {
        "username": username,
        "full_name": full_name,
        "password": password,
        "status": status,
        "role_id": role_id,
        "employee_id": employee_id,
    }, errors


@bp.route("/", strict_slashes=False)
@permission_required("manage_users")
def index():
    rows = get_db().execute(
        """
        SELECT u.*, r.name AS role_name, e.full_name AS employee_name
        FROM users u
        JOIN roles r ON r.id = u.role_id
        LEFT JOIN employees e ON e.id = u.employee_id
        ORDER BY u.full_name
        """
    ).fetchall()
    return render_template("users/index.html", rows=rows)


@bp.route("/new", methods=["GET", "POST"])
@permission_required("manage_users")
def new():
    connection = get_db()
    form = {"username": "", "full_name": "", "password": "", "status": "ACTIVE", "role_id": "", "employee_id": ""}
    errors = []
    if request.method == "POST":
        with write_tx() as tx:
            form, errors = _validate(tx, request.form)
            if not errors:
                cursor = tx.execute(
                    """
                    INSERT INTO users (username, password_hash, full_name, employee_id, role_id, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        form["username"],
                        generate_password_hash(form["password"]),
                        form["full_name"],
                        form["employee_id"],
                        form["role_id"],
                        form["status"],
                        now(),
                    ),
                )
                write_audit(tx, current_user()["id"], "Created user", "user", cursor.lastrowid, form["username"])
        if not errors:
            flash("User account created.", "success")
            return redirect(url_for("users.index"))
    return render_template("users/form.html", form=form, errors=errors, editing=False, roles=_roles(connection), employees=_employees(connection))


@bp.route("/<int:user_id>/edit", methods=["GET", "POST"])
@permission_required("manage_users")
def edit(user_id):
    connection = get_db()
    current = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if current is None:
        abort(404)
    form = {
        "username": current["username"],
        "full_name": current["full_name"],
        "password": "",
        "status": current["status"],
        "role_id": current["role_id"],
        "employee_id": current["employee_id"] or "",
    }
    errors = []
    if request.method == "POST":
        with write_tx() as tx:
            form, errors = _validate(tx, request.form, user_id)
            form["username"] = current["username"]
            if not errors:
                if form["password"]:
                    tx.execute(
                        """
                        UPDATE users
                        SET full_name = ?, employee_id = ?, role_id = ?, status = ?, password_hash = ?
                        WHERE id = ?
                        """,
                        (
                            form["full_name"],
                            form["employee_id"],
                            form["role_id"],
                            form["status"],
                            generate_password_hash(form["password"]),
                            user_id,
                        ),
                    )
                else:
                    tx.execute(
                        """
                        UPDATE users
                        SET full_name = ?, employee_id = ?, role_id = ?, status = ?
                        WHERE id = ?
                        """,
                        (form["full_name"], form["employee_id"], form["role_id"], form["status"], user_id),
                    )
                write_audit(tx, current_user()["id"], "Updated user", "user", user_id, current["username"])
        if not errors:
            flash("User account updated.", "success")
            return redirect(url_for("users.index"))
    return render_template(
        "users/form.html",
        form=form,
        errors=errors,
        editing=True,
        roles=_roles(connection),
        employees=_employees(connection),
        user_id=user_id,
    )
