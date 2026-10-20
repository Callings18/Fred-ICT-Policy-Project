from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

from app.clock import at_days_ago, now, today
from app.constants import PERMISSIONS, ROLE_DESCRIPTIONS, ROLE_PERMISSIONS
from app.reports import build_report
from app.services import ensure_access_review, record_activity, review_alert, write_audit

DEMO_PASSWORD = "Monitor#2026"


def _weekdays(start_day, count, older_than=0):
    found = []
    day = max(start_day, older_than + 1)
    while len(found) < count and day < 80:
        if (datetime.now() - timedelta(days=day)).weekday() < 5:
            found.append(day)
        day += 1
    return found


def _on_weekday(weekday):
    day = 1
    while day < 21:
        if (datetime.now() - timedelta(days=day)).weekday() == weekday:
            return day
        day += 1
    raise RuntimeError("Could not find a matching weekday for the demonstration data.")


def seed(connection):
    for name, description in ROLE_DESCRIPTIONS.items():
        connection.execute(
            "INSERT INTO roles (name, description) VALUES (?, ?)",
            (name, description),
        )
    for code, label in PERMISSIONS:
        connection.execute("INSERT INTO permissions (code, name) VALUES (?, ?)", (code, label))
    roles = {row["name"]: row["id"] for row in connection.execute("SELECT id, name FROM roles")}
    permissions = {row["code"]: row["id"] for row in connection.execute("SELECT id, code FROM permissions")}
    for role_name, codes in ROLE_PERMISSIONS.items():
        for code in codes:
            connection.execute(
                "INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                (roles[role_name], permissions[code]),
            )

    weekdays = _weekdays(1, 6)
    leave_anchor = weekdays[0]
    left_day = leave_anchor + 6
    left_date = (datetime.now() - timedelta(days=left_day)).date().isoformat()
    employees = [
        ("EMP-1001", "Fred Likasi", "ICT", "System Administrator", "likasifred@gmail.com", "ACTIVE", "ACTIVE", "2016-03-14", None),
        ("EMP-1042", "Chanda Mulenga", "Finance", "Accountant", "chanda.mulenga@demo.local", "ACTIVE", "ACTIVE", "2021-04-12", None),
        ("EMP-1108", "Mutale Banda", "Human Resources", "HR Partner", "mutale.banda@demo.local", "ACTIVE", "ACTIVE", "2019-11-03", None),
        ("EMP-1077", "Joseph Phiri", "Operations", "Registry Clerk", "joseph.phiri@demo.local", "ACTIVE", "ACTIVE", "2023-01-16", None),
        ("EMP-1210", "Mwansa Tembo", "Procurement", "Buyer", "mwansa.tembo@demo.local", "ACTIVE", "ACTIVE", "2022-06-01", None),
        ("EMP-0984", "Bupe Zulu", "ICT", "Service Desk Analyst", "bupe.zulu@demo.local", "ACTIVE", "ACTIVE", "2020-02-24", None),
        ("EMP-1302", "Kondwani Mwale", "ICT", "Network Officer", "kondwani.mwale@demo.local", "ACTIVE", "ACTIVE", "2018-09-10", None),
        ("EMP-1419", "Thandiwe Lungu", "Human Resources", "HR Officer", "thandiwe.lungu@demo.local", "ACTIVE", "ACTIVE", "2017-05-22", None),
        ("EMP-1155", "Gift Bwalya", "Finance", "Accounts Assistant", "gift.bwalya@demo.local", "LEFT", "ACTIVE", "2021-08-19", left_date),
    ]
    employee_ids = {}
    created = now()
    for number, name, department, position, email, employment, access, hire, left in employees:
        cursor = connection.execute(
            """
            INSERT INTO employees (
                employee_number, full_name, department, position, email,
                employment_status, ict_access_status, hire_date, left_date, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (number, name, department, position, email, employment, access, hire, left, created),
        )
        employee_ids[number] = cursor.lastrowid

    password_hash = generate_password_hash(DEMO_PASSWORD)
    accounts = [
        ("admin", "Fred Likasi", "EMP-1001", "System Administrator"),
        ("officer", "Bupe Zulu", "EMP-0984", "ICT/Security Officer"),
        ("manager", "Patrick Sakala", None, "Management"),
        ("hr", "Thandiwe Lungu", "EMP-1419", "HR Officer"),
    ]
    user_ids = {}
    for username, full_name, employee_number, role_name in accounts:
        cursor = connection.execute(
            """
            INSERT INTO users (username, password_hash, full_name, employee_id, role_id, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?)
            """,
            (
                username,
                password_hash,
                full_name,
                employee_ids.get(employee_number) if employee_number else None,
                roles[role_name],
                created,
            ),
        )
        user_ids[username] = cursor.lastrowid

    devices = [
        ("ICT-WS-01", "10.10.1.1", "Windows 11", "EMP-1001"),
        ("FIN-WS-14", "10.10.4.14", "Windows 11", "EMP-1042"),
        ("HR-WS-02", "10.10.4.22", "Windows 11", "EMP-1108"),
        ("OPS-WS-09", "10.10.8.9", "Windows 11", "EMP-1077"),
        ("PROC-WS-03", "10.10.6.3", "Windows 11", "EMP-1210"),
        ("ICT-WS-11", "10.10.1.11", "Windows 11", "EMP-0984"),
        ("ICT-WS-18", "10.10.1.18", "Windows 11", "EMP-1302"),
        ("HR-WS-06", "10.10.4.6", "Windows 11", "EMP-1419"),
        ("FIN-WS-22", "10.10.4.28", "Windows 11", "EMP-1155"),
    ]
    device_ids = {}
    for hostname, ip_address, operating_system, employee_number in devices:
        cursor = connection.execute(
            """
            INSERT INTO devices (hostname, ip_address, operating_system, employee_id, status, registered_at)
            VALUES (?, ?, ?, ?, 'ACTIVE', ?)
            """,
            (hostname, ip_address, operating_system, employee_ids[employee_number], created),
        )
        device_ids[employee_number] = cursor.lastrowid

    rules = [
        ("After-hours sign-in", "LOGIN", "OUTSIDE_HOURS", "08:00-17:00", "HIGH", "Flags sign-ins outside the organisation working window of 08:00 to 17:00."),
        ("After-hours application use", "APPLICATION", "OUTSIDE_HOURS", "08:00-17:00", "MEDIUM", "Flags application use outside the organisation working window."),
        ("Weekend activity", "ANY", "WEEKEND", "SAT,SUN", "MEDIUM", "Flags any monitored activity on Saturday or Sunday."),
        ("Sensitive resource access", "RESOURCE_ACCESS", "RESOURCE_CONTAINS", "payroll,salary,hr-confidential,disciplinary", "CRITICAL", "Flags access to resources whose name suggests payroll or confidential HR data."),
        ("Unapproved application", "APPLICATION", "APPLICATION_IN", "utorrent,bittorrent,anydesk,teamviewer", "HIGH", "Flags applications that are not approved for organisational computers."),
        ("Unusually long application use", "APPLICATION", "DURATION_OVER", "240", "LOW", "Flags one application session longer than 240 minutes."),
        ("Activity after employment ended", "ANY", "EMPLOYEE_NOT_ACTIVE", "NOT_ACTIVE", "CRITICAL", "Flags activity on or after the date an employee left or transferred."),
    ]
    for name, activity_type, condition_type, condition_value, severity, description in rules:
        connection.execute(
            """
            INSERT INTO policy_rules (
                name, activity_type, condition_type, condition_value, severity, status,
                description, created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?)
            """,
            (name, activity_type, condition_type, condition_value, severity, description, user_ids["admin"], created),
        )

    routine = [number for number, *_rest in employees if number != "EMP-1155"]
    applications = ["Microsoft Outlook", "Microsoft Excel", "Google Chrome", "Microsoft Word", "SAP"]
    for index, number in enumerate(routine):
        for offset in weekdays:
            record_activity(
                connection,
                {
                    "employee_id": employee_ids[number],
                    "device_id": device_ids[number],
                    "activity_type": "LOGIN",
                    "application": "",
                    "resource": "",
                    "occurred_at": at_days_ago(offset, 8, 12),
                    "duration_minutes": None,
                    "details": "Interactive sign-in on an authorised device.",
                },
                "SEED",
            )
            record_activity(
                connection,
                {
                    "employee_id": employee_ids[number],
                    "device_id": device_ids[number],
                    "activity_type": "APPLICATION",
                    "application": applications[index % len(applications)],
                    "resource": "",
                    "occurred_at": at_days_ago(offset, 9, 20),
                    "duration_minutes": 55,
                    "details": "Routine organisational use.",
                },
                "SEED",
            )
            record_activity(
                connection,
                {
                    "employee_id": employee_ids[number],
                    "device_id": device_ids[number],
                    "activity_type": "LOGOUT",
                    "application": "",
                    "resource": "",
                    "occurred_at": at_days_ago(offset, 16, 35),
                    "duration_minutes": None,
                    "details": "User signed out.",
                },
                "SEED",
            )
        record_activity(
            connection,
            {
                "employee_id": employee_ids[number],
                "device_id": device_ids[number],
                "activity_type": "NETWORK",
                "application": "Corporate VPN",
                "resource": "vpn-gateway",
                "occurred_at": at_days_ago(weekdays[0], 8, 20),
                "duration_minutes": None,
                "details": "Corporate VPN session established.",
            },
            "SEED",
        )

    history_days = _weekdays(1, 2, older_than=left_day)
    for offset, hour, activity_type, application in (
        (history_days[0], 10, "LOGIN", ""),
        (history_days[1], 11, "APPLICATION", "Microsoft Excel"),
    ):
        record_activity(
            connection,
            {
                "employee_id": employee_ids["EMP-1155"],
                "device_id": device_ids["EMP-1155"],
                "activity_type": activity_type,
                "application": application,
                "resource": "",
                "occurred_at": at_days_ago(offset, hour, 5),
                "duration_minutes": 40 if application else None,
                "details": "Activity recorded while the employee was still in post.",
            },
            "SEED",
        )

    scripted = [
        ("EMP-1042", "LOGIN", "", "", at_days_ago(weekdays[0], 22, 15), None, "Sign-in outside the published working window."),
        ("EMP-1077", "APPLICATION", "uTorrent", "", at_days_ago(weekdays[1], 14, 10), 15, "Application start recorded on the registry workstation."),
        ("EMP-1108", "RESOURCE_ACCESS", "SAP", "payroll-register", at_days_ago(weekdays[2], 11, 5), 20, "Opened the monthly payroll register."),
        ("EMP-1210", "APPLICATION", "Microsoft Excel", "", at_days_ago(weekdays[3], 9, 0), 310, "Workbook left open through a long procurement exercise."),
        ("EMP-0984", "LOGIN", "", "", at_days_ago(_on_weekday(5), 10, 20), None, "Saturday sign-in from the service desk."),
        ("EMP-1155", "LOGIN", "", "", at_days_ago(weekdays[0], 10, 5), None, "Sign-in after the recorded leaving date."),
    ]
    for number, activity_type, application, resource, occurred_at, duration, details in scripted:
        record_activity(
            connection,
            {
                "employee_id": employee_ids[number],
                "device_id": device_ids[number],
                "activity_type": activity_type,
                "application": application,
                "resource": resource,
                "occurred_at": occurred_at,
                "duration_minutes": duration,
                "details": details,
            },
            "SEED",
        )

    def alert_for(employee_number, rule_name):
        return connection.execute(
            """
            SELECT a.id
            FROM alerts a
            JOIN employees e ON e.id = a.employee_id
            WHERE e.employee_number = ? AND a.rule_name = ?
            ORDER BY a.id DESC
            LIMIT 1
            """,
            (employee_number, rule_name),
        ).fetchone()

    after_hours = alert_for("EMP-1042", "After-hours sign-in")
    unapproved = alert_for("EMP-1077", "Unapproved application")
    review_alert(
        connection,
        after_hours["id"],
        user_ids["officer"],
        "REVIEWED",
        "Checked with the service desk. This sign-in was an approved on-call maintenance session. No further action.",
    )
    review_alert(
        connection,
        unapproved["id"],
        user_ids["officer"],
        "DISMISSED",
        "ICT confirmed uTorrent was opened during a controlled software-removal test. The activity is not a policy breach.",
    )
    write_audit(connection, user_ids["officer"], "Reviewed alert", "alert", after_hours["id"], "Outcome set to reviewed after an on-call check.")
    write_audit(connection, user_ids["officer"], "Reviewed alert", "alert", unapproved["id"], "Outcome set to dismissed after a software-removal test was confirmed.")

    review_id, _created = ensure_access_review(
        connection,
        employee_ids["EMP-1155"],
        "Employment status is LEFT and ICT access is still active. Review whether accounts and devices should be revoked.",
        at_days_ago(left_day, 9, 0),
    )
    write_audit(
        connection,
        user_ids["hr"],
        "Opened access review",
        "access_review",
        review_id,
        "Gift Bwalya left the organisation with ICT access still active.",
    )

    start = (datetime.now().date() - timedelta(days=30)).isoformat()
    report_id = build_report(
        connection,
        user_ids["manager"],
        "compliance",
        {"date_from": start, "date_to": today(), "employee_id": "", "severity": "", "status": ""},
    )
    write_audit(connection, user_ids["manager"], "Generated report", "report", report_id, "Compliance summary for the demonstration dataset.")
    write_audit(
        connection,
        user_ids["admin"],
        "Loaded demonstration data",
        "system",
        None,
        "Demonstration employees, devices, activities, rules, and alerts were loaded.",
    )
