from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.auth import can, current_user, permission_required
from app.clock import now, today
from app.constants import ACCESS_STATUSES, EMPLOYMENT_STATUSES, LEAVING_STATUSES
from app.db import get_db, write_tx
from app.services import maybe_open_review, write_audit
from app.validate import EMPLOYEE_NUMBER, clean, parse_date
from app import like, paging

bp = Blueprint("employees", __name__, url_prefix="/employees")


def _validate(connection, form, employee_id=None):
    errors = []
    number = clean(form.get("employee_number"), 20).upper()
    name = clean(form.get("full_name"), 120)
    department = clean(form.get("department"), 80)
    position = clean(form.get("position"), 80)
    email = clean(form.get("email"), 120).lower()
    status = form.get("employment_status", "")
    access = form.get("ict_access_status", "")
    if not EMPLOYEE_NUMBER.match(number or ""):
        errors.append("Employee number must be 2–20 letters, numbers, or hyphens.")
    if len(name) < 3:
        errors.append("Enter the employee's full name.")
    if not department:
        errors.append("Enter a department.")
    if not position:
        errors.append("Enter a position.")
    if email and "@" not in email:
        errors.append("Enter a valid email address or leave it blank.")
    if status not in EMPLOYMENT_STATUSES:
        errors.append("Choose an employment status.")
    if access not in ACCESS_STATUSES:
        errors.append("Choose an ICT access status.")
    try:
        hire_date = parse_date(form.get("hire_date"), "hire date")
        left_date = parse_date(form.get("left_date"), "leaving date")
    except ValueError as exc:
        errors.append(str(exc))
        hire_date = ""
        left_date = ""
    if number and not errors:
        existing = connection.execute(
            "SELECT id FROM employees WHERE employee_number = ? AND id != ?",
            (number, employee_id or 0),
        ).fetchone()
        if existing:
            errors.append("That employee number is already in use.")
    if status == "ACTIVE":
        left_date = ""
    elif status in LEAVING_STATUSES and not left_date:
        left_date = today()
    return {
        "employee_number": number,
        "full_name": name,
        "department": department,
        "position": position,
        "email": email,
        "employment_status": status,
        "ict_access_status": access,
        "hire_date": hire_date,
        "left_date": left_date,
    }, errors


@bp.route("/", strict_slashes=False)
@permission_required("view_employees")
def index():
    connection = get_db()
    clauses = ["1 = 1"]
    params = []
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    if q:
        term = like(q)
        clauses.append(
            "(full_name LIKE ? ESCAPE '\\' OR employee_number LIKE ? ESCAPE '\\' OR department LIKE ? ESCAPE '\\')"
        )
        params.extend([term, term, term])
    if status in EMPLOYMENT_STATUSES:
        clauses.append("employment_status = ?")
        params.append(status)
    where = " AND ".join(clauses)
    total = connection.execute(f"SELECT COUNT(*) FROM employees WHERE {where}", params).fetchone()[0]
    pager = paging(total)
    rows = connection.execute(
        f"""
        SELECT * FROM employees
        WHERE {where}
        ORDER BY full_name
        LIMIT ? OFFSET ?
        """,
        [*params, pager["per_page"], pager["offset"]],
    ).fetchall()
    return render_template(
        "employees/index.html",
        rows=rows,
        pager=pager,
        statuses=EMPLOYMENT_STATUSES,
        filters={"q": q, "status": status},
    )


