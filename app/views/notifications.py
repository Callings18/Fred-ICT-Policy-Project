from flask import Blueprint, abort, redirect, render_template, request, url_for

from app import paging
from app.auth import current_user, login_required
from app.clock import now
from app.db import get_db, write_tx

bp = Blueprint("notifications", __name__, url_prefix="/notifications")


def _safe_href(href):
    if href and href.startswith("/") and not href.startswith("//"):
        return href
    return url_for("notifications.index")


@bp.route("/", methods=["GET", "POST"], strict_slashes=False)
@login_required
def index():
    user = current_user()
    if request.method == "POST":
        with write_tx() as connection:
            connection.execute(
                "UPDATE notifications SET read_at = ? WHERE user_id = ? AND read_at IS NULL",
                (now(), user["id"]),
            )
        return redirect(url_for("notifications.index"))
    connection = get_db()
    total = connection.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id = ?",
        (user["id"],),
    ).fetchone()[0]
    window = paging(total)
    rows = connection.execute(
        """
        SELECT id, title, body, href, created_at, read_at
        FROM notifications
        WHERE user_id = ?
        ORDER BY read_at IS NOT NULL, created_at DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        (user["id"], window["per_page"], window["offset"]),
    ).fetchall()
    unread = connection.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND read_at IS NULL",
        (user["id"],),
    ).fetchone()[0]
    return render_template("notifications/index.html", rows=rows, pager=window, unread=unread)


@bp.route("/<int:notification_id>")
@login_required
def open_item(notification_id):
    user = current_user()
    connection = get_db()
    row = connection.execute(
        "SELECT id, href, user_id FROM notifications WHERE id = ?",
        (notification_id,),
    ).fetchone()
    if row is None or row["user_id"] != user["id"]:
        abort(404)
    with write_tx() as tx:
        tx.execute(
            "UPDATE notifications SET read_at = ? WHERE id = ? AND read_at IS NULL",
            (now(), notification_id),
        )
    return redirect(_safe_href(row["href"]))
