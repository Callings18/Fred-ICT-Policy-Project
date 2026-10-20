from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.auth import current_user, permission_required
from app.clock import now
from app.constants import DEVICE_STATUSES
from app.db import get_db, write_tx
from app.services import write_audit
from app.validate import HOSTNAME, clean, valid_ip
from app import like, paging

bp = Blueprint("devices", __name__, url_prefix="/devices")


def _validate(connection, form, device_id=None):
    errors = []
    hostname = clean(form.get("hostname"), 63)
    ip_address = clean(form.get("ip_address"), 45)
    operating_system = clean(form.get("operating_system"), 80)
    status = form.get("status", "")
    employee_raw = form.get("employee_id", "")
    if not HOSTNAME.match(hostname or ""):
        errors.append("Enter a hostname using letters, numbers, dots, or hyphens.")
    if not valid_ip(ip_address):
        errors.append("Enter a valid IP address or leave it blank.")
    if not operating_system:
        errors.append("Enter the operating system.")
    if status not in DEVICE_STATUSES:
        errors.append("Choose a device status.")
    employee_id = None
    if employee_raw:
        if not str(employee_raw).isdigit():
            errors.append("Choose an employee.")
        else:
            employee_id = int(employee_raw)
            if connection.execute("SELECT id FROM employees WHERE id = ?", (employee_id,)).fetchone() is None:
                errors.append("Choose an employee.")
    if hostname and not any("hostname" in error for error in errors):
        taken = connection.execute(
            "SELECT id FROM devices WHERE hostname = ? AND id != ?",
            (hostname, device_id or 0),
        ).fetchone()
        if taken:
            errors.append("That hostname is already registered.")
    return {
        "hostname": hostname,
        "ip_address": ip_address,
        "operating_system": operating_system,
        "status": status,
        "employee_id": employee_id,
    }, errors


def _employees(connection):
    return connection.execute("SELECT id, full_name, employee_number FROM employees ORDER BY full_name").fetchall()


@bp.route("/", strict_slashes=False)
@permission_required("view_devices")
def index():
    connection = get_db()
    clauses = ["1 = 1"]
    params = []
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    if q:
        term = like(q)
        clauses.append(
            "(d.hostname LIKE ? ESCAPE '\\' OR IFNULL(d.ip_address, '') LIKE ? ESCAPE '\\' OR IFNULL(e.full_name, '') LIKE ? ESCAPE '\\')"
        )
        params.extend([term, term, term])
    if status in DEVICE_STATUSES:
        clauses.append("d.status = ?")
        params.append(status)
    where = " AND ".join(clauses)
    total = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM devices d
        LEFT JOIN employees e ON e.id = d.employee_id
        WHERE {where}
        """,
        params,
    ).fetchone()[0]
    pager = paging(total)
    rows = connection.execute(
        f"""
        SELECT d.*, e.full_name
        FROM devices d
        LEFT JOIN employees e ON e.id = d.employee_id
        WHERE {where}
        ORDER BY d.hostname
        LIMIT ? OFFSET ?
        """,
        [*params, pager["per_page"], pager["offset"]],
    ).fetchall()
    return render_template(
        "devices/index.html",
        rows=rows,
        pager=pager,
        statuses=DEVICE_STATUSES,
        filters={"q": q, "status": status},
    )


@bp.route("/new", methods=["GET", "POST"])
@permission_required("manage_devices")
def new():
    form = {"hostname": "", "ip_address": "", "operating_system": "Windows 11", "status": "ACTIVE", "employee_id": ""}
    errors = []
    connection = get_db()
    if request.method == "POST":
        with write_tx() as tx:
            form, errors = _validate(tx, request.form)
            if not errors:
                cursor = tx.execute(
                    """
                    INSERT INTO devices (hostname, ip_address, operating_system, employee_id, status, registered_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        form["hostname"],
                        form["ip_address"] or None,
                        form["operating_system"],
                        form["employee_id"],
                        form["status"],
                        now(),
                    ),
                )
                write_audit(tx, current_user()["id"], "Registered device", "device", cursor.lastrowid, form["hostname"])
                device_id = cursor.lastrowid
        if not errors:
            flash("Device registered.", "success")
            return redirect(url_for("devices.detail", device_id=device_id))
    return render_template("devices/form.html", form=form, errors=errors, editing=False, employees=_employees(connection))


@bp.route("/<int:device_id>")
@permission_required("view_devices")
def detail(device_id):
    connection = get_db()
    device = connection.execute(
        """
        SELECT d.*, e.full_name, e.employee_number
        FROM devices d
        LEFT JOIN employees e ON e.id = d.employee_id
        WHERE d.id = ?
        """,
        (device_id,),
    ).fetchone()
    if device is None:
        abort(404)
    activities = connection.execute(
        """
        SELECT a.id, a.activity_type, a.application, a.occurred_at, e.full_name
        FROM activities a
        JOIN employees e ON e.id = a.employee_id
        WHERE a.device_id = ?
        ORDER BY a.occurred_at DESC
        LIMIT 15
        """,
        (device_id,),
    ).fetchall()
    return render_template("devices/detail.html", device=device, activities=activities)


@bp.route("/<int:device_id>/edit", methods=["GET", "POST"])
@permission_required("manage_devices")
def edit(device_id):
    connection = get_db()
    current = connection.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
    if current is None:
        abort(404)
    form = dict(current)
    form["employee_id"] = current["employee_id"] or ""
    errors = []
    if request.method == "POST":
        with write_tx() as tx:
            form, errors = _validate(tx, request.form, device_id)
            if not errors:
                tx.execute(
                    """
                    UPDATE devices
                    SET hostname = ?, ip_address = ?, operating_system = ?, employee_id = ?, status = ?
                    WHERE id = ?
                    """,
                    (
                        form["hostname"],
                        form["ip_address"] or None,
                        form["operating_system"],
                        form["employee_id"],
                        form["status"],
                        device_id,
                    ),
                )
                write_audit(tx, current_user()["id"], "Updated device", "device", device_id, form["hostname"])
        if not errors:
            flash("Device updated.", "success")
            return redirect(url_for("devices.detail", device_id=device_id))
    return render_template(
        "devices/form.html",
        form=form,
        errors=errors,
        editing=True,
        employees=_employees(connection),
        device_id=device_id,
    )
