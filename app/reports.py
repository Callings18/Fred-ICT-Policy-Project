import json

from app.clock import human_date, human_enum, human_when, now
from app.constants import REPORT_TYPES


def allowed_report_types(permissions):
    allowed = []
    for key, (label, permission) in REPORT_TYPES.items():
        if permission in permissions:
            allowed.append((key, label))
    return allowed


def can_read_report(permissions, report_type):
    if "view_reports" not in permissions:
        return False
    spec = REPORT_TYPES.get(report_type)
    if spec is None:
        return False
    return spec[1] in permissions


def _between(column, filters, clauses, params):
    if filters.get("date_from"):
        clauses.append(f"{column} >= ?")
        params.append(filters["date_from"] + "T00:00:00")
    if filters.get("date_to"):
        clauses.append(f"{column} <= ?")
        params.append(filters["date_to"] + "T23:59:59")


def describe_filters(filters, employee_name):
    parts = []
    if filters.get("date_from") or filters.get("date_to"):
        parts.append(f"{human_date(filters.get('date_from'))} to {human_date(filters.get('date_to'))}")
    if employee_name:
        parts.append(employee_name)
    if filters.get("severity"):
        parts.append(filters["severity"])
    if filters.get("status"):
        parts.append(human_enum(filters["status"]))
    return ", ".join(parts) if parts else "All current records"


def _table_report(connection, report_type, filters):
    clauses = ["1 = 1"]
    params = []
    employee_id = filters.get("employee_id") or None
    if report_type == "activities":
        _between("a.occurred_at", filters, clauses, params)
        if employee_id:
            clauses.append("a.employee_id = ?")
            params.append(employee_id)
        sql = f"""
            SELECT a.occurred_at, e.full_name, e.department, d.hostname, a.activity_type,
                   a.application, a.resource, a.duration_minutes, a.source
            FROM activities a
            JOIN employees e ON e.id = a.employee_id
            LEFT JOIN devices d ON d.id = a.device_id
            WHERE {" AND ".join(clauses)}
            ORDER BY a.occurred_at DESC, a.id DESC
            LIMIT 1001
        """
        rows = connection.execute(sql, params).fetchall()
        truncated = len(rows) > 1000
        body = []
        for row in rows[:1000]:
            duration = "—" if row["duration_minutes"] is None else str(row["duration_minutes"])
            body.append([
                human_when(row["occurred_at"]),
                row["full_name"],
                row["department"],
                row["hostname"] or "—",
                human_enum(row["activity_type"]),
                row["application"] or "—",
                row["resource"] or "—",
                duration,
                human_enum(row["source"]),
            ])
        columns = ["When", "Employee", "Department", "Device", "Type", "Application", "Resource", "Minutes", "Source"]
        return columns, body, truncated

    if report_type == "alerts":
        _between("al.created_at", filters, clauses, params)
        if employee_id:
            clauses.append("al.employee_id = ?")
            params.append(employee_id)
        if filters.get("severity"):
            clauses.append("al.severity = ?")
            params.append(filters["severity"])
        if filters.get("status"):
            clauses.append("al.status = ?")
            params.append(filters["status"])
        sql = f"""
            SELECT al.created_at, e.full_name, e.department, al.rule_name, al.severity,
                   al.status, a.activity_type, a.occurred_at
            FROM alerts al
            JOIN employees e ON e.id = al.employee_id
            JOIN activities a ON a.id = al.activity_id
            WHERE {" AND ".join(clauses)}
            ORDER BY al.created_at DESC, al.id DESC
            LIMIT 1001
        """
        rows = connection.execute(sql, params).fetchall()
        truncated = len(rows) > 1000
        body = [
            [
                human_when(row["created_at"]),
                row["full_name"],
                row["department"],
                row["rule_name"],
                row["severity"],
                human_enum(row["status"]),
                human_enum(row["activity_type"]),
                human_when(row["occurred_at"]),
            ]
            for row in rows[:1000]
        ]
        columns = ["Raised", "Employee", "Department", "Rule", "Severity", "Status", "Activity", "Activity time"]
        return columns, body, truncated

    if report_type == "findings":
        _between("f.created_at", filters, clauses, params)
        if employee_id:
            clauses.append("f.employee_id = ?")
            params.append(employee_id)
        sql = f"""
            SELECT f.created_at, e.full_name, e.department, f.title, f.status,
                   al.severity, f.closed_at
            FROM findings f
            JOIN employees e ON e.id = f.employee_id
            JOIN alerts al ON al.id = f.alert_id
            WHERE {" AND ".join(clauses)}
            ORDER BY f.created_at DESC, f.id DESC
            LIMIT 1001
        """
        rows = connection.execute(sql, params).fetchall()
        truncated = len(rows) > 1000
        body = [
            [
                human_when(row["created_at"]),
                row["full_name"],
                row["department"],
                row["title"],
                row["severity"],
                human_enum(row["status"]),
                human_when(row["closed_at"]),
            ]
            for row in rows[:1000]
        ]
        columns = ["Opened", "Employee", "Department", "Finding", "Severity", "Status", "Closed"]
        return columns, body, truncated

    if report_type == "access_reviews":
        _between("ar.created_at", filters, clauses, params)
        if employee_id:
            clauses.append("ar.employee_id = ?")
            params.append(employee_id)
        sql = f"""
            SELECT ar.created_at, e.full_name, e.department, ar.reason, ar.status,
                   ar.action, u.full_name AS reviewer, ar.completed_at
            FROM access_reviews ar
            JOIN employees e ON e.id = ar.employee_id
            LEFT JOIN users u ON u.id = ar.reviewer_id
            WHERE {" AND ".join(clauses)}
            ORDER BY ar.created_at DESC, ar.id DESC
            LIMIT 1001
        """
        rows = connection.execute(sql, params).fetchall()
        truncated = len(rows) > 1000
        body = [
            [
                human_when(row["created_at"]),
                row["full_name"],
                row["department"],
                row["reason"],
                human_enum(row["status"]),
                human_enum(row["action"]),
                row["reviewer"] or "—",
                human_when(row["completed_at"]),
            ]
            for row in rows[:1000]
        ]
        columns = ["Opened", "Employee", "Department", "Reason", "Status", "Action", "Reviewer", "Completed"]
        return columns, body, truncated

    _between("g.created_at", filters, clauses, params)
    sql = f"""
        SELECT g.created_at, u.full_name, u.username, g.action, g.entity, g.entity_id, g.details
        FROM audit_logs g
        LEFT JOIN users u ON u.id = g.user_id
        WHERE {" AND ".join(clauses)}
        ORDER BY g.created_at DESC, g.id DESC
        LIMIT 1001
    """
    rows = connection.execute(sql, params).fetchall()
    truncated = len(rows) > 1000
    body = []
    for row in rows[:1000]:
        actor = row["full_name"] or "System"
        if row["username"]:
            actor = f"{row['full_name']} ({row['username']})"
        record = "—" if row["entity_id"] is None else str(row["entity_id"])
        body.append([
            human_when(row["created_at"]),
            actor,
            row["action"],
            row["entity"] or "—",
            record,
            row["details"] or "—",
        ])
    columns = ["When", "User", "Action", "Entity", "Record", "Details"]
    return columns, body, truncated


