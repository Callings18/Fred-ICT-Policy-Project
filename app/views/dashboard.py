from flask import Blueprint, render_template

from app.auth import current_user, permission_required
from app.constants import SEVERITIES
from app.db import get_db
from app.reports import allowed_report_types

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@permission_required("view_dashboard")
def index():
    user = current_user()
    permissions = user["permissions"]
    connection = get_db()
    metrics = {
        "active_employees": _count(connection, "SELECT COUNT(*) FROM employees WHERE employment_status = 'ACTIVE'"),
        "pending_reviews": _count(connection, "SELECT COUNT(*) FROM access_reviews WHERE status = 'PENDING'"),
        "leavers": _count(
            connection,
            "SELECT COUNT(*) FROM employees WHERE employment_status = 'LEFT' AND ict_access_status = 'ACTIVE'",
        ),
    }
    show_alerts = "view_alerts" in permissions
    show_findings = "view_findings" in permissions
    show_activity_total = "view_activities" in permissions or "generate_reports" in permissions
    if show_findings:
        metrics["open_findings"] = _count(connection, "SELECT COUNT(*) FROM findings WHERE status = 'OPEN'")
    if show_alerts:
        metrics["open_alerts"] = _count(connection, "SELECT COUNT(*) FROM alerts WHERE status = 'OPEN'")
        metrics["reviewed_alerts"] = _count(connection, "SELECT COUNT(*) FROM alerts WHERE status = 'REVIEWED'")
        metrics["unresolved_alerts"] = _count(
            connection,
            "SELECT COUNT(*) FROM alerts WHERE status IN ('OPEN', 'ESCALATED')",
        )
        metrics["serious_alerts"] = _count(
            connection,
            "SELECT COUNT(*) FROM alerts WHERE status = 'OPEN' AND severity IN ('HIGH', 'CRITICAL')",
        )
        counts = {level: 0 for level in SEVERITIES}
        for row in connection.execute(
            "SELECT severity, COUNT(*) AS total FROM alerts WHERE status = 'OPEN' GROUP BY severity"
        ):
            counts[row["severity"]] = row["total"]
        peak = max(counts.values()) or 1
        severity_bars = [
            {"severity": level, "count": counts[level], "pct": round(counts[level] * 100 / peak)}
            for level in SEVERITIES
        ]
        recent_alerts = connection.execute(
            """
            SELECT al.id, al.rule_name, al.severity, al.status, al.created_at, e.full_name
            FROM alerts al
            JOIN employees e ON e.id = al.employee_id
            ORDER BY al.created_at DESC, al.id DESC
            LIMIT 8
            """
        ).fetchall()
    else:
        severity_bars = []
        recent_alerts = []
    if show_activity_total:
        metrics["activities"] = _count(connection, "SELECT COUNT(*) FROM activities")
    recent_activities = []
    if "view_activities" in permissions:
        recent_activities = connection.execute(
            """
            SELECT a.id, a.activity_type, a.occurred_at, a.application, e.full_name, d.hostname
            FROM activities a
            JOIN employees e ON e.id = a.employee_id
            LEFT JOIN devices d ON d.id = a.device_id
            ORDER BY a.occurred_at DESC, a.id DESC
            LIMIT 8
            """
        ).fetchall()
    leavers = connection.execute(
        """
        SELECT id, full_name, department, left_date, employee_number
        FROM employees
        WHERE employment_status = 'LEFT' AND ict_access_status = 'ACTIVE'
        ORDER BY left_date DESC, full_name
        """
    ).fetchall()
    pending = connection.execute(
        """
        SELECT ar.id, ar.reason, ar.created_at, e.full_name, e.department
        FROM access_reviews ar
        JOIN employees e ON e.id = ar.employee_id
        WHERE ar.status = 'PENDING'
        ORDER BY ar.created_at DESC
        LIMIT 5
        """
    ).fetchall()
    recent_reports = []
    type_keys = [key for key, _label in allowed_report_types(permissions)]
    if type_keys and "view_reports" in permissions:
        marks = ",".join("?" for _ in type_keys)
        recent_reports = connection.execute(
            f"""
            SELECT id, title, report_type, created_at
            FROM reports
            WHERE report_type IN ({marks})
            ORDER BY created_at DESC
            LIMIT 5
            """,
            type_keys,
        ).fetchall()
    return render_template(
        "dashboard.html",
        metrics=metrics,
        show_alerts=show_alerts,
        show_findings=show_findings,
        show_activity_total=show_activity_total,
        show_activity_list="view_activities" in permissions,
        severity_bars=severity_bars,
        recent_alerts=recent_alerts,
        recent_activities=recent_activities,
        leavers=leavers,
        pending=pending,
        recent_reports=recent_reports,
    )


@bp.route("/help", endpoint="help")
@permission_required("view_dashboard")
def help_page():
    return render_template("help.html")


def _count(connection, sql):
    return connection.execute(sql).fetchone()[0]
