from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.auth import current_user, permission_required
from app.clock import now
from app.constants import ACTIVITY_TYPES, CONDITION_HINTS, CONDITION_TYPES, SEVERITIES
from app.db import get_db, write_tx
from app.services import parse_window, write_audit
from app.validate import clean, clean_text

bp = Blueprint("policies", __name__, url_prefix="/policies")


def _validate(form):
    errors = []
    name = clean(form.get("name"), 120)
    if len(name) < 3:
        errors.append("Enter a rule name of at least 3 characters.")
    activity_type = form.get("activity_type", "")
    if activity_type not in ["ANY", *ACTIVITY_TYPES]:
        errors.append("Choose which activity type this rule applies to.")
    condition_type = form.get("condition_type", "")
    if condition_type not in CONDITION_TYPES:
        errors.append("Choose a condition.")
    severity = form.get("severity", "")
    if severity not in SEVERITIES:
        errors.append("Choose a severity.")
    raw_value = clean(form.get("condition_value"), 300)
    if condition_type == "WEEKEND":
        raw_value = "SAT,SUN"
    elif condition_type == "EMPLOYEE_NOT_ACTIVE":
        raw_value = "NOT_ACTIVE"
    elif condition_type == "OUTSIDE_HOURS" and parse_window(raw_value) is None:
        errors.append("Enter working hours as HH:MM-HH:MM, for example 08:00-17:00.")
    elif condition_type == "DURATION_OVER":
        try:
            number = int(raw_value)
            if number < 1:
                raise ValueError
            raw_value = str(number)
        except ValueError:
            errors.append("Enter the duration limit as a whole number of minutes.")
    elif condition_type in ("APPLICATION_IN", "RESOURCE_CONTAINS") and not raw_value:
        errors.append("Enter at least one match value for this condition.")
    description = clean_text(form.get("description"), 1000)
    fields = {
        "name": name,
        "activity_type": activity_type,
        "condition_type": condition_type,
        "condition_value": raw_value,
        "severity": severity,
        "description": description,
    }
    return fields, errors


@bp.route("/", strict_slashes=False)
@permission_required("view_policies")
def index():
    rows = get_db().execute(
        """
        SELECT * FROM policy_rules
        ORDER BY status,
                 CASE severity WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'MEDIUM' THEN 3 ELSE 4 END,
                 name
        """
    ).fetchall()
    return render_template("policies/index.html", rows=rows)


@bp.route("/new", methods=["GET", "POST"])
@permission_required("manage_policies")
def new():
    form = {
        "name": "",
        "activity_type": "ANY",
        "condition_type": "OUTSIDE_HOURS",
        "condition_value": "08:00-17:00",
        "severity": "MEDIUM",
        "description": "",
    }
    errors = []
    if request.method == "POST":
        form, errors = _validate(request.form)
        if not errors:
            with write_tx() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO policy_rules (
                        name, activity_type, condition_type, condition_value, severity,
                        status, description, created_by, created_at
                    ) VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?)
                    """,
                    (
                        form["name"],
                        form["activity_type"],
                        form["condition_type"],
                        form["condition_value"],
                        form["severity"],
                        form["description"],
                        current_user()["id"],
                        now(),
                    ),
                )
                write_audit(
                    connection,
                    current_user()["id"],
                    "Created policy rule",
                    "policy_rule",
                    cursor.lastrowid,
                    form["name"],
                )
            flash("Policy rule created. It will apply to activities recorded from now on.", "success")
            return redirect(url_for("policies.index"))
    return render_template("policies/form.html", form=form, errors=errors, editing=False, hints=CONDITION_HINTS)


@bp.route("/<int:rule_id>/edit", methods=["GET", "POST"])
@permission_required("manage_policies")
def edit(rule_id):
    connection = get_db()
    rule = connection.execute("SELECT * FROM policy_rules WHERE id = ?", (rule_id,)).fetchone()
    if rule is None:
        abort(404)
    form = dict(rule)
    errors = []
    if request.method == "POST":
        form, errors = _validate(request.form)
        if not errors:
            with write_tx() as tx:
                tx.execute(
                    """
                    UPDATE policy_rules
                    SET name = ?, activity_type = ?, condition_type = ?, condition_value = ?,
                        severity = ?, description = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        form["name"],
                        form["activity_type"],
                        form["condition_type"],
                        form["condition_value"],
                        form["severity"],
                        form["description"],
                        now(),
                        rule_id,
                    ),
                )
                write_audit(tx, current_user()["id"], "Updated policy rule", "policy_rule", rule_id, form["name"])
            flash("Policy rule updated. Existing alerts keep the severity they were raised with.", "success")
            return redirect(url_for("policies.index"))
    return render_template(
        "policies/form.html",
        form=form,
        errors=errors,
        editing=True,
        hints=CONDITION_HINTS,
        rule_id=rule_id,
    )


@bp.post("/<int:rule_id>/toggle")
@permission_required("manage_policies")
def toggle(rule_id):
    with write_tx() as connection:
        rule = connection.execute("SELECT * FROM policy_rules WHERE id = ?", (rule_id,)).fetchone()
        if rule is None:
            abort(404)
        status = "INACTIVE" if rule["status"] == "ACTIVE" else "ACTIVE"
        connection.execute(
            "UPDATE policy_rules SET status = ?, updated_at = ? WHERE id = ?",
            (status, now(), rule_id),
        )
        action = "Deactivated policy rule" if status == "INACTIVE" else "Activated policy rule"
        write_audit(connection, current_user()["id"], action, "policy_rule", rule_id, rule["name"])
    flash("Policy rule is now " + status.lower() + ".", "success")
    return redirect(url_for("policies.index"))
