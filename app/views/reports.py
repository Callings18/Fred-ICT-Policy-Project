import csv
import io
import json

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for

from app.auth import current_user, permission_required
from app.constants import ALERT_STATUSES, SEVERITIES
from app.db import get_db, write_tx
from app.reports import allowed_report_types, build_report, can_read_report
from app.services import write_audit
from app.validate import parse_date
from app import paging

bp = Blueprint("reports", __name__, url_prefix="/reports")


@bp.route("/", strict_slashes=False)
@permission_required("view_reports")
def index():
    permissions = current_user()["permissions"]
    type_keys = [key for key, _label in allowed_report_types(permissions)]
    connection = get_db()
    if not type_keys:
        rows = []
        pager = paging(0)
    else:
        marks = ",".join("?" for _ in type_keys)
        total = connection.execute(
            f"SELECT COUNT(*) FROM reports WHERE report_type IN ({marks})",
            type_keys,
        ).fetchone()[0]
        pager = paging(total)
        rows = connection.execute(
            f"""
            SELECT r.*, u.full_name AS author
            FROM reports r
            LEFT JOIN users u ON u.id = r.generated_by
            WHERE r.report_type IN ({marks})
            ORDER BY r.created_at DESC, r.id DESC
            LIMIT ? OFFSET ?
            """,
            [*type_keys, pager["per_page"], pager["offset"]],
        ).fetchall()
    return render_template("reports/index.html", rows=rows, pager=pager)


@bp.route("/new", methods=["GET", "POST"])
@permission_required("generate_reports")
def new():
    user = current_user()
    types = allowed_report_types(user["permissions"])
    connection = get_db()
    employees = connection.execute("SELECT id, full_name FROM employees ORDER BY full_name").fetchall()
    form = {"report_type": types[0][0] if types else "", "date_from": "", "date_to": "", "employee_id": "", "severity": "", "status": ""}
    errors = []
    if request.method == "POST":
        form = {key: request.form.get(key, "") for key in form}
        allowed = {key for key, _label in types}
        if form["report_type"] not in allowed:
            errors.append("Choose a report you are allowed to generate.")
        try:
            form["date_from"] = parse_date(form["date_from"], "start date")
            form["date_to"] = parse_date(form["date_to"], "end date")
        except ValueError as exc:
            errors.append(str(exc))
        if form["date_from"] and form["date_to"] and form["date_from"] > form["date_to"]:
            errors.append("The start date must be on or before the end date.")
        if form["employee_id"] and not str(form["employee_id"]).isdigit():
            errors.append("Choose an employee.")
        if form["severity"] and form["severity"] not in SEVERITIES:
            errors.append("Choose a severity.")
        if form["status"] and form["status"] not in ALERT_STATUSES:
            errors.append("Choose an alert status.")
        if not errors:
            filters = {
                "date_from": form["date_from"],
                "date_to": form["date_to"],
                "employee_id": int(form["employee_id"]) if form["employee_id"] else "",
                "severity": form["severity"] if form["report_type"] == "alerts" else "",
                "status": form["status"] if form["report_type"] == "alerts" else "",
            }
            with write_tx() as tx:
                report_id = build_report(tx, user["id"], form["report_type"], filters)
                write_audit(tx, user["id"], "Generated report", "report", report_id, form["report_type"])
            flash("Report generated.", "success")
            return redirect(url_for("reports.detail", report_id=report_id))
    return render_template(
        "reports/form.html",
        form=form,
        errors=errors,
        types=types,
        employees=employees,
        severities=SEVERITIES,
        statuses=ALERT_STATUSES,
    )


def _load(report_id):
    report = get_db().execute(
        """
        SELECT r.*, u.full_name AS author
        FROM reports r
        LEFT JOIN users u ON u.id = r.generated_by
        WHERE r.id = ?
        """,
        (report_id,),
    ).fetchone()
    if report is None:
        abort(404)
    if not can_read_report(current_user()["permissions"], report["report_type"]):
        abort(403)
    content = json.loads(report["content_json"])
    return report, content


@bp.route("/<int:report_id>")
@permission_required("view_reports")
def detail(report_id):
    report, content = _load(report_id)
    return render_template("reports/detail.html", report=report, content=content)


@bp.route("/<int:report_id>/export")
@permission_required("view_reports")
def export(report_id):
    report, content = _load(report_id)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    if content["kind"] == "compliance":
        writer.writerow(["Summary", "Value"])
        for item in content["summary"]:
            writer.writerow([item["label"], item["value"]])
        for table in content["tables"]:
            writer.writerow([])
            writer.writerow([table["title"]])
            writer.writerow(table["columns"])
            writer.writerows(table["rows"])
    else:
        writer.writerow(content["columns"])
        writer.writerows(content["rows"])
    payload = "\ufeff" + buffer.getvalue()
    filename = f"ipmcs-report-{report_id}.csv"
    return Response(
        payload,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
