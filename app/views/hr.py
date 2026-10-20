from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.auth import current_user, permission_required
from app.clock import today
from app.constants import EMPLOYMENT_STATUSES, LEAVING_STATUSES
from app.db import get_db, write_tx
from app.services import maybe_open_review, write_audit
from app.validate import clean, parse_date

bp = Blueprint("hr", __name__, url_prefix="/hr")


@bp.route("/", methods=["GET", "POST"], strict_slashes=False)
@permission_required("hr_sync")
def index():
    connection = get_db()
    form = {"employee_number": "", "employment_status": "LEFT", "left_date": today()}
    errors = []
    if request.method == "POST":
        form = {
            "employee_number": clean(request.form.get("employee_number"), 20).upper(),
            "employment_status": request.form.get("employment_status", ""),
            "left_date": request.form.get("left_date", ""),
        }
        if form["employment_status"] not in EMPLOYMENT_STATUSES:
            errors.append("Choose an employment status.")
        try:
            form["left_date"] = parse_date(form["left_date"], "effective date")
        except ValueError as exc:
            errors.append(str(exc))
        if not errors:
            with write_tx() as tx:
                employee = tx.execute(
                    "SELECT * FROM employees WHERE employee_number = ?",
                    (form["employee_number"],),
                ).fetchone()
                if employee is None:
                    errors.append("No employee was found with that number.")
                else:
                    left_date = form["left_date"]
                    if form["employment_status"] == "ACTIVE":
                        left_date = None
                    elif form["employment_status"] in LEAVING_STATUSES and not left_date:
                        left_date = employee["left_date"] or today()
                    tx.execute(
                        "UPDATE employees SET employment_status = ?, left_date = ? WHERE id = ?",
                        (form["employment_status"], left_date, employee["id"]),
                    )
                    review_id, opened = maybe_open_review(
                        tx,
                        employee["id"],
                        employee["employment_status"],
                        form["employment_status"],
                        "HR intake",
                    )
                    write_audit(
                        tx,
                        current_user()["id"],
                        "HR status update",
                        "employee",
                        employee["id"],
                        f"{employee['full_name']} set to {form['employment_status']}.",
                    )
                    if opened:
                        write_audit(
                            tx,
                            current_user()["id"],
                            "Opened access review",
                            "access_review",
                            review_id,
                            employee["full_name"],
                        )
            if not errors:
                flash(f"Employment status for {form['employee_number']} is now {form['employment_status']}.", "success")
                if opened:
                    flash("A pending access review was opened for ICT to decide on access.", "info")
                return redirect(url_for("hr.index"))
    recent = connection.execute(
        """
        SELECT employee_number, full_name, department, employment_status, ict_access_status, left_date
        FROM employees
        ORDER BY created_at DESC, full_name
        LIMIT 8
        """
    ).fetchall()
    return render_template(
        "hr/index.html",
        form=form,
        errors=errors,
        recent=recent,
        statuses=EMPLOYMENT_STATUSES,
    )
