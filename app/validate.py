import ipaddress
import re
from datetime import datetime

from app.constants import ACTIVITY_TYPES

HOSTNAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]{0,62}$")
EMPLOYEE_NUMBER = re.compile(r"^[A-Za-z0-9-]{2,20}$")
USERNAME = re.compile(r"^[a-z0-9._-]{3,32}$")


def clean(value, limit=120):
    if value is None:
        return ""
    return " ".join(str(value).split())[:limit]


def clean_text(value, limit=2000):
    if value is None:
        return ""
    text = str(value).replace("\r\n", "\n").strip()
    return text[:limit]


def acceptable_password(password):
    return bool(password) and len(password) >= 8 and re.search(r"[A-Za-z]", password) and re.search(r"\d", password)


def parse_occurred(value):
    raw = (value or "").strip()
    if not raw:
        raise ValueError("Enter the date and time of the activity.")
    if len(raw) == 16:
        raw = raw + ":00"
    try:
        datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("Enter a valid date and time.") from exc
    return raw


def parse_duration(value):
    if value is None or str(value).strip() == "":
        return None
    try:
        number = int(str(value).strip())
    except ValueError as exc:
        raise ValueError("Duration must be a whole number of minutes.") from exc
    if number < 0 or number > 100000:
        raise ValueError("Duration is out of range.")
    return number


def parse_date(value, label):
    raw = (value or "").strip()
    if not raw:
        return ""
    try:
        datetime.strptime(raw, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"Enter a valid {label}.") from exc
    return raw


def valid_ip(value):
    if not value:
        return True
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def _employee(connection, data):
    if data.get("employee_id"):
        try:
            employee_id = int(data.get("employee_id"))
        except (TypeError, ValueError) as exc:
            raise ValueError("Choose an employee.") from exc
        return connection.execute("SELECT * FROM employees WHERE id = ?", (employee_id,)).fetchone()
    number = clean(data.get("employee_number"), 20)
    if number:
        return connection.execute(
            "SELECT * FROM employees WHERE employee_number = ?",
            (number,),
        ).fetchone()
    return None


def _device(connection, data):
    if data.get("device_id"):
        try:
            device_id = int(data.get("device_id"))
        except (TypeError, ValueError) as exc:
            raise ValueError("Choose a device.") from exc
        return connection.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
    hostname = clean(data.get("hostname"), 63)
    if hostname:
        return connection.execute("SELECT * FROM devices WHERE hostname = ?", (hostname,)).fetchone()
    return None


def validate_activity(connection, data):
    errors = []
    employee = None
    device = None
    try:
        employee = _employee(connection, data)
        if employee is None:
            errors.append("Choose a known employee.")
    except ValueError as exc:
        errors.append(str(exc))
    try:
        device = _device(connection, data)
        if device is None:
            errors.append("Choose a known device.")
    except ValueError as exc:
        errors.append(str(exc))

    activity_type = clean(data.get("activity_type"), 40)
    if activity_type not in ACTIVITY_TYPES:
        errors.append("Choose an activity type.")

    application = clean(data.get("application"), 120)
    resource = clean(data.get("resource"), 200)
    if activity_type == "APPLICATION" and not application:
        errors.append("Enter the application name.")
    if activity_type == "RESOURCE_ACCESS" and not resource:
        errors.append("Enter the resource that was accessed.")

    occurred_at = None
    try:
        occurred_at = parse_occurred(data.get("occurred_at"))
    except ValueError as exc:
        errors.append(str(exc))

    duration = None
    try:
        duration = parse_duration(data.get("duration_minutes"))
    except ValueError as exc:
        errors.append(str(exc))

    details = clean_text(data.get("details"), 2000)
    fields = {
        "employee_id": employee["id"] if employee else None,
        "device_id": device["id"] if device else None,
        "activity_type": activity_type,
        "application": application,
        "resource": resource,
        "occurred_at": occurred_at,
        "duration_minutes": duration,
        "details": details,
    }
    return fields, errors
