import re

import pymysql

from app.clock import now
from app.constants import LEAVING_STATUSES


def write_audit(connection, user_id, action, entity=None, entity_id=None, details=None):
    connection.execute(
        """
        INSERT INTO audit_logs (user_id, action, entity, entity_id, details, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, action, entity, entity_id, details, now()),
    )


def parse_window(value):
    match = re.fullmatch(r"(\d{2}):(\d{2})-(\d{2}):(\d{2})", (value or "").strip())
    if not match:
        return None
    hour_start, minute_start, hour_end, minute_end = (int(part) for part in match.groups())
    if hour_start > 23 or hour_end > 23 or minute_start > 59 or minute_end > 59:
        return None
    start = hour_start * 60 + minute_start
    end = hour_end * 60 + minute_end
    if start >= end:
        return None
    return start, end


def rule_matches(rule, activity):
    if rule["activity_type"] != "ANY" and rule["activity_type"] != activity["activity_type"]:
        return False
    kind = rule["condition_type"]
    value = rule["condition_value"] or ""
    occurred = activity["occurred_at"]
    if kind == "OUTSIDE_HOURS":
        window = parse_window(value)
        if window is None:
            return False
        try:
            from datetime import datetime

            moment = datetime.fromisoformat(occurred)
        except ValueError:
            return False
        minutes = moment.hour * 60 + moment.minute
        start, end = window
        return minutes < start or minutes >= end
    if kind == "WEEKEND":
        try:
            from datetime import datetime

            moment = datetime.fromisoformat(occurred)
        except ValueError:
            return False
        return moment.weekday() >= 5
    if kind == "APPLICATION_IN":
        application = (activity["application"] or "").strip().lower()
        if not application:
            return False
        names = [part.strip().lower() for part in value.split(",") if part.strip()]
        return any(name in application for name in names)
    if kind == "RESOURCE_CONTAINS":
        haystack = f"{activity['resource'] or ''} {activity['details'] or ''}".lower()
        keys = [part.strip().lower() for part in value.split(",") if part.strip()]
        return any(key in haystack for key in keys)
    if kind == "DURATION_OVER":
        try:
            limit = int(value)
        except ValueError:
            return False
        duration = activity["duration_minutes"]
        return duration is not None and int(duration) > limit
    if kind == "EMPLOYEE_NOT_ACTIVE":
        if activity["employment_status"] == "ACTIVE":
            return False
        left = activity["left_date"]
        if not left:
            return True
        return str(occurred)[:10] >= str(left)[:10]
    return False


def notify_permission(connection, permission, title, body, href, exclude_user_id=None):
    recipients = connection.execute(
        """
        SELECT DISTINCT u.id
        FROM users u
        JOIN role_permissions rp ON rp.role_id = u.role_id
        JOIN permissions p ON p.id = rp.permission_id
        WHERE p.code = ? AND u.status = 'ACTIVE'
        """,
        (permission,),
    ).fetchall()
    for recipient in recipients:
        if exclude_user_id and recipient["id"] == exclude_user_id:
            continue
        connection.execute(
            """
            INSERT INTO notifications (user_id, title, body, href, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (recipient["id"], title, body[:300], href, now()),
        )


def organisation_name(connection):
    row = connection.execute("SELECT value FROM settings WHERE `key` = 'organisation_name'").fetchone()
    if row is None or not row["value"].strip():
        return "ICT Policy Monitoring"
    return row["value"]


def raise_alerts_for_activity(connection, activity_id):
    activity = connection.execute(
        """
        SELECT a.*, e.full_name, e.employment_status, e.left_date
        FROM activities a
        JOIN employees e ON e.id = a.employee_id
        WHERE a.id = ?
        """,
        (activity_id,),
    ).fetchone()
    rules = connection.execute("SELECT * FROM policy_rules WHERE status = 'ACTIVE'").fetchall()
    created = []
    for rule in rules:
        if not rule_matches(rule, activity):
            continue
        try:
            cursor = connection.execute(
                """
                INSERT INTO alerts (
                    activity_id, policy_rule_id, employee_id, rule_name, severity, status, created_at
                ) VALUES (?, ?, ?, ?, ?, 'OPEN', ?)
                """,
                (
                    activity_id,
                    rule["id"],
                    activity["employee_id"],
                    rule["name"],
                    rule["severity"],
                    now(),
                ),
            )
        except pymysql.err.IntegrityError:
            continue
        created.append({"id": cursor.lastrowid, "rule": rule["name"], "severity": rule["severity"]})
        notify_permission(
            connection,
            "review_alerts",
            "Alert for review",
            f"{activity['full_name']} — {rule['name']} ({rule['severity']})",
            f"/alerts/{cursor.lastrowid}",
        )
    return created


def record_activity(connection, fields, source):
    cursor = connection.execute(
        """
        INSERT INTO activities (
            employee_id, device_id, activity_type, application, resource,
            occurred_at, duration_minutes, details, source, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            fields["employee_id"],
            fields["device_id"],
            fields["activity_type"],
            fields.get("application") or None,
            fields.get("resource") or None,
            fields["occurred_at"],
            fields.get("duration_minutes"),
            fields.get("details") or None,
            source,
            now(),
        ),
    )
    activity_id = cursor.lastrowid
    alerts = raise_alerts_for_activity(connection, activity_id)
    return activity_id, alerts


def review_alert(connection, alert_id, reviewer_id, status, notes):
    if status not in ("REVIEWED", "DISMISSED", "ESCALATED"):
        raise ValueError("Choose a review outcome.")
    notes = (notes or "").strip()
    if not notes:
        raise ValueError("Add a note explaining the outcome. An alert is not a confirmed violation.")
    if len(notes) > 2000:
        raise ValueError("Keep the review note under 2000 characters.")
    row = connection.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
    if row is None:
        return None
    connection.execute(
        """
        UPDATE alerts
        SET status = ?, reviewer_id = ?, review_notes = ?, reviewed_at = ?
        WHERE id = ?
        """,
        (status, reviewer_id, notes, now(), alert_id),
    )
    if status == "ESCALATED":
        ensure_finding(connection, row, reviewer_id, notes)
    return row


def ensure_finding(connection, alert, user_id, notes):
    employee = connection.execute(
        "SELECT full_name FROM employees WHERE id = ?",
        (alert["employee_id"],),
    ).fetchone()
    title = f"{alert['rule_name']} — {employee['full_name']}"
    summary = (notes or "").strip()
    existing = connection.execute(
        "SELECT id, status FROM findings WHERE alert_id = ?",
        (alert["id"],),
    ).fetchone()
    if existing is None:
        cursor = connection.execute(
            """
            INSERT INTO findings (
                alert_id, employee_id, title, status, summary, opened_by, created_at
            ) VALUES (?, ?, ?, 'OPEN', ?, ?, ?)
            """,
            (alert["id"], alert["employee_id"], title, summary, user_id, now()),
        )
        finding_id = cursor.lastrowid
        opened = True
    elif existing["status"] == "CLOSED":
        connection.execute(
            """
            UPDATE findings
            SET status = 'OPEN', summary = ?, conclusion = NULL, closed_by = NULL, closed_at = NULL
            WHERE id = ?
            """,
            (summary, existing["id"]),
        )
        finding_id = existing["id"]
        opened = True
    else:
        return existing["id"], False
    notify_permission(
        connection,
        "view_findings",
        "Compliance finding opened",
        title,
        f"/findings/{finding_id}",
        exclude_user_id=user_id,
    )
    return finding_id, opened


def close_finding(connection, finding_id, user_id, conclusion):
    conclusion = (conclusion or "").strip()
    if not conclusion:
        raise ValueError("Add a conclusion. Closing a finding does not confirm a policy breach.")
    if len(conclusion) > 2000:
        raise ValueError("Keep the conclusion under 2000 characters.")
    row = connection.execute("SELECT * FROM findings WHERE id = ?", (finding_id,)).fetchone()
    if row is None:
        return None
    if row["status"] != "OPEN":
        return False
    connection.execute(
        """
        UPDATE findings
        SET status = 'CLOSED', conclusion = ?, closed_by = ?, closed_at = ?
        WHERE id = ?
        """,
        (conclusion, user_id, now(), finding_id),
    )
    return True


def ensure_access_review(connection, employee_id, reason, created_at=None):
    existing = connection.execute(
        """
        SELECT id FROM access_reviews
        WHERE employee_id = ? AND status = 'PENDING'
        """,
        (employee_id,),
    ).fetchone()
    if existing:
        return existing["id"], False
    cursor = connection.execute(
        """
        INSERT INTO access_reviews (employee_id, reason, status, created_at)
        VALUES (?, ?, 'PENDING', ?)
        """,
        (employee_id, reason, created_at or now()),
    )
    employee = connection.execute("SELECT full_name FROM employees WHERE id = ?", (employee_id,)).fetchone()
    notify_permission(
        connection,
        "complete_reviews",
        "Access review opened",
        f"{employee['full_name']} — {reason}",
        f"/reviews/{cursor.lastrowid}",
    )
    return cursor.lastrowid, True


def maybe_open_review(connection, employee_id, old_status, new_status, source):
    if new_status in LEAVING_STATUSES and old_status != new_status:
        reason = f"Employment status changed from {old_status} to {new_status} ({source})."
        return ensure_access_review(connection, employee_id, reason)
    return None, False


def complete_access_review(connection, review_id, reviewer_id, action, notes):
    if action not in ("REVIEW_ONLY", "REVOKE_ACCESS"):
        raise ValueError("Choose review only or revoke access.")
    notes = (notes or "").strip()
    if not notes:
        raise ValueError("Add a note describing the decision.")
    if len(notes) > 2000:
        raise ValueError("Keep the note under 2000 characters.")
    review = connection.execute("SELECT * FROM access_reviews WHERE id = ?", (review_id,)).fetchone()
    if review is None:
        return None
    if review["status"] != "PENDING":
        return False
    connection.execute(
        """
        UPDATE access_reviews
        SET status = 'COMPLETED', action = ?, reviewer_id = ?, notes = ?, completed_at = ?
        WHERE id = ?
        """,
        (action, reviewer_id, notes, now(), review_id),
    )
    if action == "REVOKE_ACCESS":
        connection.execute(
            "UPDATE employees SET ict_access_status = 'REVOKED' WHERE id = ?",
            (review["employee_id"],),
        )
        connection.execute(
            "UPDATE devices SET status = 'INACTIVE' WHERE employee_id = ?",
            (review["employee_id"],),
        )
    return True
