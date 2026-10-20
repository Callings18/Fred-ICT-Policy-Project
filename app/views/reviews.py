from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.auth import can, current_user, permission_required
from app.constants import REVIEW_ACTIONS
from app.db import get_db, write_tx
from app.services import complete_access_review, write_audit
from app import paging

bp = Blueprint("reviews", __name__, url_prefix="/reviews")


@bp.route("/", strict_slashes=False)
@permission_required("view_reviews")
def index():
    connection = get_db()
    status = request.args.get("status", "")
    clauses = ["1 = 1"]
    params = []
    if status in ("PENDING", "COMPLETED"):
        clauses.append("ar.status = ?")
        params.append(status)
    where = " AND ".join(clauses)
    total = connection.execute(
        f"SELECT COUNT(*) FROM access_reviews ar WHERE {where}",
        params,
    ).fetchone()[0]
    pager = paging(total)
    rows = connection.execute(
        f"""
        SELECT ar.*, e.full_name, e.department, e.employment_status, e.ict_access_status
        FROM access_reviews ar
        JOIN employees e ON e.id = ar.employee_id
        WHERE {where}
        ORDER BY CASE ar.status WHEN 'PENDING' THEN 0 ELSE 1 END, ar.created_at DESC
        LIMIT ? OFFSET ?
        """,
        [*params, pager["per_page"], pager["offset"]],
    ).fetchall()
    return render_template("reviews/index.html", rows=rows, pager=pager, status=status)


@bp.route("/<int:review_id>", methods=["GET", "POST"])
@permission_required("view_reviews")
def detail(review_id):
    errors = []
    if request.method == "POST":
        if not can("complete_reviews"):
            abort(403)
        action = request.form.get("action", "")
        notes = request.form.get("notes", "")
        try:
            with write_tx() as connection:
                result = complete_access_review(connection, review_id, current_user()["id"], action, notes)
                if result is None:
                    abort(404)
                if result is False:
                    errors = ["This review has already been completed."]
                else:
                    employee = connection.execute(
                        "SELECT full_name FROM employees e JOIN access_reviews ar ON ar.employee_id = e.id WHERE ar.id = ?",
                        (review_id,),
                    ).fetchone()
                    detail_text = f"{action} for {employee['full_name']}."
                    if action == "REVOKE_ACCESS":
                        detail_text += " ICT access marked revoked and assigned devices set inactive. The identity provider is not changed by this record."
                    write_audit(
                        connection,
                        current_user()["id"],
                        "Completed access review",
                        "access_review",
                        review_id,
                        detail_text,
                    )
            if not errors:
                flash("Access review completed.", "success")
                return redirect(url_for("reviews.detail", review_id=review_id))
        except ValueError as exc:
            errors = [str(exc)]
    connection = get_db()
    review = connection.execute(
        """
        SELECT ar.*, e.full_name, e.employee_number, e.department, e.position,
               e.employment_status, e.ict_access_status, e.left_date, e.email,
               u.full_name AS reviewer_name
        FROM access_reviews ar
        JOIN employees e ON e.id = ar.employee_id
        LEFT JOIN users u ON u.id = ar.reviewer_id
        WHERE ar.id = ?
        """,
        (review_id,),
    ).fetchone()
    if review is None:
        abort(404)
    devices = connection.execute(
        "SELECT hostname, ip_address, operating_system, status FROM devices WHERE employee_id = ? ORDER BY hostname",
        (review["employee_id"],),
    ).fetchall()
    later_count = connection.execute(
        """
        SELECT COUNT(*) FROM activities
        WHERE employee_id = ? AND (? IS NULL OR occurred_at >= ?)
        """,
        (review["employee_id"], review["left_date"], (review["left_date"] or "") + "T00:00:00"),
    ).fetchone()[0]
    later_activities = []
    if can("view_activities"):
        later_activities = connection.execute(
            """
            SELECT a.id, a.activity_type, a.application, a.resource, a.occurred_at, d.hostname
            FROM activities a
            LEFT JOIN devices d ON d.id = a.device_id
            WHERE a.employee_id = ? AND (? IS NULL OR a.occurred_at >= ?)
            ORDER BY a.occurred_at DESC
            LIMIT 15
            """,
            (review["employee_id"], review["left_date"], (review["left_date"] or "") + "T00:00:00"),
        ).fetchall()
    return render_template(
        "reviews/detail.html",
        review=review,
        devices=devices,
        later_count=later_count,
        later_activities=later_activities,
        show_activities=can("view_activities"),
        actions=REVIEW_ACTIONS,
        errors=errors,
        form_action=request.form.get("action", ""),
        form_notes=request.form.get("notes", review["notes"] or ""),
    )
