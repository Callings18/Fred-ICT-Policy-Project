from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.auth import can, current_user, permission_required
from app.constants import REVIEW_OUTCOMES, SEVERITIES, ALERT_STATUSES
from app.db import get_db, write_tx
from app.services import review_alert, write_audit
from app import paging, like

bp = Blueprint("alerts", __name__, url_prefix="/alerts")


@bp.route("/", strict_slashes=False)
@permission_required("view_alerts")
def index():
    connection = get_db()
    clauses = ["1 = 1"]
    params = []
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    severity = request.args.get("severity", "")
    if q:
        term = like(q)
        clauses.append(
            "(e.full_name LIKE ? ESCAPE '\\' OR al.rule_name LIKE ? ESCAPE '\\' OR IFNULL(al.review_notes, '') LIKE ? ESCAPE '\\')"
        )
        params.extend([term, term, term])
    if status in ALERT_STATUSES:
        clauses.append("al.status = ?")
        params.append(status)
    if severity in SEVERITIES:
        clauses.append("al.severity = ?")
        params.append(severity)
    where = " AND ".join(clauses)
    total = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM alerts al
        JOIN employees e ON e.id = al.employee_id
        WHERE {where}
        """,
        params,
    ).fetchone()[0]
    pager = paging(total)
    rows = connection.execute(
        f"""
        SELECT al.*, e.full_name, e.department
        FROM alerts al
        JOIN employees e ON e.id = al.employee_id
        WHERE {where}
        ORDER BY CASE al.status WHEN 'OPEN' THEN 0 WHEN 'ESCALATED' THEN 1 ELSE 2 END,
                 al.created_at DESC, al.id DESC
        LIMIT ? OFFSET ?
        """,
        [*params, pager["per_page"], pager["offset"]],
    ).fetchall()
    return render_template(
        "alerts/index.html",
        rows=rows,
        pager=pager,
        statuses=ALERT_STATUSES,
        severities=SEVERITIES,
        filters={"q": q, "status": status, "severity": severity},
    )


@bp.route("/<int:alert_id>", methods=["GET", "POST"])
@permission_required("view_alerts")
def detail(alert_id):
    errors = []
    if request.method == "POST":
        if not can("review_alerts"):
            abort(403)
        outcome = request.form.get("status", "")
        notes = request.form.get("review_notes", "")
        try:
            with write_tx() as connection:
                row = review_alert(connection, alert_id, current_user()["id"], outcome, notes)
                if row is None:
                    abort(404)
                write_audit(
                    connection,
                    current_user()["id"],
                    "Reviewed alert",
                    "alert",
                    alert_id,
                    f"Outcome set to {outcome}.",
                )
            flash("Review saved. The outcome is a human decision, not an automatic finding.", "success")
            return redirect(url_for("alerts.detail", alert_id=alert_id))
        except ValueError as exc:
            errors = [str(exc)]
    connection = get_db()
    alert = connection.execute(
        """
        SELECT al.*, e.full_name, e.employee_number, e.department, e.employment_status,
               u.full_name AS reviewer_name
        FROM alerts al
        JOIN employees e ON e.id = al.employee_id
        LEFT JOIN users u ON u.id = al.reviewer_id
        WHERE al.id = ?
        """,
        (alert_id,),
    ).fetchone()
    if alert is None:
        abort(404)
    activity = connection.execute(
        """
        SELECT a.*, d.hostname
        FROM activities a
        LEFT JOIN devices d ON d.id = a.device_id
        WHERE a.id = ?
        """,
        (alert["activity_id"],),
    ).fetchone()
    finding = connection.execute(
        "SELECT id, status FROM findings WHERE alert_id = ?",
        (alert_id,),
    ).fetchone()
    return render_template(
        "alerts/detail.html",
        alert=alert,
        activity=activity,
        outcomes=REVIEW_OUTCOMES,
        errors=errors,
        form_status=request.form.get("status", alert["status"] if alert["status"] != "OPEN" else "REVIEWED"),
        form_notes=request.form.get("review_notes", alert["review_notes"] or ""),
        finding=finding,
    )
