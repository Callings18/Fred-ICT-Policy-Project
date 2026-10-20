from flask import Blueprint, render_template, request

from app.auth import permission_required
from app.db import get_db
from app.validate import parse_date
from app import like, paging

bp = Blueprint("auditlog", __name__, url_prefix="/audit")


@bp.route("/", strict_slashes=False)
@permission_required("view_audit")
def index():
    connection = get_db()
    clauses = ["1 = 1"]
    params = []
    q = request.args.get("q", "").strip()
    action = request.args.get("action", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    try:
        if date_from:
            date_from = parse_date(date_from, "start date")
        if date_to:
            date_to = parse_date(date_to, "end date")
    except ValueError:
        date_from = ""
        date_to = ""
    if q:
        term = like(q)
        clauses.append(
            """(
                IFNULL(u.full_name, '') LIKE ? ESCAPE '\\'
                OR IFNULL(u.username, '') LIKE ? ESCAPE '\\'
                OR g.action LIKE ? ESCAPE '\\'
                OR IFNULL(g.entity, '') LIKE ? ESCAPE '\\'
                OR IFNULL(g.details, '') LIKE ? ESCAPE '\\'
            )"""
        )
        params.extend([term, term, term, term, term])
    if action:
        clauses.append("g.action = ?")
        params.append(action)
    if date_from:
        clauses.append("g.created_at >= ?")
        params.append(date_from + "T00:00:00")
    if date_to:
        clauses.append("g.created_at <= ?")
        params.append(date_to + "T23:59:59")
    where = " AND ".join(clauses)
    total = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM audit_logs g
        LEFT JOIN users u ON u.id = g.user_id
        WHERE {where}
        """,
        params,
    ).fetchone()[0]
    pager = paging(total)
    rows = connection.execute(
        f"""
        SELECT g.*, u.full_name, u.username
        FROM audit_logs g
        LEFT JOIN users u ON u.id = g.user_id
        WHERE {where}
        ORDER BY g.created_at DESC, g.id DESC
        LIMIT ? OFFSET ?
        """,
        [*params, pager["per_page"], pager["offset"]],
    ).fetchall()
    actions = connection.execute("SELECT DISTINCT action FROM audit_logs ORDER BY action").fetchall()
    return render_template(
        "audit/index.html",
        rows=rows,
        pager=pager,
        actions=actions,
        filters={"q": q, "action": action, "date_from": date_from, "date_to": date_to},
    )
