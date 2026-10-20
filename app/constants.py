ROLE_ADMIN = "System Administrator"
ROLE_OFFICER = "ICT/Security Officer"
ROLE_MANAGEMENT = "Management"
ROLE_HR = "HR Officer"

PERMISSIONS = [
    ("view_dashboard", "View dashboard"),
    ("view_activities", "View activities"),
    ("record_activities", "Record activities"),
    ("view_alerts", "View alerts"),
    ("review_alerts", "Review alerts"),
    ("view_findings", "View compliance findings"),
    ("manage_findings", "Manage compliance findings"),
    ("view_policies", "View policy rules"),
    ("manage_policies", "Manage policy rules"),
    ("view_employees", "View employees"),
    ("manage_employees", "Manage employees"),
    ("view_devices", "View devices"),
    ("manage_devices", "Manage devices"),
    ("view_reviews", "View access reviews"),
    ("complete_reviews", "Complete access reviews"),
    ("view_reports", "View reports"),
    ("generate_reports", "Generate reports"),
    ("view_audit", "View audit log"),
    ("manage_users", "Manage users"),
    ("hr_sync", "Submit HR status updates"),
]

ROLE_PERMISSIONS = {
    ROLE_ADMIN: [code for code, _name in PERMISSIONS],
    ROLE_OFFICER: [
        "view_dashboard",
        "view_activities",
        "record_activities",
        "view_alerts",
        "review_alerts",
        "view_findings",
        "manage_findings",
        "view_policies",
        "view_employees",
        "view_devices",
        "manage_devices",
        "view_reviews",
        "complete_reviews",
        "view_reports",
        "generate_reports",
        "view_audit",
    ],
    ROLE_MANAGEMENT: [
        "view_dashboard",
        "view_alerts",
        "view_findings",
        "view_reports",
        "generate_reports",
    ],
    ROLE_HR: [
        "view_dashboard",
        "view_employees",
        "manage_employees",
        "view_reviews",
        "hr_sync",
    ],
}

ROLE_DESCRIPTIONS = {
    ROLE_ADMIN: "Manages accounts, policy rules, devices, and system security.",
    ROLE_OFFICER: "Reviews monitored activities and alerts, records compliance findings, and completes ICT access reviews.",
    ROLE_MANAGEMENT: "Views dashboards, alerts, and compliance reports for oversight.",
    ROLE_HR: "Maintains employee status and submits leavers for an ICT access review.",
}

ACTIVITY_TYPES = ["LOGIN", "LOGOUT", "APPLICATION", "RESOURCE_ACCESS", "NETWORK"]
SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
ALERT_STATUSES = ["OPEN", "REVIEWED", "DISMISSED", "ESCALATED"]
REVIEW_OUTCOMES = ["REVIEWED", "DISMISSED", "ESCALATED"]
EMPLOYMENT_STATUSES = ["ACTIVE", "LEFT", "TRANSFERRED"]
ACCESS_STATUSES = ["ACTIVE", "REVOKED"]
REVIEW_ACTIONS = ["REVIEW_ONLY", "REVOKE_ACCESS"]
ACCOUNT_STATUSES = ["ACTIVE", "INACTIVE"]
RULE_STATUSES = ["ACTIVE", "INACTIVE"]
DEVICE_STATUSES = ["ACTIVE", "INACTIVE"]
CONDITION_TYPES = ["OUTSIDE_HOURS", "WEEKEND", "APPLICATION_IN", "RESOURCE_CONTAINS", "DURATION_OVER", "EMPLOYEE_NOT_ACTIVE"]

CONDITION_HINTS = {
    "OUTSIDE_HOURS": "Use a same-day window such as 08:00-17:00. Events outside it are flagged.",
    "WEEKEND": "No extra value is required. Saturday and Sunday events are flagged.",
    "APPLICATION_IN": "Comma-separated application names. A match is case-insensitive.",
    "RESOURCE_CONTAINS": "Comma-separated words to look for in the resource or details.",
    "DURATION_OVER": "A whole number of minutes. Longer sessions are flagged.",
    "EMPLOYEE_NOT_ACTIVE": "Flags events on or after the leaving or transfer date.",
}

LEAVING_STATUSES = ("LEFT", "TRANSFERRED")

REPORT_TYPES = {
    "activities": ("Monitored activities", "view_activities"),
    "alerts": ("Policy alerts", "view_alerts"),
    "access_reviews": ("Access reviews", "view_reviews"),
    "audit": ("Audit log", "view_audit"),
    "compliance": ("Compliance summary", "view_reports"),
    "findings": ("Compliance findings", "view_findings"),
}