def _compliance(connection, filters):
    activity_clauses = ["1 = 1"]
    activity_params = []
    alert_clauses = ["1 = 1"]
    alert_params = []
    _between("occurred_at", filters, activity_clauses, activity_params)
    _between("created_at", filters, alert_clauses, alert_params)
    if filters.get("employee_id"):
        activity_clauses.append("employee_id = ?")
        activity_params.append(filters["employee_id"])
        alert_clauses.append("employee_id = ?")
        alert_params.append(filters["employee_id"])

    activity_count = connection.execute(
        f"SELECT COUNT(*) FROM activities WHERE {' AND '.join(activity_clauses)}",
        activity_params,
    ).fetchone()[0]
    alert_count = connection.execute(
        f"SELECT COUNT(*) FROM alerts WHERE {' AND '.join(alert_clauses)}",
        alert_params,
    ).fetchone()[0]
    open_count = connection.execute(
        f"SELECT COUNT(*) FROM alerts WHERE status = 'OPEN' AND {' AND '.join(alert_clauses)}",
        alert_params,
    ).fetchone()[0]
    pending = connection.execute(
        "SELECT COUNT(*) FROM access_reviews WHERE status = 'PENDING'"
    ).fetchone()[0]
    summary = [
        {"label": "Monitored activities", "value": str(activity_count)},
        {"label": "Alerts raised", "value": str(alert_count)},
        {"label": "Alerts still open", "value": str(open_count)},
        {"label": "Pending access reviews", "value": str(pending)},
        {"label": "Open findings", "value": str(connection.execute("SELECT COUNT(*) FROM findings WHERE status = 'OPEN'").fetchone()[0])},
    ]
    severity_rows = connection.execute(
        f"""
        SELECT severity, COUNT(*) AS total
        FROM alerts
        WHERE {' AND '.join(alert_clauses)}
        GROUP BY severity
        ORDER BY CASE severity
            WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'MEDIUM' THEN 3 ELSE 4 END
        """,
        alert_params,
    ).fetchall()
    status_rows = connection.execute(
        f"""
        SELECT status, COUNT(*) AS total
        FROM alerts
        WHERE {' AND '.join(alert_clauses)}
        GROUP BY status
        ORDER BY status
        """,
        alert_params,
    ).fetchall()
    leavers = connection.execute(
        """
        SELECT full_name, department, left_date, ict_access_status
        FROM employees
        WHERE employment_status = 'LEFT' AND ict_access_status = 'ACTIVE'
        ORDER BY full_name
        """
    ).fetchall()
    tables = [
        {
            "title": "Alerts by severity",
            "columns": ["Severity", "Alerts"],
            "rows": [[row["severity"], str(row["total"])] for row in severity_rows] or [["—", "0"]],
        },
        {
            "title": "Alerts by status",
            "columns": ["Status", "Alerts"],
            "rows": [[human_enum(row["status"]), str(row["total"])] for row in status_rows] or [["—", "0"]],
        },
        {
            "title": "Leavers whose ICT access is still active",
            "columns": ["Employee", "Department", "Left", "ICT access"],
            "rows": [
                [row["full_name"], row["department"], human_date(row["left_date"]), human_enum(row["ict_access_status"])]
                for row in leavers
            ] or [["None", "—", "—", "—"]],
        },
    ]
    return {"kind": "compliance", "summary": summary, "tables": tables}


def build_report(connection, user_id, report_type, filters):
    label = REPORT_TYPES[report_type][0]
    employee_name = None
    if filters.get("employee_id"):
        employee = connection.execute(
            "SELECT full_name FROM employees WHERE id = ?",
            (filters["employee_id"],),
        ).fetchone()
        employee_name = employee["full_name"] if employee else None
    summary = describe_filters(filters, employee_name)
    if report_type == "compliance":
        content = _compliance(connection, filters)
    else:
        columns, rows, truncated = _table_report(connection, report_type, filters)
        content = {"kind": "table", "columns": columns, "rows": rows, "truncated": truncated}
    title = f"{label} — {summary}"
    cursor = connection.execute(
        """
        INSERT INTO reports (title, report_type, filter_summary, generated_by, created_at, content_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (title, report_type, summary, user_id, now(), json.dumps(content)),
    )
    return cursor.lastrowid
