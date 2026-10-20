from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app import like, paging
from app.auth import can, current_user, permission_required
from app.db import get_db, write_tx
from app.services import close_finding, write_audit

bp = Blueprint("findings", __name__, url_prefix="/findings")

FINDING_STATUSES = ("OPEN", "CLOSED")


@bp.route("/", strict_slashes=False)
@permission_required("view_findings")
def index():
    connection = get_db()
    clauses = ["1 = 1"]
    params = []
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    if q:
        term = like(q)
        clauses.append("(f.title LIKE ? ESCAPE '\\' OR e.full_name LIKE ? ESCAPE '\\' OR f.summary LIKE ? ESCAPE '\\')")
        params.extend([term, term, term])
    if status in FINDING_STATUSES:
        clauses.append("f.status = ?")
        params.append(status)
    where = " AND ".join(clauses)
    total = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM findings f
        JOIN employees e ON e.id = f.employee_id
        WHERE {where}
        """,
        params,
    ).fetchone()[0]
    window = paging(total)
    rows = connection.execute(
        f"""
        SELECT f.id, f.title, f.status, f.created_at, e.full_name, e.department, al.severity
        FROM findings f
        JOIN employees e ON e.id = f.employee_id
        JOIN alerts al ON al.id = f.alert_id
        WHERE {where}
        ORDER BY CASE f.status WHEN 'OPEN' THEN 0 ELSE 1 END, f.created_at DESC, f.id DESC
        LIMIT ? OFFSET ?
        """,
        (*params, window["per_page"], window["offset"]),
    ).fetchall()
    return render_template(
        "findings/index.html",
        rows=rows,
        pager=window,
        statuses=FINDING_STATUSES,
        filters={"q": q, "status": status},
    )


@bp.route("/<int:finding_id>", methods=["GET", "POST"])
@permission_required("view_findings")
def detail(finding_id):
    errors = []
    if request.method == "POST":
        if not can("manage_findings"):
            abort(403)
        try:
            with write_tx() as connection:
                result = close_finding(connection, finding_id, current_user()["id"], request.form.get("conclusion", ""))
                if result is None:
                    abort(404)
                if result is False:
                    errors = ["This finding is already closed."]
                else:
                    write_audit(
                        connection,
                        current_user()["id"],
                        "Closed finding",
                        "finding",
                        finding_id,
                        "A person recorded a conclusion. This is not an automatic policy breach.",
                    )
            if not errors:
                flash("Finding closed. The conclusion is a human record, not a confirmed breach.")
                return redirect(url_for("findings.detail", finding_id=finding_id))
        except ValueError as exc:
            errors = [str(exc)]
    connection = get_db()
    finding = connection.execute(
        """
        SELECT f.*, e.full_name, e.employee_number, e.department,
               opener.full_name AS opener_name, closer.full_name AS closer_name,
               al.rule_name, al.severity, al.status AS alert_status, al.id AS alert_id
        FROM findings f
        JOIN employees e ON e.id = f.employee_id
        JOIN alerts al ON al.id = f.alert_id
        LEFT JOIN users opener ON opener.id = f.opened_by
        LEFT JOIN users closer ON closer.id = f.closed_by
        WHERE f.id = ?
        """,
        (finding_id,),
    ).fetchone()
    if finding is None:
        abort(404)
    return render_template("findings/detail.html", finding=finding, errors=errors)
