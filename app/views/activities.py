from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.auth import current_user, permission_required
from app.constants import ACTIVITY_TYPES
from app.db import get_db, write_tx
from app.services import record_activity, write_audit
from app.validate import validate_activity
from app import paging, like

bp = Blueprint("activities", __name__, url_prefix="/activities")


@bp.route("/", strict_slashes=False)
@permission_required("view_activities")
def index():
    connection = get_db()
    clauses = ["1 = 1"]
    params = []
    q = request.args.get("q", "").strip()
    activity_type = request.args.get("type", "")
    employee_id = request.args.get("employee", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    if q:
        term = like(q)
        clauses.append(
            """(
                e.full_name LIKE ? ESCAPE '\\' OR e.employee_number LIKE ? ESCAPE '\\'
                OR IFNULL(a.application, '') LIKE ? ESCAPE '\\'
                OR IFNULL(a.resource, '') LIKE ? ESCAPE '\\'
                OR IFNULL(d.hostname, '') LIKE ? ESCAPE '\\'
            )"""
        )
        params.extend([term, term, term, term, term])
    if activity_type in ACTIVITY_TYPES:
        clauses.append("a.activity_type = ?")
        params.append(activity_type)
    if employee_id.isdigit():
        clauses.append("a.employee_id = ?")
        params.append(int(employee_id))
    if date_from:
        clauses.append("a.occurred_at >= ?")
        params.append(date_from + "T00:00:00")
    if date_to:
        clauses.append("a.occurred_at <= ?")
        params.append(date_to + "T23:59:59")
    where = " AND ".join(clauses)
    total = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM activities a
        JOIN employees e ON e.id = a.employee_id
        LEFT JOIN devices d ON d.id = a.device_id
        WHERE {where}
        """,
        params,
    ).fetchone()[0]
    pager = paging(total)
    rows = connection.execute(
        f"""
        SELECT a.*, e.full_name, e.employee_number, d.hostname
        FROM activities a
        JOIN employees e ON e.id = a.employee_id
        LEFT JOIN devices d ON d.id = a.device_id
        WHERE {where}
        ORDER BY a.occurred_at DESC, a.id DESC
        LIMIT ? OFFSET ?
        """,
        [*params, pager["per_page"], pager["offset"]],
    ).fetchall()
    employees = connection.execute(
        "SELECT id, full_name FROM employees ORDER BY full_name"
    ).fetchall()
    return render_template(
        "activities/index.html",
        rows=rows,
        pager=pager,
        employees=employees,
        activity_types=ACTIVITY_TYPES,
        filters={"q": q, "type": activity_type, "employee": employee_id, "date_from": date_from, "date_to": date_to},
    )


@bp.route("/new", methods=["GET", "POST"])
@permission_required("record_activities")
def new():
    connection = get_db()
    employees = connection.execute(
        "SELECT id, full_name, employee_number FROM employees ORDER BY full_name"
    ).fetchall()
    devices = connection.execute(
        """
        SELECT d.id, d.hostname, e.full_name
        FROM devices d
        LEFT JOIN employees e ON e.id = d.employee_id
        ORDER BY d.hostname
        """
    ).fetchall()
    form = {
        "employee_id": "",
        "device_id": "",
        "activity_type": "LOGIN",
        "application": "",
        "resource": "",
        "occurred_at": datetime.now().strftime("%Y-%m-%dT%H:%M"),
        "duration_minutes": "",
        "details": "",
    }
    errors = []
    if request.method == "POST":
        form.update({key: request.form.get(key, "") for key in form})
        with write_tx() as tx:
            fields, errors = validate_activity(tx, request.form)
            if not errors:
                activity_id, alerts = record_activity(tx, fields, "MANUAL")
                write_audit(
                    tx,
                    current_user()["id"],
                    "Recorded activity",
                    "activity",
                    activity_id,
                    f"Recorded {fields['activity_type']} from the monitoring form.",
                )
        if not errors:
            if alerts:
                names = ", ".join(item["rule"] for item in alerts)
                flash(f"Activity recorded. Flagged for review by: {names}.", "success")
            else:
                flash("Activity recorded. No policy rule matched.", "success")
            return redirect(url_for("activities.detail", activity_id=activity_id))
    return render_template(
        "activities/form.html",
        form=form,
        errors=errors,
        employees=employees,
        devices=devices,
        activity_types=ACTIVITY_TYPES,
    )


@bp.route("/<int:activity_id>")
@permission_required("view_activities")
def detail(activity_id):
    connection = get_db()
    activity = connection.execute(
        """
        SELECT a.*, e.full_name, e.employee_number, e.department, d.hostname, d.ip_address
        FROM activities a
        JOIN employees e ON e.id = a.employee_id
        LEFT JOIN devices d ON d.id = a.device_id
        WHERE a.id = ?
        """,
        (activity_id,),
    ).fetchone()
    if activity is None:
        abort(404)
    alerts = connection.execute(
        """
        SELECT id, rule_name, severity, status, created_at
        FROM alerts
        WHERE activity_id = ?
        ORDER BY id
        """,
        (activity_id,),
    ).fetchall()
    return render_template("activities/detail.html", activity=activity, alerts=alerts)
