import re
from contextlib import contextmanager

import pymysql
from flask import current_app, g
from pymysql.cursors import DictCursor

_NAME = re.compile(r"^[A-Za-z0-9_]+$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS roles (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(80) NOT NULL UNIQUE,
    description VARCHAR(500) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS permissions (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(120) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS role_permissions (
    role_id INT NOT NULL,
    permission_id INT NOT NULL,
    PRIMARY KEY (role_id, permission_id),
    CONSTRAINT fk_role_permissions_role FOREIGN KEY (role_id) REFERENCES roles(id),
    CONSTRAINT fk_role_permissions_permission FOREIGN KEY (permission_id) REFERENCES permissions(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS employees (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    employee_number VARCHAR(20) NOT NULL UNIQUE,
    full_name VARCHAR(120) NOT NULL,
    department VARCHAR(80) NOT NULL,
    position VARCHAR(80) NOT NULL,
    email VARCHAR(120),
    employment_status VARCHAR(20) NOT NULL,
    ict_access_status VARCHAR(20) NOT NULL,
    hire_date VARCHAR(10),
    left_date VARCHAR(10),
    created_at VARCHAR(32) NOT NULL,
    CONSTRAINT chk_employment CHECK (employment_status IN ('ACTIVE', 'LEFT', 'TRANSFERRED')),
    CONSTRAINT chk_access CHECK (ict_access_status IN ('ACTIVE', 'REVOKED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS users (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(32) NOT NULL UNIQUE,
    password_hash VARCHAR(512) NOT NULL,
    full_name VARCHAR(120) NOT NULL,
    employee_id INT NULL,
    role_id INT NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at VARCHAR(32) NOT NULL,
    last_login VARCHAR(32),
    CONSTRAINT chk_user_status CHECK (status IN ('ACTIVE', 'INACTIVE')),
    CONSTRAINT fk_users_employee FOREIGN KEY (employee_id) REFERENCES employees(id),
    CONSTRAINT fk_users_role FOREIGN KEY (role_id) REFERENCES roles(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS devices (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    hostname VARCHAR(63) NOT NULL UNIQUE,
    ip_address VARCHAR(45),
    operating_system VARCHAR(80) NOT NULL,
    employee_id INT NULL,
    status VARCHAR(20) NOT NULL,
    registered_at VARCHAR(32) NOT NULL,
    CONSTRAINT chk_device_status CHECK (status IN ('ACTIVE', 'INACTIVE')),
    CONSTRAINT fk_devices_employee FOREIGN KEY (employee_id) REFERENCES employees(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS policy_rules (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(160) NOT NULL,
    activity_type VARCHAR(32) NOT NULL,
    condition_type VARCHAR(40) NOT NULL,
    condition_value VARCHAR(500) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    description TEXT,
    created_by INT NULL,
    created_at VARCHAR(32) NOT NULL,
    updated_at VARCHAR(32),
    CONSTRAINT chk_rule_severity CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    CONSTRAINT chk_rule_status CHECK (status IN ('ACTIVE', 'INACTIVE')),
    CONSTRAINT fk_rules_user FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS activities (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    employee_id INT NOT NULL,
    device_id INT NULL,
    activity_type VARCHAR(32) NOT NULL,
    application VARCHAR(160),
    resource VARCHAR(200),
    occurred_at VARCHAR(32) NOT NULL,
    duration_minutes INT,
    details TEXT,
    source VARCHAR(32) NOT NULL,
    created_at VARCHAR(32) NOT NULL,
    CONSTRAINT chk_activity_type CHECK (activity_type IN ('LOGIN', 'LOGOUT', 'APPLICATION', 'RESOURCE_ACCESS', 'NETWORK')),
    CONSTRAINT fk_activities_employee FOREIGN KEY (employee_id) REFERENCES employees(id),
    CONSTRAINT fk_activities_device FOREIGN KEY (device_id) REFERENCES devices(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS alerts (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    activity_id INT NOT NULL,
    policy_rule_id INT NOT NULL,
    employee_id INT NOT NULL,
    rule_name VARCHAR(160) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    reviewer_id INT NULL,
    review_notes TEXT,
    created_at VARCHAR(32) NOT NULL,
    reviewed_at VARCHAR(32),
    UNIQUE KEY uq_alert_activity_rule (activity_id, policy_rule_id),
    CONSTRAINT chk_alert_severity CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    CONSTRAINT chk_alert_status CHECK (status IN ('OPEN', 'REVIEWED', 'DISMISSED', 'ESCALATED')),
    CONSTRAINT fk_alerts_activity FOREIGN KEY (activity_id) REFERENCES activities(id),
    CONSTRAINT fk_alerts_rule FOREIGN KEY (policy_rule_id) REFERENCES policy_rules(id),
    CONSTRAINT fk_alerts_employee FOREIGN KEY (employee_id) REFERENCES employees(id),
    CONSTRAINT fk_alerts_reviewer FOREIGN KEY (reviewer_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS access_reviews (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    employee_id INT NOT NULL,
    reason TEXT NOT NULL,
    status VARCHAR(20) NOT NULL,
    action VARCHAR(32),
    reviewer_id INT NULL,
    notes TEXT,
    created_at VARCHAR(32) NOT NULL,
    completed_at VARCHAR(32),
    CONSTRAINT chk_review_status CHECK (status IN ('PENDING', 'COMPLETED')),
    CONSTRAINT chk_review_action CHECK (action IS NULL OR action IN ('REVIEW_ONLY', 'REVOKE_ACCESS')),
    CONSTRAINT fk_reviews_employee FOREIGN KEY (employee_id) REFERENCES employees(id),
    CONSTRAINT fk_reviews_user FOREIGN KEY (reviewer_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS reports (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(300) NOT NULL,
    report_type VARCHAR(40) NOT NULL,
    filter_summary VARCHAR(300) NOT NULL,
    generated_by INT NULL,
    created_at VARCHAR(32) NOT NULL,
    content_json LONGTEXT NOT NULL,
    CONSTRAINT fk_reports_user FOREIGN KEY (generated_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS audit_logs (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    action VARCHAR(160) NOT NULL,
    entity VARCHAR(40),
    entity_id INT,
    details TEXT,
    created_at VARCHAR(32) NOT NULL,
    CONSTRAINT fk_audit_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS findings (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    alert_id INT NOT NULL UNIQUE,
    employee_id INT NOT NULL,
    title VARCHAR(300) NOT NULL,
    status VARCHAR(20) NOT NULL,
    summary TEXT NOT NULL,
    conclusion TEXT,
    opened_by INT NULL,
    closed_by INT NULL,
    created_at VARCHAR(32) NOT NULL,
    closed_at VARCHAR(32),
    CONSTRAINT chk_finding_status CHECK (status IN ('OPEN', 'CLOSED')),
    CONSTRAINT fk_findings_alert FOREIGN KEY (alert_id) REFERENCES alerts(id),
    CONSTRAINT fk_findings_employee FOREIGN KEY (employee_id) REFERENCES employees(id),
    CONSTRAINT fk_findings_opener FOREIGN KEY (opened_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_findings_closer FOREIGN KEY (closed_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS settings (
    `key` VARCHAR(80) PRIMARY KEY,
    value VARCHAR(200) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS notifications (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(160) NOT NULL,
    body VARCHAR(500) NOT NULL,
    href VARCHAR(300) NOT NULL,
    created_at VARCHAR(32) NOT NULL,
    read_at VARCHAR(32),
    CONSTRAINT fk_notifications_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IF NOT EXISTS idx_findings_status ON findings(status);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, read_at);
CREATE INDEX IF NOT EXISTS idx_activities_occurred ON activities(occurred_at);
CREATE INDEX IF NOT EXISTS idx_activities_employee ON activities(employee_id);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_employee ON alerts(employee_id);
CREATE INDEX IF NOT EXISTS idx_reviews_status ON access_reviews(status);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at);
"""


class Row(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return dict.__getitem__(self, key)


class Cursor:
    def __init__(self, raw):
        self._raw = raw
        self.lastrowid = raw.lastrowid

    def fetchone(self):
        row = self._raw.fetchone()
        if row is None:
            return None
        return Row(row)

    def fetchall(self):
        return [Row(row) for row in self._raw.fetchall()]

    def __iter__(self):
        return iter(self.fetchall())


class Connection:
    def __init__(self, raw):
        self._raw = raw

    def execute(self, sql, params=None):
        cursor = self._raw.cursor()
        cursor.execute(sql.replace("?", "%s"), params or ())
        return Cursor(cursor)

    def commit(self):
        self._raw.commit()

    def rollback(self):
        self._raw.rollback()

    def close(self):
        self._raw.close()

    def literal(self, value):
        return self._raw.escape(value)


def db_settings(config):
    name = config.get("DB_NAME") or "ipmcs"
    if not _NAME.match(name):
        raise ValueError("The database name may contain only letters, numbers, and underscores.")
    return {
        "host": config.get("DB_HOST") or "127.0.0.1",
        "port": int(config.get("DB_PORT") or 3306),
        "user": config.get("DB_USER") or "root",
        "password": config.get("DB_PASSWORD") or "",
        "database": name,
    }


def _connect(settings, database):
    return pymysql.connect(
        host=settings["host"],
        port=settings["port"],
        user=settings["user"],
        password=settings["password"],
        database=database,
        charset="utf8mb4",
        autocommit=False,
        cursorclass=DictCursor,
    )


def ensure_database(config):
    settings = db_settings(config)
    connection = pymysql.connect(
        host=settings["host"],
        port=settings["port"],
        user=settings["user"],
        password=settings["password"],
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{settings['database']}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        connection.close()
    return settings


def drop_database(config):
    settings = db_settings(config)
    connection = pymysql.connect(
        host=settings["host"],
        port=settings["port"],
        user=settings["user"],
        password=settings["password"],
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET SESSION lock_wait_timeout = 8")
            cursor.execute(
                "SELECT ID FROM information_schema.PROCESSLIST WHERE DB = %s AND ID <> CONNECTION_ID()",
                (settings["database"],),
            )
            for row in cursor.fetchall():
                cursor.execute(f"KILL {int(row['ID'])}")
            cursor.execute(f"DROP DATABASE IF EXISTS `{settings['database']}`")
    finally:
        connection.close()


def get_db():
    if "db" not in g:
        settings = db_settings(current_app.config)
        g.db = Connection(_connect(settings, settings["database"]))
    return g.db


@contextmanager
def write_tx():
    connection = get_db()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def init_db(app):
    ensure_database(app.config)
    with app.app_context():
        connection = get_db()
        for statement in _statements(SCHEMA):
            connection.execute(statement)
        if app.config.get("SEED", True):
            count = connection.execute("SELECT COUNT(*) AS total FROM roles").fetchone()["total"]
            if count == 0:
                from app.seed import seed

                seed(connection)
        connection.execute(
            """
            INSERT INTO settings (`key`, value)
            SELECT 'organisation_name', 'ICT Policy Monitoring'
            WHERE NOT EXISTS (SELECT 1 FROM settings WHERE `key` = 'organisation_name')
            """
        )
        _sync_access(connection)
        _backfill_notifications(connection)
        connection.commit()


def _statements(script):
    parts = []
    for chunk in script.split(";"):
        statement = chunk.strip()
        if statement:
            parts.append(statement)
    return parts


def _sync_access(connection):
    from app.constants import PERMISSIONS, ROLE_DESCRIPTIONS, ROLE_PERMISSIONS

    for code, label in PERMISSIONS:
        connection.execute(
            """
            INSERT INTO permissions (code, name) VALUES (?, ?)
            ON DUPLICATE KEY UPDATE name = VALUES(name)
            """,
            (code, label),
        )
    roles = {row["name"]: row["id"] for row in connection.execute("SELECT id, name FROM roles")}
    if not roles:
        return
    for name, description in ROLE_DESCRIPTIONS.items():
        connection.execute("UPDATE roles SET description = ? WHERE name = ?", (description, name))
    permissions = {row["code"]: row["id"] for row in connection.execute("SELECT id, code FROM permissions")}
    for role_name, codes in ROLE_PERMISSIONS.items():
        role_id = roles.get(role_name)
        if role_id is None:
            continue
        for code in codes:
            permission_id = permissions.get(code)
            if permission_id is None:
                continue
            connection.execute(
                "INSERT IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                (role_id, permission_id),
            )


def _backfill_notifications(connection):
    existing = connection.execute("SELECT COUNT(*) AS total FROM notifications").fetchone()["total"]
    if existing:
        return
    from app.services import notify_permission

    alerts = connection.execute(
        """
        SELECT al.id, al.rule_name, al.severity, e.full_name
        FROM alerts al
        JOIN employees e ON e.id = al.employee_id
        WHERE al.status = 'OPEN'
        ORDER BY al.id
        """
    ).fetchall()
    for alert in alerts:
        notify_permission(
            connection,
            "review_alerts",
            "Alert for review",
            f"{alert['full_name']} — {alert['rule_name']} ({alert['severity']})",
            f"/alerts/{alert['id']}",
        )
    reviews = connection.execute(
        """
        SELECT ar.id, ar.reason, e.full_name
        FROM access_reviews ar
        JOIN employees e ON e.id = ar.employee_id
        WHERE ar.status = 'PENDING'
        ORDER BY ar.id
        """
    ).fetchall()
    for review in reviews:
        notify_permission(
            connection,
            "complete_reviews",
            "Access review opened",
            f"{review['full_name']} — {review['reason']}",
            f"/reviews/{review['id']}",
        )


def dump_sql(connection):
    lines = [
        "-- ICT Policy Monitoring backup",
        "SET NAMES utf8mb4;",
        "SET FOREIGN_KEY_CHECKS=0;",
    ]
    tables = [list(row.values())[0] for row in connection.execute("SHOW TABLES").fetchall()]
    for table in tables:
        if not _NAME.match(table):
            continue
        created = connection.execute(f"SHOW CREATE TABLE `{table}`").fetchone()
        create_sql = list(created.values())[1]
        lines.append(f"DROP TABLE IF EXISTS `{table}`;")
        lines.append(create_sql + ";")
        rows = connection.execute(f"SELECT * FROM `{table}`").fetchall()
        if not rows:
            continue
        columns = list(rows[0].keys())
        column_sql = ", ".join(f"`{column}`" for column in columns)
        for row in rows:
            values = ", ".join(connection.literal(row[column]) for column in columns)
            lines.append(f"INSERT INTO `{table}` ({column_sql}) VALUES ({values});")
    lines.append("SET FOREIGN_KEY_CHECKS=1;")
    return "\n".join(lines) + "\n"


def close_db(_exception=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()
