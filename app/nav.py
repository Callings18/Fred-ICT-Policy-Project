NAV = [
    ("Overview", [
        ("dashboard.index", "Dashboard", "view_dashboard", None),
        ("notifications.index", "Notifications", "view_dashboard", "notifications"),
        ("dashboard.help", "How to use", "view_dashboard", None),
    ]),
    ("Monitoring", [
        ("activities.index", "Activities", "view_activities", None),
        ("alerts.index", "Alerts", "view_alerts", "alerts"),
        ("findings.index", "Findings", "view_findings", "findings"),
        ("policies.index", "Policy rules", "view_policies", None),
    ]),
    ("People and assets", [
        ("employees.index", "Employees", "view_employees", None),
        ("devices.index", "Devices", "view_devices", None),
        ("reviews.index", "Access reviews", "view_reviews", "reviews"),
    ]),
    ("Assurance", [
        ("reports.index", "Reports", "view_reports", None),
        ("auditlog.index", "Audit log", "view_audit", None),
    ]),
    ("Administration", [
        ("users.index", "Users", "manage_users", None),
        ("roles.index", "Roles and permissions", "manage_users", None),
        ("settings.index", "System settings", "manage_users", None),
        ("hr.index", "HR intake", "hr_sync", None),
    ]),
]