@bp.route("/new", methods=["GET", "POST"])
@permission_required("manage_employees")
def new():
    form = {
        "employee_number": "",
        "full_name": "",
        "department": "",
        "position": "",
        "email": "",
        "employment_status": "ACTIVE",
        "ict_access_status": "ACTIVE",
        "hire_date": today(),
        "left_date": "",
    }
    errors = []
    if request.method == "POST":
        with write_tx() as connection:
            form, errors = _validate(connection, request.form)
            if not errors:
                cursor = connection.execute(
                    """
                    INSERT INTO employees (
                        employee_number, full_name, department, position, email,
                        employment_status, ict_access_status, hire_date, left_date, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        form["employee_number"],
                        form["full_name"],
                        form["department"],
                        form["position"],
                        form["email"] or None,
                        form["employment_status"],
                        form["ict_access_status"],
                        form["hire_date"] or None,
                        form["left_date"] or None,
                        now(),
                    ),
                )
                employee_id = cursor.lastrowid
                review_id, opened = maybe_open_review(
                    connection, employee_id, None, form["employment_status"], "employee record"
                )
                write_audit(
                    connection,
                    current_user()["id"],
                    "Created employee",
                    "employee",
                    employee_id,
                    form["full_name"],
                )
                if opened:
                    write_audit(
                        connection,
                        current_user()["id"],
                        "Opened access review",
                        "access_review",
                        review_id,
                        form["full_name"],
                    )
        if not errors:
            flash("Employee record saved.", "success")
            if opened:
                flash("An access review was opened because of the employment status.", "info")
            return redirect(url_for("employees.detail", employee_id=employee_id))
    return render_template("employees/form.html", form=form, errors=errors, editing=False)


@bp.route("/<int:employee_id>")
@permission_required("view_employees")
def detail(employee_id):
    connection = get_db()
    employee = connection.execute("SELECT * FROM employees WHERE id = ?", (employee_id,)).fetchone()
    if employee is None:
        abort(404)
    devices = connection.execute(
        "SELECT * FROM devices WHERE employee_id = ? ORDER BY hostname",
        (employee_id,),
    ).fetchall()
    reviews = connection.execute(
        """
        SELECT ar.*, u.full_name AS reviewer_name
        FROM access_reviews ar
        LEFT JOIN users u ON u.id = ar.reviewer_id
        WHERE ar.employee_id = ?
        ORDER BY ar.created_at DESC
        """,
        (employee_id,),
    ).fetchall()
    activity_count = connection.execute(
        "SELECT COUNT(*) FROM activities WHERE employee_id = ?",
        (employee_id,),
    ).fetchone()[0]
    activities = []
    if can("view_activities"):
        activities = connection.execute(
            """
            SELECT a.id, a.activity_type, a.application, a.resource, a.occurred_at, d.hostname
            FROM activities a
            LEFT JOIN devices d ON d.id = a.device_id
            WHERE a.employee_id = ?
            ORDER BY a.occurred_at DESC
            LIMIT 12
            """,
            (employee_id,),
        ).fetchall()
    return render_template(
        "employees/detail.html",
        employee=employee,
        devices=devices,
        reviews=reviews,
        activities=activities,
        activity_count=activity_count,
        show_activities=can("view_activities"),
    )


@bp.route("/<int:employee_id>/edit", methods=["GET", "POST"])
@permission_required("manage_employees")
def edit(employee_id):
    connection = get_db()
    current = connection.execute("SELECT * FROM employees WHERE id = ?", (employee_id,)).fetchone()
    if current is None:
        abort(404)
    form = dict(current)
    errors = []
    if request.method == "POST":
        with write_tx() as tx:
            form, errors = _validate(tx, request.form, employee_id)
            if not errors:
                tx.execute(
                    """
                    UPDATE employees
                    SET employee_number = ?, full_name = ?, department = ?, position = ?, email = ?,
                        employment_status = ?, ict_access_status = ?, hire_date = ?, left_date = ?
                    WHERE id = ?
                    """,
                    (
                        form["employee_number"],
                        form["full_name"],
                        form["department"],
                        form["position"],
                        form["email"] or None,
                        form["employment_status"],
                        form["ict_access_status"],
                        form["hire_date"] or None,
                        form["left_date"] or None,
                        employee_id,
                    ),
                )
                review_id, opened = maybe_open_review(
                    tx,
                    employee_id,
                    current["employment_status"],
                    form["employment_status"],
                    "employee record",
                )
                write_audit(tx, current_user()["id"], "Updated employee", "employee", employee_id, form["full_name"])
                if opened:
                    write_audit(
                        tx,
                        current_user()["id"],
                        "Opened access review",
                        "access_review",
                        review_id,
                        f"Status changed to {form['employment_status']}.",
                    )
        if not errors:
            flash("Employee record updated.", "success")
            if opened:
                flash("An access review was opened for this status change.", "info")
            return redirect(url_for("employees.detail", employee_id=employee_id))
    return render_template("employees/form.html", form=form, errors=errors, editing=True, employee_id=employee_id)
